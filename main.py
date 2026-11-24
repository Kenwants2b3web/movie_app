import customtkinter as ctk

import database
from home import HomeFrame
from login import LoginFrame
from theme import BG

ctk.set_appearance_mode("dark")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MediaHub")
        self.configure(fg_color=BG)
        self.show_login()

    def center(self, width, height):
        # customtkinter makes the window bigger on high DPI screens,
        # so the size has to be scaled here too
        scale = ctk.ScalingTracker.get_window_scaling(self)

        # a small screen should never get a window bigger than itself
        width = min(width, int((self.winfo_screenwidth() - 40) / scale))
        height = min(height, int((self.winfo_screenheight() - 90) / scale))

        x = int((self.winfo_screenwidth() - width * scale) / 2)
        y = int((self.winfo_screenheight() - height * scale) / 2)
        x = max(x, 0)
        y = max(y, 0)
        self.geometry(str(width) + "x" + str(height) + "+" + str(x) + "+" + str(y))

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()

    def show_login(self):
        self.clear()
        self.state("normal")
        self.minsize(1, 1)
        self.center(800, 500)
        self.resizable(False, False)
        LoginFrame(self, self.show_home).pack(fill="both", expand=True)

    def show_home(self, username):
        user_id = database.get_user_id(username)
        if user_id is None:
            # should not happen, but never open the home screen without a user
            self.show_login()
            return

        self.clear()
        self.center(1150, 680)
        self.resizable(True, True)
        self.minsize(1020, 560)
        HomeFrame(self, user_id, username, self.show_login).pack(fill="both", expand=True)


if __name__ == "__main__":
    database.create_tables()
    app = App()
    app.mainloop()
