import io

import customtkinter as ctk
from PIL import Image

from theme import BG, FIELD, RED, RED_HOVER, GRAY, ERROR, HEART

CATEGORY_NAMES = {"movie": "Movie", "tv": "TV Show"}


class DetailsWindow(ctk.CTkToplevel):
    # the popup that opens when you click a card

    def __init__(self, master, item, poster_bytes, saved, on_toggle):
        super().__init__(master)
        self.item = item
        self.saved = saved

        # function from home.py, returns (new state, error message)
        self.on_toggle = on_toggle

        self.title(item["title"][:60])
        self.configure(fg_color=BG)
        self.resizable(False, False)

        window = master.winfo_toplevel()
        self.transient(window)
        self.center_over(window, 760, 470)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.build_poster(poster_bytes)
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

    def build_poster(self, poster_bytes):
        size = (230, 345)
        label = ctk.CTkLabel(
            self, text="No Image", width=size[0], height=size[1],
            fg_color=FIELD, corner_radius=8, text_color=GRAY,
        )
        if poster_bytes:
            try:
                image = Image.open(io.BytesIO(poster_bytes)).convert("RGB")
                picture = ctk.CTkImage(
                    light_image=image, dark_image=image, size=size
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
            wraplength=410, justify="left", anchor="w",
        ).pack(fill="x")

        category = CATEGORY_NAMES.get(self.item.get("category"), "Title")
        if self.item["rating"] > 0:
            rating = "\u2605 " + str(self.item["rating"])
        else:
            rating = "Not rated yet"
        ctk.CTkLabel(
            info, text=category + "   |   " + self.item["year"] + "   |   " + rating,
            font=("Segoe UI", 13), text_color=GRAY, anchor="w",
        ).pack(fill="x", pady=(4, 14))

        overview = self.item.get("overview") or ""
        if overview.strip() == "":
            overview = "No description is available for this title yet."

        box = ctk.CTkTextbox(
            info, width=410, height=190, fg_color=FIELD,
            font=("Segoe UI", 13), wrap="word",
        )
        box.insert("1.0", overview)
        box.configure(state="disabled")
        box.pack(fill="x")

        self.message = ctk.CTkLabel(
            info, text="", font=("Segoe UI", 12), text_color=ERROR,
            anchor="w",
        )
        self.message.pack(fill="x", pady=(6, 0))

        buttons = ctk.CTkFrame(info, fg_color="transparent")
        buttons.pack(fill="x", side="bottom")

        self.fav_button = ctk.CTkButton(
            buttons, text="", width=240, height=40,
            font=("Segoe UI", 14, "bold"), command=self.toggle,
        )
        self.fav_button.pack(side="left")

        ctk.CTkButton(
            buttons, text="Close", width=90, height=40, fg_color="transparent",
            border_width=1, hover_color=FIELD, command=self.destroy,
        ).pack(side="right")

        if self.item.get("id") is None:
            self.fav_button.configure(
                text="Cannot be saved", state="disabled", fg_color=FIELD
            )
        else:
            self.refresh_button()

    def refresh_button(self):
        if self.saved:
            self.fav_button.configure(
                text="\u2665  Saved - click to remove", fg_color="transparent",
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
            self.message.configure(text=message)
            return
        self.saved = state
        self.message.configure(text="")
        self.refresh_button()
