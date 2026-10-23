import customtkinter as ctk

import auth
import database

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class LoginApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Movie App - Login")
        self.geometry("400x450")
        self.resizable(False, False)

        title = ctk.CTkLabel(self, text="Welcome", font=("Arial", 28, "bold"))
        title.pack(pady=(40, 20))

        self.username_entry = ctk.CTkEntry(
            self, placeholder_text="Username", width=250
        )
        self.username_entry.pack(pady=8)

        self.password_entry = ctk.CTkEntry(
            self, placeholder_text="Password", show="*", width=250
        )
        self.password_entry.pack(pady=8)

        login_btn = ctk.CTkButton(
            self, text="Login", width=250, command=self.do_login
        )
        login_btn.pack(pady=(20, 8))

        register_btn = ctk.CTkButton(
            self,
            text="Register",
            width=250,
            fg_color="transparent",
            border_width=1,
            command=self.do_register,
        )
        register_btn.pack(pady=8)

        self.message = ctk.CTkLabel(self, text="")
        self.message.pack(pady=15)

    def do_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        ok, msg = auth.login(username, password)
        self.show_message(msg, ok)

        if ok:
            self.open_home(username)

    def do_register(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        ok, msg = auth.register(username, password)
        self.show_message(msg, ok)

    def show_message(self, text, success):
        if success:
            color = "green"
        else:
            color = "red"
        self.message.configure(text=text, text_color=color)

    def open_home(self, username):
        # placeholder for now, the movie search screen will go here next sprint
        self.message.configure(text="Logged in as " + username)


if __name__ == "__main__":
    database.create_tables()
    app = LoginApp()
    app.mainloop()
