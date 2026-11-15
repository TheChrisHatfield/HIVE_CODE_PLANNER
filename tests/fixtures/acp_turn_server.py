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
import os
import sys
import time

SESSIONS: dict[str, int] = {}
FS_WRITE_CAP = False  # set from initialize clientCapabilities.fs.writeTextFile (U11)
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


def emit_write_no_diff(session_id: str, call_id: str = "w-nodiff") -> None:
    """U6: a completed edit tool call with no diff content (a write the client sees no diff for)."""
    update(session_id, {"sessionUpdate": "tool_call", "toolCallId": call_id,
                        "title": "edit src/app.py", "kind": "edit"})
    update(session_id, {"sessionUpdate": "tool_call_update", "toolCallId": call_id,
                        "status": "completed", "content": []})


def emit_write_diff(session_id: str, call_id: str = "w1") -> None:
    """A completed tool call that carries an ACP `diff` content item (a file write)."""
    update(session_id, {"sessionUpdate": "tool_call", "toolCallId": call_id,
                        "title": "edit src/app.py", "kind": "edit"})
    update(session_id, {"sessionUpdate": "tool_call_update", "toolCallId": call_id,
                        "status": "completed",
                        "content": [{"type": "diff", "path": "src/app.py",
                                     "oldText": "return a + b\n",
                                     "newText": "return a - b\n"}]})


def run_turn(req_id, session_id: str, text: str) -> None:
    global _next_perm
    turn = SESSIONS.get(session_id, 0) + 1
    SESSIONS[session_id] = turn

    if "CRASH_MID_TURN" in text:
        text_chunk(session_id, "partial before crash")
        sys.exit(3)

    approval_marker = next(
        (m for m in ("NEEDS_APPROVAL", "NEEDS_EXEC_APPROVAL", "NEEDS_QUESTION", "NEEDS_PLAN") if m in text),
        None,
    )
    if approval_marker is not None:
        marker_text = f"{approval_marker}:"
        action = text.split(marker_text, 1)[1].strip() if marker_text in text else "edit file"
        kind = {"NEEDS_APPROVAL": "write_or_command", "NEEDS_EXEC_APPROVAL": "write_or_command",
                "NEEDS_QUESTION": "question", "NEEDS_PLAN": "plan"}[approval_marker]
        tool_kind = "execute" if approval_marker == "NEEDS_EXEC_APPROVAL" else "edit"
        _next_perm += 1
        perm_id = f"perm-{_next_perm}"
        send({"jsonrpc": "2.0", "id": perm_id, "method": "session/request_permission",
              "params": {
                  "sessionId": session_id,
                  "kind": kind,
                  "toolCall": {"toolCallId": f"tc-{perm_id}", "title": action, "kind": tool_kind},
                  "options": [
                      {"optionId": "allow", "name": "Allow", "kind": "allow_once"},
                      {"optionId": "reject", "name": "Reject", "kind": "reject_once"},
                  ],
              }})
        allowed = False
        while True:  # wait for the client's answer to this permission request
            msg = read_message()
            if msg is None:
                sys.exit(0)
            if msg.get("id") == perm_id and "result" in msg:
                outcome = msg["result"].get("outcome", {})
                allowed = outcome.get("outcome") == "selected"
                answer = msg["result"].get("answer")
                extra = f" answer={answer}" if answer is not None else ""
                text_chunk(session_id, f"permission outcome: {json.dumps(outcome)}{extra}")
                break
        # Real ACP: an approved write reuses the permission request's toolCallId.
        approved_call = f"tc-{perm_id}"
        if "WRITE_AFTER_EXEC_APPROVAL" in text:
            # R22: an approved non-write `execute` must not guard a later unapproved edit.
            emit_write_diff(session_id, "w-unguarded")
        elif allowed and "WRITE_SHELL_AFTER_EDIT_APPROVAL" in text:
            # R22: an approved edit for src/app.py must not guard a different, unapproved shell write.
            update(session_id, {"sessionUpdate": "tool_call", "toolCallId": "x-shell",
                                "title": "shell", "kind": "execute",
                                "rawInput": {"command": "echo changed > other.txt"}})
            update(session_id, {"sessionUpdate": "tool_call_update", "toolCallId": "x-shell",
                                "status": "completed", "rawOutput": {"exitCode": 0}})
        elif allowed and "WRITE_TWICE" in text:
            # U6: two writes after a single approval. The second must be unguarded.
            emit_write_diff(session_id, approved_call)
            emit_write_diff(session_id, "w2")
        elif allowed and "WRITE_NO_DIFF" in text:
            emit_write_no_diff(session_id, approved_call)
        elif allowed and "WRITE_DIFF" in text:
            emit_write_diff(session_id, approved_call)
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "FS_WRITE_REQUEST:" in text:
        # U11: the provider writes a file. With clientCapabilities.fs.writeTextFile false, the
        # agent writes on its own (no request reaches the client; R35 shows this shape). With
        # writeTextFile true, the agent routes the write through the client as fs/write_text_file.
        rel = text.split("FS_WRITE_REQUEST:", 1)[1].split()[0]
        if not FS_WRITE_CAP:
            os.makedirs(os.path.dirname(rel) or ".", exist_ok=True)
            with open(rel, "w", encoding="utf-8") as handle:
                handle.write("u11 provider self-write")
        else:
            _next_perm += 1
            write_id = f"fsw-{_next_perm}"
            send({"jsonrpc": "2.0", "id": write_id, "method": "fs/write_text_file",
                  "params": {"sessionId": session_id, "path": rel, "content": "u11 client write"}})
            while True:
                msg = read_message()
                if msg is None:
                    sys.exit(0)
                if msg.get("id") == write_id and ("result" in msg or "error" in msg):
                    break
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "WRITE_DIFF_UNGUARDED" in text:
        # Provider writes a file with no session/request_permission at all (R22 unguarded_write).
        emit_write_diff(session_id)
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "WRITE_NO_DIFF_UNGUARDED" in text:
        # U6: a write with no diff content and no permission request at all.
        emit_write_no_diff(session_id)
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "WRITE_EMPTY_ID_UNGUARDED" in text:
        # Empty toolCallId still carries kind=edit; that write must count.
        update(session_id, {"sessionUpdate": "tool_call", "toolCallId": "",
                            "title": "edit src/app.py", "kind": "edit"})
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "WRITE_THEN_CRASH" in text:
        emit_write_diff(session_id)
        sys.exit(3)

    if "WRITE_EXEC_UNGUARDED" in text:
        # U10: a shell write (redirect) as an `execute` tool call, with no session/request_permission.
        update(session_id, {"sessionUpdate": "tool_call", "toolCallId": "x1",
                            "title": "shell", "kind": "execute",
                            "rawInput": {"command": "echo changed > src/app.py"}})
        update(session_id, {"sessionUpdate": "tool_call_update", "toolCallId": "x1",
                            "status": "completed", "rawOutput": {"exitCode": 0}})
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "WRITE_EXEC_UPDATE_ONLY" in text:
        # Kind and command arrive only on tool_call_update (not on the opening tool_call).
        update(session_id, {"sessionUpdate": "tool_call", "toolCallId": "x3",
                            "title": "shell"})
        update(session_id, {"sessionUpdate": "tool_call_update", "toolCallId": "x3",
                            "kind": "execute", "status": "completed",
                            "rawInput": {"command": "echo changed > src/app.py"},
                            "rawOutput": {"exitCode": 0}})
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "WRITE_PY_EXEC_UNGUARDED" in text:
        # H1: an interpreter one-liner that writes a file; no redirect, no permission request.
        update(session_id, {"sessionUpdate": "tool_call", "toolCallId": "x2",
                            "title": "python", "kind": "execute",
                            "rawInput": {"command": "python -c \"open('src/app.py','w').write('x')\""}})
        update(session_id, {"sessionUpdate": "tool_call_update", "toolCallId": "x2",
                            "status": "completed", "rawOutput": {"exitCode": 0}})
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

    if "EXEC_SECRET" in text:
        # F3: an `execute` call whose arguments carry credentials. Evidence must mask them.
        update(session_id, {"sessionUpdate": "tool_call", "toolCallId": "s1",
                            "title": "ruff", "kind": "execute",
                            "rawInput": {"command": "ruff check --token=TESTSECRET123 --password hunter2 src/"}})
        update(session_id, {"sessionUpdate": "tool_call_update", "toolCallId": "s1",
                            "status": "completed", "rawOutput": {"exitCode": 0}})
        text_chunk(session_id, "checked")
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "REFUSE" in text:
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "refusal"}})
        return

    if "G6_WRITE_UNLESS_CANCEL" in text:
        _next_perm += 1
        perm_id = f"perm-{_next_perm}"
        send({"jsonrpc": "2.0", "id": perm_id, "method": "session/request_permission",
              "params": {
                  "sessionId": session_id,
                  "kind": "write_or_command",
                  "toolCall": {"toolCallId": f"tc-{perm_id}", "title": "write probe", "kind": "edit"},
                  "options": [
                      {"optionId": "allow-once", "name": "Allow", "kind": "allow_once"},
                      {"optionId": "reject-once", "name": "Reject", "kind": "reject_once"},
                  ],
              }})
        cancelled = False
        while True:
            msg = read_message()
            if msg is None:
                sys.exit(0)
            if msg.get("method") == "session/cancel":
                cancelled = True
            if msg.get("id") == perm_id and "result" in msg:
                break
        if not cancelled:
            time.sleep(0.8)
            probe = os.path.join(".hive", "voice-bot", "g6-live-probe.tmp")
            os.makedirs(os.path.dirname(probe), exist_ok=True)
            with open(probe, "w", encoding="utf-8") as handle:
                handle.write("probe")
        send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
        return

    if "HANG_PROMPT" in text:
        # Stays in the turn until session/cancel or stdin closes. Used to prove a client
        # timeout cannot leave this process holding the session for the next task.
        while True:
            msg = read_message()
            if msg is None:
                sys.exit(0)
            if msg.get("method") == "session/cancel":
                send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "cancelled"}})
                return
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
    global _next_session, FS_WRITE_CAP
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}
        if method == "initialize":
            caps = (params.get("clientCapabilities") or {}).get("fs") or {}
            FS_WRITE_CAP = bool(caps.get("writeTextFile"))
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
