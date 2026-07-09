"""Optional format dependencies (PDF, etc.) for ingest and Load Sources."""

from __future__ import annotations


def pdf_support_available() -> bool:
    try:
        import fitz  # noqa: F401
    except ImportError:
        return False
    return True


def pdf_support_message() -> str:
    from hive_planner.runtime_paths import is_portable_runtime

    if is_portable_runtime():
        return (
            "PDF support is missing from this Hive Planner build. "
            "Rebuild with scripts\\build_portable.ps1 (includes pymupdf) or use a dev install: "
            "pip install -e \".[pdf]\""
        )
    return "PDF support requires pymupdf: pip install -e \".[pdf]\""
