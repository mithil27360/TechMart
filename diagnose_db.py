import os
import mysql.connector
from dotenv import load_dotenv

# Load .env
load_dotenv()

def test_connection():
    print("--- Database Diagnostics ---")
    
    # Check Environment Variables
    env_vars = ["MYSQL_HOST", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE", "MYSQL_PORT"]
    for var in env_vars:
        val = os.getenv(var)
        print(f"{var}: {val if var != 'MYSQL_PASSWORD' else '********'}")

    # Build Config
    config = {
        "host":         os.getenv("MYSQL_HOST"),
        "user":         os.getenv("MYSQL_USER"),
        "password":     os.getenv("MYSQL_PASSWORD"),
        "database":     os.getenv("MYSQL_DATABASE"),
        "port":         int(os.getenv("MYSQL_PORT", 3306)),
    }
    
    # Add SSL if remote
    if config.get("host") not in ("localhost", "127.0.0.1"):
        config["ssl_disabled"] = False
        config["ssl_verify_identity"] = False
        print("Using SSL for remote connection.")

    try:
        print(f"Attempting connection to {config['host']}:{config['port']}...")
        conn = mysql.connector.connect(**config)
        if conn.is_connected():
            print("✅ SUCCESS: Connected to MySQL!")
            
            # Check Tables
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [t[0] for t in cursor.fetchall()]
            print(f"Found Tables: {tables}")
            
            # Check User Table specifically
            if 'users' in tables:
                cursor.execute("SELECT COUNT(*) FROM users")
                count = cursor.fetchone()[0]
                print(f"Users in DB: {count}")
            
            conn.close()
    except mysql.connector.Error as err:
        print(f"❌ ERROR: {err}")
        if err.errno == 2003:
            print("Hint: Host unreachable. Check IP Allowlist or Hostname.")
        elif err.errno == 1045:
            print("Hint: Access denied. Check User/Password.")
        elif err.errno == 1049:
            print("Hint: Database not found.")
        else:
            print(f"Hint: Generic error code {err.errno}")

if __name__ == "__main__":
    test_connection()
