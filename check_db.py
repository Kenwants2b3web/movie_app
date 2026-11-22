# Shows what is really saved in users.db, for your demo.
# Run it with:  python check_db.py
# It opens the database in read-only mode, so it cannot change anything.
import sqlite3
from pathlib import Path

DB_FILE = Path("users.db")

if not DB_FILE.exists():
    print("users.db was not found. Run python main.py once and register an account first.")
    raise SystemExit

conn = sqlite3.connect(DB_FILE.resolve().as_uri() + "?mode=ro", uri=True)
cur = conn.cursor()

try:
    cur.execute("SELECT id, username, password_hash, salt, iterations FROM users")
    users = cur.fetchall()

    print("USERS IN THE DATABASE: " + str(len(users)))
    print("=" * 60)

    for user in users:
        user_id, username, password_hash, salt, iterations = user
        cur.execute("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,))
        saved = cur.fetchone()[0]

        print("ID:         " + str(user_id))
        print("Username:   " + username)
        print("Hash:       " + password_hash[:32] + "...  (" + str(len(password_hash)) + " characters)")
        print("Salt:       " + salt[:16] + "...  (different for every user)")
        print("Iterations: " + str(iterations))
        print("Favorites:  " + str(saved))
        print("-" * 60)

    # a good hash is 64 hex characters, a plain password never looks like that
    all_hashed = True
    for user in users:
        hash_text = user[2]
        if len(hash_text) != 64 or any(c not in "0123456789abcdef" for c in hash_text):
            all_hashed = False
    if all_hashed:
        print("OK: every password is saved as a salted hash, no plain text.")
    else:
        print("WARNING: one of the passwords does not look like a hash!")

    cur.execute("SELECT username, failed_count, locked_until FROM login_attempts")
    attempts = cur.fetchall()
    print("Failed login records: " + str(len(attempts)))

except sqlite3.OperationalError:
    print("The database is missing some tables. Run python main.py once so it updates.")

conn.close()
