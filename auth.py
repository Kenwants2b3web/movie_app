import hashlib
import hmac
import os
import re
import sqlite3
import time

import database

MAX_ATTEMPTS = 5
LOCK_SECONDS = 30

# how many times PBKDF2 repeats, higher is slower for hackers
# old accounts used 100000 and get upgraded the next time they log in
ITERATIONS = 600000

USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_]{3,30}")

COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789",
    "qwerty123", "iloveyou", "admin123", "letmein123", "welcome123",
}

GENERIC_ERROR = "Invalid username or password."
DB_ERROR = "Something went wrong. Please try again."


def hash_password(password, salt, iterations=ITERATIONS):
    hashed = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, iterations
    )
    return hashed.hex()


def valid_username(username):
    return USERNAME_PATTERN.fullmatch(username) is not None


def seconds_locked(key):
    # how many seconds are left on the lock, 0 means not locked
    count, locked_until = database.get_attempts(key)
    left = locked_until - time.time()
    if left > 0:
        return int(left) + 1
    return 0


def record_failure(key):
    count, locked_until = database.get_attempts(key)
    now = time.time()

    # the old lock already ended, so start counting again
    if locked_until != 0 and locked_until <= now:
        count = 0
        locked_until = 0

    count += 1
    if count >= MAX_ATTEMPTS:
        locked_until = now + LOCK_SECONDS
    database.save_attempts(key, count, locked_until)


def register(username, password):
    if not valid_username(username):
        return False, "Username: 3-30 letters, numbers or underscore."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if len(password) > 128:
        return False, "Password is too long (max 128 characters)."
    if password.lower() in COMMON_PASSWORDS:
        return False, "That password is too common. Pick another one."
    if password.lower() == username.lower():
        return False, "Password cannot be the same as the username."

    try:
        # every user gets their own random salt
        salt = os.urandom(16)
        hashed = hash_password(password, salt)

        if database.add_user(username, hashed, salt.hex(), ITERATIONS):
            return True, "Account created! You can log in now."
        return False, "Username already exists."
    except sqlite3.Error:
        return False, DB_ERROR


def login(username, password):
    # returns (ok, message, username as saved in the database)
    try:
        # wrong format never reaches the database
        if not valid_username(username) or len(password) > 128:
            hash_password("x", b"\x00" * 16)
            return False, GENERIC_ERROR, None

        key = username.lower()

        left = seconds_locked(key)
        if left > 0:
            return False, "Too many tries. Wait " + str(left) + " seconds.", None

        user = database.get_user(username)

        # same message for wrong username or wrong password
        if user is None:
            # hash anyway so the response time looks the same
            hash_password(password, b"\x00" * 16)
            record_failure(key)
            return False, GENERIC_ERROR, None

        name, stored_hash, salt_hex, iterations = user
        new_hash = hash_password(password, bytes.fromhex(salt_hex), iterations)

        # compare_digest is safer than == for comparing hashes
        if hmac.compare_digest(stored_hash, new_hash):
            database.clear_attempts(key)
            if iterations < ITERATIONS:
                upgrade_hash(name, password)
            return True, "Login successful!", name

        record_failure(key)
        return False, GENERIC_ERROR, None
    except sqlite3.Error:
        return False, DB_ERROR, None


def upgrade_hash(name, password):
    # old account: save the password again with the stronger settings
    salt = os.urandom(16)
    hashed = hash_password(password, salt)
    database.update_password(name, hashed, salt.hex(), ITERATIONS)


# quick terminal test
if __name__ == "__main__":
    database.create_tables()
    print(register("testuser", "Str0ng-pass!"))
    print(login("testuser", "Str0ng-pass!"))
    print(login("testuser", "wrongpass"))
