import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
import db
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
db.init_db()  # Auto-initialize database on startup (for Render Free Tier)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "techmart_secret_key")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_IMAGES = 5
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB max total upload

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Helper functions ---

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("Access denied. Administrators only.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_categories():
    conn = db.get_connection()
    if not conn: return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM categories ORDER BY parent_id IS NOT NULL, name")
    categories = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Organize into hierarchy: parents with their children
    hierarchy = {}
    for cat in categories:
        if cat['parent_id'] is None:
            hierarchy[cat['category_id']] = {'name': cat['name'], 'children': []}
        else:
            if cat['parent_id'] in hierarchy:
                hierarchy[cat['parent_id']]['children'].append(cat)
    return hierarchy

@app.context_processor
def inject_notif_count():
    notif_count = 0
    if 'user_id' in session:
        conn = db.get_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = false", (session['user_id'],))
            notif_count = cursor.fetchone()['count']
            cursor.close()
            conn.close()
    return dict(notif_count=notif_count)

# --- API Routes ---

@app.route('/api/search/suggestions')
def search_suggestions():
    q = request.args.get('q', '').strip()
    cat_id = request.args.get('cat_id', '').strip()
    
    if len(q) < 2:
        return jsonify([])
        
    conn = db.get_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    query = """
        SELECT item_id, title, price, quantity 
        FROM items 
        WHERE (title LIKE %s OR description LIKE %s) AND quantity > 0
    """
    params = [f"%{q}%", f"%{q}%"]
    
    if cat_id:
        query += " AND category_id = %s"
        params.append(cat_id)
        
    query += " LIMIT 5"
    
    cursor.execute(query, tuple(params))
    suggestions = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify(suggestions)

# --- Routes ---

@app.route('/healthz')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'buyer':
            return redirect(url_for('browse'))
        else:
            return redirect(url_for('post_item'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        if session['role'] == 'admin': return redirect(url_for('admin_dashboard'))
        if session['role'] == 'seller': return redirect(url_for('post_item'))
        return redirect(url_for('browse'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        conn = db.get_connection()
        if not conn:
            flash("Database connection failed.", "error")
            return redirect(url_for('register'))
            
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT role_id FROM roles WHERE role_name = %s", (role,))
            role_row = cursor.fetchone()
            if not role_row:
                flash("Invalid role.", "error")
                return redirect(url_for('register'))
            role_id = role_row['role_id']
            
            # Auto-verify: no OTP needed
            cursor.execute("INSERT INTO users (name, email, password, role_id, is_verified) VALUES (%s, %s, %s, %s, TRUE)", 
                           (name, email, password, role_id))
            conn.commit()
            flash("Account created! You can now log in.", "success")
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash(f"Error: {err.msg}", "error")
        finally:
            cursor.close()
            conn.close()
            
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session['role'] == 'admin': return redirect(url_for('admin_dashboard'))
        if session['role'] == 'seller': return redirect(url_for('post_item'))
        return redirect(url_for('browse'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = db.get_connection()
        if not conn:
            flash("Database connection failed.", "error")
            return redirect(url_for('login'))
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT u.*, r.role_name as role FROM users u JOIN roles r ON u.role_id = r.role_id WHERE u.email = %s AND u.password = %s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            session['user_id'] = user['user_id']
            session['name'] = user['name']
            session['role'] = user['role']
            flash(f"Welcome back, {user['name']}!", "success")
            if user['role'] == 'buyer':
                return redirect(url_for('browse'))
            elif user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('post_item'))
        else:
            flash("Invalid email or password.", "error")
            
    return render_template('login.html')



@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

@app.route('/browse', methods=['GET', 'POST'])
def browse():
    if 'user_id' not in session or session['role'] not in ['buyer', 'admin']:
        return redirect(url_for('login'))
        
    category_id = request.values.get('category_id')
    min_price = request.values.get('min_price')
    max_price = request.values.get('max_price')
    item_condition = request.values.get('condition')
    search_query = request.values.get('q')
    
    # 1. Log Search History
    if search_query or category_id or min_price or max_price:
        conn_log = db.get_connection()
        cursor_log = conn_log.cursor()
        cursor_log.execute("""
            INSERT INTO search_history (user_id, query, category_id, min_price, max_price) 
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], search_query, category_id, min_price, max_price))
        conn_log.commit()
        cursor_log.close()
        conn_log.close()

    # 2. Build Query — Left join primary image
    query = """
        SELECT i.*, c.name as category_name, u.name as seller_name,
               img.image_url as primary_image,
               cond.condition_name as item_condition
        FROM items i 
        JOIN categories c ON i.category_id = c.category_id 
        JOIN users u ON i.seller_id = u.user_id 
        JOIN conditions cond ON i.condition_id = cond.condition_id
        LEFT JOIN items_img img ON img.item_id = i.item_id AND img.is_primary = TRUE
        WHERE i.quantity > 0
    """
    params = []
    
    if category_id:
        query += " AND (i.category_id = %s OR c.parent_id = %s)"
        params.extend([category_id, category_id])
    if min_price and min_price.strip():
        query += " AND i.price >= %s"
        params.append(min_price)
    if max_price and max_price.strip():
        query += " AND i.price <= %s"
        params.append(max_price)
    if item_condition and item_condition.strip():
        query += " AND i.condition_id = (SELECT condition_id FROM conditions WHERE condition_name = %s)"
        params.append(item_condition)
    if search_query and search_query.strip():
        query += " AND (i.title LIKE %s OR i.description LIKE %s)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
        
    query += " ORDER BY i.created_at DESC"
    
    conn = db.get_connection()
    if not conn: return "DB Error"
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, tuple(params))
    items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('browse.html', items=items, categories=get_categories())

@app.route('/post', methods=['GET', 'POST'])
def post_item():
    if 'user_id' not in session or session['role'] != 'seller':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        price = request.form.get('price')
        category_id = request.form.get('category_id')
        item_condition = request.form.get('condition')
        quantity = request.form.get('quantity')
        uploaded_files = request.files.getlist('images')
        
        conn = db.get_connection()
        if not conn: return "DB Error"
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO items (title, description, price, category_id, seller_id, condition_id, quantity) 
                VALUES (%s, %s, %s, %s, %s, (SELECT condition_id FROM conditions WHERE condition_name = %s), %s)
            """, (title, description, price, category_id, session['user_id'], item_condition, quantity))
            conn.commit()
            item_id = cursor.lastrowid
            
            # Save uploaded images
            valid_images = [f for f in uploaded_files if f and f.filename and allowed_file(f.filename)]
            for idx, file in enumerate(valid_images[:MAX_IMAGES]):
                ext = file.filename.rsplit('.', 1)[1].lower()
                unique_name = f"{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
                cursor.execute("""
                    INSERT INTO items_img (item_id, image_url, display_order, is_primary)
                    VALUES (%s, %s, %s, %s)
                """, (item_id, unique_name, idx, idx == 0))
            conn.commit()
            flash("Item listed! Smart alerts have been sent to interested buyers.", "success")
        except mysql.connector.Error as err:
            flash(f"Error: {err.msg}", "error")
        finally:
            cursor.close()
            conn.close()
            
    return render_template('post_item.html', categories=get_categories())

@app.route('/interests', methods=['GET', 'POST'])
def interests():
    if 'user_id' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
        
    conn = db.get_connection()
    if not conn: return "DB Error"
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        category_id = request.form.get('category_id') or None
        min_price = request.form.get('min_price') or None
        max_price = request.form.get('max_price') or None
        keyword = request.form.get('keyword') or None
        item_condition = request.form.get('condition') or None
        
        cursor.execute("""
            INSERT INTO interests (user_id, category_id, min_price, max_price, keyword, condition_id) 
            VALUES (%s, %s, %s, %s, %s, (SELECT condition_id FROM conditions WHERE condition_name = %s))
        """, (session['user_id'], category_id, min_price, max_price, keyword, item_condition))
        conn.commit()
        flash("Interest registered! We will notify you when matching items appear.", "success")
        
    cursor.execute("""
        SELECT i.*, c.name as category_name 
        FROM interests i 
        LEFT JOIN categories c ON i.category_id = c.category_id 
        WHERE i.user_id = %s
    """, (session['user_id'],))
    user_interests = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('interests.html', interests=user_interests, categories=get_categories())

@app.route('/interests/delete/<int:interest_id>', methods=['POST'])
def delete_interest(interest_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn: return "DB Error"
    cursor = conn.cursor()
    cursor.execute("DELETE FROM interests WHERE interest_id = %s AND user_id = %s", (interest_id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Interest deleted.", "success")
    return redirect(url_for('interests'))

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = db.get_connection()
    if not conn: return "DB Error"
    cursor = conn.cursor(dictionary=True)
    
    # Using the RESTORED stored procedure
    user_notifications = []
    try:
        cursor.callproc('get_notifications', (session['user_id'],))
        for result in cursor.stored_results():
            user_notifications.extend(result.fetchall())
    except mysql.connector.Error:
        # Fallback to plain SQL if procedure is missing
        cursor.execute("""
            SELECT n.*, i.title, i.price 
            FROM notifications n
            JOIN items i ON n.item_id = i.item_id
            WHERE n.user_id = %s
            ORDER BY n.sent_at DESC
        """, (session['user_id'],))
        user_notifications = cursor.fetchall()
        
    cursor.close()
    conn.close()
    return render_template('notifications.html', notifications=user_notifications)

@app.route('/listings')
def listings():
    if 'user_id' not in session or session['role'] != 'seller':
        return redirect(url_for('login'))
        
    conn = db.get_connection()
    if not conn: return "DB Error"
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT i.*, c.name as category_name, cond.condition_name,
               img.image_url as primary_image,
               COALESCE(SUM(oi.quantity), 0) as order_count
        FROM items i
        JOIN categories c ON i.category_id = c.category_id
        JOIN conditions cond ON i.condition_id = cond.condition_id
        LEFT JOIN items_img img ON img.item_id = i.item_id AND img.is_primary = TRUE
        LEFT JOIN order_items oi ON oi.item_id = i.item_id
        WHERE i.seller_id = %s
        GROUP BY i.item_id, c.name, cond.condition_name, img.image_url
        ORDER BY i.created_at DESC
    """, (session['user_id'],))
    user_items = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('my_listings.html', items=user_items)

# --- Admin Routes ---

@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = db.get_connection()
    if not conn: return "DB Error"
    cursor = conn.cursor(dictionary=True)
    
    # Stats
    cursor.execute("SELECT COUNT(*) as count FROM users u JOIN roles r ON u.role_id=r.role_id WHERE r.role_name='buyer'")
    buyer_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM users u JOIN roles r ON u.role_id=r.role_id WHERE r.role_name='seller'")
    seller_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM items")
    item_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM orders")
    order_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status_id = (SELECT status_id FROM order_status WHERE status_name='pending')")
    pending_count = cursor.fetchone()['count']
    cursor.execute("SELECT COALESCE(SUM(total_price), 0) as revenue FROM orders")
    total_revenue = cursor.fetchone()['revenue']
    
    # Recent users
    cursor.execute("SELECT u.*, r.role_name as role FROM users u JOIN roles r ON u.role_id=r.role_id ORDER BY created_at DESC LIMIT 5")
    recent_users = cursor.fetchall()
    
    # Recent orders
    cursor.execute("""
        SELECT o.order_id, o.total_price, o.order_date, s.status_name as status,
               i.title, b.name as buyer_name
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN items i ON oi.item_id = i.item_id
        JOIN users b ON o.buyer_id = b.user_id
        JOIN order_status s ON o.status_id = s.status_id
        ORDER BY o.order_date DESC LIMIT 5
    """)
    recent_orders = cursor.fetchall()
    
    # Top selling items
    cursor.execute("""
        SELECT i.item_id, i.title, i.price, i.quantity, u.name as seller_name,
               COALESCE(SUM(oi.quantity), 0) as units_sold,
               COALESCE(SUM(oi.quantity * oi.price_at_purchase), 0) as revenue,
               img.image_url as primary_image
        FROM items i
        JOIN users u ON i.seller_id = u.user_id
        LEFT JOIN order_items oi ON oi.item_id = i.item_id
        LEFT JOIN items_img img ON img.item_id = i.item_id AND img.is_primary = TRUE
        GROUP BY i.item_id, i.title, i.price, i.quantity, u.name, img.image_url
        ORDER BY units_sold DESC
        LIMIT 8
    """)
    top_items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin/dashboard.html',
        stats={
            'buyers': buyer_count, 'sellers': seller_count,
            'total_items': item_count, 'total_orders': order_count,
            'pending_orders': pending_count, 'total_revenue': total_revenue
        },
        recent_users=recent_users,
        recent_orders=recent_orders,
        top_items=top_items
    )

@app.route('/admin/users')
@admin_required
def admin_users():
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.*, r.role_name as role 
        FROM users u 
        JOIN roles r ON u.role_id=r.role_id 
        ORDER BY created_at DESC
    """)
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    if user_id == session['user_id']:
        flash("You cannot delete your own admin account.", "error")
        return redirect(url_for('admin_users'))
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("User and all related data (items, interests, notifications) deleted.", "success")
    return redirect(url_for('admin_users'))

@app.route('/admin/items')
@admin_required
def admin_items():
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT i.*, c.name as category_name, u.name as seller_name,
               img.image_url as primary_image
        FROM items i 
        JOIN categories c ON i.category_id = c.category_id 
        JOIN users u ON i.seller_id = u.user_id 
        LEFT JOIN items_img img ON img.item_id = i.item_id AND img.is_primary = TRUE
        ORDER BY i.created_at DESC
    """)
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin/items.html', items=items)

@app.route('/admin/items/delete/<int:item_id>', methods=['POST'])
@admin_required
def admin_delete_item(item_id):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items WHERE item_id = %s", (item_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Marketplace listing deleted.", "success")
    return redirect(url_for('admin_items'))

@app.route('/admin/categories', methods=['GET', 'POST'])
@admin_required
def admin_categories():
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        name = request.form.get('name')
        parent_id = request.form.get('parent_id') or None
        cursor.execute("INSERT INTO categories (name, parent_id) VALUES (%s, %s)", (name, parent_id))
        conn.commit()
        flash(f"Category '{name}' added.", "success")
        return redirect(url_for('admin_categories'))
        
    cursor.execute("SELECT * FROM categories ORDER BY parent_id IS NOT NULL, name")
    all_cats = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Re-use our tree builder
    cat_tree = get_categories()
    return render_template('admin/categories.html', categories=cat_tree, all_cats=all_cats)

@app.route('/admin/categories/delete/<int:cat_id>', methods=['POST'])
@admin_required
def admin_delete_category(cat_id):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM categories WHERE category_id = %s", (cat_id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Category deleted.", "success")
    return redirect(url_for('admin_categories'))

@app.route('/notifications/read/<int:notif_id>', methods=['POST'])
def mark_read(notif_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = true WHERE notification_id = %s AND user_id = %s", (notif_id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('notifications'))

# --- Order & Wishlist Routes ---

@app.route('/buy/<int:item_id>', methods=['POST'])
def buy_item(item_id):
    if 'user_id' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
        
    qty = int(request.form.get('quantity', 1))
    notes = request.form.get('notes', '')
    
    conn = db.get_connection()
    # ACID: Standard transactional isolation in InnoDB
    cursor = conn.cursor(dictionary=True)
    
    try:
        # ISOLATION: Use SELECT ... FOR UPDATE to lock the row for the duration of this transaction
        cursor.execute("SELECT * FROM items WHERE item_id = %s FOR UPDATE", (item_id,))
        item = cursor.fetchone()
        
        if not item or item['quantity'] < qty:
            conn.rollback()
            flash("Sorry, this item is out of stock or quantity exceeds availability.", "error")
            return redirect(url_for('browse'))
        
        # ATOMICITY: All or nothing
        total_price = item['price'] * qty
        # Create Order
        cursor.execute("""
            INSERT INTO orders (buyer_id, total_price, status_id, notes) 
            VALUES (%s, %s, (SELECT status_id FROM order_status WHERE status_name = 'pending'), %s)
        """, (session['user_id'], total_price, notes))
        
        order_id = cursor.lastrowid
        
        # Create Order Item (Cart)
        cursor.execute("""
            INSERT INTO order_items (order_id, item_id, seller_id, quantity, price_at_purchase)
            VALUES (%s, %s, %s, %s, %s)
        """, (order_id, item_id, item['seller_id'], qty, item['price']))
        
        # Decrement Item stock
        cursor.execute("UPDATE items SET quantity = quantity - %s WHERE item_id = %s", (qty, item_id))
        
        conn.commit()
        flash(f"Purchase successful! Order confirmed.", "success")
    except Exception as e:
        conn.rollback() # DURABILITY will handle the server-crash case via redo logs
        flash(f"Transaction failed: {str(e)}", "error")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('orders'))

@app.route('/orders')
def orders():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    
    if session['role'] == 'buyer':
        cursor.execute("""
            SELECT o.*, oi.quantity, oi.price_at_purchase, i.title, 
                   u.name as seller_name, s.status_name as status,
                   img.image_url as primary_image
            FROM orders o 
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN items i ON oi.item_id = i.item_id 
            JOIN users u ON oi.seller_id = u.user_id 
            JOIN order_status s ON o.status_id = s.status_id
            LEFT JOIN items_img img ON img.item_id = oi.item_id AND img.is_primary = TRUE
            WHERE o.buyer_id = %s 
            ORDER BY o.order_date DESC
        """, (session['user_id'],))
    else:
        cursor.execute("""
            SELECT o.*, oi.quantity, oi.price_at_purchase, i.title,
                   u.name as buyer_name, s.status_name as status,
                   img.image_url as primary_image
            FROM orders o 
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN items i ON oi.item_id = i.item_id 
            JOIN users u ON o.buyer_id = u.user_id 
            JOIN order_status s ON o.status_id = s.status_id
            LEFT JOIN items_img img ON img.item_id = oi.item_id AND img.is_primary = TRUE
            WHERE oi.seller_id = %s 
            ORDER BY o.order_date DESC
        """, (session['user_id'],))
        
    user_orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('orders.html', orders=user_orders)

@app.route('/wishlist', methods=['GET', 'POST'])
def wishlist():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        item_id = request.form.get('item_id')
        try:
            cursor.execute("INSERT INTO wishlist (user_id, item_id) VALUES (%s, %s)", (session['user_id'], item_id))
            conn.commit()
            flash("Item added to your wishlist!", "success")
        except:
            flash("Already in your wishlist.", "info")
            
    cursor.execute("""
        SELECT w.*, i.title, i.price, cond.condition_name as item_condition, c.name as category_name 
        FROM wishlist w 
        JOIN items i ON w.item_id = i.item_id 
        JOIN categories c ON i.category_id = c.category_id 
        JOIN conditions cond ON i.condition_id = cond.condition_id
        WHERE w.user_id = %s
    """, (session['user_id'],))
    items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return render_template('wishlist.html', items=items)

@app.route('/wishlist/remove/<int:wish_id>', methods=['POST'])
def remove_wish(wish_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM wishlist WHERE wishlist_id = %s AND user_id = %s", (wish_id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    flash("Item removed from wishlist.", "success")
    return redirect(url_for('wishlist'))

# --- Server Start ---

@app.route('/orders/<int:order_id>/status', methods=['POST'])
def update_order_status(order_id):
    if 'user_id' not in session or session['role'] != 'seller':
        return redirect(url_for('login'))
    new_status = request.form.get('status')
    allowed = ['confirmed', 'completed', 'cancelled']
    if new_status not in allowed:
        flash("Invalid status.", "error")
        return redirect(url_for('orders'))
    conn = db.get_connection()
    cursor = conn.cursor()
    # Only allow status update if this seller owns an item in the order
    cursor.execute("""
        UPDATE orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        SET o.status_id = (SELECT status_id FROM order_status WHERE status_name = %s)
        WHERE o.order_id = %s AND oi.seller_id = %s
    """, (new_status, order_id, session['user_id']))
    conn.commit()
    cursor.close()
    conn.close()
    flash(f"Order #{order_id} marked as {new_status}.", "success")
    return redirect(url_for('orders'))

@app.route('/admin/orders')
@admin_required
def admin_orders():
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT o.order_id, o.total_price, o.order_date, s.status_name as status,
               oi.quantity, i.title,
               b.name as buyer_name, sel.name as seller_name,
               img.image_url as primary_image
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN items i ON oi.item_id = i.item_id
        JOIN users b ON o.buyer_id = b.user_id
        JOIN users sel ON oi.seller_id = sel.user_id
        JOIN order_status s ON o.status_id = s.status_id
        LEFT JOIN items_img img ON img.item_id = oi.item_id AND img.is_primary = TRUE
        ORDER BY o.order_date DESC
    """)
    all_orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin/orders.html', orders=all_orders)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, host='0.0.0.0', port=port)
