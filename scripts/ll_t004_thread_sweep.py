"""Operator LL-T004(c): spawn llama-server per thread pair; Moshi-shaped POST timings.

Does not change rag_timeout, 96, or R40 3/8/4000. Does not autostart from Hive listen.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOG_DIR = REPO / ".hive" / "voice-bot"
PID_FILE = LOG_DIR / "rag_llm_8002.pid"
OUT = LOG_DIR / "ll-t004-thread-sweep.json"
MODELS = "http://127.0.0.1:8002/v1/models"
CHAT = "http://127.0.0.1:8002/v1/chat/completions"
ALIAS = os.environ.get("LLM_MODEL_NAME") or "Qwen/Qwen2.5-1.5B-Instruct"


def _exe() -> Path:
    raw = os.environ.get("LLAMA_SERVER_EXE") or ""
    path = Path(raw)
    if not path.is_file():
        raise SystemExit("LLAMA_SERVER_EXE is not set or not found")
    return path


def _gguf() -> Path:
    raw = os.environ.get("LLAMA_GGUF_PATH") or ""
    path = Path(raw)
    if not path.is_file():
        raise SystemExit("LLAMA_GGUF_PATH is not set or not found")
    return path


def _http_up(timeout: float = 2.0) -> bool:
    req = urllib.request.Request(MODELS, headers={"Authorization": "Bearer dummy"})
    try:
        urllib.request.urlopen(req, timeout=timeout).close()
        return True
    except urllib.error.HTTPError as exc:
        return exc.code != 503
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def _kill_port() -> None:
    if PID_FILE.is_file():
        raw = PID_FILE.read_text(encoding="utf-8").strip()
        if raw.isdigit():
            subprocess.run(["taskkill", "/PID", raw, "/F"], capture_output=True, check=False)
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction SilentlyContinue |"
            " ForEach-Object { taskkill /PID $_.OwningProcess /F }",
        ],
        capture_output=True,
        check=False,
    )
    deadline = time.time() + 25
    while time.time() < deadline:
        if not _http_up():
            return
        time.sleep(0.4)
    raise SystemExit("llama-server still answering after stop")


def _start(threads: int, batch: int) -> subprocess.Popen:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    err = (LOG_DIR / "ll-t004-sweep.err").open("ab")
    out = (LOG_DIR / "ll-t004-sweep.out").open("ab")
    env = os.environ.copy()
    env.pop("CUDA_VISIBLE_DEVICES", None)
    args = [
        str(_exe()),
        "-m",
        str(_gguf()),
        "--host",
        "127.0.0.1",
        "--port",
        "8002",
        "--api-key",
        "dummy",
        "--alias",
        ALIAS,
        "-ngl",
        "0",
        "--parallel",
        "1",
        "--cache-ram",
        "0",
        "--fit",
        "off",
        "--ctx-size",
        "4096",
        "--threads",
        str(threads),
        "--threads-batch",
        str(batch),
    ]
    proc = subprocess.Popen(args, cwd=str(LOG_DIR), env=env, stdout=out, stderr=err)
    deadline = time.time() + 90
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"llama-server exited {proc.returncode} t={threads} tb={batch}")
        if _http_up():
            PID_FILE.write_text(str(proc.pid), encoding="utf-8")
            return proc
        time.sleep(0.4)
    proc.kill()
    raise SystemExit(f"llama-server not ready t={threads} tb={batch}")


def _post(context_chars: int = 4000) -> dict:
    ctx = ("Retrieval block. " * ((context_chars // 16) + 1))[:context_chars]
    body = json.dumps(
        {
            "model": ALIAS,
            "messages": [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "Reply with one short line of context for Moshi."}],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Say a one-line fact.\n\n" + ctx}],
                },
            ],
            "max_tokens": 96,
            "temperature": 0,
            "reasoning_effort": "low",
            "stop": ["\n"],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        CHAT,
        data=body,
        headers={"Authorization": "Bearer dummy", "Content-Type": "application/json"},
        method="POST",
    )
    payload = None
    wall_ms = 0.0
    deadline = time.time() + 90
    last_err: Exception | None = None
    while time.time() < deadline:
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            wall_ms = (time.perf_counter() - t0) * 1000
            break
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in (401,):
                raise
            # 503: weights still loading after /v1/models started answering.
            time.sleep(1.0)
    if payload is None:
        raise last_err or SystemExit("chat POST never succeeded")
    timings = payload.get("timings") or {}
    choice = (payload.get("choices") or [{}])[0]
    text = ((choice.get("message") or {}).get("content") or "")[:80]
    return {
        "wall_ms": round(wall_ms, 1),
        "prompt_ms": timings.get("prompt_ms"),
        "predicted_ms": timings.get("predicted_ms"),
        "prompt_n": timings.get("prompt_n"),
        "predicted_n": timings.get("predicted_n"),
        "cache_n": timings.get("cache_n"),
        "draft_n": timings.get("draft_n"),
        "draft_n_accepted": timings.get("draft_n_accepted"),
        "text": text,
    }


def default_cores(argv: list[str], detected: int | None = None) -> int:
    """Host core count, or an explicit argv integer. Not a hardcoded 36-core lab box."""
    if len(argv) > 1:
        try:
            value = int(argv[1])
        except ValueError as exc:
            raise SystemExit("cores must be a positive integer") from exc
        if value < 1:
            raise SystemExit("cores must be a positive integer")
        return value
    n = os.cpu_count() if detected is None else detected
    return max(1, int(n or 1))


def cold_score(row: dict) -> float:
    """Uncached mixed-tail prefill. Identical-prompt warm is not the metric (LL-T004)."""
    ms = row["cold"].get("prompt_ms")
    if ms is None:
        return float(row["cold"]["wall_ms"])
    return float(ms)


def main() -> None:
    cores = default_cores(sys.argv)
    ordered: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for n in (8, 12, 16, 20, 24, 32):
        if n <= cores:
            pair = (n, n)
            if pair not in seen:
                seen.add(pair)
                ordered.append(pair)
    baseline = (max(1, cores - 2), cores)
    if baseline not in seen:
        ordered.append(baseline)

    rows = []
    proc: subprocess.Popen | None = None
    try:
        for threads, batch in ordered:
            print(f"pair threads={threads} batch={batch}", flush=True)
            if proc is not None:
                proc.kill()
                proc.wait(timeout=15)
            _kill_port()
            proc = _start(threads, batch)
            cold = _post()
            warm = _post()
            row = {"threads": threads, "threads_batch": batch, "cold": cold, "warm": warm}
            rows.append(row)
            print(json.dumps(row), flush=True)
    finally:
        if proc is not None:
            proc.kill()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
        _kill_port()

    if not rows:
        raise SystemExit("no rows")
    winner = min(rows, key=cold_score)
    OUT.write_text(json.dumps({"cores": cores, "rows": rows, "winner_cold": winner}, indent=2), encoding="utf-8")
    print("WINNER", json.dumps(winner), flush=True)
    proc = _start(winner["threads"], winner["threads_batch"])
    print(f"left running pid={proc.pid} t={winner['threads']} tb={winner['threads_batch']}", flush=True)


if __name__ == "__main__":
    main()
