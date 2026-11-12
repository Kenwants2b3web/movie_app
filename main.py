import customtkinter as ctk

import database
from home import HomeFrame
from login import LoginFrame
from theme import BG

ctk.set_appearance_mode("dark")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MovieHub")
        self.configure(fg_color=BG)
        self.show_login()

    def center(self, width, height):
        # customtkinter makes the window bigger on high DPI screens,
        # so the size has to be scaled here too
        scale = ctk.ScalingTracker.get_window_scaling(self)
        x = int((self.winfo_screenwidth() - width * scale) / 2)
        y = int((self.winfo_screenheight() - height * scale) / 2)
        self.geometry(str(width) + "x" + str(height) + "+" + str(max(x, 0)) + "+" + str(max(y, 0)))

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()

    def show_login(self):
        self.clear()
        self.center(800, 500)
        self.resizable(False, False)
        LoginFrame(self, self.show_home).pack(fill="both", expand=True)

    def show_home(self, username):
        self.clear()
        self.center(1100, 650)
        self.resizable(False, False)
        HomeFrame(self, username, self.show_login).pack(fill="both", expand=True)


if __name__ == "__main__":
    database.create_tables()
    app = App()
    app.mainloop()
