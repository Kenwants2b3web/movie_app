import io
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
from PIL import Image

import api
from theme import (BG, FIELD, CARD, TOPBAR, RED, RED_HOVER, GRAY, ERROR)

COLUMNS = 5
POSTER_SIZE = (150, 225)


class HomeFrame(ctk.CTkFrame):
    def __init__(self, master, username, on_logout):
        super().__init__(master, corner_radius=0, fg_color=BG)
        self.username = username
        self.on_logout = on_logout

        self.kind = "movie"       # "movie" or "tv"
        self.last_query = ""      # empty means show the popular list
        self.search_id = 0        # used to ignore old results
        self.poster_labels = {}

        # background threads put their results here, the GUI reads them
        self.queue = queue.Queue()
        self.pool = ThreadPoolExecutor(max_workers=5)
        self.after_id = None

        self.build_top_bar()
        self.build_content()

        self.check_queue()
        self.load_results()

    def build_top_bar(self):
        bar = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color=TOPBAR)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        ctk.CTkLabel(
            bar, text="MovieHub", font=("Segoe UI", 24, "bold"),
            text_color=RED,
        ).pack(side="left", padx=(25, 20))

        self.search_entry = ctk.CTkEntry(
            bar, placeholder_text="Search movies or TV shows", width=340,
            height=40, fg_color=FIELD, border_width=0,
        )
        self.search_entry.pack(side="left", padx=(0, 8))
        self.search_entry.bind("<Return>", lambda event: self.do_search())

        self.search_button = ctk.CTkButton(
            bar, text="Search", width=80, height=40, fg_color=RED,
            hover_color=RED_HOVER, font=("Segoe UI", 13, "bold"),
            command=self.do_search,
        )
        self.search_button.pack(side="left", padx=(0, 15))

        self.type_switch = ctk.CTkSegmentedButton(
            bar, values=["Movies", "TV Shows"], command=self.change_type,
            fg_color=FIELD, selected_color=RED,
            selected_hover_color=RED_HOVER, unselected_color=FIELD,
            unselected_hover_color="#3a3a3a",
        )
        self.type_switch.set("Movies")
        self.type_switch.pack(side="left")

        ctk.CTkButton(
            bar, text="Logout", width=80, height=34, fg_color="transparent",
            border_width=1, hover_color=FIELD, command=self.on_logout,
        ).pack(side="right", padx=(10, 25))

        # long usernames get cut so the top bar does not break
        name = self.username
        if len(name) > 14:
            name = name[:14] + "..."
        ctk.CTkLabel(
            bar, text="Hi, " + name, font=("Segoe UI", 13),
            text_color=GRAY,
        ).pack(side="right")

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

        self.grid_area = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.grid_area.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        for col in range(COLUMNS):
            self.grid_area.grid_columnconfigure(col, weight=1)

    def do_search(self):
        # an empty search goes back to the popular list
        self.last_query = self.search_entry.get().strip()[:100]
        self.load_results()

    def change_type(self, value):
        if value == "Movies":
            self.kind = "movie"
        else:
            self.kind = "tv"
        self.load_results()

    def load_results(self):
        # every new search gets a new id, so old answers can be ignored
        self.search_id += 1
        this_id = self.search_id

        self.status.configure(text="Loading...", text_color=GRAY)

        if self.kind == "movie":
            label = "Movies"
        else:
            label = "TV Shows"

        if self.last_query == "":
            self.heading.configure(text="Popular " + label)
            func = api.get_popular
            args = (self.kind,)
        else:
            self.heading.configure(text='Results for "' + self.last_query + '"')
            func = api.search
            args = (self.kind, self.last_query)

        threading.Thread(
            target=self.worker, args=(this_id, func, args), daemon=True
        ).start()

    def worker(self, search_id, func, args):
        # runs in the background so the window does not freeze
        try:
            results = func(*args)
            self.queue.put(("results", search_id, results))
        except api.ApiError as error:
            self.queue.put(("error", search_id, str(error)))
        except Exception:
            self.queue.put(("error", search_id, "Something went wrong."))

    def load_poster(self, search_id, index, path):
        try:
            data = api.get_poster(path)
        except Exception:
            data = None
        self.queue.put(("poster", search_id, (index, data)))

    def check_queue(self):
        try:
            while True:
                kind, search_id, data = self.queue.get_nowait()
                if search_id != self.search_id:
                    continue  # answer from an old search
                if kind == "results":
                    self.show_results(data)
                elif kind == "error":
                    self.show_error(data)
                elif kind == "poster":
                    self.show_poster(data)
        except queue.Empty:
            pass
        self.after_id = self.after(100, self.check_queue)

    def clear_grid(self):
        for widget in self.grid_area.winfo_children():
            widget.destroy()
        self.poster_labels = {}

    def show_error(self, message):
        self.clear_grid()
        self.status.configure(text=message, text_color=ERROR)

    def show_results(self, results):
        self.clear_grid()

        if len(results) == 0:
            self.status.configure(text="No results found.", text_color=GRAY)
            return

        self.status.configure(
            text=str(len(results)) + " results", text_color=GRAY
        )

        for index, item in enumerate(results):
            card = self.make_card(item, index)
            card.grid(
                row=index // COLUMNS, column=index % COLUMNS,
                padx=8, pady=8, sticky="n",
            )
            if item["poster_path"]:
                self.pool.submit(
                    self.load_poster, self.search_id, index,
                    item["poster_path"],
                )

    def make_card(self, item, index):
        card = ctk.CTkFrame(
            self.grid_area, width=180, fg_color=CARD, corner_radius=10
        )

        if item["poster_path"]:
            poster_text = "Loading..."
        else:
            poster_text = "No Image"

        poster = ctk.CTkLabel(
            card, text=poster_text, width=POSTER_SIZE[0],
            height=POSTER_SIZE[1], fg_color=FIELD, corner_radius=8,
            text_color=GRAY,
        )
        poster.pack(padx=15, pady=(15, 8))
        self.poster_labels[index] = poster

        title = item["title"]
        if len(title) > 30:
            title = title[:30] + "..."
        ctk.CTkLabel(
            card, text=title, font=("Segoe UI", 14, "bold"), width=150,
            height=46, wraplength=150, anchor="nw", justify="left",
        ).pack(padx=15)

        info = item["year"] + "   *   rating " + str(item["rating"])
        ctk.CTkLabel(
            card, text=info, font=("Segoe UI", 12), text_color=GRAY,
            anchor="w",
        ).pack(padx=15, pady=(2, 15), anchor="w")

        return card

    def show_poster(self, data):
        index, image_bytes = data
        label = self.poster_labels.get(index)
        if label is None:
            return

        if image_bytes is None:
            label.configure(text="No Image")
            return

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            picture = ctk.CTkImage(
                light_image=image, dark_image=image, size=POSTER_SIZE
            )
            label.configure(image=picture, text="")
        except Exception:
            label.configure(text="No Image")

    def destroy(self):
        # stop the timer and the background threads when we leave this screen
        if self.after_id is not None:
            self.after_cancel(self.after_id)
        self.pool.shutdown(wait=False, cancel_futures=True)
        super().destroy()
