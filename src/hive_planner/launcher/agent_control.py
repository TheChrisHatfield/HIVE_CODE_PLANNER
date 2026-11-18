"""Loopback control plane so mcp-serve can drive a running Hive Planner GUI.

The GUI process owns the socket. Cursor's `mcp-serve` is a different process and
must POST here; it must not open Moshi or send 0x00.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

CONTROL_REL = Path(".hive") / "launcher" / "agent-control.json"
TEMP_NAME = "hive-planner-agent-control.json"

ACTIONS: dict[str, str] = {
    "voice.talk": "Same as the mic button: start listening / Moshi call.",
    "voice.hangup": "Same as the mic button off: stop the call or finish a WAV.",
    "voice.toggle": "Same as clicking the mic once.",
    "voice.end_call": "Same as the hang-up control.",
    "voice.submit_typed": "Same as the typed-instruction side button. Args: text.",
    "voice.bridge_start": "Start the launcher-owned voice bridge (no yes/no dialog).",
    "voice.bridge_stop": "Stop the launcher-owned voice bridge (no yes/no dialog).",
    "voice.live": "Live panel: listening, connecting, notices, speak_now.",
    "launcher.status": "Portable flag, pid, active project, hive root.",
    "launcher.catalog": "Allow-listed actions and home-button ids.",
    "launcher.home": "Same as a Home button. Args: action_id.",
}

Dispatch = Callable[[str, dict[str, Any]], dict[str, Any]]


def control_path(hive_root: Path) -> Path:
    return Path(hive_root).resolve() / CONTROL_REL


def temp_control_path(hive_root: Path | None = None) -> Path:
    override = os.environ.get("HIVE_AGENT_CONTROL_FILE", "").strip()
    if override:
        return Path(override)
    if hive_root is not None:
        digest = hashlib.sha256(str(Path(hive_root).resolve()).encode("utf-8")).hexdigest()[:16]
        return Path(tempfile.gettempdir()) / f"hive-planner-agent-control-{digest}.json"
    return Path(tempfile.gettempdir()) / TEMP_NAME


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    except AttributeError:
        return False
    return True


def candidate_control_files(root: Path | None) -> list[Path]:
    files: list[Path] = []
    if root is not None:
        resolved = Path(root).resolve()
        files.append(temp_control_path(resolved))
        files.append(control_path(resolved))
        files.append(resolved / "dist" / "HivePlannerPortable" / CONTROL_REL)
    else:
        files.append(temp_control_path())
    seen: set[Path] = set()
    out: list[Path] = []
    for path in files:
        try:
            key = path.resolve()
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def load_control_doc(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        pid = int(raw.get("pid") or 0)
        port = int(raw.get("port") or 0)
    except (TypeError, ValueError):
        return None
    token = str(raw.get("token") or "").strip()
    if pid <= 0 or port <= 0 or not token:
        return None
    if not pid_alive(pid):
        return None
    stored_root = str(raw.get("hive_root") or "").strip()
    return {
        "pid": pid,
        "port": port,
        "token": token,
        "path": str(path),
        "hive_root": stored_root,
    }


def _hive_root_ok(doc: dict[str, Any], want: Path | None) -> bool:
    if want is None:
        return True
    stored = str(doc.get("hive_root") or "").strip()
    if stored:
        try:
            return Path(stored).resolve() == want
        except OSError:
            return False
    try:
        return Path(doc["path"]).resolve().is_relative_to(want)
    except (OSError, TypeError, ValueError):
        return False


def matching_control_docs(root: Path | None) -> list[dict[str, Any]]:
    want = Path(root).resolve() if root is not None else None
    by_pid: dict[int, dict[str, Any]] = {}
    for path in candidate_control_files(root):
        if not path.is_file():
            continue
        doc = load_control_doc(path)
        if doc is None or not _hive_root_ok(doc, want):
            continue
        by_pid[int(doc["pid"])] = doc
    return list(by_pid.values())


def discover_control(root: Path | None) -> dict[str, Any] | None:
    rows = matching_control_docs(root)
    if not rows:
        return None
    if len(rows) > 1:
        return {"ambiguous": True, "instances": rows}
    return rows[0]


def write_control_docs(hive_root: Path, payload: dict[str, Any]) -> list[Path]:
    text = json.dumps(payload, indent=2)
    written: list[Path] = []
    hive_root = Path(hive_root).resolve()
    for path in (control_path(hive_root), temp_control_path(hive_root)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        written.append(path)
    return written


def remove_control_docs(hive_root: Path, pid: int) -> None:
    hive_root = Path(hive_root).resolve()
    for path in (control_path(hive_root), temp_control_path(hive_root)):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            continue
        if int(raw.get("pid") or 0) != pid:
            continue
        try:
            path.unlink()
        except OSError:
            pass


def call_live_launcher(
    root: Path | None,
    *,
    action: str | None = None,
    arguments: dict[str, Any] | None = None,
    live: bool = False,
    catalog: bool = False,
    timeout: float = 60.0,
) -> dict[str, Any]:
    doc = discover_control(root)
    if doc is None:
        return {
            "ok": False,
            "error": "launcher_not_running",
            "hint": "Start HivePlanner.exe so the loopback control plane can bind, then retry.",
        }
    if doc.get("ambiguous"):
        rows = []
        for item in doc.get("instances") or []:
            if isinstance(item, dict):
                rows.append({"pid": item.get("pid"), "hive_root": item.get("hive_root")})
        return {"ok": False, "error": "ambiguous_launcher", "instances": rows}
    headers = {"Authorization": f"Bearer {doc['token']}", "Content-Type": "application/json"}
    if catalog:
        path = "/v1/agent/catalog"
        data = None
        method = "GET"
    elif live or not action:
        path = "/v1/agent/live"
        data = None
        method = "GET"
    else:
        path = "/v1/agent/invoke"
        data = json.dumps({"action": action, "arguments": dict(arguments or {})}).encode("utf-8")
        method = "POST"
    req = urllib.request.Request(
        f"http://127.0.0.1:{doc['port']}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeError):
            return {"ok": False, "error": f"http_{exc.code}", "pid": doc["pid"], "port": doc["port"]}
        if isinstance(body, dict):
            body.setdefault("ok", False)
            return body
        return {"ok": False, "error": f"http_{exc.code}"}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeError) as exc:
        return {"ok": False, "error": str(exc) or "launcher_unreachable", "pid": doc["pid"]}
    if not isinstance(body, dict):
        return {"ok": False, "error": "invalid_control_payload"}
    body.setdefault("ok", True)
    body["pid"] = doc["pid"]
    body["port"] = doc["port"]
    return body


class AgentControlServer:
    """127.0.0.1 HTTP server that forwards allow-listed actions to the GUI."""

    def __init__(self, hive_root: Path, dispatch: Dispatch) -> None:
        self.hive_root = Path(hive_root).resolve()
        self.dispatch = dispatch
        self.token = secrets.token_urlsafe(32)
        self.pid = os.getpid()
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(self))
        self.port = int(self._httpd.server_address[1])
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="hive-agent-control", daemon=True)

    def start(self) -> None:
        write_control_docs(
            self.hive_root,
            {
                "pid": self.pid,
                "port": self.port,
                "token": self.token,
                "bind": "127.0.0.1",
                "hive_root": str(self.hive_root),
            },
        )
        self._thread.start()

    def stop(self) -> None:
        try:
            self._httpd.shutdown()
        except Exception:
            pass
        try:
            self._httpd.server_close()
        except Exception:
            pass
        remove_control_docs(self.hive_root, self.pid)


def _make_handler(server: AgentControlServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _client_ok(self) -> bool:
            host = str(self.client_address[0] or "")
            return host in {"127.0.0.1", "::1", "localhost"}

        def _auth_ok(self) -> bool:
            header = str(self.headers.get("Authorization") or "")
            return header == f"Bearer {server.token}"

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeError):
                return {}
            return data if isinstance(data, dict) else {}

        def _send(self, code: int, payload: dict[str, Any]) -> None:
            blob = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)

        def do_GET(self) -> None:  # noqa: N802
            if not self._client_ok() or not self._auth_ok():
                self._send(401, {"ok": False, "error": "unauthorized"})
                return
            if self.path == "/v1/agent/catalog":
                self._send(200, server.dispatch("launcher.catalog", {}))
                return
            if self.path == "/v1/agent/live":
                self._send(200, server.dispatch("voice.live", {}))
                return
            self._send(404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._client_ok() or not self._auth_ok():
                self._send(401, {"ok": False, "error": "unauthorized"})
                return
            if self.path != "/v1/agent/invoke":
                self._send(404, {"ok": False, "error": "not_found"})
                return
            body = self._read_json()
            action = str(body.get("action") or "").strip()
            raw_args = body.get("arguments")
            arguments = raw_args if isinstance(raw_args, dict) else {}
            if action not in ACTIONS:
                self._send(400, {"ok": False, "error": "agent_action_unknown", "action": action})
                return
            result = server.dispatch(action, arguments)
            code = 400 if result.get("error") == "agent_action_unknown" else 200
            self._send(code, result)

    return Handler


def start_agent_control(app: Any) -> AgentControlServer:
    from hive_planner.runtime_paths import default_hive_root

    hive_root = default_hive_root()
    server = AgentControlServer(hive_root, lambda action, args: dispatch_app_action(app, action, args))
    server.start()
    return server


def stop_agent_control(server: AgentControlServer | None) -> None:
    if server is not None:
        server.stop()


def _marshal(app: Any, fn: Callable[[], dict[str, Any]], timeout: float = 60.0) -> dict[str, Any]:
    root = getattr(app, "root", None)
    after = getattr(root, "after", None) if root is not None else None
    if not callable(after):
        return fn()
    box: dict[str, Any] = {}
    done = threading.Event()

    def wrapped() -> None:
        try:
            box["payload"] = fn()
        except Exception as exc:
            box["payload"] = {"ok": False, "error": str(exc)}
        finally:
            done.set()

    try:
        after(0, wrapped)
    except Exception as exc:
        return {"ok": False, "error": str(exc) or "launcher_ui_gone"}
    if not done.wait(timeout):
        return {"ok": False, "error": "launcher_ui_timeout"}
    payload = box.get("payload")
    return payload if isinstance(payload, dict) else {"ok": False, "error": "invalid_dispatch"}


def dispatch_app_action(app: Any, action: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = dict(arguments or {})
    if action not in ACTIONS:
        return {"ok": False, "error": "agent_action_unknown", "action": action}

    def run() -> dict[str, Any]:
        return _dispatch_on_ui(app, action, args)

    return _marshal(app, run)


def _notice_text(app: Any) -> str | None:
    ctrl = getattr(app, "voice_controller", None)
    feed = getattr(ctrl, "notice_feed", None)
    if not callable(feed):
        return None
    row = feed()
    if not row or len(row) < 2:
        return None
    text = row[1]
    return str(text) if text else None


def _live_payload(app: Any) -> dict[str, Any]:
    panel = getattr(app, "voice_panel", None)
    ctrl = getattr(app, "voice_controller", None)
    listening = bool(getattr(panel, "listening", False) or getattr(ctrl, "mic_active", False))
    connecting_fn = getattr(ctrl, "mic_connecting", None)
    connecting = bool(connecting_fn()) if callable(connecting_fn) else False
    return {
        "ok": True,
        "listening": listening,
        "connecting": connecting,
        "notice": _notice_text(app),
        "speak_now": bool(listening and not connecting),
        "cue": "Speak now. The Hive mic is on." if listening and not connecting else None,
        "active_project": str(getattr(getattr(app, "config", None), "active_project", "") or "") or None,
        "pid": os.getpid(),
    }


def _home_ids(app: Any) -> list[str]:
    try:
        from hive_planner.launcher.home_groups import HOME_ACTIONS

        return [str(key) for key in HOME_ACTIONS]
    except Exception:
        return []


def _dispatch_on_ui(app: Any, action: str, args: dict[str, Any]) -> dict[str, Any]:
    panel = getattr(app, "voice_panel", None)
    ctrl = getattr(app, "voice_controller", None)
    if action == "launcher.catalog":
        return {
            "ok": True,
            "actions": [{"id": key, "description": desc} for key, desc in ACTIONS.items()],
            "home_action_ids": _home_ids(app),
        }
    if action in {"voice.live", "launcher.status"}:
        live = _live_payload(app)
        if action == "launcher.status":
            from hive_planner.runtime_paths import default_hive_root, is_portable_runtime

            live["portable"] = is_portable_runtime()
            live["hive_root"] = str(default_hive_root())
        return live
    if action == "voice.talk":
        if panel is None or not hasattr(panel, "apply_mic"):
            return {"ok": False, "error": "voice_panel_missing"}
        refusal = panel.apply_mic(True)
        live = _live_payload(app)
        if refusal:
            live.update({"ok": False, "error": str(refusal), "speak_now": False, "cue": None})
            return live
        live["ok"] = True
        return live
    if action == "voice.hangup":
        if panel is None or not hasattr(panel, "apply_mic"):
            return {"ok": False, "error": "voice_panel_missing"}
        refusal = panel.apply_mic(False)
        live = _live_payload(app)
        if refusal:
            live.update({"ok": False, "error": str(refusal)})
            return live
        live["ok"] = True
        live["speak_now"] = False
        live["cue"] = None
        return live
    if action == "voice.toggle":
        listening = bool(getattr(panel, "listening", False))
        return _dispatch_on_ui(app, "voice.hangup" if listening else "voice.talk", args)
    if action == "voice.end_call":
        end = getattr(panel, "_end_call", None)
        if not callable(end):
            return {"ok": False, "error": "voice_panel_missing"}
        end()
        live = _live_payload(app)
        live["ok"] = True
        live["speak_now"] = False
        return live
    if action == "voice.submit_typed":
        text = str(args.get("text") or "").strip()
        if not text:
            return {"ok": False, "error": "text is required"}
        submit = getattr(ctrl, "submit_typed", None)
        if not callable(submit):
            return {"ok": False, "error": "voice_controller_missing"}
        result = submit(text)
        ok = bool(getattr(result, "ok", False))
        message = str(getattr(result, "message", "") or "")
        if isinstance(result, dict):
            ok = bool(result.get("ok"))
            message = str(result.get("message") or "")
        return {"ok": ok, "message": message, "error": None if ok else message}
    if action == "voice.bridge_start":
        start = getattr(ctrl, "start_bridge", None)
        if not callable(start):
            return {"ok": False, "error": "voice_controller_missing"}
        started = start()
        ok = bool(getattr(started, "ok", False))
        code = str(getattr(started, "code", "") or "")
        return {"ok": ok, "error": None if ok else code or "bridge_start_failed", "code": code}
    if action == "voice.bridge_stop":
        stop = getattr(ctrl, "stop_bridge", None)
        if not callable(stop):
            return {"ok": False, "error": "voice_controller_missing"}
        stopped = stop()
        ok = bool(getattr(stopped, "ok", False))
        code = str(getattr(stopped, "code", "") or "")
        return {"ok": ok, "error": None if ok else code or "bridge_stop_failed", "code": code}
    if action == "launcher.home":
        action_id = str(args.get("action_id") or "").strip()
        lookup = getattr(app, "_home_action_command", None)
        if not action_id or not callable(lookup):
            return {"ok": False, "error": "action_id is required"}
        command = lookup(action_id)
        if command is None:
            return {"ok": False, "error": "agent_action_unknown", "action_id": action_id}
        command()
        return {"ok": True, "action_id": action_id}
    return {"ok": False, "error": "agent_action_unknown", "action": action}
