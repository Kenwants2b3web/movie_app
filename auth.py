import hashlib
import hmac
import os

import database


def hash_password(password, salt):
    # PBKDF2 with 100000 rounds so brute force is slower
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return hashed.hex()


def register(username, password):
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    # every user gets their own random salt
    salt = os.urandom(16)
    hashed = hash_password(password, salt)

    if database.add_user(username, hashed, salt.hex()):
        return True, "Account created! You can log in now."
    return False, "Username already exists."


def login(username, password):
    user = database.get_user(username)

    # same message for wrong username or wrong password
    if user is None:
        return False, "Invalid username or password."

    stored_hash, salt_hex = user
    new_hash = hash_password(password, bytes.fromhex(salt_hex))

    # compare_digest is safer than == for comparing hashes
    if hmac.compare_digest(stored_hash, new_hash):
        return True, "Login successful!"
    return False, "Invalid username or password."


# quick terminal test
if __name__ == "__main__":
    database.create_tables()
    print(register("testuser", "password123"))
    print(login("testuser", "password123"))
    print(login("testuser", "wrongpass"))
