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
from ui.layout import initial_size
from ui.preview import PreviewLabel
from ui.settings_window import SettingsWindow


class MainWindow(ctk.CTk):
    def __init__(self, settings_manager=None, *, prompt_on_start=True):
        super().__init__()
        self.title("FM Newgen Face Installer")
        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)
        width, height = initial_size(self)
        self.geometry(f"{width}x{height}+24+24")
        self.minsize(min(560, width), min(480, height))
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
        self.player_id = StringVar(master=self)
        self.player_type = StringVar(master=self, value="Newgen (FM24)")
        self._layout_id = None
        self._ui_scale = None
        self._wide_layout = None
        self._fonts = []
        self._build()
        self.bind("<Configure>", self._schedule_layout, add="+")
        self.after_idle(self._apply_layout)
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
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(18, 12))
        ctk.CTkLabel(
            header,
            text="FOOTBALL MANAGER 2024",
            font=self._font(12, "bold"),
            text_color="#5fbea0",
            anchor="w",
            height=20,
        ).pack(fill="x")
        ctk.CTkLabel(
            header, text="FM Newgen Face Installer", font=self._font(30, "bold"), anchor="w", height=38
        ).pack(fill="x", pady=(2, 4))
        ctk.CTkLabel(
            header,
            text="Choose a player. Pick a face. Install.",
            text_color="#9aaeb6",
            anchor="w",
            font=self._font(16),
            height=24,
        ).pack(fill="x")

        # On small/high-DPI displays the form scrolls, while status/settings stay
        # visible. Large displays show the complete form without scrolling.
        self.card = ctk.CTkScrollableFrame(
            self, fg_color="#1c2931", corner_radius=12, scrollbar_button_color="#354b58"
        )
        self.card.grid(row=1, column=0, sticky="nsew", padx=28)
        self.card.grid_columnconfigure(0, weight=1, uniform="panels")
        self.card.grid_columnconfigure(1, weight=1, uniform="panels")
        card = self.form = ctk.CTkFrame(self.card, fg_color="transparent")
        card.grid(row=0, column=0, sticky="new", pady=12)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="Player Unique ID", font=self._font(18, "bold"), anchor="w", height=24).grid(
            row=0, column=0, sticky="ew", padx=22, pady=(10, 6)
        )
        self.id_entry = ctk.CTkEntry(
            card,
            textvariable=self.player_id,
            height=52,
            font=self._font(23),
            fg_color="#131d23",
            border_color="#3a505b",
        )
        self.id_entry.grid(row=1, column=0, sticky="ew", padx=22)
        self.id_hint = ctk.CTkLabel(
            card,
            text="Enter the player's in-game Unique ID (digits only).",
            anchor="w",
            text_color="#9aaeb6",
            font=self._font(14),
            justify="left",
            height=22,
        )
        self.id_hint.grid(row=2, column=0, sticky="ew", padx=22, pady=(3, 10))

        type_row = ctk.CTkFrame(card, fg_color="transparent")
        type_row.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 12))
        ctk.CTkLabel(type_row, text="Player type", font=self._font(16), height=22).pack(
            anchor="w", pady=(0, 6)
        )
        self.type_menu = ctk.CTkOptionMenu(
            type_row,
            variable=self.player_type,
            values=["Newgen (FM24)", "Real player"],
            width=190,
            height=42,
            font=self._font(16),
            dropdown_font=self._font(16),
            command=lambda value: self._update_actions(),
        )
        self.type_menu.pack(fill="x")

        image_row = ctk.CTkFrame(card, fg_color="transparent")
        image_row.grid(row=4, column=0, sticky="ew", padx=22)
        ctk.CTkLabel(image_row, text="Face Image", font=self._font(18, "bold"), height=24).pack(
            anchor="w", pady=(0, 6)
        )
        self.select_button = ctk.CTkButton(
            image_row,
            text="Select Image",
            command=self.select_image,
            width=126,
            height=46,
            font=self._font(16),
            fg_color="#354b58",
            hover_color="#425e6d",
        )
        self.select_button.pack(fill="x")

        preview_frame = self.preview_frame = ctk.CTkFrame(
            self.card, fg_color="#131d23", height=360, corner_radius=8
        )
        preview_frame.grid(row=0, column=1, sticky="new", padx=(4, 18), pady=18)
        preview_frame.grid_propagate(False)
        preview_frame.grid_columnconfigure(0, weight=1)
        preview_frame.grid_rowconfigure(0, weight=1)
        self.preview_label = PreviewLabel(
            preview_frame,
            text="Image\npreview",
            width=200,
            font=self._font(18),
            text_color="#7f96a0",
            fg_color="#202f37",
            corner_radius=8,
        )
        self.preview_label.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        details = self.details = ctk.CTkFrame(card, fg_color="transparent")
        details.grid(row=5, column=0, sticky="ew", padx=22, pady=(10, 12))
        self.filename_label = ctk.CTkLabel(
            details,
            text="No image selected",
            anchor="w",
            justify="left",
            wraplength=290,
            font=self._font(16, "bold"),
        )
        self.filename_label.pack(fill="x")
        self.image_details = ctk.CTkLabel(
            details,
            text="PNG, JPG, JPEG or WEBP\nOriginal size and transparency kept",
            text_color="#9aaeb6",
            anchor="w",
            justify="left",
            wraplength=270,
            font=self._font(14),
        )
        self.image_details.pack(fill="x", pady=(5, 0))

        actions = self.actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=28, pady=(16, 0))
        actions.grid_columnconfigure((0, 1, 2), weight=1, uniform="actions")
        self.install_button = ctk.CTkButton(
            actions,
            text="Install Face",
            height=50,
            command=self.install,
            fg_color="#167a62",
            hover_color="#12634f",
            font=self._font(17, "bold"),
        )
        self.install_button.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.remove_button = ctk.CTkButton(
            actions,
            text="Remove Face",
            height=50,
            width=135,
            command=self.remove,
            fg_color="transparent",
            border_width=1,
            border_color="#725058",
            hover_color="#453039",
            text_color="#edb1b5",
            font=self._font(16),
        )
        self.remove_button.grid(row=0, column=2, sticky="ew")
        self.fix_button = ctk.CTkButton(
            actions,
            text="Fix Mapping",
            height=50,
            width=125,
            command=self.repair_mapping,
            fg_color="#354b58",
            hover_color="#425e6d",
            font=self._font(16),
        )
        self.fix_button.grid(row=0, column=1, padx=(0, 12), sticky="ew")

        self.progress = ctk.CTkProgressBar(self, height=3, mode="determinate", progress_color="#5fbea0")
        self.progress.grid(row=3, column=0, sticky="ew", padx=28, pady=(14, 0))
        self.progress.set(0)
        self.status_label = ctk.CTkLabel(
            self,
            text="Ready. Select a face image to get started.",
            anchor="w",
            justify="left",
            wraplength=615,
            height=76,
            text_color="#9aaeb6",
            font=self._font(15),
        )
        self.status_label.grid(row=4, column=0, sticky="ew", padx=30, pady=(8, 2))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=5, column=0, sticky="ew", padx=28, pady=(4, 20))
        footer.grid_columnconfigure(0, weight=1)
        self.folder_label = ctk.CTkLabel(
            footer,
            text="",
            anchor="w",
            justify="left",
            wraplength=465,
            text_color="#9aaeb6",
            font=self._font(14),
        )
        self.folder_label.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.settings_button = ctk.CTkButton(
            footer,
            text="Settings",
            command=self.open_settings,
            fg_color="#293943",
            hover_color="#354b58",
            height=40,
            width=110,
            font=self._font(15),
        )
        self.settings_button.grid(row=0, column=1)

    def _font(self, size, weight="normal"):
        font = ctk.CTkFont(family="Segoe UI", size=size, weight=weight)
        self._fonts.append((font, size))
        return font

    def _schedule_layout(self, event):
        if event.widget is not self or self._closing:
            return
        if self._layout_id is not None:
            self.after_cancel(self._layout_id)
        self._layout_id = self.after(100, self._apply_layout)

    def _apply_layout(self):
        self._layout_id = None
        if self._closing:
            return
        width = self.winfo_width() / self._get_window_scaling()
        height = self.winfo_height() / self._get_window_scaling()
        # Enlarge text on spacious windows, but keep a wide, short desktop from
        # spending all its vertical space on oversized controls.
        scale = min(1.4, max(1.0, round(width / 880 * 20) / 20), max(1.0, round(height / 740 * 20) / 20))
        if scale != self._ui_scale:
            self._ui_scale = scale
            for font, base_size in self._fonts:
                font.configure(size=round(base_size * scale))
            self.id_entry.configure(height=round(52 * scale))
            self.type_menu.configure(height=round(42 * scale))
            self.select_button.configure(height=round(46 * scale))
            for button in (self.install_button, self.fix_button, self.remove_button):
                button.configure(height=round(50 * scale))
            self.preview_frame.configure(height=round(360 * scale))
        wide = width >= 760
        if wide != self._wide_layout:
            self._wide_layout = wide
            self.form.grid_configure(columnspan=1 if wide else 2)
            self.preview_frame.grid_configure(
                row=0 if wide else 1,
                column=1 if wide else 0,
                columnspan=1 if wide else 2,
                padx=(4, 18) if wide else 22,
                pady=18 if wide else (0, 20),
            )
            self.actions.grid_columnconfigure(2, weight=1 if wide else 0, uniform="actions" if wide else "")
            self.install_button.grid_configure(
                row=0,
                column=0,
                columnspan=1 if wide else 2,
                padx=(0, 12) if wide else 0,
                pady=0 if wide else (0, 8),
            )
            self.fix_button.grid_configure(row=0 if wide else 1, column=1 if wide else 0)
            self.remove_button.grid_configure(row=0 if wide else 1, column=2 if wide else 1)
        self.status_label.configure(wraplength=max(220, int(width - 64)))
        self.folder_label.configure(wraplength=max(160, int(width - 200 * scale)))
        viewport_height = self.grid_bbox(0, 1)[3] / self._get_window_scaling()
        preview_height = min(360 * scale, max(220, viewport_height - 52)) if wide else 320
        self.preview_frame.configure(height=round(preview_height))
        self.after(40, self._fit_preview_and_text)

    def _fit_preview_and_text(self):
        if self._closing:
            return
        scale = self.preview_label._get_widget_scaling()
        text_width = max(140, int(self.form.winfo_width() / scale - 48))
        for label in (self.id_hint, self.filename_label, self.image_details):
            label.configure(wraplength=text_width)
        if self.preview is not None:
            image = self.preview.cget("dark_image")
            width = max(80, self.preview_frame.winfo_width() / scale - 48)
            height = max(80, self.preview_frame.winfo_height() / scale - 48)
            ratio = min(width / image.width, height / image.height)
            size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
            if self.preview.cget("size") != size:
                self.preview.configure(size=size)

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
        self.preview = None
        self.filename_label.configure(text=path.name)
        self._run(
            lambda: preview_image(path, (900, 900)),
            lambda result: self._selected(path, result),
            "Reading face image…",
        )

    def _selected(self, path, result):
        image, dimensions = result
        preview = ctk.CTkImage(light_image=image, dark_image=image, size=(1, 1))
        # Keep the previous preview alive until Tk has accepted its replacement.
        self.preview_label.configure(image=preview, text="")
        self.preview = preview
        self.selected_image = path
        self._fit_preview_and_text()
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
