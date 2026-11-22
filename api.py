import os
import re
import threading
import time
from collections import OrderedDict

import requests
from dotenv import load_dotenv

# the key lives in the .env file, never write it inside the code
load_dotenv()
API_KEY = (os.getenv("TMDB_API_KEY") or "").strip()

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_URL = "https://image.tmdb.org/t/p/w342"

# poster paths from TMDB look like /abc123.jpg
POSTER_PATTERN = re.compile(r"/[A-Za-z0-9_-]{5,60}\.(jpg|png)")
MAX_POSTER_BYTES = 2000000

CACHE_SECONDS = 300
results_cache = {}
poster_cache = OrderedDict()
cache_lock = threading.Lock()

session = requests.Session()
session.headers.update({
    "accept": "application/json",
    "User-Agent": "MovieHub-school-project/1.0",
})


class ApiError(Exception):
    # code tells the screen what kind of problem it was:
    # "network", "key", "busy", "server" or "input"
    def __init__(self, message, code="server"):
        super().__init__(message)
        self.code = code


def is_configured():
    return API_KEY != ""


def check_kind(kind):
    if kind not in ("movie", "tv"):
        raise ApiError("Unknown type.", "input")


def clean_text(value, limit=200):
    # only keep normal text, remove control characters
    if not isinstance(value, str):
        return ""
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    return value.strip()[:limit]


def clean_query(query):
    if not isinstance(query, str):
        return ""
    return " ".join(clean_text(query, 300).split())[:100]


def make_request(path, params=None):
    if API_KEY == "":
        raise ApiError("TMDB_API_KEY not found. Check your .env file.", "key")

    params = dict(params or {})
    headers = {}

    # long keys are the v4 token, short keys are the v3 key
    if len(API_KEY) > 40:
        headers["Authorization"] = "Bearer " + API_KEY
    else:
        params["api_key"] = API_KEY

    try:
        response = session.get(
            BASE_URL + path, params=params, headers=headers,
            timeout=(5, 10), allow_redirects=False,
        )
    except requests.exceptions.RequestException:
        # not showing the real error because it can contain the key
        raise ApiError("Could not reach TMDB.", "network") from None

    if response.status_code == 401:
        raise ApiError("TMDB rejected the API key.", "key")
    if response.status_code == 429:
        raise ApiError("TMDB is busy right now.", "busy")
    if response.status_code != 200:
        raise ApiError("TMDB error (" + str(response.status_code) + ").", "server")

    try:
        data = response.json()
    except ValueError:
        raise ApiError("Unexpected reply from TMDB.", "server") from None

    if not isinstance(data, dict):
        raise ApiError("Unexpected reply from TMDB.", "server")
    return data


def clean_results(items, kind):
    # never trust the data from the internet, check every field
    if not isinstance(items, list):
        return []

    results = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue

        if kind == "movie":
            title = clean_text(item.get("title"))
            date = item.get("release_date")
        else:
            title = clean_text(item.get("name"))
            date = item.get("first_air_date")

        if isinstance(date, str) and re.fullmatch(r"\d{4}", date[:4]):
            year = date[:4]
        else:
            year = "TBA"

        try:
            rating = float(item.get("vote_average") or 0)
        except (TypeError, ValueError):
            rating = 0
        rating = round(min(max(rating, 0), 10), 1)

        poster = item.get("poster_path")
        if not (isinstance(poster, str) and POSTER_PATTERN.fullmatch(poster)):
            poster = None

        movie_id = item.get("id")
        if not isinstance(movie_id, int):
            movie_id = None

        results.append({
            "id": movie_id,
            "title": title or "Untitled",
            "year": year,
            "rating": rating,
            "poster_path": poster,
            "overview": clean_text(item.get("overview"), 1000),
        })
    return results


def get_cached(key):
    with cache_lock:
        saved = results_cache.get(key)
        if saved is not None and time.time() - saved[0] < CACHE_SECONDS:
            return saved[1]
    return None


def save_cache(key, data):
    with cache_lock:
        if len(results_cache) > 50:
            results_cache.clear()
        results_cache[key] = (time.time(), data)


def search(kind, query):
    check_kind(kind)
    query = clean_query(query)
    if query == "":
        return []

    key = ("search", kind, query.lower())
    cached = get_cached(key)
    if cached is not None:
        return cached

    data = make_request(
        "/search/" + kind, {"query": query, "include_adult": "false"}
    )
    results = clean_results(data.get("results"), kind)
    save_cache(key, results)
    return results


def get_popular(kind):
    check_kind(kind)

    key = ("popular", kind)
    cached = get_cached(key)
    if cached is not None:
        return cached

    data = make_request("/" + kind + "/popular")
    results = clean_results(data.get("results"), kind)
    save_cache(key, results)
    return results


def get_poster(poster_path):
    # only download paths that look right, always from the TMDB image server
    if not isinstance(poster_path, str) or not POSTER_PATTERN.fullmatch(poster_path):
        raise ApiError("Bad poster path.", "input")

    with cache_lock:
        if poster_path in poster_cache:
            poster_cache.move_to_end(poster_path)
            return poster_cache[poster_path]

    try:
        response = session.get(
            IMAGE_URL + poster_path, timeout=(5, 10), stream=True,
            allow_redirects=False,
        )
    except requests.exceptions.RequestException:
        raise ApiError("Could not download poster.", "network") from None

    try:
        if response.status_code != 200:
            raise ApiError("Poster not found.", "server")
        if response.headers.get("Content-Type", "") not in ("image/jpeg", "image/png"):
            raise ApiError("Poster is not an image.", "server")

        # read in small pieces so a huge file can be stopped early
        data = bytearray()
        for chunk in response.iter_content(16384):
            data.extend(chunk)
            if len(data) > MAX_POSTER_BYTES:
                raise ApiError("Poster is too big.", "server")
    except requests.exceptions.RequestException:
        raise ApiError("Could not download poster.", "network") from None
    finally:
        response.close()

    data = bytes(data)
    with cache_lock:
        poster_cache[poster_path] = data
        if len(poster_cache) > 100:
            poster_cache.popitem(last=False)
    return data


# quick terminal test: python api.py
if __name__ == "__main__":
    print("Testing TMDB search...")
    try:
        for movie in search("movie", "Avengers")[:5]:
            print(movie["title"], movie["year"], movie["rating"])
    except ApiError as error:
        print("Error:", error)
