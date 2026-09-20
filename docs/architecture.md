# Architecture and safety contracts

## Boundaries

- `app.py`: GUI entry point and bounded local error logging.
- `ui/`: Tk widgets, file pickers, explicit confirmations and one background worker.
- `core/validation.py`: filename-safe ASCII Player IDs; never converted to floats.
- `core/config_manager.py`: streaming XML search, validation and byte edits.
- `core/image_manager.py`: image validation, PNG staging and preview generation.
- `core/installer.py`: read-only operation plans, confirmations and image rollback.
- `core/filesystem.py`: signatures, durable copies and OS folder locking.
- `core/settings_manager.py`: atomic local JSON settings and Downloads discovery.

Tk calls stay on the main thread; the worker sends results through a queue.
Disk operations never run inside widget event handlers. Closing during a write
is deferred until the operation finishes.

`ui/layout.py` reads the Windows monitor work area directly because Tk can cache
screen dimensions before DPI awareness changes. Window size is fitted in logical
units without reducing the user's DPI scale. Resize callbacks reflow the form,
adjust fonts and fit previews; actions remain outside the scrolling region.

`ui/preview.py` clears the underlying Tcl image binding when a preview is removed.
CustomTkinter 6.0's default label leaves that binding behind for `image=None`.
Replacement previews are attached before their strong reference is switched;
Tk image creation, clearing and resizing all happen on the UI thread.

## Config access

Expat validates structure and supplies original byte offsets; it does not build
a DOM or serialize records. Lookup feeds bounded lines and exits on the first
exact `from` attribute inside the root maps list. Comments and other lists do not
count. Mutations inspect the complete XML stream and validate the expected tail.

Supported layout: root `record`, one direct `list id="maps"` as its last child,
list/root closing tags on separate lines. Mutations refuse ambiguous XML instead
of normalizing it. DTDs/entities and excessive nesting are rejected.

Add inserts one encoded line before the list close, using nearby indentation and
line endings. Remove drops exactly one matching record's lines. Explicit newgen
repair changes only the `to` attribute's byte range. All other bytes are copied.

## FM24 player types

The image filename and `from` are numeric. Newgen portrait targets use `r-ID`;
real-player targets use `ID`. The UI requires a player-type choice and defaults
to newgen. Core APIs default to the real-player form for backwards compatibility;
callers specify `newgen=True` explicitly. No numeric-ID heuristic is used.

Normal image replacement leaves existing correct config mappings untouched.
Legacy newgen targets require the separately confirmed repair operation.
Unexpected custom targets are not silently changed; duplicate `from` records
are refused on remove/repair.

## Commit sequence

1. Build a read-only plan with source/config/image signatures.
2. Obtain confirmation when overwriting, removing or repairing.
3. Acquire the OS folder lock and verify that the plan is still current.
4. Stage and validate the image, if any.
5. For a config mutation, back up the original and stream to a same-folder temp.
6. Flush/fsync; verify the temp's XML, tail and target mapping count/value.
7. Commit the image, then atomically replace the config.
8. Roll back the image on an ordinary config-commit exception.

If rollback fails, retain recovery data and report its path. A pre-existing
`config.xml.tmp` is never blindly deleted. Correct-mapping replacement and
missing-mapping removal do not rewrite config or refresh its backup.

The image and config cannot be atomically committed together. A process kill or
power loss between commits may leave an orphan/missing image, although the config
is never intentionally truncated. Signatures and locks reduce stale/concurrent
writes; they cannot coordinate arbitrary external editors or guarantee network
filesystem semantics.

## Packaging and privacy

Windows onedir builds use PyInstaller with explicit CustomTkinter assets and
Pillow WEBP support. Dependency/runtime license notices accompany the bundle.
No game binaries, facepacks, photos or real configuration files are distributed.
Settings and bounded logs live under LOCALAPPDATA. There is no network client,
telemetry, automatic updater or access to Football Manager process memory.
