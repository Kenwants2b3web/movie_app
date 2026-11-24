import io
import math
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
from PIL import Image, ImageOps

import common
import favorites
import providers
from details import DetailsWindow, CATEGORY_NAMES
from theme import (BG, FIELD, CARD, CARD_HOVER, TOPBAR, RED, RED_HOVER, GRAY,
                   ERROR, HEART, SKELETON_DARK, SKELETON_LIGHT)
from widgets import SmoothScrollFrame, SkeletonCard, blend

# pictures are small, so a huge picture is not a real cover
Image.MAX_IMAGE_PIXELS = 12000000

MAX_COLUMNS = 8
SLOT_WIDTH = 196        # card width plus the space around it
SKELETON_COUNT = 10
SEARCH_COOLDOWN = 0.4   # seconds between searches


# words used in the "nothing saved" messages
PLURAL_NAMES = {"movie": "movies", "tv": "TV shows", "music": "songs", "game": "games"}
SINGLE_NAMES = {"movie": "movie", "tv": "TV show", "music": "song", "game": "game"}


def card_text(item):
    # the small text under the title: artist or genres, year, rating
    lines = []
    subtitle = item.get("subtitle") or ""
    if subtitle:
        if len(subtitle) > 24:
            subtitle = subtitle[:24] + "..."
        lines.append(subtitle)

    info = item["year"]
    if item["rating"] > 0:
        info = info + "   \u2605 " + str(item["rating"])
    elif item["category"] != "music":
        info = info + "   Not rated yet"
    lines.append(info)
    return "\n".join(lines)


class HomeFrame(ctk.CTkFrame):
    def __init__(self, master, user_id, username, on_logout):
        super().__init__(master, corner_radius=0, fg_color=BG)
        self.user_id = user_id
        self.username = username
        self.on_logout = on_logout

        self.kind = "movie"          # movie, tv, music or game (the switch)
        self.result_kind = "movie"   # the type of the results on the screen
        self.view = "browse"         # "browse" or "favorites"
        self.last_query = ""         # empty means show the popular list
        self.search_id = 0           # used to ignore old results
        self.last_search_time = 0

        self.columns = 5
        self.items = []              # cards (or skeleton cards) for the grid
        self.shown = 0               # how many of them are visible
        self.skeleton_cards = []
        self.poster_labels = {}
        self.poster_images = {}      # kept so the popup can show the picture
        self.card_sizes = {}
        self.hearts = {}             # key -> heart button
        self.cards_by_key = {}       # key -> card
        self.saved_keys = set()      # keys of the titles this user saved
        self.details = None          # the popup window, if one is open
        self.footer_url = None
        self.pulse_phase = 0

        self.fav_category = None     # which favorites tab is open (None = All)
        self.fav_label_map: dict[str, str | None] = {}   # tab label -> category (None = All)
        self.fav_values = []         # the labels now on the tabs

        # timers, so they can all be stopped when leaving this screen
        self.jobs = {}

        # background threads put their results here, the GUI reads them
        self.queue = queue.Queue()
        self.pool = ThreadPoolExecutor(max_workers=5)

        window = self.winfo_toplevel()
        self.scale = ctk.ScalingTracker.get_window_scaling(window)

        self.build_top_bar()
        self.build_content()

        # recalculate the columns when the window size changes
        self.bind("<Configure>", self.on_resize)

        self.search_entry.focus()
        self.check_queue()
        self.load_results()

    # ---------- timers ----------

    def schedule(self, name, delay, func):
        self.cancel(name)
        self.jobs[name] = self.after(delay, func)

    def cancel(self, name):
        job = self.jobs.pop(name, None)
        if job is not None:
            self.after_cancel(job)

    # ---------- screen parts ----------

    def build_top_bar(self):
        bar = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color=TOPBAR)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        ctk.CTkLabel(
            bar, text="MediaHub", font=("Segoe UI", 24, "bold"),
            text_color=RED,
        ).pack(side="left", padx=(25, 15))

        ctk.CTkButton(
            bar, text="Logout", width=80, height=34, fg_color="transparent",
            border_width=1, hover_color=FIELD, command=self.on_logout,
        ).pack(side="right", padx=(10, 25))

        # long usernames get cut so the top bar does not break
        name = self.username
        if len(name) > 12:
            name = name[:12] + "..."
        ctk.CTkLabel(
            bar, text="Hi, " + name, font=("Segoe UI", 13),
            text_color=GRAY,
        ).pack(side="right")

        self.fav_button = ctk.CTkButton(
            bar, text="\u2665  Saved", width=95, height=34,
            fg_color="transparent", border_width=1, hover_color=FIELD,
            command=self.toggle_favorites_view,
        )
        self.fav_button.pack(side="right", padx=(0, 15))

        self.type_switch = ctk.CTkSegmentedButton(
            bar, values=list(providers.LABELS), command=self.change_type,
            fg_color=FIELD, selected_color=RED,
            selected_hover_color=RED_HOVER, unselected_color=FIELD,
            unselected_hover_color="#3a3a3a",
        )
        self.type_switch.set("Movies")
        self.type_switch.pack(side="right", padx=(0, 15))

        self.search_button = ctk.CTkButton(
            bar, text="Search", width=80, height=40, fg_color=RED,
            hover_color=RED_HOVER, font=("Segoe UI", 13, "bold"),
            command=self.do_search,
        )
        self.search_button.pack(side="right", padx=(8, 15))

        # the search box takes all the space that is left
        self.search_entry = ctk.CTkEntry(
            bar, placeholder_text="Search movies", width=150,
            height=40, fg_color=FIELD, border_width=0,
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda event: self.do_search())

    def build_content(self):
        self.heading = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 22, "bold"), anchor="w"
        )
        self.heading.pack(fill="x", padx=30, pady=(18, 0))

        self.status = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 13), text_color=GRAY,
            anchor="w",
        )
        self.status.pack(fill="x", padx=30, pady=(2, 5))

        # the credit line for the data source (the sources ask for this)
        self.footer = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 11), text_color=GRAY, anchor="w",
        )
        self.footer.pack(side="bottom", fill="x", padx=30, pady=(0, 8))
        self.footer.bind("<Button-1>", self.open_footer_link)

        # category tabs, only shown in the Saved view
        # (they live in their own small frame, so there is a fixed place for them)
        self.filter_holder = ctk.CTkFrame(self, height=0, fg_color="transparent")
        self.filter_holder.pack(fill="x")
        self.fav_filter = ctk.CTkSegmentedButton(
            self.filter_holder, values=["All"], command=self.change_fav_filter,
            fg_color=FIELD, selected_color=RED,
            selected_hover_color=RED_HOVER, unselected_color=FIELD,
            unselected_hover_color="#3a3a3a",
        )

        self.grid_area = SmoothScrollFrame(self, fg_color="transparent")
        self.grid_area.pack(fill="both", expand=True, padx=20, pady=(0, 5))
        for col in range(self.columns):
            self.grid_area.grid_columnconfigure(col, weight=1)

    def update_fav_button(self):
        if self.view == "favorites":
            self.fav_button.configure(fg_color=RED, border_width=0, hover_color=RED_HOVER)
        else:
            self.fav_button.configure(fg_color="transparent", border_width=1, hover_color=FIELD)

    def update_footer(self):
        if self.view == "favorites":
            text = providers.ALL_ATTRIBUTION
            self.footer_url = None
        else:
            provider = providers.PROVIDERS[self.kind]
            text = provider["attribution"]
            self.footer_url = provider["attribution_url"]

        if self.footer_url:
            self.footer.configure(text=text, cursor="hand2")
        else:
            self.footer.configure(text=text, cursor="arrow")

    def open_footer_link(self, event):
        if self.footer_url:
            common.open_link(self.footer_url)

    # ---------- responsive layout ----------

    def on_resize(self, event):
        # wait a moment so we do not redo the layout on every pixel
        self.schedule("resize", 120, self.update_columns)

    def update_columns(self):
        width = self.grid_area.winfo_width()
        if width < 100:
            return

        columns = int(width / (SLOT_WIDTH * self.scale))
        columns = max(2, min(MAX_COLUMNS, columns))

        if columns != self.columns:
            self.columns = columns
            self.relayout()

    def relayout(self):
        for col in range(MAX_COLUMNS):
            if col < self.columns:
                weight = 1
            else:
                weight = 0
            self.grid_area.grid_columnconfigure(col, weight=weight)

        for index, widget in enumerate(self.items[:self.shown]):
            widget.grid(
                row=index // self.columns, column=index % self.columns,
                padx=8, pady=8, sticky="n",
            )

    # ---------- searching ----------

    def do_search(self):
        # stops people from sending a search on every key press
        now = time.monotonic()
        if now - self.last_search_time < SEARCH_COOLDOWN:
            return
        self.last_search_time = now

        # an empty search goes back to the popular list
        self.last_query = self.search_entry.get().strip()[:100]
        self.load_results()

    def change_type(self, value):
        self.kind = providers.LABELS[value]
        self.load_results()

    def back_to_popular(self):
        self.last_query = ""
        self.search_entry.delete(0, "end")
        # taking the focus away brings the placeholder text back
        self.winfo_toplevel().focus_set()
        self.load_results()

    def load_results(self):
        # every new search gets a new id, so old answers can be ignored
        self.search_id += 1
        this_id = self.search_id

        self.view = "browse"
        self.result_kind = self.kind
        self.update_fav_button()
        self.update_footer()
        self.fav_filter.pack_forget()
        self.type_switch.set(providers.PROVIDERS[self.kind]["label"])

        provider = providers.PROVIDERS[self.kind]
        self.search_entry.configure(placeholder_text=provider["placeholder"])

        self.status.configure(text="Loading...", text_color=GRAY)
        self.show_skeleton()

        if self.last_query == "":
            self.heading.configure(text=provider["popular_title"])
            func = provider["popular"]
            args = ()
        else:
            self.heading.configure(text='Results for "' + self.last_query + '"')
            func = provider["search"]
            args = (self.last_query,)

        threading.Thread(
            target=self.worker, args=(this_id, func, args), daemon=True
        ).start()

    def worker(self, search_id, func, args):
        # runs in the background so the window does not freeze
        try:
            results = func(*args)
            self.queue.put(("results", search_id, results))
        except common.ApiError as error:
            self.queue.put(("error", search_id, (str(error), error.code)))
        except Exception:
            self.queue.put(("error", search_id, ("Something went wrong.", "server")))

    def load_image(self, search_id, index, url):
        # also runs in the background: download, open and shrink the picture
        try:
            data = common.get_image(url)
            image = Image.open(io.BytesIO(data)).convert("RGB")
            image.thumbnail((600, 600))
        except Exception:
            image = None
        self.queue.put(("poster", search_id, (index, image)))

    def check_queue(self):
        try:
            while True:
                kind, search_id, data = self.queue.get_nowait()
                if search_id != self.search_id:
                    continue  # answer from an old search
                if kind == "results":
                    self.show_results(data)
                elif kind == "error":
                    self.show_error(data[0], data[1])
                elif kind == "poster":
                    self.show_poster(data)
        except queue.Empty:
            pass
        self.schedule("queue", 100, self.check_queue)

    # ---------- favorites ----------

    def toggle_favorites_view(self):
        if self.view == "favorites":
            self.load_results()
        else:
            self.open_favorites()

    def open_favorites(self):
        self.fav_category = None   # always start with everything
        self.view = "favorites"
        self.update_fav_button()
        self.update_footer()

        # no category is selected at the top while we look at favorites
        self.type_switch.set("")

        self.fav_filter.pack(anchor="w", padx=30, pady=(0, 8))
        self.show_favorites()

    def show_favorites(self):
        # a new id so answers from an older search are ignored
        self.search_id += 1
        self.heading.configure(text="My Favorites")
        self.status.configure(text="", text_color=GRAY)
        self.grid_area.scroll_to_top()

        try:
            saved = favorites.all_for(self.user_id)
        except ValueError as error:
            self.show_message_panel(
                "Can't open your favorites", str(error),
                "Try again", self.show_favorites,
            )
            return

        # the tabs always count everything, even when one tab is open
        self.update_fav_filter(saved)

        if self.fav_category is not None:
            saved = [item for item in saved if item["category"] == self.fav_category]

        if len(saved) == 0:
            self.show_no_favorites()
            return

        # movies first, then TV, music and games. Newest first inside each group
        order = {}
        for number, category in enumerate(providers.ORDER):
            order[category] = number
        saved.sort(key=lambda item: order.get(item["category"], 99))

        self.render_items(saved, self.saved_text(len(saved)), True)

    def saved_text(self, count):
        if self.fav_category is None:
            return str(count) + " saved"
        label = providers.PROVIDERS[self.fav_category]["label"]
        return str(count) + " saved in " + label

    def update_fav_filter(self, saved=None):
        # the tab names show how many titles are saved in each category
        if saved is None:
            try:
                keys = favorites.saved_keys(self.user_id)
            except ValueError:
                return
            categories = [key.split(":")[0] for key in keys]
        else:
            categories = [item["category"] for item in saved]

        self.fav_label_map = {"All (" + str(len(categories)) + ")": None}
        for category in providers.ORDER:
            label = providers.PROVIDERS[category]["label"]
            count = categories.count(category)
            self.fav_label_map[label + " (" + str(count) + ")"] = category

        # the tabs are only rebuilt when a number changed, never while one is being clicked
        labels = list(self.fav_label_map)
        if labels != self.fav_values:
            self.fav_filter.configure(values=labels)
            self.fav_values = labels

        for label, category in self.fav_label_map.items():
            if category == self.fav_category:
                self.fav_filter.set(label)

    def change_fav_filter(self, label):
        self.fav_category = self.fav_label_map.get(label)
        self.show_favorites()

    def go_browse(self, category):
        self.kind = category
        self.last_query = ""
        self.search_entry.delete(0, "end")
        self.winfo_toplevel().focus_set()
        self.load_results()

    def show_no_favorites(self):
        self.status.configure(text="", text_color=GRAY)

        if self.fav_category is None:
            self.show_message_panel(
                "No favorites yet",
                "Click the heart on any movie, song or game to save it here.",
                "Browse titles", self.load_results,
            )
            return

        category = self.fav_category
        self.show_message_panel(
            "No saved " + PLURAL_NAMES[category] + " yet",
            "Click the heart on any " + SINGLE_NAMES[category] + " to save it here.",
            "Browse " + PLURAL_NAMES[category], lambda: self.go_browse(category),
        )

    def toggle_favorite(self, item):
        # returns (new state, error message)
        try:
            now_saved = favorites.toggle(self.user_id, item["category"], item)
        except ValueError as error:
            self.status.configure(text=str(error), text_color=ERROR)
            return None, str(error)

        key = favorites.make_key(item["category"], item["id"])
        if now_saved:
            self.saved_keys.add(key)
        else:
            self.saved_keys.discard(key)

        heart = self.hearts.get(key)
        if heart is not None:
            self.set_heart(heart, now_saved)

        # in the favorites list a removed title disappears
        if self.view == "favorites" and not now_saved:
            self.remove_card(key)
            self.update_fav_filter()

        return now_saved, ""

    def set_heart(self, button, saved):
        if saved:
            button.configure(text="\u2665", text_color=HEART)
        else:
            button.configure(text="\u2661", text_color="white")

    def remove_card(self, key):
        card = self.cards_by_key.pop(key, None)
        self.hearts.pop(key, None)
        if card is None:
            return

        if card in self.items:
            position = self.items.index(card)
            self.items.remove(card)
            if position < self.shown:
                self.shown -= 1
        card.destroy()
        self.relayout()

        if len(self.items) == 0:
            self.show_no_favorites()
        else:
            self.status.configure(
                text=self.saved_text(len(self.items)), text_color=GRAY
            )

    def open_details(self, item, index):
        if self.details is not None:
            try:
                self.details.destroy()
            except Exception:
                pass

        saved = False
        if item.get("id") is not None:
            key = favorites.make_key(item["category"], item["id"])
            saved = key in self.saved_keys

        provider = providers.PROVIDERS[item["category"]]
        self.details = DetailsWindow(
            self, item, self.poster_images.get(index), saved,
            lambda: self.toggle_favorite(item),
            provider["trailer"], provider["link_text"],
        )

    # ---------- what is shown in the grid ----------

    def clear_grid(self):
        self.cancel("pulse")
        self.cancel("reveal")
        for widget in self.grid_area.winfo_children():
            widget.destroy()
        self.items = []
        self.shown = 0
        self.skeleton_cards = []
        self.poster_labels = {}
        self.poster_images = {}
        self.card_sizes = {}
        self.hearts = {}
        self.cards_by_key = {}

    def show_skeleton(self):
        self.clear_grid()
        self.grid_area.scroll_to_top()

        # the gray cards have the same shape as the real cards will have
        image_height = providers.PROVIDERS[self.kind]["image_size"][1]
        for i in range(SKELETON_COUNT):
            self.skeleton_cards.append(
                SkeletonCard(self.grid_area, self.scale, image_height)
            )
        self.items = list(self.skeleton_cards)
        self.shown = len(self.items)
        self.relayout()
        self.pulse()

    def pulse(self):
        # the gray blocks fade light and dark, like a wave across the cards
        self.pulse_phase += 0.25
        for i, card in enumerate(self.skeleton_cards):
            amount = (math.sin(self.pulse_phase - i * 0.35) + 1) / 2
            card.set_color(blend(SKELETON_DARK, SKELETON_LIGHT, amount))
        self.schedule("pulse", 70, self.pulse)

    def show_results(self, results):
        if len(results) == 0:
            self.clear_grid()
            self.show_empty()
            return

        # remember which type these results are
        items = []
        for result in results:
            item = dict(result)
            item["category"] = self.result_kind
            items.append(item)
        self.render_items(items, str(len(items)) + " results")

    def render_items(self, items, status_text, show_tags=False):
        self.clear_grid()

        try:
            self.saved_keys = favorites.saved_keys(self.user_id)
        except ValueError:
            self.saved_keys = set()

        self.status.configure(text=status_text, text_color=GRAY)

        for index, item in enumerate(items):
            self.items.append(self.make_card(item, index, show_tags))
            if item.get("image"):
                self.pool.submit(
                    self.load_image, self.search_id, index, item["image"],
                )
        self.reveal()

    def reveal(self):
        # show one row of cards at a time so the grid builds up step by step
        self.shown = min(self.shown + self.columns, len(self.items))
        self.relayout()
        if self.shown < len(self.items):
            self.schedule("reveal", 60, self.reveal)

    def show_message_panel(self, title, text, button_text=None, command=None):
        self.clear_grid()

        panel = ctk.CTkFrame(self.grid_area, fg_color="transparent")
        panel.grid(row=0, column=0, columnspan=MAX_COLUMNS, pady=(70, 0))

        ctk.CTkLabel(
            panel, text=title, font=("Segoe UI", 22, "bold"),
        ).pack()
        ctk.CTkLabel(
            panel, text=text, font=("Segoe UI", 14), text_color=GRAY,
            wraplength=480, justify="center",
        ).pack(pady=(8, 20))

        if button_text:
            ctk.CTkButton(
                panel, text=button_text, width=170, height=40,
                fg_color=RED, hover_color=RED_HOVER,
                font=("Segoe UI", 14, "bold"), command=command,
            ).pack()

    def show_empty(self):
        self.status.configure(text="", text_color=GRAY)

        if self.last_query == "":
            self.show_message_panel(
                "Nothing to show right now",
                "The list is temporarily unavailable. "
                "Please try again in a moment.",
                "Try again", self.load_results,
            )
            return

        query = self.last_query
        if len(query) > 40:
            query = query[:40] + "..."
        self.show_message_panel(
            'No results for "' + query + '"',
            "This title may be temporarily unavailable or not in our "
            "database yet. Check the spelling or try another title.",
            "Back to popular", self.back_to_popular,
        )

    def show_error(self, message, code):
        self.status.configure(text="", text_color=GRAY)

        if code == "network":
            title = "You seem to be offline"
            text = "Check your internet connection and try again."
        elif code == "busy":
            title = "Too many requests"
            text = "The service is busy. Wait a few seconds and try again."
        elif code == "key":
            title = "API key problem"
            text = message + " Check the key in your .env file."
        else:
            title = "Temporarily unavailable"
            text = message + " Please try again in a moment."

        self.show_message_panel(title, text, "Try again", self.load_results)

    def make_card(self, item, index, show_tag=False):
        size = providers.PROVIDERS[item["category"]]["image_size"]
        self.card_sizes[index] = size

        card = ctk.CTkFrame(
            self.grid_area, width=180, fg_color=CARD, corner_radius=10
        )

        if item.get("image"):
            poster_text = "Loading..."
        else:
            poster_text = "No Image"

        poster = ctk.CTkLabel(
            card, text=poster_text, width=size[0], height=size[1],
            fg_color=FIELD, corner_radius=8, text_color=GRAY,
        )
        poster.pack(padx=15, pady=(15, 8))
        self.poster_labels[index] = poster

        # in the Saved view every card says what it is (MOVIE, SONG, GAME...)
        tag_label = None
        if show_tag:
            tag_label = ctk.CTkLabel(
                card, text=CATEGORY_NAMES.get(item["category"], "Title").upper(),
                font=("Segoe UI", 10, "bold"), text_color=RED, anchor="w",
            )
            tag_label.pack(padx=15, anchor="w")

        title = item["title"]
        if len(title) > 30:
            title = title[:30] + "..."
        title_label = ctk.CTkLabel(
            card, text=title, font=("Segoe UI", 14, "bold"), width=150,
            height=46, wraplength=150, anchor="nw", justify="left",
        )
        title_label.pack(padx=15)

        info_label = ctk.CTkLabel(
            card, text=card_text(item), font=("Segoe UI", 12),
            text_color=GRAY, anchor="w", justify="left",
        )
        info_label.pack(padx=15, pady=(2, 15), anchor="w")

        # clicking the card opens the details popup
        clickable = [card, poster, title_label, info_label]
        if tag_label is not None:
            clickable.append(tag_label)
        self.add_card_events(card, clickable, item, index)

        # the heart button sits on the top right corner of the picture
        if item.get("id") is not None:
            key = favorites.make_key(item["category"], item["id"])
            heart = ctk.CTkButton(
                card, text="", width=36, height=36, corner_radius=0,
                fg_color=BG, bg_color=BG, hover_color=FIELD,
                font=("Segoe UI Symbol", 17),
                command=lambda: self.toggle_favorite(item),
            )
            self.set_heart(heart, key in self.saved_keys)
            heart.place(x=158, y=22, anchor="ne")
            self.hearts[key] = heart
            self.cards_by_key[key] = card

        return card

    def add_card_events(self, card, widgets, item, index):
        def click(event):
            self.open_details(item, index)

        def enter(event):
            card.configure(fg_color=CARD_HOVER)

        def leave(event):
            card.configure(fg_color=CARD)

        for widget in widgets:
            widget.bind("<Button-1>", click)
            widget.bind("<Enter>", enter)
            widget.bind("<Leave>", leave)
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass

    def show_poster(self, data):
        index, image = data
        label = self.poster_labels.get(index)
        if label is None or not label.winfo_exists():
            return

        if image is None:
            label.configure(text="No Image")
            return

        self.poster_images[index] = image
        size = self.card_sizes.get(index, (150, 225))
        try:
            # cut the picture to the shape of the card, twice as big so it stays sharp
            fitted = ImageOps.fit(image, (size[0] * 2, size[1] * 2))
            picture = ctk.CTkImage(
                light_image=fitted, dark_image=fitted, size=size
            )
            label.configure(image=picture, text="")
        except Exception:
            label.configure(text="No Image")

    def destroy(self):
        # close the popup, stop every timer and the background threads
        if self.details is not None:
            try:
                self.details.destroy()
            except Exception:
                pass
        for name in list(self.jobs):
            self.cancel(name)
        self.pool.shutdown(wait=False, cancel_futures=True)
        super().destroy()