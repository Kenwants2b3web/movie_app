# Movies and TV shows (TMDB)
import os
import re

from dotenv import load_dotenv

import common
from common import ApiError, clean_text, clean_query

# the key lives in the .env file, never write it inside the code
load_dotenv()
API_KEY = (os.getenv("TMDB_API_KEY") or "").strip()

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_URL = "https://image.tmdb.org/t/p/w342"

# poster paths from TMDB look like /abc123.jpg
POSTER_PATTERN = re.compile(r"/[A-Za-z0-9_-]{5,60}\.(jpg|png)")
VIDEO_KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]{11}")


def is_configured():
    return API_KEY != ""


def check_kind(kind):
    if kind not in ("movie", "tv"):
        raise ApiError("Unknown type.", "input")


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

    return common.get_json(BASE_URL + path, params, headers)


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
        if isinstance(poster, str) and POSTER_PATTERN.fullmatch(poster):
            image = IMAGE_URL + poster
        else:
            image = None

        movie_id = item.get("id")
        if not isinstance(movie_id, int) or isinstance(movie_id, bool):
            movie_id = None

        link = None
        if movie_id is not None:
            link = "https://www.themoviedb.org/" + kind + "/" + str(movie_id)

        results.append({
            "id": movie_id,
            "title": title or "Untitled",
            "subtitle": "",
            "year": year,
            "rating": rating,
            "image": image,
            "overview": clean_text(item.get("overview"), 1000),
            "link": link,
        })
    return results


def search(kind, query):
    check_kind(kind)
    query = clean_query(query)
    if query == "":
        return []

    key = ("tmdb-search", kind, query.lower())
    cached = common.get_cached(key)
    if cached is not None:
        return cached

    data = make_request(
        "/search/" + kind, {"query": query, "include_adult": "false"}
    )
    results = clean_results(data.get("results"), kind)
    common.save_cache(key, results)
    return results


def get_popular(kind):
    check_kind(kind)

    key = ("tmdb-popular", kind)
    cached = common.get_cached(key)
    if cached is not None:
        return cached

    data = make_request("/" + kind + "/popular")
    results = clean_results(data.get("results"), kind)
    common.save_cache(key, results)
    return results


def get_trailer(kind, item_id):
    # TMDB has no movie files (streaming rights belong to the studios),
    # but it knows the YouTube trailer. We only return the YouTube address.
    check_kind(kind)
    item_id = str(item_id)
    if not item_id.isdigit() or len(item_id) > 10:
        raise ApiError("This title has no trailer.", "input")

    key = ("tmdb-trailer", kind, item_id)
    cached = common.get_cached(key)
    if cached is not None:
        return cached

    data = make_request("/" + kind + "/" + item_id + "/videos")
    videos = data.get("results")
    if not isinstance(videos, list):
        videos = []

    best = None
    for video in videos:
        if not isinstance(video, dict) or video.get("site") != "YouTube":
            continue
        video_key = video.get("key")
        if not (isinstance(video_key, str) and VIDEO_KEY_PATTERN.fullmatch(video_key)):
            continue

        score = 0
        if video.get("type") == "Trailer":
            score += 2
        elif video.get("type") == "Teaser":
            score += 1
        else:
            continue
        if video.get("official") is True:
            score += 1

        if best is None or score > best[0]:
            best = (score, video_key)

    if best is None:
        raise ApiError("No trailer is available for this title yet.", "empty")

    url = "https://www.youtube.com/watch?v=" + best[1]
    common.save_cache(key, url)
    return url


# quick terminal test: python api.py
if __name__ == "__main__":
    print("Testing TMDB search...")
    try:
        for movie in search("movie", "Avengers")[:5]:
            print(movie["title"], movie["year"], movie["rating"])
    except ApiError as error:
        print("Error:", error)
