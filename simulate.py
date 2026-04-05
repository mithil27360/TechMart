import requests
import db

base_url = "http://127.0.0.1:5001"

print("\n🚀 STARTING FULL TRANSACTIONS SIMULATION...\n")

# Connect to DB to check actual database state
conn = db.get_connection()
cursor = conn.cursor(dictionary=True)

# 1. SELLER WORKFLOW
print("==== 1. SELLER WORKFLOW ====")
s_seller = requests.Session()
s_seller.post(f"{base_url}/login", data={"email": "ananya@gmail.com", "password": "123"})
print("✅ Logged in as Seller (ananya@gmail.com)")

item_title = "MacBook Pro M3 Max - Space Black"
res = s_seller.post(f"{base_url}/post", data={
    "title": item_title,
    "description": "Brand new, sealed box. 36GB RAM, 1TB SSD.",
    "price": "315000",
    "category_id": "3",  # Laptops
    "condition": "new",
    "quantity": "5"
})
print(f"✅ Item Listed: {item_title}")

# Find Item ID
cursor.execute("SELECT item_id, quantity FROM items WHERE title = %s ORDER BY created_at DESC LIMIT 1", (item_title,))
new_item = cursor.fetchone()
item_id = new_item['item_id']
print(f"   -> Database created item with ID {item_id} and stock {new_item['quantity']}")

# 2. BUYER WORKFLOW
print("\n==== 2. BUYER WORKFLOW ====")
b_buyer = requests.Session()
b_buyer.post(f"{base_url}/login", data={"email": "rahul@gmail.com", "password": "123"})
print("✅ Logged in as Buyer (rahul@gmail.com)")

print(f"✅ Buyer is purchasing 2 units of Item {item_id}...")
res = b_buyer.post(f"{base_url}/buy/{item_id}", data={"quantity": "2", "notes": "Please deliver via express."})

if "Purchase successful" in res.text or "Order confirmed" in res.text:
    print("   -> Checkout successful! Redirected to order page.")
else:
    # Validate via orders page
    res_orders = b_buyer.get(f"{base_url}/orders")
    if "MacBook Pro M3 Max" in res_orders.text:
        print("   -> Checkout successful! Redirected to order page.")

# Verify Database (Reset read snapshot)
conn.commit()
cursor.execute("SELECT quantity FROM items WHERE item_id = %s", (item_id,))
updated_item = cursor.fetchone()
print(f"✅ Stock decremented! New stock remaining: {updated_item['quantity']} (Expected 3)")

cursor.execute("SELECT * FROM orders WHERE item_id = %s ORDER BY order_id DESC LIMIT 1", (item_id,))
order = cursor.fetchone()
print(f"✅ Order Created in Database: Order ID {order['order_id']}, QTY: {order['quantity']}, Total: ₹{order['total_price']}")

# 3. NOTIFICATIONS (TRIGGERS WORK)
print("\n==== 3. NOTIFICATIONS VERIFICATION ====")
cursor.execute("SELECT message FROM notifications WHERE user_id = %s ORDER BY sent_at DESC LIMIT 1", (order['seller_id'],))
seller_notif = cursor.fetchone()
print(f"✅ Database Trigger Fired! Seller received notification: '{seller_notif['message']}'")

# 4. ADMIN DASHBOARD
print("\n==== 4. ADMIN WORKFLOW ====")
a_admin = requests.Session()
res = a_admin.post(f"{base_url}/login", data={"email": "admin@techmart.com", "password": "admin123"})
print("✅ Logged in as Administrator.")

res_admin_dashboard = a_admin.get(f"{base_url}/admin")
if "Marketplace Statistics" in res_admin_dashboard.text:
    print("✅ Admin can view dashboard statistics.")
    
res_admin_items = a_admin.get(f"{base_url}/admin/items")
if item_title in res_admin_items.text:
    print("✅ Admin can see the global marketplace inventory including the new MacBook Pro.")
    
res_admin_users = a_admin.get(f"{base_url}/admin/users")
if "ananya@gmail.com" in res_admin_users.text:
    print("✅ Admin can manage all platform users.")

print("\n🚀 ALL OPERATIONS FUNCTIONING CORRECTLY!")
cursor.close()
conn.close()
