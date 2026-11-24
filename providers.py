# One place that knows every category.
# To add a new category: write a small api file with search() and get_popular(),
# then add one entry here. The screens do not need to change.
import api
import games_api
import music_api

ALL_ATTRIBUTION = (
    "Data from TMDB, Apple Music and RAWG. This product uses the TMDB API "
    "but is not endorsed or certified by TMDB."
)

PROVIDERS = {
    "movie": {
        "label": "Movies",
        "popular_title": "Popular Movies",
        "placeholder": "Search movies",
        "image_size": (150, 225),
        "search": lambda query: api.search("movie", query),
        "popular": lambda: api.get_popular("movie"),
        "trailer": lambda item_id: api.get_trailer("movie", item_id),
        "link_text": None,
        "attribution": "This product uses the TMDB API but is not endorsed or certified by TMDB.",
        "attribution_url": "https://www.themoviedb.org",
    },
    "tv": {
        "label": "TV",
        "popular_title": "Popular TV Shows",
        "placeholder": "Search TV shows",
        "image_size": (150, 225),
        "search": lambda query: api.search("tv", query),
        "popular": lambda: api.get_popular("tv"),
        "trailer": lambda item_id: api.get_trailer("tv", item_id),
        "link_text": None,
        "attribution": "This product uses the TMDB API but is not endorsed or certified by TMDB.",
        "attribution_url": "https://www.themoviedb.org",
    },
    "music": {
        "label": "Music",
        "popular_title": "Top Songs",
        "placeholder": "Search songs or artists",
        "image_size": (150, 150),
        "search": lambda query: music_api.search(query),
        "popular": lambda: music_api.get_popular(),
        "trailer": None,
        "link_text": "Open in Apple Music",
        "attribution": "Music data from the Apple iTunes Search API and Apple Music charts.",
        "attribution_url": None,
    },
    "game": {
        "label": "Games",
        "popular_title": "Popular Games",
        "placeholder": "Search games",
        "image_size": (150, 100),
        "search": lambda query: games_api.search(query),
        "popular": lambda: games_api.get_popular(),
        "trailer": None,
        "link_text": "Open on RAWG",
        "attribution": "Game data provided by RAWG (rawg.io).",
        "attribution_url": "https://rawg.io",
    },
}

# the order of the buttons on the screen, and label -> category
ORDER = ["movie", "tv", "music", "game"]
LABELS = {}
for category in ORDER:
    LABELS[PROVIDERS[category]["label"]] = category
