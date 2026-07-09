"""Portable Tesseract OCR runtime for image-only PDF sources."""

from __future__ import annotations

import os
import hashlib
import shutil
import subprocess
import tempfile
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

ocr_pdf_enabled: ContextVar[bool] = ContextVar("ocr_pdf_enabled", default=True)

TESSERACT_EXE_NAME = "tesseract.exe" if os.name == "nt" else "tesseract"
VENDOR_TESSERACT_REL = Path("vendor") / "tesseract"
DEFAULT_OCR_LANG = "eng"
DEFAULT_OCR_DPI = 200

D_DRIVE_TESSERACT_CANDIDATES: tuple[Path, ...] = (
    Path("D:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("D:/Tesseract-OCR/tesseract.exe"),
    Path("D:/tools/Tesseract-OCR/tesseract.exe"),
    Path("D:/tools/tesseract/tesseract.exe"),
)

WINDOWS_TESSERACT_CANDIDATES: tuple[Path, ...] = (
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
)


@dataclass(frozen=True)
class TesseractInstall:
    exe: Path
    tessdata_dir: Path
    source: str

    def to_dict(self) -> dict:
        return {
            "exe": str(self.exe),
            "tessdata_dir": str(self.tessdata_dir),
            "source": self.source,
        }


@dataclass
class OcrRuntimeStatus:
    available: bool
    install: TesseractInstall | None = None
    searched: list[str] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "install": self.install.to_dict() if self.install else None,
            "searched": self.searched,
            "detail": self.detail,
        }


def _tessdata_for_exe(exe: Path) -> Path | None:
    candidates = (
        exe.parent / "tessdata",
        exe.parent.parent / "tessdata",
    )
    for candidate in candidates:
        if (candidate / f"{DEFAULT_OCR_LANG}.traineddata").is_file():
            return candidate
        if candidate.is_dir() and any(candidate.glob("*.traineddata")):
            return candidate
    prefix = os.environ.get("TESSDATA_PREFIX", "").strip()
    if prefix:
        pref = Path(prefix)
        if pref.is_dir() and any(pref.glob("*.traineddata")):
            return pref
        nested = pref / "tessdata"
        if nested.is_dir() and any(nested.glob("*.traineddata")):
            return nested
    return None


def _validate_install(exe: Path, source: str) -> TesseractInstall | None:
    if not exe.is_file():
        return None
    tessdata = _tessdata_for_exe(exe)
    if tessdata is None:
        return None
    return TesseractInstall(exe=exe.resolve(), tessdata_dir=tessdata.resolve(), source=source)


def _scan_drive_for_tesseract(drive_root: Path, *, max_depth: int = 4) -> Path | None:
    if not drive_root.is_dir():
        return None
    drive_root = drive_root.resolve()
    for root, dirs, files in os.walk(drive_root):
        depth = len(Path(root).relative_to(drive_root).parts)
        if depth > max_depth:
            dirs.clear()
            continue
        if TESSERACT_EXE_NAME in files:
            candidate = Path(root) / TESSERACT_EXE_NAME
            if _validate_install(candidate, "d-drive:scan") is not None:
                return candidate
        dirs[:] = [name for name in dirs if name.lower() not in {"windows", "$recycle.bin", "system volume information"}]
    return None


_cached_status: OcrRuntimeStatus | None = None


def _scan_d_drive_enabled() -> bool:
    flag = os.environ.get("HIVE_TESSERACT_SCAN_D", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def discover_tesseract(*, scan_d_drive: bool | None = None, refresh: bool = False) -> OcrRuntimeStatus:
    """Locate a Tesseract install: env, bundled vendor, D: drive, then system paths."""
    global _cached_status
    if scan_d_drive is None:
        scan_d_drive = _scan_d_drive_enabled()
    if _cached_status is not None and not refresh and (
        not scan_d_drive or "d-drive:scan" in _cached_status.searched
    ):
        return _cached_status

    searched: list[str] = []
    checks: list[tuple[str, Path | None]] = []

    env_exe = os.environ.get("HIVE_TESSERACT_EXE", "").strip()
    if env_exe:
        checks.append(("env:HIVE_TESSERACT_EXE", Path(env_exe)))

    from hive_planner.runtime_paths import default_hive_root, portable_app_root

    for label, root in (
        ("portable:vendor/tesseract", portable_app_root() / VENDOR_TESSERACT_REL / TESSERACT_EXE_NAME),
        ("repo:vendor/tesseract", default_hive_root() / VENDOR_TESSERACT_REL / TESSERACT_EXE_NAME),
    ):
        checks.append((label, root))

    for candidate in D_DRIVE_TESSERACT_CANDIDATES:
        checks.append((f"d-drive:{candidate.as_posix()}", candidate))
    if scan_d_drive:
        checks.append(("d-drive:scan", None))

    for candidate in WINDOWS_TESSERACT_CANDIDATES:
        checks.append((f"windows:{candidate.as_posix()}", candidate))

    which = shutil.which("tesseract")
    if which:
        checks.append(("path:tesseract", Path(which)))

    for label, path in checks:
        searched.append(label)
        if label == "d-drive:scan":
            found = _scan_drive_for_tesseract(Path("D:/"))
            if found is not None:
                install = _validate_install(found, "d-drive:scan")
                if install is not None:
                    status = OcrRuntimeStatus(True, install, searched, "Tesseract found on D: drive")
                    _cached_status = status
                    return status
            continue
        if path is None:
            continue
        install = _validate_install(path, label)
        if install is not None:
            status = OcrRuntimeStatus(True, install, searched, f"Tesseract found ({label})")
            _cached_status = status
            return status

    status = OcrRuntimeStatus(
        False,
        None,
        searched,
        "Tesseract not found — install to D:\\Program Files\\Tesseract-OCR or set HIVE_TESSERACT_EXE.",
    )
    _cached_status = status
    return status


def ocr_runtime_status(*, scan_d_drive: bool | None = None, refresh: bool = False) -> OcrRuntimeStatus:
    return discover_tesseract(scan_d_drive=scan_d_drive, refresh=refresh)


def ensure_ocr_runtime(*, scan_d_drive: bool | None = None) -> OcrRuntimeStatus:
    """Return OCR runtime status, re-scanning once when the cached result was unavailable."""
    status = discover_tesseract(scan_d_drive=scan_d_drive)
    if status.available:
        return status
    return discover_tesseract(scan_d_drive=scan_d_drive, refresh=True)


def _run_tesseract_on_png(install: TesseractInstall, png_path: Path, *, lang: str = DEFAULT_OCR_LANG) -> str:
    env = os.environ.copy()
    env["TESSDATA_PREFIX"] = str(install.tessdata_dir.parent)
    completed = subprocess.run(
        [
            str(install.exe),
            str(png_path),
            "stdout",
            "-l",
            lang,
            "--psm",
            "3",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(err or f"Tesseract exited {completed.returncode}")
    return completed.stdout.strip()


def ocr_pdf_pages(
    pdf_path: Path,
    install: TesseractInstall,
    *,
    dpi: int = DEFAULT_OCR_DPI,
    lang: str = DEFAULT_OCR_LANG,
    page_indices: list[int] | None = None,
) -> list[tuple[int, str]]:
    try:
        import fitz  # pymupdf
    except ImportError as exc:
        raise RuntimeError("PDF OCR requires pymupdf: pip install -e '.[pdf]'") from exc

    pages_text: list[tuple[int, str]] = []
    with fitz.open(pdf_path) as doc:
        if doc.needs_pass:
            raise RuntimeError("Password-protected PDF is not supported")
        with tempfile.TemporaryDirectory(prefix="hive-ocr-") as tmp:
            tmp_dir = Path(tmp)
            indices = page_indices if page_indices is not None else list(range(len(doc)))
            for page_num in indices:
                if page_num < 0 or page_num >= len(doc):
                    continue
                page = doc[page_num]
                pix = page.get_pixmap(dpi=dpi)
                png_path = tmp_dir / f"page-{page_num + 1}.png"
                pix.save(str(png_path))
                try:
                    text = _run_tesseract_on_png(install, png_path, lang=lang)
                except RuntimeError:
                    continue
                if text:
                    pages_text.append((page_num + 1, text))
    return pages_text


def ocr_sidecar_basename(pdf_path: Path) -> str:
    """Unique sidecar filename for batch OCR (avoids stem collisions in one output dir)."""
    digest = hashlib.sha256(str(pdf_path.resolve()).encode("utf-8")).hexdigest()[:8]
    return f"{pdf_path.stem}-{digest}.ocr.md"


def convert_pdf_to_markdown(
    pdf_path: Path,
    output_path: Path | None = None,
    *,
    install: TesseractInstall | None = None,
    dpi: int = DEFAULT_OCR_DPI,
    lang: str = DEFAULT_OCR_LANG,
) -> Path:
    """OCR a PDF and write a searchable markdown sidecar (.ocr.md by default)."""
    pdf_path = pdf_path.resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    if install is None:
        status = ensure_ocr_runtime()
        if not status.available or status.install is None:
            raise RuntimeError(status.detail)
        install = status.install

    try:
        import fitz  # pymupdf
    except ImportError as exc:
        raise RuntimeError("PDF OCR requires pymupdf: pip install -e '.[pdf]'") from exc

    with fitz.open(pdf_path) as doc:
        page_count = len(doc)

    pages_text = ocr_pdf_pages(pdf_path, install, dpi=dpi, lang=lang)
    if not pages_text:
        raise RuntimeError("OCR produced no text")

    ocr_page_nums = {page_num for page_num, _ in pages_text}
    unresolved = [page_num for page_num in range(1, page_count + 1) if page_num not in ocr_page_nums]

    title = pdf_path.stem.replace("-", " ").title()
    lines = [f"# {title}", "", "> OCR extraction via Tesseract", ""]
    if unresolved:
        unresolved_label = ", ".join(str(n) for n in unresolved)
        lines.extend(
            [f"> Warning: {len(unresolved)} page(s) produced no OCR text: {unresolved_label}", ""]
        )
    raw_parts: list[str] = []
    for page_num, text in pages_text:
        lines.extend([f"## Page {page_num}", "", text, ""])
        raw_parts.append(text)
    body = "\n".join(lines).strip() + "\n"

    dest = output_path or pdf_path.with_suffix(pdf_path.suffix + ".ocr.md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")
    return dest


def pdf_needs_ocr(pdf_path: Path) -> bool:
    try:
        import fitz
    except ImportError:
        return False
    try:
        with fitz.open(pdf_path) as doc:
            for page_num in range(len(doc)):
                if doc[page_num].get_text("text").strip():
                    return False
            return len(doc) > 0
    except Exception:
        return False
