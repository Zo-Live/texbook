# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


ROOT = Path(SPECPATH).parent
ICON_PATH = ROOT / "docs" / "icon.ico"
ENTRYPOINT = ROOT / "src" / "texbook" / "gui" / "__main__.py"


a = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(str(ICON_PATH), "docs")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="texbook",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
)
