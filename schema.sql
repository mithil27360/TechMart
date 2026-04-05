-- 1. DROP EXISTING CONSTRUCTS FOR CLEAN INITIATION
DROP PROCEDURE IF EXISTS get_notifications;
DROP PROCEDURE IF EXISTS mark_notification_read;
DROP TRIGGER IF EXISTS notify_users_after_item;
DROP TRIGGER IF EXISTS notify_seller_after_order;

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
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role_id INT NOT NULL,
    google_id VARCHAR(255) UNIQUE,
    is_verified BOOLEAN DEFAULT FALSE,
    otp_token VARCHAR(6),
    otp_expiry TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
CREATE INDEX idx_interests_user ON interests(user_id);
CREATE INDEX idx_notif_user ON notifications(user_id);
CREATE INDEX idx_matching_interests ON interests(category_id, min_price, max_price);

-- 5. SEED INITIAL DATA
INSERT INTO users (name, email, password, role_id) VALUES
('Rahul', 'rahul@gmail.com', '123', 1),    -- buyer
('Ananya', 'ananya@gmail.com', '123', 2),  -- seller
('Kiran', 'kiran@gmail.com', '123', 1),    -- buyer
('Administrator', 'admin@techmart.com', 'admin123', 3); -- admin

INSERT INTO categories (name, parent_id) VALUES
('Electronics', null), ('Phones', 1), ('Laptops', 1);

INSERT INTO items (title, description, price, category_id, seller_id, condition_id, quantity) VALUES
('iPhone 13', 'Good condition, 1 year old', 50000, 2, 2, 2, 5),          -- used
('MacBook Air', 'Silicon M1, Space Grey', 75000, 3, 2, 1, 3),            -- new
('Mac Studio Silicon M2', 'Ultra performance desktop', 150000, 1, 2, 1, 2); -- new

-- 6. PROCEDURES
DELIMITER $$
CREATE PROCEDURE get_notifications(IN p_user_id INT)
BEGIN
    SELECT n.*, i.title, i.price 
    FROM notifications n
    JOIN items i ON n.item_id = i.item_id
    WHERE n.user_id = p_user_id
    ORDER BY n.sent_at DESC;
END $$

CREATE PROCEDURE mark_notification_read(IN p_notif_id INT, IN p_user_id INT)
BEGIN
    UPDATE notifications SET is_read = TRUE 
    WHERE notification_id = p_notif_id AND user_id = p_user_id;
END $$
DELIMITER ;

-- 7. TRIGGERS
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
DELIMITER ;
