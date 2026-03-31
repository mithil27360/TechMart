import os
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail, Message
from werkzeug.middleware.proxy_fix import ProxyFix
import db
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
db.init_db()  # Auto-initialize database on startup (for Render Free Tier)

app = Flask(__name__)
# Render/Heroku use proxies, this ensures https is detected correctly
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "techmart_secret_key")

# --- OAuth & Mail Config ---
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

app.config.update(
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "True") == "True",
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER")
)
mail = Mail(app)

# --- Helper functions ---

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("Access denied. Administrators only.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def verified_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' in session and not session.get('is_verified', False):
            flash("Please verify your email to continue.", "info")
            return redirect(url_for('verify_otp'))
        return f(*args, **kwargs)
    return decorated_function

def send_otp_email(email, user_id):
    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=10)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET otp_token = %s, otp_expiry = %s WHERE user_id = %s", (otp, expiry, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    msg = Message("Your TechMart Verification Code", recipients=[email])
    msg.body = f"Your verification code is: {otp}. It expires in 10 minutes."
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Mail error: {e}")
        return False

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
            
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)", 
                           (name, email, password, role))
            conn.commit()
            flash("Registration successful! Please login.", "success")
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
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            if not user['is_verified']:
                session['user_id'] = user['user_id']
                session['email'] = user['email']
                send_otp_email(user['email'], user['user_id'])
                return redirect(url_for('verify_otp'))
                
            session['user_id'] = user['user_id']
            session['name'] = user['name']
            session['role'] = user['role']
            session['is_verified'] = True
            flash(f"Welcome back, {user['name']}!", "success")
            if user['role'] == 'buyer':
                return redirect(url_for('browse'))
            else:
                return redirect(url_for('post_item'))
        else:
            flash("Invalid email or password.", "error")
            
    return render_template('login.html')

# --- Social Auth Routes ---

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/callback')
def auth_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    if not user_info:
        flash("Google authentication failed.", "error")
        return redirect(url_for('login'))
    
    email = user_info['email']
    google_id = user_info['sub']
    name = user_info.get('name', email.split('@')[0])
    
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE google_id = %s OR email = %s", (google_id, email))
    user = cursor.fetchone()
    
    if user:
        # Link Google ID if not present
        if not user['google_id']:
            cursor.execute("UPDATE users SET google_id = %s WHERE user_id = %s", (google_id, user['user_id']))
            conn.commit()
    else:
        # Create new user (default to buyer)
        cursor.execute("INSERT INTO users (name, email, google_id, role, password, is_verified) VALUES (%s, %s, %s, 'buyer', 'oauth_user', True)", 
                       (name, email, google_id))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
        user = cursor.fetchone()

    cursor.close()
    conn.close()
    
    session['user_id'] = user['user_id']
    session['name'] = user['name']
    session['role'] = user['role']
    session['is_verified'] = True # Google matches are verified by default
    
    flash(f"Logged in with Google as {user['name']}!", "success")
    return redirect(url_for('browse') if user['role'] == 'buyer' else url_for('post_item'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'user_id' not in session: return redirect(url_for('login'))
    if session.get('is_verified'): return redirect(url_for('index'))
    
    if request.method == 'POST':
        otp = request.form.get('otp')
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        if user and user['otp_token'] == otp and user['otp_expiry'] > datetime.now():
            cursor.execute("UPDATE users SET is_verified = True, otp_token = NULL WHERE user_id = %s", (session['user_id'],))
            conn.commit()
            session['is_verified'] = True
            session['name'] = user['name']
            session['role'] = user['role']
            flash("Email verified successfully!", "success")
            return redirect(url_for('browse') if user['role'] == 'buyer' else url_for('post_item'))
        else:
            flash("Invalid or expired OTP.", "error")
            
        cursor.close()
        conn.close()
        
    return render_template('verify_otp.html')

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

    # 2. Build Query
    # Professional Fix: Ensure we match against the hierarchy correctly and items are visible
    query = """
        SELECT i.*, c.name as category_name, u.name as seller_name 
        FROM items i 
        JOIN categories c ON i.category_id = c.category_id 
        JOIN users u ON i.seller_id = u.user_id 
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
        query += " AND i.item_condition = %s"
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
        
        conn = db.get_connection()
        if not conn: return "DB Error"
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO items (title, description, price, category_id, seller_id, item_condition, quantity) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (title, description, price, category_id, session['user_id'], item_condition, quantity))
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
            INSERT INTO interests (user_id, category_id, min_price, max_price, keyword, item_condition) 
            VALUES (%s, %s, %s, %s, %s, %s)
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
        SELECT i.*, c.name as category_name 
        FROM items i 
        JOIN categories c ON i.category_id = c.category_id 
        WHERE i.seller_id = %s 
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
    
    # Get Stats
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role='buyer'")
    buyer_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE role='seller'")
    seller_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM items")
    item_count = cursor.fetchone()['count']
    cursor.execute("SELECT COUNT(*) as count FROM categories")
    cat_count = cursor.fetchone()['count']
    
    # Recent users
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 5")
    recent_users = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin/dashboard.html', 
                          stats={'buyers': buyer_count, 'sellers': seller_count, 'total_items': item_count, 'cats': cat_count},
                          recent_users=recent_users)

@app.route('/admin/users')
@admin_required
def admin_users():
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
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
        SELECT i.*, c.name as category_name, u.name as seller_name 
        FROM items i 
        JOIN categories c ON i.category_id = c.category_id 
        JOIN users u ON i.seller_id = u.user_id 
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
            INSERT INTO orders (item_id, buyer_id, seller_id, quantity, total_price, notes) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (item_id, session['user_id'], item['seller_id'], qty, total_price, notes))
        
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
            SELECT o.*, i.title, u.name as seller_name 
            FROM orders o 
            JOIN items i ON o.item_id = i.item_id 
            JOIN users u ON o.seller_id = u.user_id 
            WHERE o.buyer_id = %s 
            ORDER BY o.order_date DESC
        """, (session['user_id'],))
    else:
        cursor.execute("""
            SELECT o.*, i.title, u.name as buyer_name 
            FROM orders o 
            JOIN items i ON o.item_id = i.item_id 
            JOIN users u ON o.buyer_id = u.user_id 
            WHERE o.seller_id = %s 
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
        SELECT w.*, i.title, i.price, i.item_condition, c.name as category_name 
        FROM wishlist w 
        JOIN items i ON w.item_id = i.item_id 
        JOIN categories c ON i.category_id = c.category_id 
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, host='0.0.0.0', port=port)
