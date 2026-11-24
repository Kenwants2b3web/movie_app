# Security checks for MovieHub. Run it with:  python security_test.py
# It uses its own temporary database, so your real users.db is not touched.
import os
import tempfile
import time

import api
import auth
import common
import database
import favorites
import games_api
import music_api

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
movie = {"id": 603, "title": "The Matrix", "subtitle": "", "year": "1999", "rating": 8.2,
         "image": "https://image.tmdb.org/t/p/w342/abc12345.jpg", "overview": "A hacker learns the truth.",
         "link": "https://www.themoviedb.org/movie/603"}
song = {"id": 1440935467, "title": "Some Song", "subtitle": "Some Artist", "year": "2019", "rating": 0,
        "image": "https://is1-ssl.mzstatic.com/image/thumb/a/b/300x300bb.jpg", "overview": "Genre: Pop",
        "link": "https://music.apple.com/us/album/some-song/1440935467"}
game = {"id": 3498, "title": "Grand Theft Auto V", "subtitle": "Action", "year": "2013", "rating": 8.9,
        "image": "https://media.rawg.io/media/games/456/sample-cover.jpg",
        "overview": "Genres: Action", "link": "https://rawg.io/games/grand-theft-auto-v"}

check("a movie favorite can be saved", favorites.toggle(user_a, "movie", movie) is True)
check("saving again removes it (toggle)", favorites.toggle(user_a, "movie", movie) is False)
favorites.toggle(user_a, "movie", movie)
check("a song can be saved", favorites.toggle(user_a, "music", song) is True)
check("a game can be saved", favorites.toggle(user_a, "game", game) is True)
keys = favorites.saved_keys(user_a)
check("all three categories are listed for the owner", {"movie:603", "music:1440935467", "game:3498"} <= keys)
check("another user cannot see them", favorites.saved_keys(user_b) == set())

favorites.toggle(user_b, "movie", movie)
favorites.toggle(user_b, "movie", movie)
check("removing as user B does not remove user A's favorite", "movie:603" in favorites.saved_keys(user_a))

listed = {item["category"]: item for item in favorites.all_for(user_a)}
check("saved song keeps its artist and link", listed["music"]["subtitle"] == "Some Artist" and listed["music"]["link"] == song["link"])
check("saved game keeps its picture address", listed["game"]["image"] == game["image"])

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

favorites.toggle(user_a, "movie", dict(movie, id=888, title="A" * 900, rating=99,
                 image="https://evil.example.com/a.jpg", link="javascript:alert(1)", overview="x" * 5000))
conn = database.get_connection()
row = conn.execute("SELECT title, rating, image, overview, link FROM favorites WHERE item_id = '888'").fetchone()
conn.close()
check("long title is cut to 200", len(row[0]) == 200)
check("rating is capped at 10", row[1] == 10)
check("picture from another server is not saved", row[2] is None)
check("long overview is cut to 1000", len(row[3]) == 1000)
check("a javascript: link is not saved", row[4] is None)

# favorites saved by the first version only had a poster path
conn = database.get_connection()
conn.execute("INSERT INTO favorites (user_id, category, item_id, title, year, rating, image) VALUES (?, 'movie', '999', 'Old save', '2000', 7, '/oldposter1.jpg')", (user_a,))
conn.commit()
conn.close()
old = [item for item in favorites.all_for(user_a) if item["id"] == "999"][0]
check("old favorites get a full picture address", old["image"] == "https://image.tmdb.org/t/p/w342/oldposter1.jpg")

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
print("--- Addresses (pictures and links) ---")
check("picture from TMDB is allowed", common.is_image_url("https://image.tmdb.org/t/p/w342/abc.jpg"))
check("picture from Apple is allowed", common.is_image_url("https://is3-ssl.mzstatic.com/image/a/100x100bb.jpg"))
check("picture from RAWG is allowed", common.is_image_url("https://media.rawg.io/media/games/a.jpg"))
bad_images = [
    "http://image.tmdb.org/a.jpg",
    "https://image.tmdb.org.evil.com/a.jpg",
    "https://evilmzstatic.com/a.jpg",
    "https://evil.com/?image.tmdb.org",
    "https://user@image.tmdb.org/a.jpg",
    "https://evil.com\\@image.tmdb.org/a.jpg",
    "https://image.tmdb.org:8080/a.jpg",
    "https://image.tmdb.org./a.jpg",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "https://image.tmdb.org/a b.jpg",
    None,
    12345,
]
check("tricky picture addresses are all rejected", not any(common.is_image_url(u) for u in bad_images))
check("YouTube and Apple Music links are allowed", common.is_safe_link("https://www.youtube.com/watch?v=abcdefghijk") and common.is_safe_link("https://music.apple.com/us/album/x/1"))
check("other links are rejected", not any(common.is_safe_link(u) for u in ["http://www.youtube.com/watch?v=a", "https://youtube.com.evil.com/", "https://evil.com/", "ftp://rawg.io/"]))
check("opening a bad link is refused", common.open_link("https://evil.com/") is False)

def raises(func, code):
    try:
        func()
    except common.ApiError as error:
        return error.code == code
    return False

check("downloading a picture from another server is refused", raises(lambda: common.get_image("https://evil.com/a.jpg"), "input"))

print()
print("--- API clients ---")
check("unknown movie type is rejected", raises(lambda: api.search("evil", "x"), "input"))
check("trailer for a bad id is rejected", raises(lambda: api.get_trailer("movie", "1; DROP TABLE users"), "input"))
check("trailer for a bad type is rejected", raises(lambda: api.get_trailer("evil", 5), "input"))
check("empty search returns nothing (movies, music, games)", api.search("movie", "   ") == [] and music_api.search("  ") == [] and games_api.search("") == [])
check("search text is cleaned", common.clean_query("  hello\x00 \n  world  ") == "hello world")

hostile_movies = [
    {"title": "A" * 5000, "release_date": "<script>", "vote_average": "abc",
     "poster_path": "/../../evil.jpg", "id": "7; DROP TABLE", "overview": 123},
    "not a dict", None,
    {"title": "Fine\x00Title", "release_date": "2020-01-01", "vote_average": 99,
     "poster_path": "/abc12345.jpg", "id": 5},
]
cleaned = api.clean_results(hostile_movies, "movie")
check("bad movie data does not crash the app", len(cleaned) == 2)
check("long titles are cut", len(cleaned[0]["title"]) <= 200)
check("bad poster path is removed", cleaned[0]["image"] is None)
check("bad rating becomes 0 and big rating is capped at 10", cleaned[0]["rating"] == 0 and cleaned[1]["rating"] == 10)
check("control characters are removed from titles", "\x00" not in cleaned[1]["title"])
check("good poster becomes a full TMDB address", cleaned[1]["image"] == "https://image.tmdb.org/t/p/w342/abc12345.jpg")

hostile_songs = [
    {"trackId": "1; DROP", "trackName": "x"},
    {"trackId": 5, "trackName": "T" * 999, "artistName": None, "artworkUrl100": "https://evil.com/100x100bb.jpg",
     "trackViewUrl": "javascript:alert(1)", "releaseDate": "oops", "trackTimeMillis": "long"},
    {"trackId": 6, "trackName": "Good", "artistName": "Band", "artworkUrl100": "https://is1-ssl.mzstatic.com/a/100x100bb.jpg",
     "trackViewUrl": "https://music.apple.com/us/album/x/6", "releaseDate": "2021-03-04T08:00:00Z", "trackTimeMillis": 215000,
     "collectionName": "Album", "primaryGenreName": "Pop"},
    "junk", None, 42,
]
songs = music_api.clean_results(hostile_songs)
check("bad song data does not crash the app", len(songs) == 2)
check("song with a bad picture and link loses them", songs[0]["image"] is None and songs[0]["link"] is None)
check("song picture is upgraded to 300x300", songs[1]["image"] == "https://is1-ssl.mzstatic.com/a/300x300bb.jpg")
check("song details are put together", songs[1]["year"] == "2021" and "Length: 3:35" in songs[1]["overview"])

feed = music_api.clean_feed([
    {"id": "123", "name": "Chart Song", "artistName": "Star", "artworkUrl100": "https://is1-ssl.mzstatic.com/a/100x100bb.jpg",
     "url": "https://music.apple.com/us/song/x/123", "genres": [{"name": "Music"}, {"name": "Pop"}], "releaseDate": "2026-05-01"},
    {"id": "abc"}, {"id": 5}, "x",
])
check("chart feed items are cleaned", len(feed) == 1 and feed[0]["overview"] == "Genre: Pop")

hostile_games = [
    {"id": "x", "name": "bad id"},
    {"id": 1, "name": "G" * 999, "released": "<b>", "rating": "high", "background_image": "http://media.rawg.io/a.jpg",
     "slug": "../../etc/passwd", "genres": "nope", "platforms": [None, 5], "metacritic": 9999},
    {"id": 2, "name": "Good Game", "released": "2020-01-01", "rating": 4.5, "background_image": "https://media.rawg.io/media/a.jpg",
     "slug": "good-game", "genres": [{"name": "Action"}, {"name": "RPG"}, {"name": "Indie"}],
     "platforms": [{"platform": {"name": "PC"}}, {"platform": {"name": "PlayStation 5"}}], "metacritic": 88},
    7, None,
]
games = games_api.clean_results(hostile_games)
check("bad game data does not crash the app", len(games) == 2)
check("game with bad picture, slug and rating is cleaned", games[0]["image"] is None and games[0]["link"] is None and games[0]["rating"] == 0)
check("game rating changes from 0-5 to 0-10", games[1]["rating"] == 9.0)
check("game details are put together", games[1]["subtitle"] == "Action, RPG" and "Platforms: PC, PlayStation 5" in games[1]["overview"] and "Metacritic score: 88" in games[1]["overview"])
check("game link is built from a safe slug", games[1]["link"] == "https://rawg.io/games/good-game")

import re
source_files = ["api.py", "games_api.py", "music_api.py", "common.py", "providers.py"]
check("no API key is written inside the code files", not any(re.search(r"[0-9a-f]{32}", open(f).read()) for f in source_files))

print()
passed = sum(results)
print(str(passed) + " of " + str(len(results)) + " checks passed")
os.remove(database.DB_NAME)
