-- 1. DROP EXISTING CONSTRUCTS FOR CLEAN INITIATION
DROP PROCEDURE IF EXISTS generate_seller_report;
DROP PROCEDURE IF EXISTS get_notifications;
DROP PROCEDURE IF EXISTS mark_notification_read;
DROP TRIGGER IF EXISTS prevent_self_purchase;
DROP TRIGGER IF EXISTS notify_users_after_item;
DROP TRIGGER IF EXISTS notify_seller_after_order;

DROP TABLE IF EXISTS seller_performance;
DROP TABLE IF EXISTS search_history;
DROP TABLE IF EXISTS items_img;
DROP TABLE IF EXISTS wishlist;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS interests;
DROP TABLE IF EXISTS items;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS conditions;
DROP TABLE IF EXISTS order_status;
DROP TABLE IF EXISTS roles;

-- 2. LOOKUP TABLES
CREATE TABLE roles (
    role_id INT PRIMARY KEY AUTO_INCREMENT,
    role_name VARCHAR(20) UNIQUE NOT NULL
);

CREATE TABLE order_status (
    status_id INT PRIMARY KEY AUTO_INCREMENT,
    status_name VARCHAR(20) UNIQUE NOT NULL
);

CREATE TABLE conditions (
    condition_id INT PRIMARY KEY AUTO_INCREMENT,
    condition_name VARCHAR(20) UNIQUE NOT NULL
);

-- Seed Lookup Data
INSERT INTO roles (role_name) VALUES ('buyer'), ('seller'), ('admin');
INSERT INTO order_status (status_name) VALUES ('pending'), ('confirmed'), ('cancelled'), ('completed');
INSERT INTO conditions (condition_name) VALUES ('new'), ('used'), ('refurbished');

-- 3. CORE ENTITIES
CREATE TABLE users (
    user_id      INT PRIMARY KEY AUTO_INCREMENT,
    name         VARCHAR(100) NOT NULL,
    email        VARCHAR(100) UNIQUE NOT NULL,
    password     VARCHAR(255) NOT NULL,
    role_id      INT NOT NULL,
    is_verified  BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(role_id)
);

CREATE TABLE categories (
    category_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    parent_id INT,
    description TEXT,
    FOREIGN KEY (parent_id) REFERENCES categories(category_id) ON DELETE SET NULL
);

CREATE TABLE items (
    item_id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    category_id INT NOT NULL,
    seller_id INT NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL CHECK (price > 0),
    condition_id INT NOT NULL,
    quantity INT NOT NULL CHECK (quantity >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE RESTRICT,
    FOREIGN KEY (seller_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (condition_id) REFERENCES conditions(condition_id)
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    buyer_id INT NOT NULL,
    total_price DECIMAL(10,2),
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status_id INT NOT NULL,
    notes TEXT,
    FOREIGN KEY (buyer_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (status_id) REFERENCES order_status(status_id)
);

CREATE TABLE order_items (
    order_item_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    item_id INT NOT NULL,
    seller_id INT NOT NULL,
    quantity INT DEFAULT 1,
    price_at_purchase DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE RESTRICT,
    FOREIGN KEY (seller_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT chk_quantity CHECK (quantity > 0),
    CONSTRAINT chk_price CHECK (price_at_purchase >= 0)
);

CREATE TABLE interests (
    interest_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    category_id INT,
    keyword VARCHAR(255),
    min_price DECIMAL(10,2),
    max_price DECIMAL(10,2),
    condition_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE,
    FOREIGN KEY (condition_id) REFERENCES conditions(condition_id),
    CHECK (min_price <= max_price)
);

CREATE TABLE notifications (
    notification_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    item_id INT NOT NULL,
    interest_id INT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT FALSE,
    message TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE,
    FOREIGN KEY (interest_id) REFERENCES interests(interest_id) ON DELETE SET NULL
);

CREATE TABLE wishlist (
    wishlist_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    item_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE,
    UNIQUE (user_id, item_id)
);

CREATE TABLE items_img (
    image_id INT PRIMARY KEY AUTO_INCREMENT,
    item_id INT NOT NULL,
    image_url TEXT NOT NULL,
    display_order INT,
    is_primary BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

CREATE TABLE search_history (
    search_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    query TEXT,
    category_id INT,
    min_price DECIMAL(10,2),
    max_price DECIMAL(10,2),
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id) ON DELETE CASCADE
);

-- 4. INDEXES
CREATE INDEX idx_items_cat ON items(category_id);
CREATE INDEX idx_items_price ON items(price);
CREATE FULLTEXT INDEX idx_items_search ON items(title, description);

CREATE INDEX idx_interests_user ON interests(user_id);
CREATE INDEX idx_notif_user ON notifications(user_id);
CREATE INDEX idx_matching_interests ON interests(category_id, min_price, max_price);


-- 5. SEED INITIAL DATA
INSERT INTO users (name, email, password, role_id) VALUES
('Rahul', 'rahul@gmail.com', '123', 1),    -- buyer
('TechMart Official', 'ananya@gmail.com', '123', 2),  -- official seller
('Kiran', 'kiran@gmail.com', '123', 1),    -- buyer
('Administrator', 'admin@techmart.com', 'admin123', 3), -- admin
('Buyer Account', 'buyer@gmail.com', 'buyer27', 1),
('Seller Account', 'seller@gmail.com', 'seller27', 2);

INSERT INTO categories (name, parent_id) VALUES
('Electronics', null), ('Phones', 1), ('Laptops', 1), ('Audio', 1), ('Watches', 1), ('Accessories', 1);

INSERT INTO items (title, description, price, category_id, seller_id, condition_id, quantity) VALUES
('MacBook Air', 'Silicon M1, Space Grey', 75000, 3, 2, 1, 3),
('Mac Studio Silicon M2', 'Ultra performance desktop', 150000, 1, 2, 1, 2),
('iPhone 12', 'Used flagship phone in good condition', 42000, 2, 2, 2, 4),
('iPhone 14 Pro', 'Brand new flagship iPhone', 95000, 2, 2, 1, 2),
('Samsung Galaxy S22', 'High-end Samsung phone', 60000, 2, 2, 1, 3),
('OnePlus 11', 'Latest OnePlus flagship', 52000, 2, 2, 1, 4),
('Google Pixel 7', 'Stock Android experience from Google', 55000, 2, 2, 1, 3),
('Lenovo ThinkPad X1 Carbon', 'Professional grade laptop', 95000, 3, 2, 2, 2),
('Asus ROG Strix G15', 'Gaming beast for high performance', 80000, 3, 2, 1, 4),
('Acer Predator Helios 300', 'Powerful gaming laptop', 78000, 3, 2, 2, 3),
('MacBook Pro M1', 'Apple Silicon high performance', 120000, 3, 2, 1, 2),
('MacBook Pro M2', 'Latest Apple Silicon laptop', 140000, 3, 2, 1, 2),
('boAt Airdopes 141', 'TWS earbuds with long battery life', 1500, 4, 2, 1, 10),
('Noise Buds VS104', 'Crystal clear sound and deep bass', 1800, 4, 2, 1, 8),
('Realme Buds Air 5', 'Active noise cancellation earbuds', 3200, 4, 2, 1, 7),
('Apple AirPods Pro 2', 'Magical sound for your ears', 24000, 4, 2, 1, 6),
('boAt Rockerz 450', 'Comfortable over-ear headphones', 2000, 4, 2, 1, 9),
('Sony WH-CH720N', 'Noise cancelling headphones from Sony', 9000, 4, 2, 1, 5),
('Apple AirPods Max', 'Premium over-ear headphones', 55000, 4, 2, 1, 2),
('JBL Flip 6 Bluetooth Speaker', 'Portable waterproof speaker', 10000, 4, 2, 1, 4),
('boAt Stone 350 Speaker', 'Rugged portable speaker', 2500, 4, 2, 1, 8),
('Marshall Emberton Speaker', 'Iconic design and sound', 15000, 4, 2, 1, 3),
('Apple Watch Series 9', 'Advanced health tracker', 45000, 5, 2, 1, 2),
('Samsung Galaxy Watch 6', 'Sleek smart watch for Android', 30000, 5, 2, 1, 3),
('Noise ColorFit Pro 5', 'Stylish and affordable smart watch', 4000, 5, 2, 1, 7),
('Anker Power Bank 20000mAh', 'Huge capacity portable charger', 3500, 6, 2, 1, 6),
('USB-C Hub 7-in-1 Adapter', 'Expand your laptop connectivity', 2500, 6, 2, 1, 5),
('Logitech MX Master 3 Mouse', 'The choice for productivity', 9000, 6, 2, 1, 8),
('Mechanical Keyboard (RGB)', 'Great tactile feel for typing and gaming', 7000, 6, 2, 2, 6);

INSERT INTO items_img (item_id, image_url, is_primary) VALUES
(1, '7e58fa0ceb5d433188a806ed16ece2ac.webp', TRUE),
(2, '9d790a19e4634228b1b12b0d21211d37.jpg', TRUE),
(3, 'a537ee19509e4311af405336d00dd0c9.png', TRUE),
(4, 'b7571b1bf7c44a7ca408a76505a96ad1.webp', TRUE),
(5, 'd747ebff3dff41cd916055632a54d3d8.jpg', TRUE),
(5, '78a053c1cf8d49d7a0224fe7bc38bcd4.avif', FALSE),
(6, '0188b08cbeb748599b9ddea1270c2abd.jpg', TRUE),
(6, 'be22505a478a478da566259424694b51.webp', FALSE),
(7, 'f0977211348b40f1861bd391059c043e.jpg', TRUE),
(7, 'e71f28ae1b724e5fb315f483db551fc7.jpg', FALSE),
(8, '5236eab31e5147fc945cc9eea7ba8a66.avif', TRUE),
(8, 'e729dfa122c94118b38c282a1c0076a7.avif', FALSE),
(8, '4b20f02a318b470ebaffc8fe3fe8ef64.jpg', FALSE),
(9, '50c38ba8843c4e67960f0d3a87848f16.jpg', TRUE),
(9, 'eac0a0b1b4f14dc39f4d181e56565875.webp', FALSE),
(9, 'd91a9daf8de84d92878dba49e4c3aa69.png', FALSE),
(10, '7b61e8f546b64429b04f7b95834d2909.webp', TRUE),
(10, '480eaac9c6cb4df9997ecfc014d373ba.jpg', FALSE),
(11, 'a69396b0c8d143c8af1c51b642b4f05c.jpg', TRUE),
(11, '0fe07af7d084416fa7f4fc587310a13b.jpg', FALSE),
(12, 'ad9e3cf35ddf4419b144859785ec41a8.jpg', TRUE),
(12, 'c6d317f90f5f42e3b86681530472088d.jpg', FALSE),
(13, '3c753568f7e64bc381b9fa7873323dec.jpg', TRUE),
(13, '11332a453fdf4c55ac974704b7e7b0cc.jpg', FALSE),
(14, 'a8d4b92c589344f5bc0f3053911eb360.jpg', TRUE),
(15, 'e6ab192a2fdf4dc7b819366e03cab6ca.jpg', TRUE),
(16, 'f0731523df8f47a3b33879465f4c243a.png', TRUE),
(17, 'd5c4eb326bc34c5ebc43f6b1e3c09c14.jpg', TRUE),
(18, '6c2c41f3ac604806991fab92d5f368df.jpg', TRUE),
(19, '083d6ee7630245f8ab5b588e8fe0792c.webp', TRUE),
(20, '75efa101637e4d9c931faf2ed8203c71.webp', TRUE),
(21, '75f69d9f9a8c497c9076fe75e9141c87.webp', TRUE),
(22, '361dd3b844ba40028c1095e032ceb871.webp', TRUE),
(23, '725ccb7283b04ac3ae88cb0301035f48.png', TRUE),
(24, '23a2fb52e5394222b2678ffc2dca4cd7.avif', TRUE),
(24, 'e1dcdbddd2aa4bb79451090d86a1eeed.jpg', FALSE),
(25, 'd904487d7291421d967c82bf7223a2c6.jpg', TRUE),
(26, 'bef054e138a7483797e671d1064977e4.jpg', TRUE),
(27, '7300902f306e42aa94c15782e0e30390.jpg', TRUE),
(28, '4b4bf3954f6646bfba4a36db44d0cd96.jpg', TRUE),
(29, '5909341daf9d46e08a61e6a62ceb0b22.jpg', TRUE);

-- 6. VIEWS (Complex Data Representation)
CREATE OR REPLACE VIEW category_sales_summary AS
SELECT c.name as category_name, COUNT(oi.order_item_id) as total_items_sold, COALESCE(SUM(oi.price_at_purchase * oi.quantity), 0) as total_revenue
FROM categories c
LEFT JOIN items i ON c.category_id = i.category_id
LEFT JOIN order_items oi ON i.item_id = oi.item_id
GROUP BY c.category_id, c.name;

-- 7. POWER-UP: Analytical View (Price Intelligence)
CREATE OR REPLACE VIEW category_price_intelligence AS
SELECT 
    i.item_id,
    i.title,
    i.price,
    c.name as category_name,
    (SELECT AVG(price) FROM items WHERE category_id = i.category_id) as category_avg_price,
    CASE 
        WHEN i.price > (SELECT AVG(price) * 1.5 FROM items WHERE category_id = i.category_id) THEN 'Overpriced'
        WHEN i.price < (SELECT AVG(price) * 0.5 FROM items WHERE category_id = i.category_id) THEN 'Underpriced'
        ELSE 'Fair Price'
    END as price_status
FROM items i
JOIN categories c ON i.category_id = c.category_id;

-- 8. POWER-UP: Analytical Table (Seller Performance)
CREATE TABLE seller_performance (
    seller_id INT PRIMARY KEY,
    total_revenue DECIMAL(15,2) DEFAULT 0,
    units_sold INT DEFAULT 0,
    avg_item_price DECIMAL(10,2) DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (seller_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 7. PROCEDURES & FUNCTIONS
DELIMITER $$

-- Procedure 1: Get Notifications
CREATE PROCEDURE get_notifications(IN p_user_id INT)
BEGIN
    SELECT n.*, i.title, i.price 
    FROM notifications n
    JOIN items i ON n.item_id = i.item_id
    WHERE n.user_id = p_user_id
    ORDER BY n.sent_at DESC;
END $$

-- Procedure 2: Mark Notification as Read
CREATE PROCEDURE mark_notification_read(IN p_notif_id INT, IN p_user_id INT)
BEGIN
    UPDATE notifications SET is_read = TRUE 
    WHERE notification_id = p_notif_id AND user_id = p_user_id;
END $$

-- Function 1: Compute Seller Rating
CREATE FUNCTION get_seller_rating(p_seller_id INT) RETURNS DECIMAL(3,1)
DETERMINISTIC
BEGIN
    DECLARE avg_rating DECIMAL(3,1);
    DECLARE total_orders INT;
    
    SELECT COUNT(*) INTO total_orders FROM order_items WHERE seller_id = p_seller_id;
    
    IF total_orders = 0 THEN
        RETURN 0.0;
    END IF;
    
    -- Mock dynamic rating based on orders for demo purposes
    SET avg_rating = 4.5 + (total_orders * 0.1);
    IF avg_rating > 5.0 THEN
        SET avg_rating = 5.0;
    END IF;
    
    RETURN avg_rating;
END $$

-- Procedure 3: POWER-UP Cursor Reporting (Seller Performance)
CREATE PROCEDURE generate_seller_report()
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE cur_seller_id INT;
    DECLARE cur_rev DECIMAL(15,2);
    DECLARE cur_units INT;
    DECLARE cur_avg DECIMAL(10,2);
    
    -- Explicit Cursor for Sellers
    DECLARE seller_cursor CURSOR FOR 
        SELECT user_id FROM users WHERE role_id = (SELECT role_id FROM roles WHERE role_name = 'seller');
    
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    OPEN seller_cursor;

    read_loop: LOOP
        FETCH seller_cursor INTO cur_seller_id;
        IF done THEN
            LEAVE read_loop;
        END IF;

        -- Calculate metrics
        SELECT COALESCE(SUM(oi.price_at_purchase * oi.quantity), 0), 
               COALESCE(SUM(oi.quantity), 0)
        INTO cur_rev, cur_units
        FROM order_items oi
        WHERE oi.seller_id = cur_seller_id;

        SELECT COALESCE(AVG(price), 0) INTO cur_avg FROM items WHERE seller_id = cur_seller_id;

        -- Populate Performance Table
        INSERT INTO seller_performance (seller_id, total_revenue, units_sold, avg_item_price)
        VALUES (cur_seller_id, cur_rev, cur_units, cur_avg)
        ON DUPLICATE KEY UPDATE 
            total_revenue = VALUES(total_revenue),
            units_sold = VALUES(units_sold),
            avg_item_price = VALUES(avg_item_price),
            last_updated = CURRENT_TIMESTAMP;
    END LOOP;

    CLOSE seller_cursor;
END $$

DELIMITER ;

-- 8. TRIGGERS
DELIMITER $$
CREATE TRIGGER notify_users_after_item
AFTER INSERT ON items
FOR EACH ROW
BEGIN
    INSERT INTO notifications(user_id, item_id, interest_id, message)
    SELECT i.user_id, NEW.item_id, i.interest_id, 
           CONCAT('New ', NEW.title, ' available in ', (SELECT name FROM categories WHERE category_id=NEW.category_id))
    FROM interests i
    WHERE i.active = TRUE
    AND (i.category_id IS NULL OR i.category_id = NEW.category_id)
    AND (i.min_price IS NULL OR NEW.price >= i.min_price)
    AND (i.max_price IS NULL OR NEW.price <= i.max_price)
    AND (i.condition_id IS NULL OR i.condition_id = NEW.condition_id)
    AND (i.keyword IS NULL OR NEW.title LIKE CONCAT('%', i.keyword, '%') OR NEW.description LIKE CONCAT('%', i.keyword, '%'));
END $$

CREATE TRIGGER notify_seller_after_order
AFTER INSERT ON order_items
FOR EACH ROW
BEGIN
    INSERT INTO notifications(user_id, item_id, message)
    VALUES (NEW.seller_id, NEW.item_id, 
           CONCAT('You have a new order for ', (SELECT title FROM items WHERE item_id=NEW.item_id), ' from ', (SELECT name FROM users WHERE user_id=(SELECT buyer_id FROM orders WHERE order_id=NEW.order_id))));
END $$

-- Trigger 3: POWER-UP Business Rule (Self-Purchase Prevention)
CREATE TRIGGER prevent_self_purchase
BEFORE INSERT ON order_items
FOR EACH ROW
BEGIN
    DECLARE b_id INT;
    SELECT buyer_id INTO b_id FROM orders WHERE order_id = NEW.order_id;
    IF b_id = NEW.seller_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Business Rule Violation: Sellers cannot buy their own items.';
    END IF;
END $$

DELIMITER ;
