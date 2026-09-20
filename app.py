"""Windows entry point (also used by the PyInstaller build)."""

import logging
from logging.handlers import RotatingFileHandler

import customtkinter as ctk

from core.settings_manager import settings_path
from ui.main_window import MainWindow


def main():
    try:
        folder = settings_path().parent
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / "app.log", maxBytes=512_000, backupCount=1, encoding="utf-8")
        logging.basicConfig(
            level=logging.WARNING, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s"
        )
    except OSError:
        logging.basicConfig(level=logging.WARNING, handlers=[logging.NullHandler()])
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
