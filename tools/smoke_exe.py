"""Launch and close the built Windows executable with isolated local settings."""

import argparse
import ctypes
import json
import os
import subprocess
import tempfile
import time
from ctypes import wintypes
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    args = parser.parse_args()
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    with tempfile.TemporaryDirectory(prefix="fm-exe-smoke-") as directory:
        root = Path(directory)
        faces = root / "Custom Faces"
        faces.mkdir()
        local = root / "LocalAppData"
        setting_dir = local / "FM Newgen Face Installer"
        setting_dir.mkdir(parents=True)
        (setting_dir / "settings.json").write_text(json.dumps({"face_folder": str(faces)}), encoding="utf-8")
        env = dict(os.environ, LOCALAPPDATA=str(local))
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0  # a background test must not steal desktop focus
        process = subprocess.Popen([str(args.exe.resolve())], env=env, startupinfo=startup)
        windows = []

        @callback_type
        def enum_window(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == process.pid:
                title = ctypes.create_unicode_buffer(300)
                user32.GetWindowTextW(hwnd, title, 300)
                if title.value == "FM Newgen Face Installer":
                    windows.append(hwnd)
            return True

        try:
            deadline = time.monotonic() + 30
            while not windows and time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Executable exited early: {process.returncode}")
                user32.EnumWindows(enum_window, 0)
                time.sleep(0.1)
            if not windows:
                raise TimeoutError("Executable never created its main window")
            time.sleep(0.7)
            assert process.poll() is None
            user32.PostMessageW(windows[0], 0x0010, 0, 0)  # WM_CLOSE: normal app shutdown
            assert process.wait(timeout=15) == 0
            log = setting_dir / "app.log"
            assert not log.exists() or not log.read_text(encoding="utf-8").strip(), (
                "Executable logged an error"
            )
            assert not list(faces.iterdir()), "Startup modified the face folder"
        finally:
            if process.poll() is None:
                process.kill()  # only the child created by this test
                process.wait()
    print("EXE SMOKE PASSED: packaged GUI initialized, settings loaded, clean exit, no startup writes")


if __name__ == "__main__":
    main()
