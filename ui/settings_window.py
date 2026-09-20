import os
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Settings · FM Newgen Face Installer")
        self.geometry("580x310")
        self.minsize(480, 300)
        self.transient(parent)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Custom Face Folder", font=("Segoe UI", 21, "bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=26, pady=(24, 8)
        )
        ctk.CTkLabel(self, text="Current Face Folder", anchor="w", text_color="#9aaeb6").grid(
            row=1, column=0, sticky="ew", padx=26
        )
        self.path_box = ctk.CTkTextbox(self, height=64, wrap="word")
        self.path_box.grid(row=2, column=0, sticky="ew", padx=26, pady=(6, 18))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=3, column=0, sticky="ew", padx=26)
        ctk.CTkButton(row, text="Change Folder", command=self.change).pack(side="left")
        self.open_button = ctk.CTkButton(
            row, text="Open Face Folder", command=self.open_folder, fg_color="#35434a", hover_color="#42545c"
        )
        self.open_button.pack(side="left", padx=10)
        ctk.CTkLabel(
            self,
            text="Your folder choice is saved locally on this computer.",
            text_color="#9aaeb6",
            anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=26, pady=18)
        self.refresh()
        self.after(80, self.grab_set)

    def refresh(self):
        path = self.parent.settings.face_folder
        self.path_box.configure(state="normal")
        self.path_box.delete("1.0", "end")
        self.path_box.insert("1.0", path or "No folder selected")
        self.path_box.configure(state="disabled")
        self.open_button.configure(state="normal" if path else "disabled")

    def change(self):
        self.parent.choose_folder(dialog_parent=self)
        self.refresh()

    def open_folder(self):
        path = Path(self.parent.settings.face_folder)
        try:
            if not path.is_dir():
                raise OSError("The selected folder no longer exists.")
            os.startfile(path)
        except OSError as error:
            messagebox.showerror("Could not open folder", str(error), parent=self)
