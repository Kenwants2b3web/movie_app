import os
import re

import requests
from dotenv import load_dotenv

# the key lives in the .env file, never write it inside the code
load_dotenv()
API_KEY = (os.getenv("TMDB_API_KEY") or "").strip()

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_URL = "https://image.tmdb.org/t/p/w342"

# poster paths from TMDB look like /abc123.jpg
POSTER_PATTERN = re.compile(r"/[A-Za-z0-9_-]+\.(jpg|png)")


class ApiError(Exception):
    pass


def check_kind(kind):
    if kind not in ("movie", "tv"):
        raise ApiError("Unknown type.")


def make_request(path, params=None):
    if API_KEY == "":
        raise ApiError("TMDB_API_KEY not found. Check your .env file.")

    params = dict(params or {})
    headers = {"accept": "application/json"}

    # long keys are the v4 token, short keys are the v3 key
    if len(API_KEY) > 40:
        headers["Authorization"] = "Bearer " + API_KEY
    else:
        params["api_key"] = API_KEY

    try:
        response = requests.get(
            BASE_URL + path, params=params, headers=headers, timeout=10
        )
    except requests.exceptions.RequestException:
        # not showing the real error because it can contain the key
        raise ApiError("Could not reach TMDB. Check your internet.") from None

    if response.status_code == 401:
        raise ApiError("TMDB rejected the API key. Check your .env file.")
    if response.status_code != 200:
        raise ApiError("TMDB error (" + str(response.status_code) + ").")

    return response.json()


def clean_results(items, kind):
    results = []
    for item in items[:20]:
        if kind == "movie":
            title = item.get("title")
            date = item.get("release_date")
        else:
            title = item.get("name")
            date = item.get("first_air_date")

        if date:
            year = date[:4]
        else:
            year = "N/A"

        rating = item.get("vote_average") or 0

        results.append({
            "id": item.get("id"),
            "title": title or "Untitled",
            "year": year,
            "rating": round(rating, 1),
            "poster_path": item.get("poster_path"),
            "overview": item.get("overview") or "",
        })
    return results


def search(kind, query):
    check_kind(kind)
    query = query.strip()[:100]
    if query == "":
        return []

    data = make_request(
        "/search/" + kind, {"query": query, "include_adult": "false"}
    )
    return clean_results(data.get("results", []), kind)


def get_popular(kind):
    check_kind(kind)
    data = make_request("/" + kind + "/popular")
    return clean_results(data.get("results", []), kind)


def get_poster(poster_path):
    # only download paths that look right, always from the TMDB image server
    if not poster_path or not POSTER_PATTERN.fullmatch(poster_path):
        raise ApiError("Bad poster path.")

    try:
        response = requests.get(IMAGE_URL + poster_path, timeout=10)
    except requests.exceptions.RequestException:
        raise ApiError("Could not download poster.") from None

    if response.status_code != 200:
        raise ApiError("Poster not found.")
    if not response.headers.get("Content-Type", "").startswith("image/"):
        raise ApiError("Poster is not an image.")
    if len(response.content) > 2000000:
        raise ApiError("Poster is too big.")

    return response.content


# quick terminal test: python api.py
if __name__ == "__main__":
    print("Testing TMDB search...")
    try:
        for movie in search("movie", "Avengers")[:5]:
            print(movie["title"], movie["year"], movie["rating"])
    except ApiError as error:
        print("Error:", error)
