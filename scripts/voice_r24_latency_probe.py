"""Live R24 probe (T018): time to first spoken_update and process resource use on the pinned runtime.

Runs one read-only ask turn against real `agent acp` in a throwaway repo (never in the project).
Measures, on the monotonic clock:
- submit_to_first_spoken_s: submit() call start -> first non-empty evidence.spoken_update
- submit_to_running_s: submit() call start -> state == running (task.started)
- submit_to_terminal_spoken_s: submit() call start -> spoken_update of the terminal outcome
Samples this process and its descendants (agent acp child) with psutil every 0.25 s for RSS and CPU seconds.
Usage: py -3.11 scripts/voice_r24_latency_probe.py [runs]
"""
import json
import os
import platform
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "src"))

from voice_turn_support import make_repo  # noqa: E402
from hive_planner.voice_task import VoiceTaskRunner  # noqa: E402
from hive_planner.voice_bot import load_voice_bot_config, rss_meets_target  # noqa: E402

BYTES_PER_MB = 1048576


def rss_bytes_meet_target(peak_bytes: int, target_mb: int | None) -> bool:
    """Judge peak RSS against a target using the unrounded byte count.

    Display rounding to 0.1 MB must not flip a tight miss into a pass (R24 / AC20).
    """
    return rss_meets_target(peak_bytes / BYTES_PER_MB, target_mb)

AGENT = os.path.join(os.environ.get("LOCALAPPDATA", ""), "cursor-agent", "agent.cmd")
TERMINAL = ("completed", "failed", "cancelled")


class ResourceSampler:
    def __init__(self, interval: float = 0.25) -> None:
        self.interval = interval
        self.self_proc = psutil.Process(os.getpid())
        self.cpu_seen: dict[int, float] = {}
        self.peak_rss: dict[str, int] = {"voice_service": 0, "agent_children": 0}
        self.max_children = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _snapshot(self) -> None:
        procs = [self.self_proc] + self.self_proc.children(recursive=True)
        child_rss = 0
        self.max_children = max(self.max_children, len(procs) - 1)
        for p in procs:
            try:
                ct = p.cpu_times()
                self.cpu_seen[p.pid] = ct.user + ct.system
                rss = p.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if p.pid == self.self_proc.pid:
                self.peak_rss["voice_service"] = max(self.peak_rss["voice_service"], rss)
            else:
                child_rss += rss
        self.peak_rss["agent_children"] = max(self.peak_rss["agent_children"], child_rss)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._snapshot()
            self._stop.wait(self.interval)

    def start(self) -> None:
        ct = self.self_proc.cpu_times()
        # psutil CPU time is cumulative per process; keep a per-run baseline for this process.
        self._self_base = ct.user + ct.system
        self._snapshot()
        self._thread.start()

    def stop(self) -> dict:
        self._stop.set()
        self._thread.join(timeout=2)
        self._snapshot()
        voice_cpu = self.cpu_seen.get(self.self_proc.pid, 0.0) - self._self_base
        child_cpu = sum(v for pid, v in self.cpu_seen.items() if pid != self.self_proc.pid)
        return {
            "cpu_seconds_voice_service": round(voice_cpu, 2),
            "cpu_seconds_agent_children": round(child_cpu, 2),
            "peak_rss_mb_voice_service": round(self.peak_rss["voice_service"] / BYTES_PER_MB, 1),
            "peak_rss_mb_agent_children": round(self.peak_rss["agent_children"] / BYTES_PER_MB, 1),
            "max_concurrent_child_processes": self.max_children,
        }


def one_run(index: int) -> dict:
    root = Path(tempfile.mkdtemp(prefix="r24-probe-"))
    paths = make_repo(root)
    runner = VoiceTaskRunner(paths, "Voice_Bot", agent_path=AGENT, request_timeout=180)
    sampler = ResourceSampler()
    out: dict = {"run": index, "repo": str(root)}
    try:
        sampler.start()
        # Wall clock (UTC) to match the ISO "at" stamps the runner writes into task.events.
        t0_wall = datetime.now(timezone.utc)
        t0 = time.monotonic()
        first = runner.submit(
            "In one sentence, describe what add(a, b) does in src/app.py. Read only; do not edit any file.",
            client_request_id=f"r24-{index}",
            mode="ask",
        )
        out["submit_returned_s"] = round(time.monotonic() - t0, 3)
        tid = first["task_id"]
        task = runner.state.coding_tasks[tid]
        deadline = t0 + 240
        while time.monotonic() < deadline and task.state not in TERMINAL:
            time.sleep(0.05)
        out["final_state"] = task.state
        # Terminal state is set before _settle speaks the outcome; wait for the runner to finish settling.
        out["idle_after_settle"] = runner.wait_idle(timeout=30)
        out["total_s"] = round(time.monotonic() - t0, 3)

        def secs(at: str) -> float:
            return round((datetime.fromisoformat(at) - t0_wall).total_seconds(), 3)

        started = [e["at"] for e in task.events if e["name"] == "task.started"]
        speech = [(e["at"], e["payload"].get("text", "")) for e in task.events if e["name"] == "speech.spoken"]
        out["submit_to_running_s"] = secs(started[0]) if started else None
        # Every spoken_update the runner emitted, in order. Event stamps are the runner's own clock.
        out["spoken_updates"] = [{"at_s": secs(at), "text": text[:80]} for at, text in speech]
        out["submit_to_first_spoken_s"] = secs(speech[0][0]) if speech else None
        out["submit_to_terminal_spoken_s"] = secs(speech[-1][0]) if speech else None
    finally:
        out["resources"] = sampler.stop()
        runner.close()
    # AC20: judge peak RSS against the targets in the voice_bot config (not hard-coded here).
    cfg = load_voice_bot_config(paths)
    out["rss_check"] = {
        "voice_service_target_mb": cfg.voice_service_rss_target_mb,
        "voice_service_ok": rss_bytes_meet_target(
            sampler.peak_rss["voice_service"], cfg.voice_service_rss_target_mb
        ),
        "agent_children_target_mb": cfg.agent_children_rss_target_mb,
        "agent_children_ok": rss_bytes_meet_target(
            sampler.peak_rss["agent_children"], cfg.agent_children_rss_target_mb
        ),
    }
    return out


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    host = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor(),
        "logical_cpus": psutil.cpu_count(logical=True),
        "ram_gb": round(psutil.virtual_memory().total / 1073741824, 1),
        "agent": AGENT,
    }
    results = [one_run(i + 1) for i in range(runs)]
    print(json.dumps({"host": host, "runs": results}, indent=2, default=str))


if __name__ == "__main__":
    main()
