"""R24 live probe rss_check must not let 0.1 MB display rounding flip a miss into a pass."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from hive_planner.voice_bot import rss_meets_target

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "voice_r24_latency_probe.py"


def _load_probe():
    spec = importlib.util.spec_from_file_location("voice_r24_latency_probe", PROBE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    return _load_probe()


def test_rss_bytes_meet_target_rejects_tight_overage_that_rounds_to_limit(probe) -> None:
    over_bytes = int(650.04 * probe.BYTES_PER_MB)
    displayed = round(over_bytes / probe.BYTES_PER_MB, 1)
    assert displayed == 650.0
    assert rss_meets_target(displayed, 650) is True
    assert probe.rss_bytes_meet_target(over_bytes, 650) is False


def test_rss_bytes_meet_target_still_passes_measured_peak(probe) -> None:
    peak_bytes = int(630.2 * probe.BYTES_PER_MB)
    assert probe.rss_bytes_meet_target(peak_bytes, 650) is True
    assert probe.rss_bytes_meet_target(peak_bytes, None) is True
