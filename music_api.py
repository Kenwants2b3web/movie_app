# Music (Apple iTunes Search API and the Apple Music charts, no key needed)
import re

import common
from common import ApiError, clean_text, clean_query

SEARCH_URL = "https://itunes.apple.com/search"

# the chart feed has two addresses, we try the second one if the first fails
FEED_URLS = [
    "https://rss.marketingtools.apple.com/api/v2/us/music/most-played/20/songs.json",
    "https://rss.applemarketingtools.com/api/v2/us/music/most-played/20/songs.json",
]

# only used if the chart feed is down
FALLBACK_SEARCH = "top hits"


def is_configured():
    return True  # no key needed


def bigger_artwork(url):
    # the search gives a 100x100 picture, the same server can give 300x300
    if isinstance(url, str):
        url = url.replace("100x100bb", "300x300bb")
    if common.is_image_url(url):
        return url
    return None


def get_year(date):
    if isinstance(date, str) and re.fullmatch(r"\d{4}", date[:4]):
        return date[:4]
    return "TBA"


def clean_results(items):
    # items from the search
    if not isinstance(items, list):
        return []

    results = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue

        track_id = item.get("trackId")
        if not isinstance(track_id, int) or isinstance(track_id, bool):
            continue

        lines = []
        album = clean_text(item.get("collectionName"), 100)
        if album:
            lines.append("Album: " + album)
        genre = clean_text(item.get("primaryGenreName"), 50)
        if genre:
            lines.append("Genre: " + genre)
        millis = item.get("trackTimeMillis")
        if isinstance(millis, int) and not isinstance(millis, bool) and millis > 0:
            seconds = millis // 1000
            lines.append("Length: " + str(seconds // 60) + ":" + str(seconds % 60).zfill(2))

        link = item.get("trackViewUrl")
        if not common.is_safe_link(link):
            link = None

        results.append({
            "id": track_id,
            "title": clean_text(item.get("trackName")) or "Untitled",
            "subtitle": clean_text(item.get("artistName"), 100),
            "year": get_year(item.get("releaseDate")),
            "rating": 0,
            "image": bigger_artwork(item.get("artworkUrl100")),
            "overview": "\n".join(lines),
            "link": link,
        })
    return results


def clean_feed(entries):
    # entries from the chart feed
    if not isinstance(entries, list):
        return []

    results = []
    for entry in entries[:20]:
        if not isinstance(entry, dict):
            continue

        song_id = entry.get("id")
        if not isinstance(song_id, str) or not re.fullmatch(r"\d{1,20}", song_id):
            continue

        names = []
        genres = entry.get("genres")
        if isinstance(genres, list):
            for genre in genres[:3]:
                if isinstance(genre, dict):
                    name = clean_text(genre.get("name"), 40)
                    if name and name != "Music":
                        names.append(name)
        overview = ""
        if names:
            overview = "Genre: " + ", ".join(names)

        link = entry.get("url")
        if not common.is_safe_link(link):
            link = None

        results.append({
            "id": int(song_id),
            "title": clean_text(entry.get("name")) or "Untitled",
            "subtitle": clean_text(entry.get("artistName"), 100),
            "year": get_year(entry.get("releaseDate")),
            "rating": 0,
            "image": bigger_artwork(entry.get("artworkUrl100")),
            "overview": overview,
            "link": link,
        })
    return results


def search(query):
    query = clean_query(query)
    if query == "":
        return []

    key = ("itunes-search", query.lower())
    cached = common.get_cached(key)
    if cached is not None:
        return cached

    # Apple answers with 403 when there are too many requests
    data = common.get_json(
        SEARCH_URL,
        {"term": query, "media": "music", "entity": "song", "limit": "20"},
        forbidden_code="busy",
    )
    results = clean_results(data.get("results"))
    common.save_cache(key, results)
    return results


def get_popular():
    key = ("itunes-popular",)
    cached = common.get_cached(key)
    if cached is not None:
        return cached

    for url in FEED_URLS:
        try:
            data = common.get_json(url, forbidden_code="busy")
        except ApiError as error:
            if error.code == "network":
                raise  # no internet, the other address will not work either
            continue

        feed = data.get("feed")
        if isinstance(feed, dict):
            results = clean_feed(feed.get("results"))
            if results:
                common.save_cache(key, results)
                return results

    # the chart is not available, show a normal search instead
    return search(FALLBACK_SEARCH)
