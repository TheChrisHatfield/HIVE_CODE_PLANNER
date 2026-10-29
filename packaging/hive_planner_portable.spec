# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — portable onedir build (dist/HivePlannerPortable/)."""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
root = Path(SPECPATH).resolve().parent
pkg = root / "src" / "hive_planner"
icon = root / "scripts" / "assets" / "HivePlanner.ico"
version_info = root / "packaging" / "version_info.txt"

# A previous portable launch may leave TCL_LIBRARY/TK_LIBRARY pointing at
# incomplete dist/_internal/_tcl_data paths; that breaks Tk collection.
for _key in ("TCL_LIBRARY", "TK_LIBRARY"):
    os.environ.pop(_key, None)

pymupdf_datas, pymupdf_binaries, pymupdf_hidden = collect_all("pymupdf")
fitz_datas, fitz_binaries, fitz_hidden = collect_all("fitz")

datas = [
    (str(pkg / "bootstrap_templates"), "hive_planner/bootstrap_templates"),
    (str(pkg / "vendor_templates"), "hive_planner/vendor_templates"),
    (str(pkg / "bug_hunt_continue.py"), "hive_planner"),
    (str(pkg / "agnostic_loop.py"), "hive_planner"),
    (str(root / "scripts" / "README.md"), "scripts"),
    (str(root / "scripts" / "assets" / "HivePlanner.ico"), "scripts/assets"),
] + pymupdf_datas + fitz_datas

# Explicit Tcl/Tk data dirs (PyInstaller runtime hook expects these names).
_tcl_root = Path(sys.base_prefix) / "tcl"
_tcl_data = _tcl_root / "tcl8.6"
_tk_data = _tcl_root / "tk8.6"
if _tcl_data.is_dir():
    datas.append((str(_tcl_data), "_tcl_data"))
if _tk_data.is_dir():
    datas.append((str(_tk_data), "_tk_data"))
_tcl8 = _tcl_root / "tcl8"
if _tcl8.is_dir():
    datas.append((str(_tcl8), "tcl8"))

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
        "hive_planner.launcher.mcp_servers",
        "hive_planner.mcp_server",
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
