# 🛒 TechMart — Premium Electronics Marketplace

TechMart is a high-performance, full-stack electronic marketplace built with **Flask** and **MySQL**. It features a robust database schema with advanced SQL "Power-Ups" like cursors, triggers, and stored procedures for automated order processing and real-time user notifications.

---

## 🚀 Quick Setup

Follow these steps to get the marketplace running locally on your machine.

### 1. Prerequisites
- **Python**: Version 3.8 or higher.
- **MySQL**: 8.0 or higher.
- **Virtual Environment**: Recommended (e.g., `venv`).

### 2. Database Configuration
1. Start your **MySQL** server.
2. Ensure you have a user with permission to create databases (default: `root`).
3. You don't need to manually create the database or tables; the application will automatically run `schema.sql` on its first launch.

### 3. Environment Setup
Create a `.env` file in the root directory with the following variables:

```env
# MySQL Database Config
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=marketnest
MYSQL_PORT=3306

# Flask Security
FLASK_SECRET_KEY=techmart_ultra_secure_secret_2026
```

### 4. Installation & Running
1. **Initialize Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Application**:
   ```bash
   python app.py
   ```
   The app will be available at [http://127.0.0.1:5001](http://127.0.0.1:5001).

---

## 🔑 Default Accounts (Demo)

Use these credentials to explore the different roles within the marketplace:

| Role | Username (Email) | Password |
| :--- | :--- | :--- |
| **Administrator** | `admin@techmart.com` | `admin123` |
| **Seller** | `ananya@gmail.com` | `123` |
| **Buyer** | `rahul@gmail.com` | `123` |

---

## 🛠️ Advanced Features
- **Automated Alerts**: Triggers notify buyers when products matching their "Interests" are posted.
- **Stock Intelligence**: ACID transactions ensure inventory is never oversold.
- **Auto-Fulfillment**: Orders are automatically marked as `SUCCESSFUL` upon purchase for a seamless demo experience.
- **Admin Dashboard**: Comprehensive stats on revenue, user growth, and top-selling items.

---

## 📂 Project Structure
- `app.py`: Main Flask application and routing logic.
- `db.py`: Database connection and auto-schema initialization.
- `schema.sql`: Complete database structure and seed data.
- `static/`: CSS and JavaScript assets.
- `templates/`: Jinja2 HTML templates.
