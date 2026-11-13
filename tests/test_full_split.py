from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
GAN_LOOP = ROOT / "scripts" / "gan-loop"
SCRIPTS = ROOT / "scripts"
for path in (str(GAN_LOOP), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _load():
    spec = importlib.util.spec_from_file_location("full_split", GAN_LOOP / "_full_split.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_does_not_fit_seeds():
    with patch("sandbox_rank_gan.weights.fit_logit") as fit_logit:
        _load()
        fit_logit.assert_not_called()


def test_split_class_n3_keeps_a_test_item():
    full = _load()
    train, val, test = full.split_class(list(range(3)), random.Random(0))
    assert len(test) == 1
    assert len(train) + len(val) + len(test) == 3
    assert sorted(train + val + test) == [0, 1, 2]


def test_split_class_locked_blend_sizes_keep_60_20_20():
    full = _load()
    pos_train, pos_val, pos_test = full.split_class(list(range(398)), random.Random(0))
    neg_train, neg_val, neg_test = full.split_class(list(range(205)), random.Random(0))
    assert (len(pos_train), len(pos_val), len(pos_test)) == (239, 80, 79)
    assert (len(neg_train), len(neg_val), len(neg_test)) == (123, 41, 41)
