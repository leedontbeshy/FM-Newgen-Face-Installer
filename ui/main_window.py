import logging
import queue
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from tkinter import StringVar, filedialog

import customtkinter as ctk

from core.image_manager import preview_image
from core.installer import FaceInstaller
from core.settings_manager import SettingsManager, downloads_folder
from core.validation import ValidationError, validate_player_id
from ui.dialogs import confirm
from ui.settings_window import SettingsWindow


class MainWindow(ctk.CTk):
    def __init__(self, settings_manager=None, *, prompt_on_start=True):
        super().__init__()
        self.title("FM Newgen Face Installer")
        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)
        scale = self._get_window_scaling()
        fit = min(
            1.0,
            (self.winfo_screenheight() - 100) / (760 * scale),
            (self.winfo_screenwidth() - 80) / (680 * scale),
        )
        ctk.set_widget_scaling(fit)
        ctk.set_window_scaling(fit)
        self.geometry("680x760+30+30")
        self.minsize(540, 560)
        self.configure(fg_color="#131d23")
        self.manager = settings_manager or SettingsManager()
        self.settings = self.manager.load()
        self.selected_image = None
        self.preview = None
        self.busy = False
        self._closing = False
        self._settings_window = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="face-installer")
        self.results = queue.Queue()
        self.player_id = StringVar()
        self.player_type = StringVar(value="Newgen (FM24)")
        self._build()
        self.player_id.trace_add("write", lambda *args: self._update_actions())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Control-o>", lambda event: self.select_image() if not self.busy else None)
        self.bind("<Control-Return>", lambda event: self.install() if self._can_install() else None)
        self._update_folder()
        self._update_actions()
        self._poll_id = self.after(60, self._poll)
        if self.manager.warning:
            self.set_status(self.manager.warning, "error")
        if prompt_on_start and not self.settings.face_folder:
            self.after(180, self.choose_folder)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 16))
        ctk.CTkLabel(
            header,
            text="FOOTBALL MANAGER 2024",
            font=("Segoe UI", 11, "bold"),
            text_color="#5fbea0",
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(header, text="FM Newgen Face Installer", font=("Segoe UI", 26, "bold"), anchor="w").pack(
            fill="x", pady=(2, 4)
        )
        ctk.CTkLabel(
            header, text="Choose a player. Pick a face. Install.", text_color="#9aaeb6", anchor="w"
        ).pack(fill="x")

        # On small/high-DPI displays the form scrolls, while status/settings stay
        # visible. Large displays show the complete form without scrolling.
        card = ctk.CTkScrollableFrame(
            self, fg_color="#1c2931", corner_radius=12, scrollbar_button_color="#354b58"
        )
        card.grid(row=1, column=0, sticky="nsew", padx=28)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="Player Unique ID", font=("Segoe UI", 14, "bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=22, pady=(19, 6)
        )
        self.id_entry = ctk.CTkEntry(
            card,
            textvariable=self.player_id,
            height=42,
            font=("Segoe UI", 17),
            fg_color="#131d23",
            border_color="#3a505b",
        )
        self.id_entry.grid(row=1, column=0, sticky="ew", padx=22)
        self.id_hint = ctk.CTkLabel(
            card,
            text="Enter the player's in-game Unique ID (digits only).",
            anchor="w",
            text_color="#9aaeb6",
            font=("Segoe UI", 12),
        )
        self.id_hint.grid(row=2, column=0, sticky="ew", padx=22, pady=(3, 12))

        type_row = ctk.CTkFrame(card, fg_color="transparent")
        type_row.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 12))
        ctk.CTkLabel(type_row, text="Player type", font=("Segoe UI", 13)).pack(side="left")
        self.type_menu = ctk.CTkOptionMenu(
            type_row,
            variable=self.player_type,
            values=["Newgen (FM24)", "Real player"],
            width=190,
            command=lambda value: self._update_actions(),
        )
        self.type_menu.pack(side="right")

        image_row = ctk.CTkFrame(card, fg_color="transparent")
        image_row.grid(row=4, column=0, sticky="ew", padx=22)
        ctk.CTkLabel(image_row, text="Face Image", font=("Segoe UI", 14, "bold")).pack(side="left")
        self.select_button = ctk.CTkButton(
            image_row,
            text="Select Image",
            command=self.select_image,
            width=126,
            fg_color="#354b58",
            hover_color="#425e6d",
        )
        self.select_button.pack(side="right")

        preview_frame = ctk.CTkFrame(card, fg_color="#131d23", height=160, corner_radius=8)
        preview_frame.grid(row=5, column=0, sticky="ew", padx=22, pady=(10, 14))
        preview_frame.grid_propagate(False)
        preview_frame.grid_columnconfigure(1, weight=1)
        preview_frame.grid_rowconfigure(0, weight=1)
        self.preview_label = ctk.CTkLabel(
            preview_frame,
            text="Image\npreview",
            width=160,
            text_color="#7f96a0",
            fg_color="#202f37",
            corner_radius=8,
        )
        self.preview_label.grid(row=0, column=0, padx=12, pady=12, sticky="ns")
        details = ctk.CTkFrame(preview_frame, fg_color="transparent")
        details.grid(row=0, column=1, sticky="ew", padx=(4, 16))
        self.filename_label = ctk.CTkLabel(
            details,
            text="No image selected",
            anchor="w",
            justify="left",
            wraplength=290,
            font=("Segoe UI", 14, "bold"),
        )
        self.filename_label.pack(fill="x")
        self.image_details = ctk.CTkLabel(
            details,
            text="PNG, JPG, JPEG or WEBP\nOriginal size and transparency kept",
            text_color="#9aaeb6",
            anchor="w",
            justify="left",
            wraplength=270,
            font=("Segoe UI", 12),
        )
        self.image_details.pack(fill="x", pady=(5, 0))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=6, column=0, sticky="ew", padx=22, pady=(0, 18))
        actions.grid_columnconfigure(0, weight=1)
        self.install_button = ctk.CTkButton(
            actions,
            text="Install Face",
            height=43,
            command=self.install,
            fg_color="#167a62",
            hover_color="#12634f",
            font=("Segoe UI", 15, "bold"),
        )
        self.install_button.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.remove_button = ctk.CTkButton(
            actions,
            text="Remove Face",
            height=43,
            width=135,
            command=self.remove,
            fg_color="transparent",
            border_width=1,
            border_color="#725058",
            hover_color="#453039",
            text_color="#edb1b5",
        )
        self.remove_button.grid(row=0, column=2)
        self.fix_button = ctk.CTkButton(
            actions,
            text="Fix Mapping",
            height=43,
            width=125,
            command=self.repair_mapping,
            fg_color="#354b58",
            hover_color="#425e6d",
        )
        self.fix_button.grid(row=0, column=1, padx=(0, 12))

        self.progress = ctk.CTkProgressBar(self, height=3, mode="determinate", progress_color="#5fbea0")
        self.progress.grid(row=2, column=0, sticky="ew", padx=28, pady=(14, 0))
        self.progress.set(0)
        self.status_label = ctk.CTkLabel(
            self,
            text="Ready. Select a face image to get started.",
            anchor="w",
            justify="left",
            wraplength=615,
            height=84,
            text_color="#9aaeb6",
            font=("Segoe UI", 13),
        )
        self.status_label.grid(row=3, column=0, sticky="ew", padx=30, pady=(8, 2))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=28, pady=(4, 20))
        footer.grid_columnconfigure(0, weight=1)
        self.folder_label = ctk.CTkLabel(
            footer,
            text="",
            anchor="w",
            justify="left",
            wraplength=465,
            text_color="#9aaeb6",
            font=("Segoe UI", 11),
        )
        self.folder_label.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.settings_button = ctk.CTkButton(
            footer,
            text="Settings",
            width=90,
            command=self.open_settings,
            fg_color="#293943",
            hover_color="#354b58",
        )
        self.settings_button.grid(row=0, column=1)

    def set_status(self, message, kind="info"):
        color = {"error": "#ef9da5", "success": "#76d8b1", "info": "#9aaeb6"}[kind]
        self.status_label.configure(text=message, text_color=color)

    def _valid_id(self):
        try:
            validate_player_id(self.player_id.get())
            return True
        except ValidationError:
            return False

    def _can_install(self):
        return not self.busy and self._valid_id() and bool(self.settings.face_folder and self.selected_image)

    def _update_actions(self):
        valid = self._valid_id()
        self.install_button.configure(state="normal" if self._can_install() else "disabled")
        self.remove_button.configure(
            state="normal" if not self.busy and valid and self.settings.face_folder else "disabled"
        )
        self.fix_button.configure(
            state="normal"
            if not self.busy
            and valid
            and self.settings.face_folder
            and self.player_type.get() == "Newgen (FM24)"
            else "disabled"
        )
        self.type_menu.configure(state="disabled" if self.busy else "normal")
        for button in (self.select_button, self.settings_button):
            button.configure(state="disabled" if self.busy else "normal")
        self.id_entry.configure(state="disabled" if self.busy else "normal")
        invalid = bool(self.player_id.get().strip()) and not valid
        self.id_hint.configure(
            text="Invalid Player ID — use digits 0–9 only."
            if invalid
            else "Enter the player's in-game Unique ID (digits only).",
            text_color="#ef9da5" if invalid else "#9aaeb6",
        )

    def _update_folder(self):
        self.folder_label.configure(
            text="Face folder\n" + (self.settings.face_folder or "Choose a folder in Settings")
        )

    def choose_folder(self, dialog_parent=None):
        if self.busy:
            return
        initial = self.settings.face_folder or str(Path.home() / "Documents")
        path = filedialog.askdirectory(
            parent=dialog_parent or self,
            title="Choose your Football Manager custom face folder",
            initialdir=initial,
            mustexist=True,
        )
        if not path:
            if not self.settings.face_folder:
                self.set_status("Choose your Custom Face Folder in Settings to enable installation.")
            return
        updated = replace(self.settings, face_folder=str(Path(path).resolve()))
        try:
            self.manager.save(updated)
        except OSError as error:
            self.set_status(f"Could not save folder setting: {error}", "error")
            return
        self.settings = updated
        self._update_folder()
        self._update_actions()
        self.set_status("Face folder saved. Select a player ID and image.")

    def select_image(self):
        if self.busy:
            return
        initial = (
            Path(self.settings.last_image_folder) if self.settings.last_image_folder else downloads_folder()
        )
        if not initial.is_dir():
            initial = Path.home()
        selected = filedialog.askopenfilename(
            parent=self,
            title="Select Face Image",
            initialdir=str(initial),
            filetypes=[
                ("Face images", "*.png *.jpg *.jpeg *.webp"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("WEBP", "*.webp"),
            ],
        )
        if selected:
            self.load_selected(Path(selected))

    def load_selected(self, path):
        path = Path(path)
        # An invalid new selection must never leave a previous image installable.
        self.selected_image = None
        self.preview_label.configure(image=None, text="Loading…")
        self.filename_label.configure(text=path.name)
        self._run(
            lambda: preview_image(path, (140, 136)),
            lambda result: self._selected(path, result),
            "Reading face image…",
        )

    def _selected(self, path, result):
        image, dimensions = result
        self.selected_image = path
        self.preview = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        self.preview_label.configure(image=self.preview, text="")
        self.filename_label.configure(text=path.name)
        self.image_details.configure(
            text=f"{dimensions[0]} × {dimensions[1]} px\nWill be installed as <Player ID>.png"
        )
        updated = replace(self.settings, last_image_folder=str(path.parent))
        try:
            self.manager.save(updated)
            self.settings = updated
            self.set_status("Image ready. Enter the Player Unique ID, then install.")
        except OSError as error:
            self.set_status(f"Image ready, but its folder could not be remembered: {error}", "error")
        self._update_actions()

    def install(self):
        if not self._can_install():
            return
        installer = FaceInstaller(self.settings.face_folder, newgen=self.player_type.get() == "Newgen (FM24)")
        player_id, source = self.player_id.get(), self.selected_image
        self._run(
            lambda: installer.prepare_install(player_id, source),
            lambda plan: self._review(installer, plan),
            "Checking the image and config mapping…",
        )

    def remove(self):
        if self.busy or not self._valid_id() or not self.settings.face_folder:
            return
        installer = FaceInstaller(self.settings.face_folder, newgen=self.player_type.get() == "Newgen (FM24)")
        player_id = self.player_id.get()
        self._run(
            lambda: installer.prepare_remove(player_id),
            lambda plan: self._review(installer, plan),
            "Checking the face and config mapping…",
        )

    def _review(self, installer, plan):
        if (
            plan.action == "install"
            and plan.newgen
            and plan.mapping_exists
            and (plan.mapping_target == installer.config.portrait_target(plan.player_id))
        ):
            self.set_status(
                "This newgen has a real-player mapping. Click Fix Mapping first.\nNo files were changed.",
                "error",
            )
            return
        confirmed = False
        if plan.needs_confirmation:
            action = {"remove": "Remove Face", "repair": "Fix Mapping", "install": "Replace Face"}[
                plan.action
            ]
            confirmed = confirm(self, plan.confirmation, action, destructive=plan.action == "remove")
            if not confirmed:
                self.set_status("Cancelled. No files were changed.")
                return
        self._run(
            lambda: installer.execute(plan, confirmed=confirmed),
            lambda result: self.set_status(
                result.message, "success" if result.kind not in {"nothing", "cancelled"} else "info"
            ),
            {
                "install": "Installing face…",
                "remove": "Removing face…",
                "repair": "Fixing the newgen mapping…",
            }[plan.action],
        )

    def repair_mapping(self):
        if (
            self.busy
            or not self._valid_id()
            or not self.settings.face_folder
            or self.player_type.get() != "Newgen (FM24)"
        ):
            return
        installer = FaceInstaller(self.settings.face_folder, newgen=True)
        player_id = self.player_id.get()
        self._run(
            lambda: installer.prepare_repair(player_id),
            lambda plan: self._review(installer, plan),
            "Checking the FM24 newgen mapping…",
        )

    def _run(self, operation, on_success, message):
        self.busy = True
        self._update_actions()
        self.set_status(message)
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        future = self.executor.submit(operation)
        future.add_done_callback(lambda done: self.results.put((done, on_success)))

    def _poll(self):
        try:
            while True:
                future, callback = self.results.get_nowait()
                self.busy = False
                self.progress.stop()
                self.progress.configure(mode="determinate")
                self.progress.set(0)
                self._update_actions()
                try:
                    value = future.result()
                    callback(value)
                except Exception as error:
                    logging.exception("Face operation failed")
                    self.set_status(f"✗ {error}", "error")
        except queue.Empty:
            pass
        if not self._closing:
            self._poll_id = self.after(60, self._poll)

    def open_settings(self):
        if self.busy:
            return
        if self._settings_window is None or not self._settings_window.winfo_exists():
            self._settings_window = SettingsWindow(self)
        else:
            self._settings_window.focus()

    def _close(self):
        if self.busy:
            self.set_status("Please wait for the current operation to finish before closing.")
            return
        self._closing = True
        # Includes CustomTkinter's scaling/theme timers and child-window timers.
        for callback in self.tk.splitlist(self.tk.call("after", "info")):
            self.after_cancel(callback)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.destroy()
