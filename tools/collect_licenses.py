"""Copy upstream notices into a Windows bundle without changing their text."""

import argparse
import shutil
import sys
from importlib import metadata
from pathlib import Path

PACKAGES = ("customtkinter", "Pillow", "darkdetect", "packaging", "pyinstaller")


def collect(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    index = ["# Bundled third-party notices", "", f"Python {sys.version.split()[0]}", ""]
    for name in PACKAGES:
        distribution = metadata.distribution(name)
        files = [
            path
            for path in distribution.files or []
            if ".dist-info/" in str(path) and path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE"))
        ]
        if not files:
            raise RuntimeError(f"No license found for {name}")
        folder = destination / name
        folder.mkdir(exist_ok=True)
        for path in files:
            shutil.copyfile(distribution.locate_file(path), folder / path.name)
        index.append(f"- {name} {distribution.version}: {name}/")

    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise FileNotFoundError("Python runtime LICENSE.txt is required for a Windows release")
    shutil.copyfile(python_license, destination / "Python-LICENSE.txt")
    extras = Path(__file__).resolve().parents[1] / "licenses"
    for source in sorted(extras.glob("*.txt")):
        shutil.copyfile(source, destination / source.name)
        index.append(f"- {source.name}")
    (destination / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    collect(parser.parse_args().destination)
