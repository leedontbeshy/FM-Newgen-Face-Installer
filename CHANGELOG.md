# Changelog

## 0.1.1 — 2026-09-20

- Fix `image "pyimage1" doesn't exist` when selecting another face in the same session.
- Clear the old Tk image before releasing it and keep the replacement alive until attached.
- Respect Windows DPI and size the initial window against the monitor's actual work area.
- Use larger text and controls, a two-column form on wide windows, and a stacked form on narrow windows.
- Keep install/repair/remove actions visible outside the scrolling form; scale text and preview when resizing.
- Add GUI regression coverage for consecutive PNG/JPG/WEBP installs, invalid-image recovery,
  narrow/wide/maximized windows and appearance changes.

## 0.1.0 — 2026-09-20

First public preview.

- Install, replace, restore and remove PNG/JPEG/WEBP faces by Player Unique ID.
- Explicit FM24 newgen (`r-` portrait target) and real-player modes.
- Confirmed repair of a legacy newgen mapping without changing its image.
- Streaming XML lookup and byte-preserving edits, backups and atomic replacement.
- Image rollback, stale-plan checks and an OS lock for concurrent app instances.
- Local settings, Downloads-first picker, image preview and background I/O.
- Synthetic tests through 500,000 mappings, GUI smoke tests and Windows packaging.
- MIT license, contribution guidance, CI and release automation.

Known release limitation: Windows executables are unsigned and may be blocked by
Smart App Control or enterprise signing policies.
