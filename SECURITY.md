# Security and data integrity

The latest tagged version and `main` receive fixes on a best-effort basis.

For vulnerabilities or reproducible data-loss/corruption bugs, use
[GitHub private vulnerability reporting](https://github.com/leedontbeshy/FM-Newgen-Face-Installer/security/advisories/new).
Include the version, operating system, reproduction steps and a small synthetic
config. Do not send real facepacks, save files, tokens or personal paths.

The application is local-only: no telemetry, cloud upload, updater or game-memory
access. It reads selected images and modifies only the chosen face folder plus
its own local settings/logs. XML DTDs and entity declarations are rejected.

Configuration commits use backups and atomic replacement. Image/config changes
cannot be a single atomic transaction across both files; see the README for
power-loss recovery limits. Filesystem locks coordinate this app's instances,
not arbitrary editors. Do not edit the same config concurrently in another app.

Windows releases are currently unsigned. Smart App Control or enterprise policy
may block them. A release checksum detects transfer damage; it is not a digital
signature and does not establish a publisher's identity.
