# Video games (RAWG, free key needed)
import os
import re

from dotenv import load_dotenv

import common
from common import ApiError, clean_text, clean_query

load_dotenv()
API_KEY = (os.getenv("RAWG_API_KEY") or "").strip()

BASE_URL = "https://api.rawg.io/api"
SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,100}")


def is_configured():
    return API_KEY != ""


def make_request(params):
    if API_KEY == "":
        raise ApiError("RAWG_API_KEY not found. Check your .env file.", "key")

    params = dict(params)
    params["key"] = API_KEY
    return common.get_json(BASE_URL + "/games", params)


def names_from(items, key, limit):
    # genres and platforms come as small lists of dictionaries
    names = []
    if isinstance(items, list):
        for item in items[:limit]:
            if key == "platform" and isinstance(item, dict):
                item = item.get("platform")
            if isinstance(item, dict):
                name = clean_text(item.get("name"), 40)
                if name:
                    names.append(name)
    return names


def clean_results(items):
    if not isinstance(items, list):
        return []

    results = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue

        game_id = item.get("id")
        if not isinstance(game_id, int) or isinstance(game_id, bool):
            continue

        released = item.get("released")
        if isinstance(released, str) and re.fullmatch(r"\d{4}", released[:4]):
            year = released[:4]
        else:
            year = "TBA"

        # RAWG rates from 0 to 5, the app shows 0 to 10 like the movies
        try:
            rating = float(item.get("rating") or 0) * 2
        except (TypeError, ValueError):
            rating = 0
        rating = round(min(max(rating, 0), 10), 1)

        genres = names_from(item.get("genres"), "genre", 4)
        platforms = names_from(item.get("platforms"), "platform", 5)

        lines = []
        if genres:
            lines.append("Genres: " + ", ".join(genres))
        if platforms:
            lines.append("Platforms: " + ", ".join(platforms))
        metacritic = item.get("metacritic")
        if isinstance(metacritic, int) and not isinstance(metacritic, bool) and 0 < metacritic <= 100:
            lines.append("Metacritic score: " + str(metacritic))

        image = item.get("background_image")
        if not common.is_image_url(image):
            image = None

        link = None
        slug = item.get("slug")
        if isinstance(slug, str) and SLUG_PATTERN.fullmatch(slug):
            link = "https://rawg.io/games/" + slug

        results.append({
            "id": game_id,
            "title": clean_text(item.get("name")) or "Untitled",
            "subtitle": ", ".join(genres[:2]),
            "year": year,
            "rating": rating,
            "image": image,
            "overview": "\n".join(lines),
            "link": link,
        })
    return results


def search(query):
    query = clean_query(query)
    if query == "":
        return []

    key = ("rawg-search", query.lower())
    cached = common.get_cached(key)
    if cached is not None:
        return cached

    data = make_request({"search": query, "page_size": "20"})
    results = clean_results(data.get("results"))
    common.save_cache(key, results)
    return results


def get_popular():
    key = ("rawg-popular",)
    cached = common.get_cached(key)
    if cached is not None:
        return cached

    data = make_request({"ordering": "-added", "page_size": "20"})
    results = clean_results(data.get("results"))
    common.save_cache(key, results)
    return results
