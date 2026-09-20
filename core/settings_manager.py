"""Atomic local JSON settings; never stored in the Football Manager folder."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from core.filesystem import flush_file, temporary_path


def downloads_folder() -> Path:
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
            return Path(os.path.expandvars(value))
        except OSError:
            pass
    return Path.home() / "Downloads"


def settings_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return base / "FM Newgen Face Installer" / "settings.json"


@dataclass
class Settings:
    face_folder: str = ""
    last_image_folder: str = ""


class SettingsManager:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else settings_path()
        self.warning = ""

    def load(self) -> Settings:
        self.warning = ""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Expected an object")
            fields = {key: data.get(key, "") for key in ("face_folder", "last_image_folder")}
            if any(not isinstance(value, str) for value in fields.values()):
                raise ValueError("Settings paths must be text")
            return Settings(**fields)
        except FileNotFoundError:
            return Settings()
        except (OSError, ValueError) as error:
            self.warning = f"Could not read saved settings: {error}\nChoose your face folder again."
            return Settings()

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = temporary_path(self.path.parent, ".settings.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(asdict(settings), stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                flush_file(stream)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
