from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


def _router():
    path = (
        Path(__file__).resolve().parents[1]
        / "code-improvements"
        / "BLUETTOOTH_SURROUND"
        / "src"
        / "bluettooth_surround"
        / "router.py"
    )
    src = path.parents[1]
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    spec = importlib.util.spec_from_file_location("bluettooth_surround_router_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bluettooth_surround_router_under_test"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_format_routing_health_counts_speakers_not_commas_in_names() -> None:
    router = _router()
    writer = SimpleNamespace(failed_error=None)
    device = SimpleNamespace(name="Headphones, Hands-Free AG Audio")
    streams = [(device, 2, 48000, None, writer, 0.0, None, None)]
    message = router.format_routing_health(streams)
    assert "1 mirrored speaker(s) active" in message
    assert "Headphones, Hands-Free AG Audio" in message
