from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GAN_LOOP = ROOT / "scripts" / "gan-loop"
SCRIPTS = ROOT / "scripts"
for path in (str(GAN_LOOP), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _load():
    spec = importlib.util.spec_from_file_location("score_frozen", GAN_LOOP / "_score_frozen.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_does_not_require_argv():
    _load()


def test_main_without_path_exits_usage():
    frozen = _load()
    with pytest.raises(SystemExit, match="usage:"):
        frozen.main(["_score_frozen.py"])


def test_load_proposals_rejects_object_and_incomplete_rows(tmp_path: Path):
    frozen = _load()
    obj_path = tmp_path / "obj.json"
    obj_path.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="JSON list"):
        frozen.load_proposals(obj_path)
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps([{"name": "only.py"}]), encoding="utf-8")
    with pytest.raises(SystemExit, match="name/source"):
        frozen.load_proposals(bad_path)


def test_load_proposals_reads_utf8_bom_list(tmp_path: Path):
    frozen = _load()
    path = tmp_path / "bom.json"
    path.write_bytes(b'\xef\xbb\xbf[{"name": "a.py", "source": "x = 1\\n"}]')
    items = frozen.load_proposals(path)
    assert items == [{"name": "a.py", "source": "x = 1\n"}]
