# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — portable onedir build (dist/HivePlannerPortable/)."""

from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent
pkg = root / "src" / "hive_planner"
icon = root / "scripts" / "assets" / "HivePlanner.ico"

datas = [
    (str(pkg / "bootstrap_templates"), "hive_planner/bootstrap_templates"),
    (str(pkg / "vendor_templates"), "hive_planner/vendor_templates"),
    (str(root / "scripts" / "README.md"), "scripts"),
]

a = Analysis(
    [str(pkg / "frozen_entry.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "hive_planner",
        "hive_planner.cli",
        "hive_planner.launcher",
        "hive_planner.launcher.app",
        "hive_planner.launcher.console_win",
        "hive_planner.launcher.theme",
        "hive_planner.launcher.user_guide",
        "importlib.metadata",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.scrolledtext",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "sentence_transformers",
        "torch",
        "pymupdf",
        "docx",
        "bs4",
        "pptx",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HivePlanner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon) if icon.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HivePlannerPortable",
)
