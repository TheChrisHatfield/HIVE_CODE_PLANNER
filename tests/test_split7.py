from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAN_LOOP = ROOT / "scripts" / "gan-loop"
SCRIPTS = ROOT / "scripts"
for path in (str(GAN_LOOP), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

spec = importlib.util.spec_from_file_location("split7", GAN_LOOP / "_split7.py")
split7 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(split7)


def _parts(n: int, seed: int = 0):
    items = list(range(n))
    train, val, test = split7.split_class(items, random.Random(seed))
    return train, val, test


def test_split_class_n3_keeps_a_test_item():
    train, val, test = _parts(3)
    assert len(test) == 1
    assert len(train) + len(val) + len(test) == 3
    assert sorted(train + val + test) == [0, 1, 2]


def test_split_class_n1_puts_the_item_in_test():
    train, val, test = _parts(1)
    assert train == []
    assert val == []
    assert test == [0]


def test_split_class_locked_blend_sizes_keep_60_20_20():
    pos_train, pos_val, pos_test = _parts(398)
    neg_train, neg_val, neg_test = _parts(205)
    assert (len(pos_train), len(pos_val), len(pos_test)) == (239, 80, 79)
    assert (len(neg_train), len(neg_val), len(neg_test)) == (123, 41, 41)
