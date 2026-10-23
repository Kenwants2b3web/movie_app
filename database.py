import sqlite3

DB_NAME = "users.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def create_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def add_user(username, password_hash, salt):
    conn = get_connection()
    cur = conn.cursor()
    try:
        # use ? placeholders so we are safe from SQL injection
        cur.execute(
            "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
            (username, password_hash, salt),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # username is already taken
        return False
    finally:
        conn.close()


def get_user(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT password_hash, salt FROM users WHERE username = ?", (username,)
    )
    row = cur.fetchone()
    conn.close()
    return row


# quick test, only runs when you run this file directly
if __name__ == "__main__":
    create_tables()
    print("Table created. users.db should now exist.")
