# MediaHub Guide (Movies, Music and Games)

This guide covers adding Music and Games to your movie app, and everything you
need to run, test, demo and explain it.

## 1. What you are building

One app, three features, one login. This matches the lab guide:
"Media and Entertainment" has 3 features - Movies and TV Shows, Music and Audio,
Video Games. You are building all three inside ONE project.

| Feature | API | Key needed? |
|---|---|---|
| Movies and TV | TMDB | yes (you already have it) |
| Music | Apple iTunes Search API + Apple Music charts | no |
| Games | RAWG | yes (free) |

## 2. Why the movies do not "play"

TMDB is a movie DATABASE. It gives posters, ratings and descriptions, but it
has no video files, because the streaming rights belong to the studios and to
services like Netflix. No free API can give you full movies legally.

What the app does instead: the "Watch trailer" button asks TMDB for the
YouTube trailer of that title and opens it in your browser. If a title has no
trailer, you get a message saying so. If your instructor asks, this is the answer.

## 3. Get the RAWG key (5 minutes)

1. Go to rawg.io/apidocs and click "Get API Key". Make a free account.
2. Copy the key.
3. Open your .env file in VS Code and make it look like this (no quotes, no spaces around =):

        TMDB_API_KEY=your_tmdb_key
        RAWG_API_KEY=your_rawg_key

Never paste keys in chat, screenshots or GitHub. .env.example is only a template
and must keep the text "your_key_here".

RAWG rules: free for non-commercial projects (about 20,000 requests a month) and
the app must link back to RAWG. The app already shows "Game data provided by RAWG"
at the bottom, and clicking it opens rawg.io.

## 4. Install the files

1. Extract the zip.
2. Copy ALL the files into your movie_app folder and choose Replace.
   New files: common.py, music_api.py, games_api.py, providers.py, GUIDE.md.
   .env is NOT in the zip, so your keys stay safe.
3. Add RAWG_API_KEY to your .env (step 3).
4. In the VS Code terminal (with (venv) showing):

        python security_test.py
        python main.py

security_test.py must say "74 of 74 checks passed".
Your users and favorites are kept: the database updates itself on the first start.

## 5. First run checklist

- Login window says MediaHub.
- Top bar has Movies | TV | Music | Games.
- Movies: click a card, then "Watch trailer" (opens your browser).
- Music: shows Top Songs. Search an artist. Click a card, "Open in Apple Music".
- Games: shows Popular Games. Search a game. Click a card, "Open on RAWG".
- Click a heart in each category, then open Saved: all three appear together.
- Shrink the window: the columns change.

## 6. How the project is organized

    main.py        starts everything
    login.py       login / register screen
    home.py        the grid, search, skeleton, saved view
    details.py     the popup
    providers.py   list of categories  <- the only place that knows all of them
    api.py         movies and TV (TMDB)
    music_api.py   music (Apple)
    games_api.py   games (RAWG)
    common.py      safe internet code used by all three
    favorites.py   saving favorites safely
    auth.py        passwords, lock after 5 wrong tries
    database.py    SQLite

Every API file has the same two functions, search(query) and get_popular(), and
returns items in the same shape (id, title, subtitle, year, rating, image,
overview, link). That is why one screen can show all categories.

## 7. How to add another category later

1. Make a new file (for example books_api.py) with search() and get_popular().
2. Clean everything you get from the internet (copy the style of games_api.py).
3. Add one entry in providers.py and add the category name in favorites.py (ALLOWED_CATEGORIES).
4. If the pictures come from a new server, add it to IMAGE_HOSTS in common.py.

## 8. Security summary (for your instructor)

- Passwords: PBKDF2-SHA256, 600,000 rounds, random salt per user. Old accounts upgrade at next login.
- SQL injection: every query uses ? placeholders, usernames only allow letters, numbers and _.
- Brute force: 5 wrong tries lock the username for 30 seconds (saved in the database).
- Users cannot see each other's favorites (every query needs the user id).
- API keys: only in .env (ignored by Git). Error messages never include the key.
- Internet data: every field is checked and cut to a safe size before it is shown or saved.
- Pictures only from image.tmdb.org, media.rawg.io and *.mzstatic.com over https, with a size limit.
- The browser only opens links from a short allowed list (YouTube, Apple Music, RAWG, TMDB).
- Proof: python security_test.py (74 checks) and python check_db.py (shows hashes, no plain text).

Honest limits: this is a local desktop app. Someone who copies users.db can still
try to guess passwords offline, which is why the hashing is slow. Music
"popular" uses Apple's chart feed; if it is down the app shows a normal search instead.

## 9. Demo script (about 5 minutes)

1. Login with a wrong password 5 times: show the lock message.
2. Run python check_db.py: show hashes and salts, no plain text.
3. Run python security_test.py: show 74 of 74.
4. Log in. Show Movies, then TV, Music, Games (watch the skeleton loading).
5. Search something that does not exist: show the "not available" message.
6. Click a movie, press Watch trailer.
7. Save a movie, a song and a game, open Saved.
8. Resize the window, then log out.

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| Games says "API key problem" | Add RAWG_API_KEY to .env and restart the app |
| Movies says "API key problem" | Check TMDB_API_KEY in .env (no quotes, no spaces) |
| "You seem to be offline" | Check the internet, then press Try again |
| "Too many requests" | Wait a few seconds (Apple allows about 20 searches a minute) |
| Trailer says none available | Some titles have no trailer, try another |
| ModuleNotFoundError | Activate the venv, then pip install -r requirements.txt |
| venv\Scripts\activate is blocked | Use Command Prompt in the VS Code terminal |
| Git push rejected | git pull origin main, then git push |
