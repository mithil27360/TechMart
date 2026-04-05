import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

def get_db_config():
    """read db settings from env"""
    load_dotenv()  # refresh in case anything changed
    config = {
        "host":     os.getenv("MYSQL_HOST", "localhost"),
        "user":     os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "techmart"),
        "port":     int(os.getenv("MYSQL_PORT", 3306)),
        "ssl_ca":   os.getenv("MYSQL_SSL_CA"),
        "unix_socket": os.getenv("MYSQL_UNIX_SOCKET"),
    }
    return config

def get_connection():
    """connect to mysql, returns connection or None"""
    try:
        raw = get_db_config()
        
        # remove None values so connector doesn't complain
        config = {k: v for k, v in raw.items() if v is not None}
        
        # if its a remote host, dont use unix socket
        if config.get("host") not in ("localhost", "127.0.0.1"):
            config.pop("unix_socket", None)
            # enable ssl for remote dbs
            if not config.get("ssl_ca"):
                config["ssl_disabled"] = False
                config["ssl_verify_identity"] = False

        conn = mysql.connector.connect(**config)
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"db connection error: {e}")
    return None

def init_db():
    """create database and run schema.sql on startup"""
    config = get_db_config()
    db_name = config["database"]
    
    # try to create database if running locally
    if config.get("host") in ("localhost", "127.0.0.1"):
        try:
            base_cfg = {
                "host": config["host"],
                "user": config["user"],
                "password": config["password"],
                "port": config["port"],
            }
            if config.get("unix_socket"):
                base_cfg["unix_socket"] = config["unix_socket"]
            
            base = mysql.connector.connect(**base_cfg)
            c = base.cursor()
            c.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
            base.commit()
            c.close()
            base.close()
            print(f"database '{db_name}' ready")
        except Error as e:
            print(f"skipping db creation: {e}")

    conn = get_connection()
    if not conn:
        print("couldnt connect to db")
        return

    cursor = conn.cursor(buffered=True)
    try:
        with open("schema.sql", "r") as f:
            raw = f.read()

        # parse schema.sql - need to handle DELIMITER for procedures/triggers
        stmts = []
        current = []
        delim = ";"
        
        for line in raw.splitlines():
            stripped = line.strip().upper()
            if stripped.startswith("DELIMITER"):
                parts = line.strip().split()
                if len(parts) == 2:
                    new_delim = parts[1]
                    if new_delim != delim:
                        block = "\n".join(current).strip()
                        if block:
                            stmts.append(block)
                        current = []
                        delim = new_delim
                continue
            
            if delim != ";" and line.strip().endswith(delim.strip()):
                current.append(line.rstrip()[: -len(delim.strip())])
                stmts.append("\n".join(current).strip())
                current = []
            else:
                current.append(line)

        # handle remaining lines
        block = "\n".join(current).strip()
        for s in block.split(";"):
            s = s.strip()
            if s:
                stmts.append(s)

        # run each statement
        for stmt in stmts:
            s = stmt.strip()
            if not s:
                continue
            try:
                cursor.execute(s)
                try: cursor.fetchall() 
                except: pass
                while cursor.nextset(): pass
                conn.commit()
            except Error as e:
                # ignore common errors like table already exists, duplicate entry etc
                if e.errno not in (1050, 1062, 1304, 1360):
                    print(f"sql warning ({e.errno}): {e.msg}")

        print("schema loaded ok")
    except FileNotFoundError:
        print("schema.sql not found, skipping")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    init_db()
