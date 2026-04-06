#!/bin/bash

# Configuration
DB_USER="root"
DB_PASS="Mithil@27"
DB_NAME="marketnest"
MYSQL_CMD="mysql -h localhost -u $DB_USER -p$DB_PASS -D $DB_NAME -N -s -e"

echo "===================================================="
echo "🚀 TECHMART INDUSTRIAL-GRADE TEST SUITE"
echo "===================================================="

# --- Section 1: Hard Integrity ---
echo -e "\n[1.1] Testing User Uniqueness (Duplicate Email)..."
$MYSQL_CMD "INSERT INTO users (name, email, password, role_id) VALUES ('Test', 'rahul@gmail.com', '123', 1);" 2>&1 | grep "Duplicate entry" && echo "✅ PASS: Duplicate email blocked." || echo "❌ FAIL: Duplicate email allowed."

echo -e "\n[1.2] Testing Price Constraint (Negative Price)..."
$MYSQL_CMD "UPDATE items SET price = -10.00 WHERE item_id = 1;" 2>&1 | grep "Check constraint" && echo "✅ PASS: Negative price blocked." || echo "❌ FAIL: Negative price allowed."

echo -e "\n[1.3] Testing Quantity Floor (Negative Quantity)..."
$MYSQL_CMD "UPDATE items SET quantity = -5 WHERE item_id = 1;" 2>&1 | grep "Check constraint" && echo "✅ PASS: Negative quantity blocked." || echo "❌ FAIL: Negative quantity allowed."

echo -e "\n[1.4] Testing Cascade Delete (Seller -> Items)..."
$MYSQL_CMD "DELETE FROM users WHERE user_id = 2;" # Seller Ananya
ITEM_COUNT=$($MYSQL_CMD "SELECT COUNT(*) FROM items WHERE seller_id = 2;")
if [ "$ITEM_COUNT" -eq 0 ]; then echo "✅ PASS: Seller items cascaded."; else echo "❌ FAIL: Orphaned items found ($ITEM_COUNT)."; fi

# Re-seed a seller for remaining tests
$MYSQL_CMD "INSERT INTO users (user_id, name, email, password, role_id) VALUES (2, 'Ananya', 'ananya@gmail.com', '123', 2);"
$MYSQL_CMD "INSERT INTO items (item_id, title, description, price, category_id, seller_id, condition_id, quantity) VALUES (1, 'iPhone 13', 'Good condition', 50000, 2, 2, 2, 5);"

# --- Section 2: Advanced Features ---
echo -e "\n[2.1] Testing Interest Trigger (matching alert)..."
$MYSQL_CMD "DELETE FROM notifications; DELETE FROM interests;"
$MYSQL_CMD "INSERT INTO interests (user_id, category_id, keyword) VALUES (1, 2, 'Pixel');"
$MYSQL_CMD "INSERT INTO items (title, price, category_id, seller_id, condition_id, quantity) VALUES ('Google Pixel 7', 45000, 2, 2, 1, 10);"
NOTIF=$($MYSQL_CMD "SELECT message FROM notifications WHERE user_id = 1 AND message LIKE '%Pixel%';")
if [ ! -z "$NOTIF" ]; then echo "✅ PASS: Interest trigger fired."; else echo "❌ FAIL: No notification found."; fi

echo -e "\n[2.2] Testing Stored Procedure (get_notifications)..."
$MYSQL_CMD "CALL get_notifications(1);" > /dev/null && echo "✅ PASS: Procedure get_notifications exists and runs."

echo -e "\n[2.3] Testing Function (get_seller_rating)..."
RATING=$($MYSQL_CMD "SELECT get_seller_rating(2);")
echo "ℹ️ Seller Rating: $RATING"
if (( $(echo "$RATING >= 0" | bc -l) )); then echo "✅ PASS: Function get_seller_rating returns value."; else echo "❌ FAIL: Invalid rating."; fi

# --- Section 3: ACID & Concurrency ---
echo -e "\n[3.1] Testing ACID Atomicity (Manual Rollback Simulation)..."
$MYSQL_CMD "START TRANSACTION; UPDATE items SET quantity = 99 WHERE item_id = 1; ROLLBACK;"
QTY=$($MYSQL_CMD "SELECT quantity FROM items WHERE item_id = 1;")
if [ "$QTY" -eq 5 ]; then echo "✅ PASS: Rollback restored state."; else echo "❌ FAIL: Rollback failed (Qty: $QTY)."; fi

# --- Section 5: Analytics Power-Ups ---
echo -e "\n[5.1] Testing Business Rule Trigger (Self-Purchase Prevention)..."
$MYSQL_CMD "INSERT INTO orders (buyer_id, total_price, status_id) VALUES (2, 50000, 1);"
ORD_ID=$($MYSQL_CMD "SELECT MAX(order_id) FROM orders;")
$MYSQL_CMD "INSERT INTO order_items (order_id, item_id, seller_id, price_at_purchase) VALUES ($ORD_ID, 1, 2, 50000);" 2>&1 | grep "Business Rule Violation" && echo "✅ PASS: Self-purchase blocked by trigger." || echo "❌ FAIL: Self-purchase allowed."

echo -e "\n[5.2] Testing Cursor Procedure (Seller Report)..."
$MYSQL_CMD "CALL generate_seller_report();"
REP_COUNT=$($MYSQL_CMD "SELECT COUNT(*) FROM seller_performance;")
if [ "$REP_COUNT" -gt 0 ]; then 
    echo "✅ PASS: Cursor procedure populated seller_performance table."
    $MYSQL_CMD "SELECT * FROM seller_performance;"
else 
    echo "❌ FAIL: Performance table empty."; 
fi

echo -e "\n[5.3] Testing Price Intelligence View..."
VIEW_RES=$($MYSQL_CMD "SELECT title, price_status FROM category_price_intelligence LIMIT 3;")
if [ ! -z "$VIEW_RES" ]; then echo "✅ PASS: Price Intelligence view is functional."; echo "$VIEW_RES"; else echo "❌ FAIL: View empty."; fi

echo -e "\n===================================================="
echo "🏁 TEST SUITE COMPLETE"
echo "===================================================="
