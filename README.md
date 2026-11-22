# Movie App (MovieHub)

ITL313-18 SIA 2 Lab final term mini project.
A desktop app with a secure login system and a movie / TV show search using the TMDB API.

## Features
- Register and login (SQLite, salted PBKDF2 hashing, login attempt limit)
- Home screen with popular movies and TV shows, and search
- Loading skeletons, smooth scrolling, clear messages when a title is not found or the service is down
- Click a card to open a details popup (poster, rating, description)
- Favorites: save titles with the heart button, each user has their own list
- Layout adjusts to the window size

## Setup
1. Clone the repo
2. Create a virtual environment: python -m venv venv
3. Activate it: venv\Scripts\activate
4. Install packages: pip install -r requirements.txt
5. Make a copy of .env.example, rename it to .env, and put your TMDB API key inside
6. Run the app: python main.py

## Files
- main.py - starts the app and switches between screens
- login.py - login and register screen
- home.py - home screen (search, results grid, favorites view, loading and error states)
- details.py - the details popup
- favorites.py - checks and saves favorites (one list per user)
- widgets.py - smooth scrolling frame and skeleton cards
- auth.py - password hashing, validation, login attempt limit
- database.py - SQLite code (all queries use ? placeholders)
- api.py - TMDB requests with input checks and cleaning of the data we get back
- theme.py - shared colors
- security_test.py - security checks (run: python security_test.py)
- check_db.py - shows what is saved in users.db (run: python check_db.py)

## Security notes
- Passwords are never saved as plain text: PBKDF2-HMAC-SHA256 + random salt per user
- All SQL queries are parameterized, usernames only allow letters, numbers and underscore
- 5 wrong logins lock the username for 30 seconds, the lock is saved in the database
- Every favorites query needs the user id, so users cannot see or change each other's favorites
- The API key is only in the .env file, which is ignored by Git
- Data from the internet is checked and cleaned before it is shown or saved

## Members
- Kenneth Floria
