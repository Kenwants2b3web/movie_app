import tkinter as tk

import customtkinter as ctk

from theme import CARD

# how many pixels one mouse wheel click scrolls
SCROLL_STEP = 110


def blend(color1, color2, amount):
    # mixes two hex colors, amount 0 gives color1 and 1 gives color2
    r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
    r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
    r = int(r1 + (r2 - r1) * amount)
    g = int(g1 + (g2 - g1) * amount)
    b = int(b1 + (b2 - b1) * amount)
    return "#%02x%02x%02x" % (r, g, b)


def round_rect(canvas, x1, y1, x2, y2, radius, color):
    # tkinter has no rounded rectangle, so draw a smooth polygon
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, fill=color, outline="")


class SmoothScrollFrame(ctk.CTkScrollableFrame):
    # same as CTkScrollableFrame but the mouse wheel glides instead of jumping

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.target_y = 0
        self.scroll_job = None
        self.stuck_count = 0

        # scroll in single pixels so the glide is smooth on every system
        self._parent_canvas.configure(yscrollincrement=1)

    def _mouse_wheel_all(self, event):
        # this replaces the built-in wheel handler of customtkinter
        if not self._check_if_valid_scroll(event.widget):
            return

        delta = event.delta
        if delta == 0 and getattr(event, "num", 0) in (4, 5):
            # linux sends button 4 and 5 instead of delta
            if event.num == 4:
                delta = 120
            else:
                delta = -120
        if delta == 0:
            return

        if abs(delta) >= 120:
            clicks = delta / 120
        else:
            clicks = delta  # mac sends small numbers

        canvas = self._parent_canvas
        bbox = canvas.bbox("all")
        if not bbox:
            return
        max_y = max(0, bbox[3] - canvas.winfo_height())

        # a new scroll starts from where the view is right now
        if self.scroll_job is None:
            self.target_y = canvas.canvasy(0)

        self.target_y = min(max(self.target_y - clicks * SCROLL_STEP, 0), max_y)

        if self.scroll_job is None:
            self.animate()

    def animate(self):
        canvas = self._parent_canvas
        current = canvas.canvasy(0)
        difference = self.target_y - current

        if abs(difference) < 1:
            self.set_position(self.target_y)
            self.scroll_job = None
            return

        # move 20 percent of the way each time, so it slows down at the end
        self.set_position(current + difference * 0.2)

        # if the view cannot move any more (end of the list), stop
        if abs(canvas.canvasy(0) - current) < 0.5:
            self.stuck_count += 1
        else:
            self.stuck_count = 0
        if self.stuck_count >= 3:
            self.stuck_count = 0
            self.scroll_job = None
            return

        self.scroll_job = self.after(12, self.animate)

    def set_position(self, y):
        bbox = self._parent_canvas.bbox("all")
        if bbox and bbox[3] > 0:
            self._parent_canvas.yview_moveto(y / bbox[3])

    def scroll_to_top(self):
        if self.scroll_job is not None:
            self.after_cancel(self.scroll_job)
            self.scroll_job = None
        self.target_y = 0
        self._parent_canvas.yview_moveto(0)

    def destroy(self):
        if self.scroll_job is not None:
            self.after_cancel(self.scroll_job)
            self.scroll_job = None
        super().destroy()


class SkeletonCard(ctk.CTkFrame):
    # gray placeholder that has the same size as a real movie card

    def __init__(self, master, scale=1.0):
        super().__init__(master, width=180, fg_color=CARD, corner_radius=10)

        width = int(150 * scale)
        height = int(300 * scale)
        self.canvas = tk.Canvas(
            self, width=width, height=height, bg=CARD, highlightthickness=0
        )
        self.canvas.pack(padx=15, pady=15)

        s = scale
        self.shapes = [
            round_rect(self.canvas, 0, 0, width, 225 * s, 8 * s, CARD),
            round_rect(self.canvas, 0, 240 * s, 130 * s, 254 * s, 5 * s, CARD),
            round_rect(self.canvas, 0, 260 * s, 90 * s, 272 * s, 5 * s, CARD),
            round_rect(self.canvas, 0, 284 * s, 100 * s, 296 * s, 5 * s, CARD),
        ]

    def set_color(self, color):
        for shape in self.shapes:
            self.canvas.itemconfig(shape, fill=color)
