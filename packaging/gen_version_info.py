"""Generate PyInstaller Windows version resource from pyproject.toml."""

from __future__ import annotations

import re
from pathlib import Path


def _read_project_version(repo_root: Path) -> str:
    text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise ValueError("version not found in pyproject.toml")
    return match.group(1).strip()


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    parts: list[int] = []
    for segment in version.split(".")[:4]:
        match = re.match(r"(\d+)", segment.strip())
        parts.append(int(match.group(1)) if match else 0)
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def render_version_info(version: str) -> str:
    filevers = _version_tuple(version)
    prodvers = filevers
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={filevers},
    prodvers={prodvers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Hive Code Planner'),
        StringStruct('FileDescription', 'HIVE Planner desktop and CLI'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'HivePlanner'),
        StringStruct('LegalCopyright', 'Copyright (c) 2026 Hive Code Planner'),
        StringStruct('OriginalFilename', 'HivePlanner.exe'),
        StringStruct('ProductName', 'HIVE Planner'),
        StringStruct('ProductVersion', '{version}')])
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    version = _read_project_version(repo_root)
    out = repo_root / "packaging" / "version_info.txt"
    out.write_text(render_version_info(version), encoding="utf-8")
    print(f"Wrote {out} (version {version})")


if __name__ == "__main__":
    main()
