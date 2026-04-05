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
db.init_db()  # setup tables on first run

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "techmart_secret_key")

# file upload config
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_IMGS = 5
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25mb limit

def allowed_file(fname):
    # check if file extension is valid
    return '.' in fname and fname.rsplit('.', 1)[1].lower() in ALLOWED_EXT


# -- helper stuff --

def admin_only(f):
    """only admins can access these routes"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("Access denied.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def get_categories():
    """get all categories organized by parent-child"""
    conn = db.get_connection()
    if not conn:
        return []
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM categories ORDER BY parent_id IS NOT NULL, name")
    cats = cur.fetchall()
    cur.close()
    conn.close()
    
    # build a simple tree structure
    tree = {}
    for c in cats:
        if c['parent_id'] is None:
            tree[c['category_id']] = {'name': c['name'], 'children': []}
        else:
            if c['parent_id'] in tree:
                tree[c['parent_id']]['children'].append(c)
    return tree

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.context_processor
def inject_notif_count():
    """show unread notification count in navbar"""
    count = 0
    if 'user_id' in session:
        conn = db.get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM notifications WHERE user_id = %s AND is_read = FALSE", (session['user_id'],))
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
    return dict(notif_count=count)


# -- api routes --

@app.route('/api/search/suggestions')
def search_suggestions():
    """live search dropdown - returns json"""
    q = request.args.get('q', '').strip()
    cat = request.args.get('cat_id', '').strip()
    
    if len(q) < 2:
        return jsonify([])
    
    conn = db.get_connection()
    if not conn:
        return jsonify([])
    cur = conn.cursor(dictionary=True)
    
    # search items by title or description, also grab primary image
    sql = """
        SELECT i.item_id, i.title, i.price, i.quantity, img.image_url as primary_image
        FROM items i 
        LEFT JOIN items_img img ON img.item_id = i.item_id AND img.is_primary = TRUE
        WHERE (i.title LIKE %s OR i.description LIKE %s) AND i.quantity > 0
    """
    params = [f"%{q}%", f"%{q}%"]
    
    if cat:
        sql += " AND category_id = %s"
        params.append(cat)
    
    sql += " LIMIT 5"
    
    cur.execute(sql, tuple(params))
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify(results)


# -- main routes --

@app.route('/healthz')
def health():
    return jsonify({"status": "ok"}), 200

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
    # redirect if already logged in
    if 'user_id' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        if session['role'] == 'seller':
            return redirect(url_for('post_item'))
        return redirect(url_for('browse'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        pw = request.form.get('password')
        role = request.form.get('role')
        
        conn = db.get_connection()
        if not conn:
            flash("Couldn't connect to database.", "error")
            return redirect(url_for('register'))
        
        cur = conn.cursor(dictionary=True)
        try:
            # get role id from roles table
            cur.execute("SELECT role_id FROM roles WHERE role_name = %s", (role,))
            role_row = cur.fetchone()
            if not role_row:
                flash("Invalid role selected.", "error")
                return redirect(url_for('register'))
            
            rid = role_row['role_id']
            
            # insert new user - auto verified, no otp needed
            cur.execute(
                "INSERT INTO users (name, email, password, role_id, is_verified) VALUES (%s, %s, %s, %s, TRUE)", 
                (name, email, pw, rid)
            )
            conn.commit()
            flash("Account created! You can now log in.", "success")
            return redirect(url_for('login'))
        except mysql.connector.Error as e:
            flash(f"Error: {e.msg}", "error")
        finally:
            cur.close()
            conn.close()
            
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        if session['role'] == 'seller':
            return redirect(url_for('post_item'))
        return redirect(url_for('browse'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        pw = request.form.get('password')
        
        conn = db.get_connection()
        if not conn:
            flash("Database error.", "error")
            return redirect(url_for('login'))
        
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT u.*, r.role_name as role FROM users u JOIN roles r ON u.role_id = r.role_id WHERE u.email = %s AND u.password = %s",
            (email, pw)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user:
            # save user info in session
            session['user_id'] = user['user_id']
            session['name'] = user['name']
            session['role'] = user['role']
            flash(f"Welcome back, {user['name']}!", "success")
            
            # redirect based on role
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'seller':
                return redirect(url_for('post_item'))
            else:
                return redirect(url_for('browse'))
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
    flash("Logged out.", "success")
    return redirect(url_for('login'))

@app.route('/browse', methods=['GET', 'POST'])
def browse():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # grab filter params
    cat_id = request.values.get('category_id')
    min_p = request.values.get('min_price')
    max_p = request.values.get('max_price')
    cond = request.values.get('condition')
    q = request.values.get('q')
    
    # log search if user searched for something
    if q or cat_id or min_p or max_p:
        conn2 = db.get_connection()
        c2 = conn2.cursor()
        c2.execute("""
            INSERT INTO search_history (user_id, query, category_id, min_price, max_price) 
            VALUES (%s, %s, %s, %s, %s)
        """, (session['user_id'], q, cat_id, min_p, max_p))
        conn2.commit()
        c2.close()
        conn2.close()

    # build the main query with filters
    sql = """
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
    
    if cat_id:
        sql += " AND (i.category_id = %s OR c.parent_id = %s)"
        params.extend([cat_id, cat_id])
    if min_p and min_p.strip():
        sql += " AND i.price >= %s"
        params.append(min_p)
    if max_p and max_p.strip():
        sql += " AND i.price <= %s"
        params.append(max_p)
    if cond and cond.strip():
        sql += " AND i.condition_id = (SELECT condition_id FROM conditions WHERE condition_name = %s)"
        params.append(cond)
    if q and q.strip():
        sql += " AND (i.title LIKE %s OR i.description LIKE %s)"
        params.append(f"%{q}%")
        params.append(f"%{q}%")
        
    sql += " ORDER BY i.created_at DESC"
    
    conn = db.get_connection()
    if not conn:
        return "db error"
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, tuple(params))
    items = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('browse.html', items=items, categories=get_categories())

@app.route('/post', methods=['GET', 'POST'])
def post_item():
    if 'user_id' not in session or session['role'] != 'seller':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        desc = request.form.get('description')
        price = request.form.get('price')
        cat_id = request.form.get('category_id')
        cond = request.form.get('condition')
        qty = request.form.get('quantity')
        files = request.files.getlist('images')
        
        conn = db.get_connection()
        if not conn:
            return "db error"
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO items (title, description, price, category_id, seller_id, condition_id, quantity) 
                VALUES (%s, %s, %s, %s, %s, (SELECT condition_id FROM conditions WHERE condition_name = %s), %s)
            """, (title, desc, price, cat_id, session['user_id'], cond, qty))
            conn.commit()
            new_id = cur.lastrowid
            
            # save images if any were uploaded
            good_files = [f for f in files if f and f.filename and allowed_file(f.filename)]
            for i, file in enumerate(good_files[:MAX_IMGS]):
                ext = file.filename.rsplit('.', 1)[1].lower()
                fname = f"{uuid.uuid4().hex}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                cur.execute("""
                    INSERT INTO items_img (item_id, image_url, display_order, is_primary)
                    VALUES (%s, %s, %s, %s)
                """, (new_id, fname, i, i == 0))  # first image is primary
            conn.commit()
            flash("Item listed successfully!", "success")
        except mysql.connector.Error as e:
            flash(f"Error: {e.msg}", "error")
        finally:
            cur.close()
            conn.close()
            
    return render_template('post_item.html', categories=get_categories())

@app.route('/interests', methods=['GET', 'POST'])
def interests():
    if 'user_id' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        return "db error"
    cur = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        cat_id = request.form.get('category_id') or None
        min_p = request.form.get('min_price') or None
        max_p = request.form.get('max_price') or None
        kw = request.form.get('keyword') or None
        cond = request.form.get('condition') or None
        
        cur.execute("""
            INSERT INTO interests (user_id, category_id, min_price, max_price, keyword, condition_id) 
            VALUES (%s, %s, %s, %s, %s, (SELECT condition_id FROM conditions WHERE condition_name = %s))
        """, (session['user_id'], cat_id, min_p, max_p, kw, cond))
        conn.commit()
        flash("Interest saved! We'll notify you when something matches.", "success")
    
    # get all interests for this user
    cur.execute("""
        SELECT i.*, c.name as category_name 
        FROM interests i 
        LEFT JOIN categories c ON i.category_id = c.category_id 
        WHERE i.user_id = %s
    """, (session['user_id'],))
    user_interests = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('interests.html', interests=user_interests, categories=get_categories())

@app.route('/interests/delete/<int:interest_id>', methods=['POST'])
def delete_interest(interest_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        return "db error"
    cur = conn.cursor()
    cur.execute("DELETE FROM interests WHERE interest_id = %s AND user_id = %s", (interest_id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()
    flash("Interest removed.", "success")
    return redirect(url_for('interests'))

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        return "db error"
    cur = conn.cursor(dictionary=True)
    
    # try using stored procedure first
    notifs = []
    try:
        cur.callproc('get_notifications', (session['user_id'],))
        for result in cur.stored_results():
            notifs.extend(result.fetchall())
    except mysql.connector.Error:
        # fallback if procedure doesnt exist
        cur.execute("""
            SELECT n.*, i.title, i.price 
            FROM notifications n
            JOIN items i ON n.item_id = i.item_id
            WHERE n.user_id = %s
            ORDER BY n.sent_at DESC
        """, (session['user_id'],))
        notifs = cur.fetchall()
    
    cur.close()
    conn.close()
    return render_template('notifications.html', notifications=notifs)

@app.route('/listings')
def listings():
    """seller's own items page"""
    if 'user_id' not in session or session['role'] != 'seller':
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        return "db error"
    cur = conn.cursor(dictionary=True)
    
    # get all items with their order count
    cur.execute("""
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
    my_items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('my_listings.html', items=my_items)


# -- admin routes --

@app.route('/admin')
@admin_only
def admin_dashboard():
    conn = db.get_connection()
    if not conn:
        return "db error"
    cur = conn.cursor(dictionary=True)
    
    # get basic stats for dashboard
    cur.execute("SELECT COUNT(*) as count FROM users u JOIN roles r ON u.role_id=r.role_id WHERE r.role_name='buyer'")
    buyers = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) as count FROM users u JOIN roles r ON u.role_id=r.role_id WHERE r.role_name='seller'")
    sellers = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) as count FROM items")
    total_items = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) as count FROM orders")
    total_orders = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) as count FROM orders WHERE status_id = (SELECT status_id FROM order_status WHERE status_name='pending')")
    pending = cur.fetchone()['count']
    cur.execute("SELECT COALESCE(SUM(total_price), 0) as rev FROM orders")
    revenue = cur.fetchone()['rev']
    
    # recent users
    cur.execute("SELECT u.*, r.role_name as role FROM users u JOIN roles r ON u.role_id=r.role_id ORDER BY created_at DESC LIMIT 5")
    recent_users = cur.fetchall()
    
    # recent orders - need to join a bunch of tables
    cur.execute("""
        SELECT o.order_id, o.total_price, o.order_date, s.status_name as status,
               i.title, b.name as buyer_name
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        JOIN items i ON oi.item_id = i.item_id
        JOIN users b ON o.buyer_id = b.user_id
        JOIN order_status s ON o.status_id = s.status_id
        ORDER BY o.order_date DESC LIMIT 5
    """)
    recent_orders = cur.fetchall()
    
    # top selling items by units sold
    cur.execute("""
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
    top_items = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('admin/dashboard.html',
        stats={
            'buyers': buyers, 'sellers': sellers,
            'total_items': total_items, 'total_orders': total_orders,
            'pending_orders': pending, 'total_revenue': revenue
        },
        recent_users=recent_users,
        recent_orders=recent_orders,
        top_items=top_items
    )

@app.route('/admin/users')
@admin_only
def admin_users():
    conn = db.get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT u.*, r.role_name as role 
        FROM users u 
        JOIN roles r ON u.role_id=r.role_id 
        ORDER BY created_at DESC
    """)
    users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_only
def admin_delete_user(user_id):
    # cant delete yourself lol
    if user_id == session['user_id']:
        flash("Can't delete your own account.", "error")
        return redirect(url_for('admin_users'))
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("User deleted.", "success")
    return redirect(url_for('admin_users'))

@app.route('/admin/items')
@admin_only
def admin_items():
    conn = db.get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT i.*, c.name as category_name, u.name as seller_name,
               img.image_url as primary_image
        FROM items i 
        JOIN categories c ON i.category_id = c.category_id 
        JOIN users u ON i.seller_id = u.user_id 
        LEFT JOIN items_img img ON img.item_id = i.item_id AND img.is_primary = TRUE
        ORDER BY i.created_at DESC
    """)
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/items.html', items=items)

@app.route('/admin/items/delete/<int:item_id>', methods=['POST'])
@admin_only
def admin_delete_item(item_id):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE item_id = %s", (item_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Item deleted.", "success")
    return redirect(url_for('admin_items'))

@app.route('/admin/categories', methods=['GET', 'POST'])
@admin_only
def admin_categories():
    conn = db.get_connection()
    cur = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        name = request.form.get('name')
        parent = request.form.get('parent_id') or None
        cur.execute("INSERT INTO categories (name, parent_id) VALUES (%s, %s)", (name, parent))
        conn.commit()
        flash(f"Category '{name}' added.", "success")
        return redirect(url_for('admin_categories'))
    
    cur.execute("SELECT * FROM categories ORDER BY parent_id IS NOT NULL, name")
    all_cats = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('admin/categories.html', categories=get_categories(), all_cats=all_cats)

@app.route('/admin/categories/delete/<int:cat_id>', methods=['POST'])
@admin_only
def admin_delete_category(cat_id):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM categories WHERE category_id = %s", (cat_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Category deleted.", "success")
    return redirect(url_for('admin_categories'))

@app.route('/notifications/read/<int:notif_id>', methods=['POST'])
def mark_read(notif_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE notifications SET is_read = true WHERE notification_id = %s AND user_id = %s", (notif_id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('notifications'))


# -- order and wishlist stuff --

@app.route('/item/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_item(item_id):
    if 'user_id' not in session or session['role'] != 'seller':
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        return "db error"
    cur = conn.cursor(dictionary=True)
    
    # make sure item belongs to this seller
    cur.execute("""
        SELECT i.*, cond.condition_name, COALESCE(SUM(oi.quantity), 0) as order_count
        FROM items i 
        JOIN conditions cond ON i.condition_id = cond.condition_id
        LEFT JOIN order_items oi ON oi.item_id = i.item_id
        WHERE i.item_id = %s AND i.seller_id = %s
        GROUP BY i.item_id, cond.condition_name
    """, (item_id, session['user_id']))
    item = cur.fetchone()
    
    if not item:
        cur.close()
        conn.close()
        flash("Item not found.", "error")
        return redirect(url_for('listings'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        desc = request.form.get('description')
        price = request.form.get('price')
        qty = request.form.get('quantity')
        cat_id = request.form.get('category_id')
        cond = request.form.get('condition')
        
        cur.execute("""
            UPDATE items 
            SET title = %s, description = %s, price = %s, quantity = %s, category_id = %s, 
                condition_id = (SELECT condition_id FROM conditions WHERE condition_name = %s)
            WHERE item_id = %s
        """, (title, desc, price, qty, cat_id, cond, item_id))
        conn.commit()
        cur.close()
        conn.close()
        flash("Listing updated.", "success")
        return redirect(url_for('listings'))
    
    cur.close()
    conn.close()
    return render_template('edit_item.html', item=item, categories=get_categories())

@app.route('/buy/<int:item_id>', methods=['POST'])
def buy_item(item_id):
    if 'user_id' not in session or session['role'] != 'buyer':
        return redirect(url_for('login'))
    
    qty = int(request.form.get('quantity', 1))
    notes = request.form.get('notes', '')
    
    conn = db.get_connection()
    cur = conn.cursor(dictionary=True)
    
    try:
        # lock the row so nobody else can buy at the same time
        cur.execute("SELECT * FROM items WHERE item_id = %s FOR UPDATE", (item_id,))
        item = cur.fetchone()
        
        if not item or item['quantity'] < qty:
            conn.rollback()
            flash("Sorry, not enough stock.", "error")
            return redirect(url_for('browse'))
        
        total = item['price'] * qty
        
        # create order
        cur.execute("""
            INSERT INTO orders (buyer_id, total_price, status_id, notes) 
            VALUES (%s, %s, (SELECT status_id FROM order_status WHERE status_name = 'pending'), %s)
        """, (session['user_id'], total, notes))
        
        oid = cur.lastrowid
        
        # add item to order
        cur.execute("""
            INSERT INTO order_items (order_id, item_id, seller_id, quantity, price_at_purchase)
            VALUES (%s, %s, %s, %s, %s)
        """, (oid, item_id, item['seller_id'], qty, item['price']))
        
        # reduce stock
        cur.execute("UPDATE items SET quantity = quantity - %s WHERE item_id = %s", (qty, item_id))
        
        conn.commit()
        flash("Purchase successful!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Something went wrong: {str(e)}", "error")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('orders'))

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    cur = conn.cursor(dictionary=True)
    
    # different query depending on buyer vs seller
    if session['role'] == 'buyer':
        cur.execute("""
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
        # seller sees orders for their items
        cur.execute("""
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
    
    user_orders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('orders.html', orders=user_orders)

@app.route('/wishlist', methods=['GET', 'POST'])
def wishlist():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    cur = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        item_id = request.form.get('item_id')
        try:
            cur.execute("INSERT INTO wishlist (user_id, item_id) VALUES (%s, %s)", (session['user_id'], item_id))
            conn.commit()
            flash("Added to wishlist!", "success")
        except:
            flash("Already in wishlist.", "info")
    
    # get all wishlist items with stock info
    cur.execute("""
        SELECT w.*, i.title, i.price, i.quantity, cond.condition_name as item_condition, c.name as category_name 
        FROM wishlist w 
        JOIN items i ON w.item_id = i.item_id 
        JOIN categories c ON i.category_id = c.category_id 
        JOIN conditions cond ON i.condition_id = cond.condition_id
        WHERE w.user_id = %s
    """, (session['user_id'],))
    items = cur.fetchall()
    
    cur.close()
    conn.close()
    return render_template('wishlist.html', items=items)

@app.route('/wishlist/remove/<int:wish_id>', methods=['POST'])
def remove_wish(wish_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM wishlist WHERE wishlist_id = %s AND user_id = %s", (wish_id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()
    flash("Removed from wishlist.", "success")
    return redirect(url_for('wishlist'))

@app.route('/orders/<int:order_id>/status', methods=['POST'])
def update_order_status(order_id):
    """seller can update order status (confirm/complete/cancel)"""
    if 'user_id' not in session or session['role'] != 'seller':
        return redirect(url_for('login'))
    
    new_status = request.form.get('status')
    ok_statuses = ['confirmed', 'completed', 'cancelled']
    if new_status not in ok_statuses:
        flash("Invalid status.", "error")
        return redirect(url_for('orders'))
    
    conn = db.get_connection()
    cur = conn.cursor()
    # only update if seller owns an item in this order
    cur.execute("""
        UPDATE orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        SET o.status_id = (SELECT status_id FROM order_status WHERE status_name = %s)
        WHERE o.order_id = %s AND oi.seller_id = %s
    """, (new_status, order_id, session['user_id']))
    conn.commit()
    cur.close()
    conn.close()
    flash(f"Order #{order_id} marked as {new_status}.", "success")
    return redirect(url_for('orders'))

@app.route('/admin/orders')
@admin_only
def admin_orders():
    conn = db.get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
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
    all_orders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('admin/orders.html', orders=all_orders)


# -- start the app --

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"starting server on port {port}...")
    app.run(debug=True, host='0.0.0.0', port=port)
