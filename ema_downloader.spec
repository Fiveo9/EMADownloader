# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone Windows build.

onedir (not onefile): the app starts in seconds on every launch, whereas a
onefile exe would re-extract ~200 MB of bundled libraries each time. The
console window is intentional: it shows the URL and logs, and closing it
exits the app — the simplest mental model for non-technical users.

Build with:  build_exe.bat   (or: pyinstaller --noconfirm ema_downloader.spec)
"""

a = Analysis(
    ["launch_exe.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("ema_downloader/webapp/templates", "templates"),
        ("ema_downloader/webapp/static", "static"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EMA文件库",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="EMA文件库",
)
