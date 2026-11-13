"""Live G5 probe (T016 / AC 4-5): real agent acp, one ask-mode turn, follow-up queued while running,
playback interruption, then persisted state read back. Runs in a throwaway repo, never in the project."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
sys.path.insert(0, str(REPO / "src"))

from voice_turn_support import make_repo, wait_task_state, wait_task_terminal  # noqa: E402
from hive_planner.voice_task import VoiceTaskRunner  # noqa: E402

AGENT = os.path.join(os.environ.get("LOCALAPPDATA", ""), "cursor-agent", "agent.cmd")
RUNNING_WAIT_S = 180
TERMINAL_WAIT_S = 240


def main() -> dict:
    root = Path(tempfile.mkdtemp(prefix="g5-live-"))
    paths = make_repo(root)
    runner = VoiceTaskRunner(paths, "Voice_Bot", agent_path=AGENT, request_timeout=RUNNING_WAIT_S)
    out = {"repo": str(root)}
    try:
        t0 = time.monotonic()
        first = runner.submit(
            "In one sentence, describe what add(a, b) does in src/app.py. Read only; do not edit any file.",
            client_request_id="g5-live-1",
            mode="ask",
        )
        out["first_submit"] = {k: first.get(k) for k in ("status", "task_id", "state")}
        tid = first.get("task_id")
        if not tid:
            out["error"] = "first submit returned no task_id"
            return out
        wait_task_state(runner, tid, "running", timeout=RUNNING_WAIT_S)
        out["running_at_s"] = round(time.monotonic() - t0, 2)

        follow = runner.submit("Also, which file did I ask about?", client_request_id="g5-live-2", mode="ask")
        out["follow_up_while_running"] = {k: follow.get(k) for k in ("status", "state", "task_id")}

        runner.interrupt_playback()
        out["state_after_interrupt"] = runner.state.coding_tasks[tid].state

        out["terminal_state"] = wait_task_terminal(runner, tid, timeout=TERMINAL_WAIT_S)
        out["terminal_reason"] = runner.state.coding_tasks[tid].reason
        out["total_s"] = round(time.monotonic() - t0, 2)
    finally:
        runner.close()

    state_file = root / ".hive" / "voice-bot" / "state.json"
    if state_file.exists():
        st = json.loads(state_file.read_text(encoding="utf-8"))
        out["queue"] = st.get("queue") or st.get("queue_entries")
        out["event_types"] = sorted({e.get("type") or e.get("event") or "?" for e in (st.get("events") or [])})[:30]
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
