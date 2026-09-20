"""Window sizing in logical units, without shrinking the application's text."""

import os


def work_area(window):
    """Return the monitor's work area in pixels (Tk can cache pre-DPI metrics)."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("size", wintypes.DWORD),
                ("monitor", wintypes.RECT),
                ("work", wintypes.RECT),
                ("flags", wintypes.DWORD),
            ]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        info = MonitorInfo()
        info.size = ctypes.sizeof(info)
        monitor = user32.MonitorFromWindow(window.winfo_id(), 2)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return info.work.right - info.work.left, info.work.bottom - info.work.top
    return window.winfo_screenwidth(), window.winfo_screenheight()


def initial_size(window):
    width, height = work_area(window)
    dpi = window._get_window_scaling()
    available_width = max(320, int(width / dpi) - 48)
    available_height = max(320, int(height / dpi) - 72)
    return min(880, available_width), min(820, available_height)
