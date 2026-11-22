import customtkinter as ctk

import auth
from theme import (BG, FIELD, RED, RED_HOVER, SIDE, GRAY, GREEN, ERROR)


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, on_login):
        super().__init__(master, corner_radius=0, fg_color=BG)

        # function from main.py that opens the home screen
        self.on_login = on_login

        # "login" or "register"
        self.mode = "login"

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.build_side_panel()
        self.build_form()

    def build_side_panel(self):
        side = ctk.CTkFrame(self, width=330, corner_radius=0, fg_color=SIDE)
        side.grid(row=0, column=0, sticky="nsew")
        side.pack_propagate(False)

        ctk.CTkLabel(
            side, text="MovieHub", font=("Segoe UI", 36, "bold"),
            text_color="white",
        ).pack(pady=(150, 5))

        ctk.CTkLabel(
            side, text="Find movies and TV shows.\nSave the ones you love.",
            font=("Segoe UI", 14), text_color="#f0c4c7", justify="center",
        ).pack()

    def build_form(self):
        form = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        form.grid(row=0, column=1, sticky="nsew")
        self.form = form

        self.heading = ctk.CTkLabel(
            form, text="Sign In", font=("Segoe UI", 30, "bold")
        )
        self.heading.pack(pady=(60, 2))

        self.subtitle = ctk.CTkLabel(
            form, text="Welcome back! Please log in.",
            font=("Segoe UI", 13), text_color=GRAY,
        )
        self.subtitle.pack(pady=(0, 25))

        self.username_entry = ctk.CTkEntry(
            form, placeholder_text="Username", width=300, height=42,
            fg_color=FIELD, border_width=0,
        )
        self.username_entry.pack(pady=7)

        self.password_entry = ctk.CTkEntry(
            form, placeholder_text="Password", show="*", width=300,
            height=42, fg_color=FIELD, border_width=0,
        )
        self.password_entry.pack(pady=7)

        # pressing Enter submits the form
        self.username_entry.bind("<Return>", lambda event: self.submit())
        self.password_entry.bind("<Return>", lambda event: self.submit())

        # only shown in register mode
        self.make_confirm_entry()

        self.show_check = ctk.CTkCheckBox(
            form, text="Show password", font=("Segoe UI", 12),
            text_color=GRAY, fg_color=RED, hover_color=RED_HOVER,
            command=self.toggle_password,
        )
        self.show_check.pack(pady=(5, 10), anchor="w", padx=(50, 0))

        self.main_button = ctk.CTkButton(
            form, text="Login", width=300, height=42,
            fg_color=RED, hover_color=RED_HOVER,
            font=("Segoe UI", 15, "bold"), command=self.submit,
        )
        self.main_button.pack(pady=(5, 5))

        self.message = ctk.CTkLabel(form, text="", font=("Segoe UI", 12))
        self.message.pack(pady=5)

        # bottom row: "No account yet?" + switch link
        bottom = ctk.CTkFrame(form, fg_color="transparent")
        bottom.pack(pady=5)

        self.switch_label = ctk.CTkLabel(
            bottom, text="No account yet?", font=("Segoe UI", 12),
            text_color=GRAY,
        )
        self.switch_label.pack(side="left")

        self.switch_button = ctk.CTkButton(
            bottom, text="Register", width=60, fg_color="transparent",
            hover_color=BG, text_color=RED, font=("Segoe UI", 12, "bold"),
            command=self.switch_mode,
        )
        self.switch_button.pack(side="left")

    def make_confirm_entry(self):
        # made again every time so the placeholder text always comes back
        if self.show_check_state() == 1:
            char = ""
        else:
            char = "*"
        self.confirm_entry = ctk.CTkEntry(
            self.form, placeholder_text="Confirm password", show=char,
            width=300, height=42, fg_color=FIELD, border_width=0,
        )
        self.confirm_entry.bind("<Return>", lambda event: self.submit())

    def show_check_state(self):
        # the checkbox does not exist yet the first time this is called
        if hasattr(self, "show_check"):
            return self.show_check.get()
        return 0

    def toggle_password(self):
        if self.show_check.get() == 1:
            char = ""
        else:
            char = "*"
        self.password_entry.configure(show=char)
        self.confirm_entry.configure(show=char)

    def button_text(self):
        if self.mode == "login":
            return "Login"
        return "Register"

    def switch_mode(self):
        self.message.configure(text="")

        if self.mode == "login":
            self.mode = "register"
            self.heading.configure(text="Create Account")
            self.subtitle.configure(text="Sign up to start exploring.")
            self.main_button.configure(text="Register")
            self.switch_label.configure(text="Already have an account?")
            self.switch_button.configure(text="Login", width=45)
            self.confirm_entry.pack(pady=7, before=self.show_check)
        else:
            self.mode = "login"
            self.heading.configure(text="Sign In")
            self.subtitle.configure(text="Welcome back! Please log in.")
            self.main_button.configure(text="Login")
            self.switch_label.configure(text="No account yet?")
            self.switch_button.configure(text="Register", width=60)
            self.confirm_entry.destroy()
            self.make_confirm_entry()

    def submit(self):
        # ignore clicks while the last one is still being checked
        if self.main_button.cget("state") == "disabled":
            return

        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if username == "" or password == "":
            self.show_message("Please fill in all fields.", False)
            return

        if self.mode == "register":
            if password != self.confirm_entry.get():
                self.show_message("Passwords do not match.", False)
                return

        # hashing takes a moment, so show that something is happening
        self.main_button.configure(state="disabled", text="Please wait...")
        self.update_idletasks()

        if self.mode == "login":
            ok, msg, name = auth.login(username, password)
        else:
            ok, msg = auth.register(username, password)

        self.main_button.configure(state="normal", text=self.button_text())

        if self.mode == "login":
            if ok:
                # this screen gets destroyed, so the password is gone too
                self.on_login(name)
                return
            self.show_message(msg, False)
        else:
            if ok:
                # go back to the login view after a successful register
                self.switch_mode()
            self.show_message(msg, ok)

    def show_message(self, text, success):
        if success:
            color = GREEN
        else:
            color = ERROR
        self.message.configure(text=text, text_color=color)
