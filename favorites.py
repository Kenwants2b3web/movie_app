import re
import sqlite3

import api
import common
import database

ALLOWED_CATEGORIES = ("movie", "tv", "music", "game")
MAX_FAVORITES = 200
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,40}")

SAVE_ERROR = "Could not reach the favorites list. Please try again."


def make_key(category, item_id):
    return category + ":" + str(item_id)


def clean_item(category, item):
    # check everything before it goes into the database
    if category not in ALLOWED_CATEGORIES:
        raise ValueError("This type cannot be saved.")

    if item.get("id") is None:
        raise ValueError("This title cannot be saved.")
    item_id = str(item["id"])
    if not ID_PATTERN.fullmatch(item_id):
        raise ValueError("This title cannot be saved.")

    title = item.get("title")
    if not isinstance(title, str) or title.strip() == "":
        raise ValueError("This title cannot be saved.")
    title = title.strip()[:200]

    subtitle = common.clean_text(item.get("subtitle"), 100)

    year = item.get("year")
    if not isinstance(year, str) or len(year) > 10:
        year = "TBA"

    try:
        rating = float(item.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0
    rating = round(min(max(rating, 0), 10), 1)

    # pictures and links are only saved if they come from an allowed server
    image = item.get("image")
    if not common.is_image_url(image):
        image = None

    link = item.get("link")
    if not common.is_safe_link(link):
        link = None

    overview = item.get("overview")
    if not isinstance(overview, str):
        overview = ""
    overview = overview[:1000]

    return item_id, title, subtitle, year, rating, image, overview, link


def toggle(user_id, category, item):
    # returns True if the title is now saved, False if it was removed
    item_id, title, subtitle, year, rating, image, overview, link = clean_item(category, item)

    try:
        if database.remove_favorite(user_id, category, item_id):
            return False

        if database.count_favorites(user_id) >= MAX_FAVORITES:
            raise ValueError(
                "Favorites are full (" + str(MAX_FAVORITES) + " max). Remove one first."
            )

        database.add_favorite(
            user_id, category, item_id, title, subtitle, year, rating,
            image, overview, link,
        )
        return True
    except sqlite3.Error:
        raise ValueError(SAVE_ERROR) from None


def saved_keys(user_id):
    try:
        rows = database.get_favorite_keys(user_id)
    except sqlite3.Error:
        raise ValueError(SAVE_ERROR) from None
    return {make_key(row[0], row[1]) for row in rows}


def all_for(user_id):
    try:
        rows = database.get_favorites(user_id)
    except sqlite3.Error:
        raise ValueError(SAVE_ERROR) from None

    items = []
    for row in rows:
        image = row[6]

        # favorites saved in the first version only kept the poster path
        if isinstance(image, str) and api.POSTER_PATTERN.fullmatch(image):
            image = api.IMAGE_URL + image
        if not common.is_image_url(image):
            image = None

        link = row[8]
        if not common.is_safe_link(link):
            link = None

        items.append({
            "category": row[0],
            "id": row[1],
            "title": row[2],
            "subtitle": row[3] or "",
            "year": row[4] or "TBA",
            "rating": row[5] or 0,
            "image": image,
            "overview": row[7] or "",
            "link": link,
        })
    return items
