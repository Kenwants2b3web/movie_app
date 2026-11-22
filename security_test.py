# Security checks for MovieHub. Run it with:  python security_test.py
# It uses its own temporary database, so your real users.db is not touched.
import os
import tempfile
import time

import api
import auth
import database
import favorites

database.DB_NAME = os.path.join(tempfile.gettempdir(), "moviehub_security_test.db")
if os.path.exists(database.DB_NAME):
    os.remove(database.DB_NAME)
database.create_tables()

results = []


def check(name, condition):
    if condition:
        print("PASS  " + name)
    else:
        print("FAIL  " + name)
    results.append(condition)


print("--- Login system ---")
ok, msg = auth.register("real_user", "G00d-Passw0rd!")
check("register a normal user", ok)

# 1. SQL injection tries
attacks = ["' OR '1'='1", "admin'--", "x'; DROP TABLE users;--", "\" OR \"\"=\"", "real_user' --"]
blocked = True
for attack in attacks:
    ok1, m1, n1 = auth.login(attack, "anything")
    ok2, m2, n2 = auth.login("real_user", attack)
    if ok1 or ok2:
        blocked = False
check("SQL injection in username or password is rejected", blocked)

conn = database.get_connection()
row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
conn.close()
check("users table still exists and was not changed by the attacks", row[0] == 1)

ok, msg = auth.register("evil'; DROP TABLE users;--", "G00d-Passw0rd!")
check("register rejects a username with SQL characters", not ok)

# 2. passwords are never saved as plain text
conn = database.get_connection()
saved = conn.execute("SELECT password_hash, salt, iterations FROM users").fetchone()
conn.close()
with open(database.DB_NAME, "rb") as f:
    file_bytes = f.read()
check("password is not saved as plain text", b"G00d-Passw0rd!" not in file_bytes)
check("saved hash is long and not the password", len(saved[0]) == 64 and saved[0] != "G00d-Passw0rd!")
check("new accounts use the strong iteration count", saved[2] == auth.ITERATIONS)

auth.register("second_user", "G00d-Passw0rd!")
conn = database.get_connection()
rows = conn.execute("SELECT password_hash, salt FROM users").fetchall()
conn.close()
check("same password gives different salt and hash for each user", rows[0][0] != rows[1][0] and rows[0][1] != rows[1][1])

# 3. validation
check("short password rejected", not auth.register("shortpw_user", "abc")[0])
check("common password rejected", not auth.register("common_user", "password123")[0])
check("very long password rejected", not auth.register("long_user", "a" * 500)[0])
check("password same as username rejected", not auth.register("sameasuser", "sameasuser")[0])
check("username with spaces rejected", not auth.register("bad name", "G00d-Passw0rd!")[0])
check("duplicate username rejected (even with different letter case)", not auth.register("REAL_USER", "G00d-Passw0rd!")[0])

# 4. lockout
for i in range(5):
    auth.login("real_user", "wrong-password")
ok, msg, name = auth.login("real_user", "G00d-Passw0rd!")
check("account locks after 5 wrong tries (even the right password fails)", not ok and "Too many" in msg)

conn = database.get_connection()
attempt = conn.execute("SELECT failed_count FROM login_attempts WHERE username = 'real_user'").fetchone()
conn.close()
check("the lock is saved in the database (survives a restart)", attempt is not None and attempt[0] >= 5)

# pretend the 30 seconds passed
database.save_attempts("real_user", 5, time.time() - 1)
ok, msg, name = auth.login("real_user", "G00d-Passw0rd!")
check("login works again after the lock ends", ok)

# 5. old accounts get upgraded
old_salt = os.urandom(16)
old_hash = auth.hash_password("0ld-Account-pw!", old_salt, 100000)
database.add_user("old_account", old_hash, old_salt.hex(), 100000)
ok, msg, name = auth.login("old_account", "0ld-Account-pw!")
conn = database.get_connection()
upgraded = conn.execute("SELECT iterations FROM users WHERE username = 'old_account'").fetchone()
conn.close()
check("old account can still log in", ok)
check("old account hash was upgraded to the strong settings", upgraded[0] == auth.ITERATIONS)
ok, msg, name = auth.login("old_account", "0ld-Account-pw!")
check("upgraded account still logs in", ok)

print()
print("--- Favorites ---")
user_a = database.get_user_id("real_user")
user_b = database.get_user_id("second_user")
movie = {"id": 603, "title": "The Matrix", "year": "1999", "rating": 8.2,
         "poster_path": "/abc12345.jpg", "overview": "A hacker learns the truth."}

check("a favorite can be saved", favorites.toggle(user_a, "movie", movie) is True)
check("saving again removes it (toggle)", favorites.toggle(user_a, "movie", movie) is False)
favorites.toggle(user_a, "movie", movie)
check("saved titles are listed for the owner", "movie:603" in favorites.saved_keys(user_a))
check("another user cannot see them", "movie:603" not in favorites.saved_keys(user_b))

favorites.toggle(user_b, "movie", movie)
favorites.toggle(user_b, "movie", movie)
check("removing as user B does not remove user A's favorite", "movie:603" in favorites.saved_keys(user_a))

def rejected(category, item):
    try:
        favorites.toggle(user_a, category, item)
    except ValueError:
        return True
    return False

check("unknown category is rejected", rejected("x'; DROP TABLE favorites;--", movie))
check("id with SQL characters is rejected", rejected("movie", dict(movie, id="1; DROP TABLE users;--")))
check("missing id is rejected", rejected("movie", dict(movie, id=None)))
check("empty title is rejected", rejected("movie", dict(movie, id=1, title="   ")))

tricky = dict(movie, id=777, title="Robert'); DROP TABLE favorites;--")
favorites.toggle(user_a, "movie", tricky)
conn = database.get_connection()
saved_title = conn.execute("SELECT title FROM favorites WHERE item_id = '777'").fetchone()
tables = conn.execute("SELECT name FROM sqlite_master WHERE name = 'favorites'").fetchall()
conn.close()
check("SQL text inside a title is saved as plain text", saved_title is not None and saved_title[0] == tricky["title"])
check("favorites table still exists after that title", len(tables) == 1)

favorites.toggle(user_a, "movie", dict(movie, id=888, title="A" * 900, rating=99, poster_path="/../../evil.jpg", overview="x" * 5000))
conn = database.get_connection()
row = conn.execute("SELECT title, rating, image, overview FROM favorites WHERE item_id = '888'").fetchone()
conn.close()
check("long title is cut to 200", len(row[0]) == 200)
check("rating is capped at 10", row[1] == 10)
check("bad poster path is not saved", row[2] is None)
check("long overview is cut to 1000", len(row[3]) == 1000)

# fill the list up to the limit
count = database.count_favorites(user_a)
for number in range(1000, 1000 + favorites.MAX_FAVORITES - count):
    favorites.toggle(user_a, "movie", dict(movie, id=number, title="Filler " + str(number)))
check("a user can save up to the limit", database.count_favorites(user_a) == favorites.MAX_FAVORITES)
check("one more than the limit is rejected", rejected("movie", dict(movie, id=5000, title="Too many")))

# deleting a user also deletes their favorites (FOREIGN KEY ... ON DELETE CASCADE)
favorites.toggle(user_b, "movie", movie)
conn = database.get_connection()
conn.execute("DELETE FROM users WHERE id = ?", (user_b,))
conn.commit()
left = conn.execute("SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_b,)).fetchone()[0]
conn.close()
check("favorites are deleted together with their user", left == 0)

print()
print("--- API client ---")


def raises(func, code):
    try:
        func()
    except api.ApiError as error:
        return error.code == code
    return False


check("unknown type is rejected", raises(lambda: api.search("evil", "x"), "input"))
check("poster path with ../ is rejected", raises(lambda: api.get_poster("/../../evil.jpg"), "input"))
check("poster path with another host is rejected", raises(lambda: api.get_poster("//evil.com/a.jpg"), "input"))
check("empty search returns nothing (no request sent)", api.search("movie", "   ") == [])
check("search text is cleaned", api.clean_query("  hello\x00 \n  world  ") == "hello world")

hostile = [
    {"title": "A" * 5000, "release_date": "<script>", "vote_average": "abc",
     "poster_path": "/../../evil.jpg", "id": "7; DROP TABLE", "overview": 123},
    "not a dict",
    None,
    {"title": "Fine\x00Title", "release_date": "2020-01-01", "vote_average": 99,
     "poster_path": "/abc12345.jpg", "id": 5},
]
cleaned = api.clean_results(hostile, "movie")
check("bad data from the internet does not crash the app", len(cleaned) == 2)
check("long titles are cut", len(cleaned[0]["title"]) <= 200)
check("bad poster path is removed", cleaned[0]["poster_path"] is None)
check("bad rating becomes 0 and big rating is capped at 10", cleaned[0]["rating"] == 0 and cleaned[1]["rating"] == 10)
check("control characters are removed from titles", "\x00" not in cleaned[1]["title"])
import re
check("no API key is written inside api.py", re.search(r"[0-9a-f]{32}", open("api.py").read()) is None)

print()
passed = sum(results)
print(str(passed) + " of " + str(len(results)) + " checks passed")
os.remove(database.DB_NAME)
