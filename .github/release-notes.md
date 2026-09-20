Windows x64 public preview of FM Newgen Face Installer for Football Manager 2024.

- Install, replace, restore and remove faces by Player Unique ID.
- Correct FM24 newgen `r-` targets and a separate real-player mode.
- Explicit repair for an old newgen mapping, without changing its image.
- Streaming, byte-preserving XML edits with backups and atomic replacement.

Download and extract the complete ZIP, then open `FMNewgenFaceInstaller.exe`.
Keep the `_internal` folder beside it. A SHA-256 checksum is supplied separately.

This artifact is built on GitHub Actions after lint, automated core/large-file
tests, source GUI smoke tests and a packaged-GUI startup check pass. A startup
check on a hosted runner does not guarantee compatibility with every Windows policy.

**Unsigned preview:** Smart App Control or enterprise signing policies may block
the executable. Do not disable security protections to run it. The checksum is
not a digital signature. The project does not yet provide trusted signed builds.

No face images, facepacks, save games or personal configuration files are included.
See the README for setup, reload-skin instructions, data safety and known limits.
