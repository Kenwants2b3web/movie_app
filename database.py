import sqlite3

DB_NAME = "users.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    # makes SQLite really follow the FOREIGN KEY rules
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL
            )
        """)

        # older databases do not have the iterations column yet
        cur.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cur.fetchall()]
        if "iterations" not in columns:
            cur.execute(
                "ALTER TABLE users ADD COLUMN iterations "
                "INTEGER NOT NULL DEFAULT 100000"
            )

        # failed logins are saved here so the lock still works after a restart
        cur.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                username TEXT PRIMARY KEY,
                failed_count INTEGER NOT NULL,
                locked_until REAL NOT NULL
            )
        """)

        # one table for every category (movie, tv, later music and game)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                item_id TEXT NOT NULL,
                title TEXT NOT NULL,
                year TEXT,
                rating REAL,
                image TEXT,
                overview TEXT,
                UNIQUE (user_id, category, item_id),
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        conn.commit()
    finally:
        conn.close()


def add_user(username, password_hash, salt, iterations):
    conn = get_connection()
    try:
        cur = conn.cursor()

        # "Ken" and "ken" count as the same username
        cur.execute(
            "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        )
        if cur.fetchone() is not None:
            return False

        # always use ? placeholders so we are safe from SQL injection
        cur.execute(
            "INSERT INTO users (username, password_hash, salt, iterations) "
            "VALUES (?, ?, ?, ?)",
            (username, password_hash, salt, iterations),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_user(username):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT username, password_hash, salt, iterations FROM users "
            "WHERE username = ? COLLATE NOCASE",
            (username,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def get_user_id(username):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return row[0]
    finally:
        conn.close()


def update_password(username, password_hash, salt, iterations):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET password_hash = ?, salt = ?, iterations = ? "
            "WHERE username = ?",
            (password_hash, salt, iterations, username),
        )
        conn.commit()
    finally:
        conn.close()


def get_attempts(key):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT failed_count, locked_until FROM login_attempts "
            "WHERE username = ?",
            (key,),
        )
        row = cur.fetchone()
        if row is None:
            return 0, 0
        return row[0], row[1]
    finally:
        conn.close()


def save_attempts(key, failed_count, locked_until):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO login_attempts "
            "(username, failed_count, locked_until) VALUES (?, ?, ?)",
            (key, failed_count, locked_until),
        )
        conn.commit()
    finally:
        conn.close()


def clear_attempts(key):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM login_attempts WHERE username = ?", (key,))
        conn.commit()
    finally:
        conn.close()


# ---------- favorites ----------
# every function needs the user_id, so one user can never touch the
# favorites of another user

def count_favorites(user_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,)
        )
        return cur.fetchone()[0]
    finally:
        conn.close()


def add_favorite(user_id, category, item_id, title, year, rating, image, overview):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO favorites "
            "(user_id, category, item_id, title, year, rating, image, overview) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, category, item_id, title, year, rating, image, overview),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_favorite(user_id, category, item_id):
    # returns True if something was really deleted
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM favorites "
            "WHERE user_id = ? AND category = ? AND item_id = ?",
            (user_id, category, item_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_favorite_keys(user_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT category, item_id FROM favorites WHERE user_id = ?",
            (user_id,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def get_favorites(user_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT category, item_id, title, year, rating, image, overview "
            "FROM favorites WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        )
        return cur.fetchall()
    finally:
        conn.close()


# quick test, only runs when you run this file directly
if __name__ == "__main__":
    create_tables()
    print("Tables created. users.db should now exist.")
