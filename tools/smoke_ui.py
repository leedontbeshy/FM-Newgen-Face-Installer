"""Exercise the real Tk event loop with isolated files and scripted dialogs.

Optional screenshots capture only the application's window for visual QA.
No game folders, real settings, or user downloads are modified.
"""

import argparse
import hashlib
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
from PIL import Image, ImageGrab

from core.config_manager import ConfigManager
from core.settings_manager import SettingsManager
from ui.main_window import MainWindow


def pump(app, condition=lambda: True, timeout=15):
    deadline = time.monotonic() + timeout
    # Do not treat the brief gap between worker stages as completion.
    stable = 0
    while time.monotonic() < deadline:
        app.update()
        if condition():
            stable += 1
            if stable > 8:
                return
        else:
            stable = 0
        time.sleep(0.02)
    raise TimeoutError("UI smoke test timed out")


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def answer_dialog(app, label):
    """Press a real CustomTkinter dialog button through its widget command."""

    def visit(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton) and child.cget("text") == label:
                child.invoke()
                return True
            if visit(child):
                return True
        return False

    def click():
        for child in app.winfo_children():
            if isinstance(child, ctk.CTkToplevel) and visit(child):
                return
        app.after(100, click)

    app.after(300, click)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args()
    ctk.set_appearance_mode("dark")
    with tempfile.TemporaryDirectory(prefix="fm-ui-smoke-") as directory:
        base = Path(directory)
        faces = base / "Custom Faces"
        faces.mkdir()
        source = base / "test-face.webp"
        Image.new("RGBA", (180, 240), (78, 139, 111, 160)).save(source, lossless=True)
        manager = SettingsManager(base / "settings.json")
        app = MainWindow(manager, prompt_on_start=False)
        try:
            with patch("ui.main_window.filedialog.askdirectory", return_value=str(faces)):
                app.choose_folder()
            # Windows runners can expose TEMP through an 8.3 path alias while
            # the app saves the resolved long path. Compare folder identity.
            assert Path(manager.load().face_folder).samefile(faces)
            assert app.install_button.cget("state") == "disabled"
            app.player_id.set("bad/id")
            assert app.remove_button.cget("state") == "disabled"
            app.player_id.set("2002999999")
            with patch("ui.main_window.filedialog.askopenfilename", return_value=str(source)):
                app.select_image()
            pump(app, lambda: not app.busy)
            assert app.selected_image == source and app.preview is not None
            assert app.install_button.cget("state") == "normal"
            app.install_button.invoke()
            pump(app, lambda: not app.busy)
            config = faces / "config.xml"
            image = faces / "2002999999.png"
            assert image.exists() and ConfigManager(config).mapping_exists("2002999999")
            assert (
                ConfigManager(config).mapping_target("2002999999")
                == "graphics/pictures/person/r-2002999999/portrait"
            )
            original_config, stamp = file_hash(config), config.stat().st_mtime_ns
            original_image = file_hash(image)
            answer_dialog(app, "Cancel")
            app.install()
            pump(app, lambda: not app.busy)
            assert file_hash(image) == original_image and file_hash(config) == original_config
            answer_dialog(app, "Replace Face")
            app.install()
            pump(app, lambda: not app.busy)
            assert file_hash(config) == original_config and config.stat().st_mtime_ns == stamp
            image.unlink()
            with patch("ui.main_window.confirm", side_effect=AssertionError("Restore must not ask")):
                app.install()
                pump(app, lambda: not app.busy)
            assert image.exists()
            # Simulate an existing mapping produced by the original app, then
            # exercise cancellation and the real explicit repair dialog.
            correct = config.read_bytes()
            legacy = correct.replace(b"person/r-2002999999/", b"person/2002999999/")
            config.write_bytes(legacy)
            image_before_repair = file_hash(image)
            app.install()
            pump(app, lambda: not app.busy)
            assert "Fix Mapping" in app.status_label.cget("text")
            assert config.read_bytes() == legacy
            answer_dialog(app, "Cancel")
            app.repair_mapping()
            pump(app, lambda: not app.busy)
            assert config.read_bytes() == legacy
            answer_dialog(app, "Fix Mapping")
            app.repair_mapping()
            pump(app, lambda: not app.busy)
            assert config.read_bytes() == correct and file_hash(image) == image_before_repair
            if args.screenshot:
                # Publishable screenshot: display a fictional folder, never the
                # machine's account name or temporary directory path.
                app.folder_label.configure(
                    text="Face folder\nC:\\Football Manager 2024\\graphics\\Custom Faces"
                )
                pump(app)
                app.update()
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                # Capture our HWND directly; other desktop windows may cover it.
                ImageGrab.grab(window=app.winfo_id()).save(args.screenshot)
            app.open_settings()
            pump(app)
            assert app._settings_window.winfo_exists()
            app._settings_window.destroy()
            answer_dialog(app, "Remove Face")
            app.remove()
            pump(app, lambda: not app.busy)
            assert not image.exists() and not ConfigManager(config).mapping_exists("2002999999")
            app.remove()
            pump(app, lambda: not app.busy)
            assert "Nothing to remove" in app.status_label.cget("text")
            app.player_type.set("Real player")
            app._update_actions()
            assert app.fix_button.cget("state") == "disabled"
            app.player_id.set("12345")
            app.install()
            pump(app, lambda: not app.busy)
            assert ConfigManager(config).mapping_target("12345") == "graphics/pictures/person/12345/portrait"
        finally:
            app.executor.shutdown(wait=True)
            app.busy = False
            app._close()
        # A second launch remembers the folder and never reopens its chooser.
        with patch(
            "ui.main_window.filedialog.askdirectory",
            side_effect=AssertionError("Folder should be remembered"),
        ):
            app = MainWindow(manager)
            pump(app)
            assert Path(app.settings.face_folder).samefile(faces)
            app._close()
    print(
        "UI SMOKE PASSED: folder, preview, validation, install, cancel, replace, restore, explicit repair, player type, settings, remove, relaunch"
    )


if __name__ == "__main__":
    main()
