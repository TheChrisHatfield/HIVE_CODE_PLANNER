"""ACP-shaped turn server for Voice_Bot runner tests (stdio, newline-delimited JSON-RPC).

Implements just enough of the ACP session surface for T004-T011 tests:

- initialize                -> protocolVersion 1
- session/new               -> new sessionId per process (sess-1, sess-2, ...)
- session/set_mode          -> ok for ask/plan/agent; error for unknown modes
- session/prompt            -> behaviour chosen by marker text in the prompt:
    CRASH_MID_TURN          streams one chunk, then exits (provider disconnect)
    NEEDS_APPROVAL:<action> sends session/request_permission, waits for the reply,
                            then streams the outcome and ends the turn
    RUN_TESTS_PASS          execute tool call `pytest -q` with exit code 0
    RUN_TESTS_FAIL          execute tool call `pytest -q` with exit code 1
    RUN_LINT                execute tool call `ruff check` (not a test command)
    REFUSE                  stopReason refusal
    CANCEL_ME               waits for session/cancel, then stopReason cancelled
    (default)               one chunk naming the session turn number, stopReason end_turn
- session/cancel           -> notification; consumed by a CANCEL_ME turn
"""

from __future__ import annotations

import json
import sys

SESSIONS: dict[str, int] = {}
_next_session = 0
_next_perm = 0


def send(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def update(session_id: str, update_body: dict) -> None:
    send({"jsonrpc": "2.0", "method": "session/update",
          "params": {"sessionId": session_id, "update": update_body}})


def text_chunk(session_id: str, text: str) -> None:
    update(session_id, {"sessionUpdate": "agent_message_chunk",
                        "content": {"type": "text", "text": text}})


def read_message() -> dict | None:
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)


def run_turn(req_id, session_id: str, text: str) -> None:
    global _next_perm
    turn = SESSIONS.get(session_id, 0) + 1
    SESSIONS[session_id] = turn

    if "CRASH_MID_TURN" in text:
        text_chunk(session_id, "partial before crash")
        sys.exit(3)

    approval_marker = next(
        (m for m in ("NEEDS_APPROVAL", "NEEDS_QUESTION", "NEEDS_PLAN") if m in text), None
    )
    if approval_marker is not None:
        marker_text = f"{approval_marker}:"
        action = text.split(marker_text, 1)[1].strip() if marker_text in text else "edit file"
        kind = {"NEEDS_APPROVAL": "write_or_command", "NEEDS_QUESTION": "question",
                "NEEDS_PLAN": "plan"}[approval_marker]
        _next_perm += 1
        perm_id = f"perm-{_next_perm}"
        send({"jsonrpc": "2.0", "id": perm_id, "method": "session/request_permission",
              "params": {
                  "sessionId": session_id,
                  "kind": kind,
                  "toolCall": {"toolCallId": f"tc-{perm_id}", "title": action, "kind": "edit"},
                  "options": [
                      {"optionId": "allow", "name": "Allow", "kind": "allow_once"},
                      {"optionId": "reject", "name": "Reject", "kind": "reject_once"},
                  ],
              }})
        while True:  # wait for the client's answer to this permission request
            msg = read_message()
            if msg is None:
                sys.exit(0)
            if msg.get("id") == perm_id and "result" in msg:
                outcome = msg["result"].get("outcome", {})
                text_chunk(session_id, f"permission outcome: {json.dumps(outcome)}")
                break
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "RUN_TESTS_PASS" in text or "RUN_TESTS_FAIL" in text:
        code = 0 if "RUN_TESTS_PASS" in text else 1
        update(session_id, {"sessionUpdate": "tool_call", "toolCallId": "c1",
                            "title": "pytest", "kind": "execute",
                            "rawInput": {"command": "pytest -q"}})
        update(session_id, {"sessionUpdate": "tool_call_update", "toolCallId": "c1",
                            "status": "completed", "rawOutput": {"exitCode": code}})
        text_chunk(session_id, f"ran tests, exit {code}")
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "RUN_LINT" in text:
        update(session_id, {"sessionUpdate": "tool_call", "toolCallId": "c2",
                            "title": "ruff", "kind": "execute",
                            "rawInput": {"command": "ruff check"}})
        update(session_id, {"sessionUpdate": "tool_call_update", "toolCallId": "c2",
                            "status": "completed", "rawOutput": {"exitCode": 0}})
        text_chunk(session_id, "linted")
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "REFUSE" in text:
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "refusal"}})
        return

    if "CANCEL_ME" in text:
        text_chunk(session_id, "working")
        while True:
            msg = read_message()
            if msg is None:
                sys.exit(0)
            if msg.get("method") == "session/cancel":
                break
        # IGNORE_CANCEL: the provider finishes normally and does not acknowledge the cancel.
        stop = "end_turn" if "IGNORE_CANCEL" in text else "cancelled"
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": stop}})
        return

    text_chunk(session_id, f"turn {turn} in {session_id}: {text[:120]}")
    send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})


def main() -> None:
    global _next_session
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": 1}})
        elif method == "session/new":
            _next_session += 1
            sid = f"sess-{_next_session}"
            SESSIONS[sid] = 0
            send({"jsonrpc": "2.0", "id": req_id, "result": {"sessionId": sid}})
        elif method == "session/set_mode":
            mode = params.get("modeId")
            if mode in ("ask", "plan", "agent"):
                send({"jsonrpc": "2.0", "id": req_id, "result": {}})
            else:
                send({"jsonrpc": "2.0", "id": req_id,
                      "error": {"code": -32602, "message": f"unknown mode {mode}"}})
        elif method == "session/prompt":
            blocks = params.get("prompt") or []
            text = " ".join(str(b.get("text", "")) for b in blocks if isinstance(b, dict))
            run_turn(req_id, str(params.get("sessionId")), text)
        # notifications (no id) such as session/cancel outside a turn are accepted silently


if __name__ == "__main__":
    main()
