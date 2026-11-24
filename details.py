import io
import queue
import threading

import customtkinter as ctk
from PIL import ImageOps

import common
from theme import BG, FIELD, RED, RED_HOVER, GRAY, GREEN, ERROR, HEART

CATEGORY_NAMES = {"movie": "Movie", "tv": "TV Show", "music": "Song", "game": "Game"}

# size of the picture in the popup for each category
POPUP_IMAGE_SIZES = {
    "movie": (230, 345), "tv": (230, 345), "music": (230, 230), "game": (230, 155),
}


class DetailsWindow(ctk.CTkToplevel):
    # the popup that opens when you click a card

    def __init__(self, master, item, image, saved, on_toggle,
                 trailer_func=None, link_text=None):
        super().__init__(master)
        self.item = item
        self.saved = saved

        # function from home.py, returns (new state, error message)
        self.on_toggle = on_toggle

        self.trailer_func = trailer_func
        self.link_text = link_text
        self.queue = queue.Queue()
        self.poll_job = None

        self.title(item["title"][:60])
        self.configure(fg_color=BG)
        self.resizable(False, False)

        window = master.winfo_toplevel()
        self.transient(window)
        self.center_over(window, 800, 480)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.build_image(image)
        self.build_info()

        self.bind("<Escape>", lambda event: self.destroy())

        # wait until the window is on the screen before taking the focus
        self.after(200, self.take_focus)

    def center_over(self, window, width, height):
        # the size is scaled on high DPI screens, so scale it here too
        scale = ctk.ScalingTracker.get_window_scaling(self)
        x = window.winfo_rootx() + int((window.winfo_width() - width * scale) / 2)
        y = window.winfo_rooty() + int((window.winfo_height() - height * scale) / 2)
        x = max(x, 0)
        y = max(y, 0)
        self.geometry(str(width) + "x" + str(height) + "+" + str(x) + "+" + str(y))

    def take_focus(self):
        if not self.winfo_exists():
            return
        try:
            self.lift()
            self.focus()
            self.grab_set()
        except Exception:
            pass

    def build_image(self, image):
        size = POPUP_IMAGE_SIZES.get(self.item.get("category"), (230, 345))
        label = ctk.CTkLabel(
            self, text="No Image", width=size[0], height=size[1],
            fg_color=FIELD, corner_radius=8, text_color=GRAY,
        )
        if image is not None:
            try:
                fitted = ImageOps.fit(image, (size[0] * 2, size[1] * 2))
                picture = ctk.CTkImage(
                    light_image=fitted, dark_image=fitted, size=size
                )
                label.configure(image=picture, text="")
            except Exception:
                pass
        label.grid(row=0, column=0, padx=(28, 10), pady=28, sticky="n")

    def build_info(self):
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=1, padx=(10, 28), pady=28, sticky="nsew")

        ctk.CTkLabel(
            info, text=self.item["title"], font=("Segoe UI", 24, "bold"),
            wraplength=440, justify="left", anchor="w",
        ).pack(fill="x")

        subtitle = self.item.get("subtitle") or ""
        if subtitle:
            ctk.CTkLabel(
                info, text=subtitle, font=("Segoe UI", 15), anchor="w",
                text_color="#d0d0d0", wraplength=440, justify="left",
            ).pack(fill="x", pady=(2, 0))

        category = self.item.get("category")
        parts = [CATEGORY_NAMES.get(category, "Title"), self.item["year"]]
        if self.item["rating"] > 0:
            parts.append("\u2605 " + str(self.item["rating"]))
        elif category != "music":
            parts.append("Not rated yet")
        ctk.CTkLabel(
            info, text="   |   ".join(parts), font=("Segoe UI", 13),
            text_color=GRAY, anchor="w",
        ).pack(fill="x", pady=(4, 14))

        overview = self.item.get("overview") or ""
        if overview.strip() == "":
            overview = "No description is available for this title yet."

        box = ctk.CTkTextbox(
            info, width=440, height=175, fg_color=FIELD,
            font=("Segoe UI", 13), wrap="word",
        )
        box.insert("1.0", overview)
        box.configure(state="disabled")
        box.pack(fill="x")

        self.message = ctk.CTkLabel(
            info, text="", font=("Segoe UI", 12), text_color=ERROR,
            anchor="w", wraplength=440, justify="left",
        )
        self.message.pack(fill="x", pady=(6, 0))

        buttons = ctk.CTkFrame(info, fg_color="transparent")
        buttons.pack(fill="x", side="bottom")

        self.fav_button = ctk.CTkButton(
            buttons, text="", width=190, height=40,
            font=("Segoe UI", 13, "bold"), command=self.toggle,
        )
        self.fav_button.pack(side="left")

        ctk.CTkButton(
            buttons, text="Close", width=80, height=40, fg_color="transparent",
            border_width=1, hover_color=FIELD, command=self.destroy,
        ).pack(side="right")

        self.action_button = None
        link = self.item.get("link")
        if self.trailer_func is not None and self.item.get("id") is not None:
            self.action_text = "\u25b6  Watch trailer"
            self.action_command = self.start_trailer
        elif self.link_text and common.is_safe_link(link):
            self.action_text = self.link_text
            self.action_command = self.open_item_link
        else:
            self.action_text = None

        if self.action_text:
            self.action_button = ctk.CTkButton(
                buttons, text=self.action_text, width=170, height=40,
                fg_color="transparent", border_width=1, hover_color=FIELD,
                font=("Segoe UI", 13, "bold"), command=self.action_command,
            )
            self.action_button.pack(side="left", padx=(10, 0))

        if self.item.get("id") is None:
            self.fav_button.configure(
                text="Cannot be saved", state="disabled", fg_color=FIELD
            )
        else:
            self.refresh_button()

    def refresh_button(self):
        if self.saved:
            self.fav_button.configure(
                text="\u2665  Remove favorite", fg_color="transparent",
                border_width=1, border_color=HEART, text_color=HEART,
                hover_color=FIELD,
            )
        else:
            self.fav_button.configure(
                text="\u2661  Add to favorites", fg_color=RED,
                border_width=0, text_color="white", hover_color=RED_HOVER,
            )

    def toggle(self):
        state, message = self.on_toggle()
        if state is None:
            self.message.configure(text=message, text_color=ERROR)
            return
        self.saved = state
        self.message.configure(text="")
        self.refresh_button()

    # ---------- the extra button (trailer or link) ----------

    def open_item_link(self):
        if common.open_link(self.item.get("link")):
            self.message.configure(text="Opened in your browser.", text_color=GREEN)
        else:
            self.message.configure(text="This link cannot be opened.", text_color=ERROR)

    def start_trailer(self):
        # asking the internet takes a moment, so it runs in the background
        func = self.trailer_func
        if self.action_button is None or func is None:
            return

        self.action_button.configure(state="disabled", text="Looking for trailer...")
        self.message.configure(text="")

        item_id = self.item["id"]

        def work():
            try:
                self.queue.put(("ok", func(item_id), ""))
            except common.ApiError as error:
                self.queue.put(("error", str(error), error.code))
            except Exception:
                self.queue.put(("error", "Something went wrong.", "server"))

        threading.Thread(target=work, daemon=True).start()
        self.poll_job = self.after(100, self.check_trailer)

    def check_trailer(self):
        self.poll_job = None
        try:
            kind, data, code = self.queue.get_nowait()
        except queue.Empty:
            self.poll_job = self.after(100, self.check_trailer)
            return

        if self.action_button is not None:
            self.action_button.configure(state="normal", text=self.action_text)

        if kind == "ok":
            if common.open_link(data):
                self.message.configure(
                    text="Opened the trailer in your browser.", text_color=GREEN
                )
            else:
                self.message.configure(
                    text="The trailer link cannot be opened.", text_color=ERROR
                )
        elif code == "empty":
            self.message.configure(text=data, text_color=GRAY)
        else:
            self.message.configure(text=data, text_color=ERROR)

    def destroy(self):
        if self.poll_job is not None:
            self.after_cancel(self.poll_job)
            self.poll_job = None
        super().destroy()