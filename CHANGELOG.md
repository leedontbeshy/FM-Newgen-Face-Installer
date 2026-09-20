# Changelog

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
