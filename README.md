# MediaHub

ITL313-18 SIA 2 Lab final term mini project - Media and Entertainment.
A desktop app with a secure login system and three features: Movies and TV Shows,
Music and Audio, and Video Games. Each feature uses its own API.

## Features
- Register and login (SQLite, salted PBKDF2 hashing, login attempt limit)
- Movies and TV shows (TMDB API) with a "Watch trailer" button (opens the YouTube trailer)
- Music (Apple iTunes Search API and Apple Music charts, no key needed)
- Games (RAWG API)
- Search, loading skeletons, smooth scrolling, clear messages when a title is not found or a service is down
- Click a card for a details popup, save titles with the heart button (one list per user)
- Layout adjusts to the window size

## Setup
1. Clone the repo
2. Create a virtual environment: python -m venv venv
3. Activate it: venv\Scripts\activate
4. Install packages: pip install -r requirements.txt
5. Copy .env.example, rename the copy to .env and put your keys inside
   (TMDB key from themoviedb.org, RAWG key from rawg.io/apidocs)
6. Run the app: python main.py

More details are in GUIDE.md.

## Files
- main.py - starts the app and switches between screens
- login.py - login and register screen
- home.py - home screen (search, grid, favorites view, loading and error states)
- details.py - the details popup (trailer or link button, favorite button)
- providers.py - the list of categories, one entry for each
- api.py - movies and TV (TMDB)
- music_api.py - music (Apple)
- games_api.py - games (RAWG)
- common.py - shared safe internet code, caching, address checks
- favorites.py - checks and saves favorites (one list per user)
- widgets.py - smooth scrolling frame and skeleton cards
- auth.py - password hashing, validation, login attempt limit
- database.py - SQLite code (all queries use ? placeholders)
- theme.py - shared colors
- security_test.py - security checks (run: python security_test.py)
- check_db.py - shows what is saved in users.db (run: python check_db.py)

## Security notes
- Passwords are never saved as plain text: PBKDF2-HMAC-SHA256 + random salt per user
- All SQL queries are parameterized, usernames only allow letters, numbers and underscore
- 5 wrong logins lock the username for 30 seconds, the lock is saved in the database
- Every favorites query needs the user id, so users cannot see or change each other's favorites
- API keys are only in the .env file, which is ignored by Git
- Pictures can only come from 3 allowed servers over https, and the browser only opens links from an allowed list
- Data from the internet is checked and cleaned before it is shown or saved

## Members
- Kenneth Floria
