"""Minimal ACP-shaped JSON-RPC server for transport tests (stdio, newline-delimited).

Behaviour by method:
- initialize           -> result with protocolVersion
- echo                 -> result echoes params
- session/prompt       -> emits one session/update notification, sends a
                          server request session/request_permission, waits for
                          its reply, then answers the prompt with that reply
- crash                -> exits without answering (simulates provider crash)
- slow                 -> answers after a delay (timeout tests)
"""

from __future__ import annotations

import json
import sys
import time


def send(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": 1}})
        elif method == "echo":
            send({"jsonrpc": "2.0", "id": req_id, "result": params})
        elif method == "session/prompt":
            send({"jsonrpc": "2.0", "method": "session/update",
                  "params": {"sessionId": "s1", "update": "started"}})
            send({"jsonrpc": "2.0", "id": "perm-1", "method": "session/request_permission",
                  "params": {"action": "write"}})
            reply = json.loads(sys.stdin.readline())
            send({"jsonrpc": "2.0", "id": req_id,
                  "result": {"stopReason": "end_turn", "permission": reply.get("result")}})
        elif method == "crash":
            sys.exit(3)
        elif method == "slow":
            time.sleep(float(params.get("seconds", 1)))
            send({"jsonrpc": "2.0", "id": req_id, "result": "late"})
        elif method == "fail":
            send({"jsonrpc": "2.0", "id": req_id,
                  "error": {"code": -32000, "message": "boom"}})
        # notifications (no id) are accepted silently


if __name__ == "__main__":
    main()
