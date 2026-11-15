"""T047 / R35 fake agent for tests. Not a real Cursor agent.

On session/prompt it sends session/request_permission. If the client selects an allow option,
it writes the nonce file named in the prompt. If the prompt contains SKIP_WRITE, it never writes.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def send(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def main() -> None:
    next_id = 1000
    while True:
        line = sys.stdin.readline()
        if not line:
            return
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method = msg.get("method")
        mid = msg.get("id")
        if method is None:
            continue  # reply to one of our server requests
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": 1}})
        elif method == "session/new":
            send({"jsonrpc": "2.0", "id": mid, "result": {"sessionId": "live-write-s1"}})
        elif method == "session/set_mode":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif method == "session/prompt":
            params = msg.get("params") or {}
            text = " ".join(str(p.get("text", "")) for p in params.get("prompt") or [])
            nonce = re.search(r"HIVE_LIVE_WRITE_NONCE=(\w+)", text)
            target = re.search(r"file (\S+?) containing", text)
            if "SKIP_WRITE" not in text and nonce and target:
                next_id += 1
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": next_id,
                        "method": "session/request_permission",
                        "params": {
                            "sessionId": "live-write-s1",
                            "options": [
                                {"optionId": "allow-once", "kind": "allow_once"},
                                {"optionId": "reject-once", "kind": "reject_once"},
                            ],
                            "toolCall": {"kind": "edit"},
                        },
                    }
                )
                reply = json.loads(sys.stdin.readline() or "{}")
                outcome = (reply.get("result") or {}).get("outcome") or {}
                if outcome.get("optionId") == "allow-once":
                    path = Path(target.group(1))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f"HIVE_LIVE_WRITE_NONCE={nonce.group(1)}", encoding="utf-8")
            send({"jsonrpc": "2.0", "id": mid, "result": {"stopReason": "end_turn"}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "result": {}})


if __name__ == "__main__":
    main()
