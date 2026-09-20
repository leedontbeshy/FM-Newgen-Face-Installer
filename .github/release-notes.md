FM Newgen Face Installer 0.1.1 — Windows x64 public preview for Football Manager 2024.

- Fix `image "pyimage1" doesn't exist` when choosing the second or later face.
- Respect Windows DPI instead of shrinking the entire interface to fit cached screen dimensions.
- Larger readable text and controls, two columns on wide windows, stacked fields on narrow windows.
- Keep install/repair/remove buttons visible while the form scrolls.
- Fit previews and text to available space when resizing or maximizing.

Download and extract the complete ZIP, then open `FMNewgenFaceInstaller.exe`.
Keep the `_internal` folder beside it. A SHA-256 checksum is supplied separately.
For an update, close the old app and extract this build into a new folder.
Existing face files and locally saved folder settings remain available.

This artifact is built on GitHub Actions after lint, automated core/large-file
tests, source GUI smoke tests and a packaged-GUI startup check pass. A startup
check on a hosted runner does not guarantee compatibility with every Windows policy.

**Unsigned preview:** Smart App Control or enterprise signing policies may block
the executable. Do not disable security protections to run it. The checksum is
not a digital signature. The project does not yet provide trusted signed builds.

No face images, facepacks, save games or personal configuration files are included.
See the README for setup, reload-skin instructions, data safety and known limits.
