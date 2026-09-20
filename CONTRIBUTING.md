# Contributing

Bug reports, documentation improvements and focused pull requests are welcome.
This is a small Windows utility; keep core filesystem logic separate from Tk.

## Development

Use Python 3.11+ with Tk on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe app.py
```

Before opening a pull request:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools\smoke_ui.py
```

The UI smoke script creates temporary faces/settings and exercises real Tk
dialogs through widget commands. It does not touch your game folder. To format
code, run `python -m ruff check --fix .` then `python -m ruff format .`.

## Data safety requirements

- Tests must use synthetic XML and images under temporary directories.
- Never commit facepacks, save games, personal `config.xml`, settings or logs.
- Existing correct mappings must remain byte-identical during image replacement.
- Preserve encoding, whitespace, ordering and unrelated bytes during XML edits.
- Never serialize a complete XML DOM to update a large config.
- Overwrites, removals and mapping repairs must require explicit UI confirmation.
- Keep backups, temporary-file validation, atomic config replacement and image rollback.
- Cover changes to filesystem behavior with failure-path and no-op tests, and
  run the synthetic large-file tests when changing the scanner/writer.

## Pull requests

Explain the concrete problem, resulting behavior and checks you ran. Include a
sanitized screenshot for UI changes. Discuss large features in an issue first.
Do not attach personal paths, full logs or real facepacks to issues.

## Releases

1. Update the version in `pyproject.toml` and the changelog.
2. Ensure CI is green on `main`.
3. Push a matching tag, for example `v0.1.0`.
4. The release workflow tests and builds Windows x64, checks the packaged GUI,
   and publishes a prerelease ZIP and SHA-256 checksum.

Unsigned binaries may be blocked by Windows policy. Do not recommend disabling
security protections; document the limitation or use a trusted signing process.
Contributions are made under the project's MIT license.
