# Verification

The automated checks are reproducible through [CI](https://github.com/leedontbeshy/FM-Newgen-Face-Installer/actions/workflows/ci.yml).
Release builds run their own tests and packaged-GUI startup check before publication.

## Coverage

- IDs: whitespace trimming, ASCII digits, invalid/path-like input, filename length.
- Config: exact lookup, early stop, comments, other lists, ordering and byte preservation.
- UTF-8/BOM, UTF-16 LE/BE, single-byte encodings, CRLF/LF and no final newline.
- Missing configs, duplicate no-ops, malformed/ambiguous tails, DTD rejection.
- Safe add/remove/repair, backup and temp validation, injected fsync/commit errors.
- JPEG/WEBP conversion, PNG byte preservation, alpha, EXIF orientation, preview size.
- Confirmation cancellation, restore, orphan images, stale plans and folder locks.
- Image rollback and unchanged config bytes/mtime during ordinary replacement.
- Local settings roundtrip and atomic failure behavior.
- Real Tk event-loop smoke: install, cancel, replace, restore, explicit repair,
  player types, settings, remove and relaunch with remembered folder.
- Consecutive PNG/JPG/WEBP selections and installs in one session, invalid-image
  recovery, narrow/wide/maximized layouts and light/dark appearance transitions.

The consecutive-image smoke case reproduced the `pyimage1` error before the
0.1.1 fix. The corrected app passes that same case. The responsive layout was
also visually inspected on a Windows display at 200% DPI.

## Large-file regression cases

Synthetic configs contain 10,000, 100,000, 250,000 and 500,000 records. Each checks
lookup at the start/middle/end, missing lookup, add, explicit repair, duplicate
no-op and remove. An add/repair/remove roundtrip must match the original SHA-256.
Run with timings using:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_large_config.py -q -s
```

A Windows 11 / Python 3.14 development run before publication passed 111 core
cases in about 25 seconds. At 250,000 records, absent lookup was about 0.8 seconds,
add 2.0 seconds, repair 1.6 seconds and remove 1.6 seconds. These are observations,
not performance guarantees. CI results are the current source of truth.

## In-game and platform limits

A user confirmed that an FM24 newgen image appeared after correcting its `r-`
target, clearing cache and reloading the skin. There is no automated game-UI test
or exhaustive coverage of skins, save versions and conflicting facepacks.

One unsigned local build was blocked before startup by Windows Application
Control (WinError 4551; CodeIntegrity signing-policy events). This is recorded as
a blocked startup check, not a pass. A successful CI startup on a hosted runner
does not mean an unsigned binary will run under every user's security policy.

Tests inject ordinary filesystem errors. Actual forced-power-loss durability and
network-share semantics have not been verified. All public fixtures/screenshots
use synthetic data; private game configs and local device logs are excluded.
