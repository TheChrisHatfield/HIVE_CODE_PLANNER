"""Adapt custom-named cartridge imports into promotable Hive layout."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from hive_planner.cartridge_promote import _is_cartridge_draft
from hive_planner.config import FEATURE_ID_RE, RepoPaths, validate_feature_id
from hive_planner.delta_emit import DRAFT_MARKER
from hive_planner.translator import DRAFT_BANNER, classify_segment, segment_text

STANDARD_LAYER_FILES = frozenset({"holistic.md", "macro.md", "memory.md"})
LayerName = str  # holistic | macro | micro | memory | specseed

_FILENAME_LAYER_HINTS: tuple[tuple[str, LayerName], ...] = (
    ("holistic", "holistic"),
    ("overview", "holistic"),
    ("mission", "holistic"),
    ("planning", "macro"),
    ("macro", "macro"),
    ("architecture", "macro"),
    ("subsystem", "macro"),
    ("memory", "memory"),
    ("guardrail", "memory"),
    ("agents", "memory"),
    ("specseed", "specseed"),
    ("spec-seed", "specseed"),
    ("dev", "micro"),
    ("feature", "micro"),
)


def _token_in_filename(token: str, filename: str) -> bool:
    normalized = filename.lower().replace("_", "-").replace(".", "-")
    if len(token) <= 4:
        return re.search(rf"(^|-){re.escape(token)}(-|$)", normalized) is not None
    return token in normalized


@dataclass
class CartridgeAdaptResult:
    feature: str
    adapted: list[str] = field(default_factory=list)
    mappings: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "feature": self.feature,
            "adapted": self.adapted,
            "mappings": self.mappings,
            "warnings": self.warnings,
            "skipped": self.skipped,
        }


def slugify_feature_id(raw: str) -> str:
    text = raw.strip().lower().replace("_", "-").replace(" ", "-")
    text = re.sub(r"[^a-z0-9-]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    if not text:
        text = "feature"
    if not FEATURE_ID_RE.match(text):
        text = f"f-{text.lstrip('-')}" if text else "feature"
    return validate_feature_id(text)


def infer_feature_id(
    *,
    requested: str | None,
    imported_rels: list[str],
    manifest: dict | None = None,
) -> str:
    cleaned = (requested or "").strip()
    if cleaned and cleaned != "example-feature":
        return validate_feature_id(cleaned)

    if manifest:
        features = manifest.get("features") or []
        for entry in features:
            try:
                return validate_feature_id(str(entry).strip())
            except ValueError:
                continue

    root_markdown = [
        Path(rel)
        for rel in imported_rels
        if rel.lower().endswith(".md") and len(Path(rel).parts) == 1
    ]
    if not root_markdown:
        root_markdown = [Path(rel) for rel in imported_rels if rel.lower().endswith(".md")]

    for path in root_markdown:
        hint = _filename_layer_hint(path.name)
        if hint in {"micro", "specseed"}:
            return slugify_feature_id(path.stem)

    if len(root_markdown) == 1:
        return slugify_feature_id(root_markdown[0].stem)

    if root_markdown:
        return slugify_feature_id(root_markdown[0].stem)

    raise ValueError("Could not infer feature id — enter a Feature id or add features[] to manifest.json.")


def _filename_layer_hint(filename: str) -> LayerName | None:
    lowered = filename.lower()
    if lowered.endswith(".specseed.md") or ".specseed." in lowered:
        return "specseed"
    for token, layer in _FILENAME_LAYER_HINTS:
        if _token_in_filename(token, lowered):
            return layer
    if lowered.startswith("micro/") or "/micro/" in lowered.replace("\\", "/"):
        return "micro"
    if lowered.startswith("specs/") or "/specs/" in lowered.replace("\\", "/"):
        return "specseed"
    return None


def _load_manifest_layer_map(cart_root: Path) -> dict[str, LayerName]:
    manifest_path = cart_root / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    layer_map = data.get("layer_map") or {}
    result: dict[str, LayerName] = {}
    for key, value in layer_map.items():
        layer = str(value).strip().lower()
        if layer in {"holistic", "macro", "micro", "memory", "specseed"}:
            result[str(key).replace("\\", "/")] = layer
    return result


def _load_manifest(cart_root: Path) -> dict | None:
    manifest_path = cart_root / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _is_standard_layer_path(rel: Path) -> bool:
    name = rel.name.lower()
    if name in STANDARD_LAYER_FILES and len(rel.parts) == 1:
        return True
    if len(rel.parts) == 2 and rel.parts[0].lower() == "micro" and rel.suffix.lower() == ".md":
        return True
    if len(rel.parts) == 2 and rel.parts[0].lower() == "specs" and name.endswith(".specseed.md"):
        return True
    return False


def _classify_file_layer(path: Path, text: str) -> LayerName:
    hint = _filename_layer_hint(path.name)
    if hint:
        return hint

    segments = segment_text(text)
    if not segments:
        return "micro"

    scores = {"holistic": 0, "macro": 0, "micro": 0, "memory": 0}
    for segment in segments:
        bucket = classify_segment(segment)
        if bucket in scores:
            scores[bucket] += 1

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "micro"
    return best


def _ensure_draft_content(source_rel: str, body: str) -> str:
    stripped = body.strip()
    if not stripped:
        return f"{DRAFT_BANNER}\n\n<!-- adapted from {source_rel} -->\n"
    first = stripped.splitlines()[0].strip()
    if first.startswith(DRAFT_MARKER) or DRAFT_BANNER in first:
        return stripped + ("\n" if not stripped.endswith("\n") else "")
    return f"{DRAFT_BANNER}\n\n<!-- adapted from {source_rel} -->\n\n{stripped}\n"


def _target_path(paths: RepoPaths, layer: LayerName, feature: str) -> Path:
    if layer == "holistic":
        return paths.cartridge / "holistic.md"
    if layer == "macro":
        return paths.cartridge / "macro.md"
    if layer == "memory":
        return paths.cartridge / "memory.md"
    if layer == "specseed":
        return paths.cartridge / "specs" / f"{feature}.specseed.md"
    return paths.cartridge / "micro" / f"{feature}.md"


def _should_write(target: Path, *, overwrite: bool) -> bool:
    if not target.is_file():
        return True
    if overwrite:
        return True
    return not _is_cartridge_draft(target)


def import_needs_cartridge_adapt(paths: RepoPaths, written: list[str]) -> bool:
    for rel in written:
        if not str(rel).lower().endswith(".md"):
            continue
        if not _is_standard_layer_path(Path(rel)):
            return True
    return False


def adapt_cartridge_for_promote(
    paths: RepoPaths,
    feature: str,
    *,
    overwrite: bool = False,
    source_rels: list[str] | None = None,
) -> CartridgeAdaptResult:
    """Map custom cartridge filenames/content into standard draft layer files."""
    feature = validate_feature_id(feature.strip())
    result = CartridgeAdaptResult(feature=feature)
    cart = paths.cartridge
    manifest = _load_manifest(cart)
    layer_map = _load_manifest_layer_map(cart)

    candidates: list[Path] = []
    if source_rels:
        for rel in source_rels:
            path = cart / rel
            if path.is_file() and path.suffix.lower() == ".md":
                candidates.append(path)
    else:
        candidates = sorted(p for p in cart.rglob("*.md") if p.is_file())

    layer_bodies: dict[LayerName, list[tuple[str, str]]] = {
        "holistic": [],
        "macro": [],
        "micro": [],
        "memory": [],
        "specseed": [],
    }

    for path in candidates:
        rel = path.relative_to(cart).as_posix()
        if rel in {"source-context.md", "research-summary.md"}:
            result.skipped.append(rel)
            continue

        if _is_standard_layer_path(Path(rel)) and _is_cartridge_draft(path):
            result.skipped.append(rel)
            continue

        mapped = layer_map.get(rel) or layer_map.get(path.name)
        text = path.read_text(encoding="utf-8", errors="replace")
        if mapped:
            layer = mapped
        elif _is_standard_layer_path(Path(rel)):
            if rel == "holistic.md":
                layer = "holistic"
            elif rel == "macro.md":
                layer = "macro"
            elif rel == "memory.md":
                layer = "memory"
            elif rel.startswith("micro/"):
                layer = "micro"
            else:
                layer = "specseed"
        else:
            layer = _classify_file_layer(path, text)

        layer_bodies[layer].append((rel, text))

    for layer, chunks in layer_bodies.items():
        if not chunks:
            continue
        target = _target_path(paths, layer, feature)
        if not _should_write(target, overwrite=overwrite):
            result.skipped.append(target.relative_to(cart).as_posix())
            continue

        if len(chunks) == 1:
            body = _ensure_draft_content(chunks[0][0], chunks[0][1])
        else:
            parts = []
            for source_rel, text in chunks:
                parts.append(f"## Source: {source_rel}\n\n{text.strip()}")
            merged = "\n\n".join(parts)
            body = _ensure_draft_content(", ".join(src for src, _ in chunks), merged)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        rel_target = target.relative_to(cart).as_posix()
        result.adapted.append(rel_target)
        for source_rel, _ in chunks:
            result.mappings[source_rel] = rel_target

    if not result.adapted and not any(_is_cartridge_draft(_target_path(paths, layer, feature)) for layer in ("holistic", "macro", "micro")):
        result.warnings.append(
            "No cartridge layers were adapted — add layer_map to manifest.json or use filenames containing "
            "holistic, planning/macro, memory, or dev/feature hints."
        )

    return result
