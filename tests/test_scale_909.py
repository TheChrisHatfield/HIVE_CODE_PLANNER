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
    spec = importlib.util.spec_from_file_location("scale_909", GAN_LOOP / "_scale_909.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_import_does_not_collect_hard_negatives():
    with patch("sandbox_rank_hard_negatives.collect") as collect:
        _load()
        collect.assert_not_called()


def test_split_class_n3_keeps_a_test_item():
    scale = _load()
    train, val, test = scale.split_class(list(range(3)), random.Random(0))
    assert len(test) == 1
    assert len(train) + len(val) + len(test) == 3
    assert sorted(train + val + test) == [0, 1, 2]


def test_split_class_909_class_sizes_keep_60_20_20():
    scale = _load()
    pos_train, pos_val, pos_test = scale.split_class(list(range(398)), random.Random(0))
    neg_train, neg_val, neg_test = scale.split_class(list(range(511)), random.Random(0))
    assert (len(pos_train), len(pos_val), len(pos_test)) == (239, 80, 79)
    assert (len(neg_train), len(neg_val), len(neg_test)) == (307, 102, 102)
