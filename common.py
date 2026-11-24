# Things that the movie, music and game code all share:
# talking to the internet safely, caching, and checking addresses.
import re
import threading
import time
import webbrowser
from collections import OrderedDict
from urllib.parse import urlsplit

import requests

CACHE_SECONDS = 300
MAX_IMAGE_BYTES = 3000000

# pictures are only allowed to come from these servers
IMAGE_HOSTS = {"image.tmdb.org", "media.rawg.io"}
IMAGE_HOST_ENDINGS = (".mzstatic.com",)

# links that the app is allowed to open in the browser
LINK_HOSTS = {
    "www.youtube.com", "music.apple.com", "itunes.apple.com",
    "geo.music.apple.com", "rawg.io", "www.themoviedb.org",
}

results_cache = {}
image_cache = OrderedDict()
cache_lock = threading.Lock()

session = requests.Session()
session.headers.update({"User-Agent": "MediaHub-school-project/1.0"})


class ApiError(Exception):
    # code tells the screen what kind of problem it was:
    # "network", "key", "busy", "server", "input" or "empty"
    def __init__(self, message, code="server"):
        super().__init__(message)
        self.code = code


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


def get_json(url, params=None, headers=None, forbidden_code="key"):
    request_headers = {"accept": "application/json"}
    if headers:
        request_headers.update(headers)

    try:
        response = session.get(
            url, params=params, headers=request_headers,
            timeout=(5, 10), allow_redirects=False,
        )
    except requests.exceptions.RequestException:
        # not showing the real error because it can contain the API key
        raise ApiError("Could not reach the server.", "network") from None

    status = response.status_code
    if status == 401:
        raise ApiError("The server rejected the API key.", "key")
    if status == 403:
        raise ApiError("The server refused the request.", forbidden_code)
    if status == 429:
        raise ApiError("The server is busy right now.", "busy")
    if status != 200:
        raise ApiError("Server error (" + str(status) + ").", "server")

    try:
        data = response.json()
    except ValueError:
        raise ApiError("Unexpected reply from the server.", "server") from None

    if not isinstance(data, dict):
        raise ApiError("Unexpected reply from the server.", "server")
    return data


# ---------- cache ----------

def get_cached(key):
    with cache_lock:
        saved = results_cache.get(key)
        if saved is not None and time.time() - saved[0] < CACHE_SECONDS:
            return saved[1]
    return None


def save_cache(key, data):
    with cache_lock:
        if len(results_cache) > 80:
            results_cache.clear()
        results_cache[key] = (time.time(), data)


# ---------- addresses ----------

def check_url(url, hosts, endings=()):
    # True only for a clean https address on a server we allow
    if not isinstance(url, str) or len(url) > 600:
        return False
    if re.search(r"[\s\x00-\x1f\\]", url):
        return False

    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False

    if parts.scheme != "https":
        return False
    if parts.username is not None or parts.password is not None:
        return False
    if port not in (None, 443):
        return False

    host = parts.hostname
    if not host:
        return False
    if host in hosts:
        return True
    for ending in endings:
        if host.endswith(ending):
            return True
    return False


def is_image_url(url):
    return check_url(url, IMAGE_HOSTS, IMAGE_HOST_ENDINGS)


def is_safe_link(url):
    return check_url(url, LINK_HOSTS)


def open_link(url):
    # never opens anything that is not on the allowed list
    if not is_safe_link(url):
        return False
    webbrowser.open(url)
    return True


def get_image(url):
    if not is_image_url(url):
        raise ApiError("Bad image address.", "input")

    with cache_lock:
        if url in image_cache:
            image_cache.move_to_end(url)
            return image_cache[url]

    try:
        response = session.get(
            url, headers={"accept": "image/*"}, timeout=(5, 10),
            stream=True, allow_redirects=False,
        )
    except requests.exceptions.RequestException:
        raise ApiError("Could not download the picture.", "network") from None

    try:
        if response.status_code != 200:
            raise ApiError("Picture not found.", "server")
        content_type = response.headers.get("Content-Type", "")
        if content_type not in ("image/jpeg", "image/png", "image/webp"):
            raise ApiError("That is not a picture.", "server")

        # read in small pieces so a huge file can be stopped early
        data = bytearray()
        for chunk in response.iter_content(16384):
            data.extend(chunk)
            if len(data) > MAX_IMAGE_BYTES:
                raise ApiError("Picture is too big.", "server")
    except requests.exceptions.RequestException:
        raise ApiError("Could not download the picture.", "network") from None
    finally:
        response.close()

    data = bytes(data)
    with cache_lock:
        image_cache[url] = data
        if len(image_cache) > 120:
            image_cache.popitem(last=False)
    return data
