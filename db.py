import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()  # reads .env into os.environ

DB_CONFIG = {
    "host":         os.getenv("MYSQL_HOST", "localhost"),
    "user":         os.getenv("MYSQL_USER", "root"),
    "password":     os.getenv("MYSQL_PASSWORD", ""),
    "database":     os.getenv("MYSQL_DATABASE", "techmart"),
    "port":         int(os.getenv("MYSQL_PORT", 3306)),
    "ssl_ca":       os.getenv("MYSQL_SSL_CA"),
    "unix_socket": os.getenv("MYSQL_UNIX_SOCKET"),
}

def get_connection():
    try:
        # Filter out None values from DB_CONFIG
        config = {k: v for k, v in DB_CONFIG.items() if v is not None}
        
        # Priority: If host is remote, DO NOT use unix_socket
        if config.get("host") not in ("localhost", "127.0.0.1"):
            config.pop("unix_socket", None)
            
            # Aiven/Remote DB compatibility: Enable SSL if host is remote
            if not config.get("ssl_ca"):
                config["ssl_disabled"] = False
                # Some versions might require ssl_verify_identity=False if not using CA
                config["ssl_verify_identity"] = False

        conn = mysql.connector.connect(**config)
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"MySQL connection error: {e}")
    return None

def init_db():
    db_name = DB_CONFIG["database"]
    # Only attempt to create database if on localhost
    if DB_CONFIG.get("host") in ("localhost", "127.0.0.1"):
        try:
            base_cfg = {
                "host": DB_CONFIG["host"],
                "user": DB_CONFIG["user"],
                "password": DB_CONFIG["password"],
                "port": DB_CONFIG["port"],
            }
            if DB_CONFIG.get("unix_socket"):
                base_cfg["unix_socket"] = DB_CONFIG["unix_socket"]
            
            base = mysql.connector.connect(**base_cfg)
            cur = base.cursor()
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
            base.commit()
            cur.close()
            base.close()
            print(f"Database '{db_name}' ready.")
        except Error as e:
            print(f"Note: Skipping database creation (likely already exists or remote restricted): {e}")

    conn = get_connection()
    if not conn:
        return

    cursor = conn.cursor(buffered=True)
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
