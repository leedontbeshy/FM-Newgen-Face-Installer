# Third-party notices

FM Newgen Face Installer's own code is MIT-licensed. Its dependencies and the
runtime bundled in a Windows release retain their respective licenses.

| Component | License / notices | Upstream |
| --- | --- | --- |
| CustomTkinter | MIT | https://github.com/TomSchimansky/CustomTkinter |
| Pillow and bundled image libraries | MIT-CMU and the additional notices included in Pillow's LICENSE | https://github.com/python-pillow/Pillow |
| darkdetect | BSD-3-Clause | https://github.com/albertosottile/darkdetect |
| packaging | Apache-2.0 or BSD-2-Clause | https://github.com/pypa/packaging |
| Python runtime | PSF and included third-party notices | https://www.python.org/ |
| Tcl/Tk runtime | Tcl/Tk license terms | https://www.tcl.tk/ |
| Roboto fonts in CustomTkinter | Apache-2.0 | https://github.com/googlefonts/roboto-2 |
| PyInstaller bootloader | GPL with the bootloader distribution exception | https://github.com/pyinstaller/pyinstaller |

`build.ps1` copies the installed distributions' license files and runtime notices
to `third-party-licenses/` in the portable folder. Its generated index records the
versions used. The checked-in `licenses/` directory supplies notices omitted by
some upstream runtime/font packages; source URLs are recorded there.

No Football Manager, Sports Interactive, SEGA or facepack assets are
included. Users supply their own images. This is an independent community tool,
not an official or affiliated Football Manager product.
