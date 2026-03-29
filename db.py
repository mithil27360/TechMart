import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()  # reads .env into os.environ

DB_CONFIG = {
    "host":         os.getenv("MYSQL_HOST", "localhost"),
    "user":         os.getenv("MYSQL_USER", "root"),
    "password":     os.getenv("MYSQL_PASSWORD", ""),
    "database":     os.getenv("MYSQL_DATABASE", "marketnest"),
    "unix_socket": os.getenv("MYSQL_UNIX_SOCKET"),
}

def get_connection():
    try:
        # Filter out None values from DB_CONFIG (like unix_socket if not set)
        config = {k: v for k, v in DB_CONFIG.items() if v is not None}
        conn = mysql.connector.connect(**config)
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"MySQL connection error: {e}")
    return None

def init_db():
    """Auto-create database if missing, then run schema.sql."""
    db_name = DB_CONFIG["database"]
    base_cfg = {
        "host": DB_CONFIG["host"],
        "user": DB_CONFIG["user"],
        "password": DB_CONFIG["password"],
    }
    if DB_CONFIG.get("unix_socket"):
        base_cfg["unix_socket"] = DB_CONFIG["unix_socket"]
    try:
        base = mysql.connector.connect(**base_cfg)
        cur = base.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
        base.commit()
        cur.close()
        base.close()
        print(f"Database '{db_name}' ready.")
    except Error as e:
        print(f"Failed to create database: {e}")
        return

    conn = get_connection()
    if not conn:
        return

    cursor = conn.cursor()
    try:
        with open("schema.sql", "r") as f:
            raw = f.read()

        statements = []
        current = []
        delimiter = ";"
        for line in raw.splitlines():
            stripped = line.strip().upper()
            if stripped.startswith("DELIMITER"):
                parts = line.strip().split()
                if len(parts) == 2:
                    new_delim = parts[1]
                    if new_delim != delimiter:
                        block = "\n".join(current).strip()
                        if block:
                            statements.append(block)
                        current = []
                        delimiter = new_delim
                continue
            if delimiter != ";" and line.strip().endswith(delimiter.strip()):
                current.append(line.rstrip()[: -len(delimiter.strip())])
                statements.append("\n".join(current).strip())
                current = []
            else:
                current.append(line)

        block = "\n".join(current).strip()
        for stmt in block.split(";"):
            s = stmt.strip()
            if s:
                statements.append(s)

        for stmt in statements:
            s = stmt.strip()
            if not s:
                continue
            try:
                cursor.execute(s)
                conn.commit()
            except Error as e:
                # Ignore: table/proc already exists, duplicate seed data
                if e.errno not in (1050, 1062, 1304, 1360):
                    print(f"Warning ({e.errno}): {e.msg}")

        print("Schema initialized successfully.")
    except FileNotFoundError:
        print("schema.sql not found.")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    init_db()
