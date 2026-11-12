import hashlib
import hmac
import os
import re
import time

import database

MAX_ATTEMPTS = 5
LOCK_SECONDS = 30

# username -> [failed tries, time when the lock ends]
failed_logins = {}


def hash_password(password, salt):
    # PBKDF2 with 100000 rounds so brute force is slower
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return hashed.hex()


def seconds_locked(username):
    # how many seconds are left on the lock, 0 means not locked
    info = failed_logins.get(username)
    if info is None:
        return 0
    left = info[1] - time.time()
    if left > 0:
        return int(left) + 1
    return 0


def record_failure(username):
    info = failed_logins.get(username, [0, 0])

    # the old lock already ended, so start counting again
    if info[1] != 0 and info[1] <= time.time():
        info = [0, 0]

    info[0] += 1
    if info[0] >= MAX_ATTEMPTS:
        info[1] = time.time() + LOCK_SECONDS
    failed_logins[username] = info


def register(username, password):
    if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
        return False, "Username: 3-30 letters, numbers or underscore."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if len(password) > 128:
        return False, "Password is too long (max 128 characters)."

    # every user gets their own random salt
    salt = os.urandom(16)
    hashed = hash_password(password, salt)

    if database.add_user(username, hashed, salt.hex()):
        return True, "Account created! You can log in now."
    return False, "Username already exists."


def login(username, password):
    left = seconds_locked(username)
    if left > 0:
        return False, "Too many tries. Wait " + str(left) + " seconds."

    user = database.get_user(username)

    # same message for wrong username or wrong password
    if user is None:
        # hash anyway so the response time looks the same
        hash_password(password, b"\x00" * 16)
        record_failure(username)
        return False, "Invalid username or password."

    stored_hash, salt_hex = user
    new_hash = hash_password(password, bytes.fromhex(salt_hex))

    # compare_digest is safer than == for comparing hashes
    if hmac.compare_digest(stored_hash, new_hash):
        failed_logins.pop(username, None)
        return True, "Login successful!"

    record_failure(username)
    return False, "Invalid username or password."


# quick terminal test
if __name__ == "__main__":
    database.create_tables()
    print(register("testuser", "password123"))
    print(login("testuser", "password123"))
    print(login("testuser", "wrongpass"))
