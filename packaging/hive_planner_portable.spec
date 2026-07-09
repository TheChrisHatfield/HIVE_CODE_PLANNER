# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — portable onedir build (dist/HivePlannerPortable/)."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
root = Path(SPECPATH).resolve().parent
pkg = root / "src" / "hive_planner"
icon = root / "scripts" / "assets" / "HivePlanner.ico"
version_info = root / "packaging" / "version_info.txt"

pymupdf_datas, pymupdf_binaries, pymupdf_hidden = collect_all("pymupdf")
fitz_datas, fitz_binaries, fitz_hidden = collect_all("fitz")

datas = [
    (str(pkg / "bootstrap_templates"), "hive_planner/bootstrap_templates"),
    (str(pkg / "vendor_templates"), "hive_planner/vendor_templates"),
    (str(root / "scripts" / "README.md"), "scripts"),
] + pymupdf_datas + fitz_datas

a = Analysis(
    [str(pkg / "frozen_entry.py")],
    pathex=[str(root / "src")],
    binaries=pymupdf_binaries + fitz_binaries,
    datas=datas,
    hiddenimports=[
        "hive_planner",
        "hive_planner.cli",
        "hive_planner.launcher",
        "hive_planner.launcher.app",
        "hive_planner.launcher.console_win",
        "hive_planner.launcher.theme",
        "hive_planner.launcher.user_guide",
        "hive_planner.format_deps",
        "importlib.metadata",
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.scrolledtext",
        "fitz",
        "pymupdf",
        "pymupdf._mupdf",
        "pymupdf._extra",
    ] + pymupdf_hidden + fitz_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "sentence_transformers",
        "torch",
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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
    icon=str(icon) if icon.is_file() else None,
    version=str(version_info) if version_info.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HivePlannerPortable",
)
