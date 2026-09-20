# Build on Windows: python -m PyInstaller --noconfirm FMNewgenFaceInstaller.spec
from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['app.py'],
    pathex=[SPECPATH],
    binaries=[],
    datas=collect_data_files('customtkinter'),
    hiddenimports=['PIL.WebPImagePlugin', 'PIL._webp', 'PIL.PngImagePlugin', 'PIL.JpegImagePlugin'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='FMNewgenFaceInstaller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='FMNewgenFaceInstaller')
