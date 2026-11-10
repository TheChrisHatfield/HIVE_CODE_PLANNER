// HIVE Voice_Bot editor adapter core (T007a scaffold, T007 context capture).
// Pure logic with no vscode import so it runs under `node --test`.
// Spec refs: R2 (truncation flags), R21 (size limits), R23 (path validation),
// R28 (no active file), R6 (approval fail-safe).

const path = require("node:path");

const APPROVAL_OUTCOMES = Object.freeze({
  APPROVED: "approved",
  DENIED: "denied",
  TIMED_OUT: "timed_out",
});

const DEFAULT_APPROVAL_TIMEOUT_MS = 120000; // R6 provisional default
// R21 default, mirrors VoiceBotConfig.snapshot_max_bytes in src/hive_planner/voice_bot.py.
const DEFAULT_SNAPSHOT_MAX_BYTES = 64 * 1024;
const VOICE_BOT_CONFIG_RELPATH = path.join(".hive", "voice-bot", "config.json");
// Index matches vscode.DiagnosticSeverity (Error=0, Warning=1, Information=2, Hint=3).
const SEVERITY_NAMES = Object.freeze(["error", "warning", "information", "hint"]);

// R23: the file must resolve inside the bound workspace root.
function isInsideWorkspace(rootPath, filePath) {
  const rel = path.relative(path.resolve(rootPath), path.resolve(rootPath, filePath));
  return rel !== "" && !rel.startsWith("..") && !path.isAbsolute(rel);
}

// R21: read snapshot_max_bytes from .hive/voice-bot/config.json (the file the Python side
// reads). `readFile(absPath)` is injected so tests need no disk access. A missing or
// unreadable file, bad JSON, or a non-positive value falls back to the default.
function loadSnapshotMaxBytes(workspaceRoot, readFile) {
  let raw;
  try {
    raw = readFile(path.join(workspaceRoot, VOICE_BOT_CONFIG_RELPATH));
  } catch (_err) {
    return DEFAULT_SNAPSHOT_MAX_BYTES;
  }
  let data;
  try {
    data = JSON.parse(raw);
  } catch (_err) {
    return DEFAULT_SNAPSHOT_MAX_BYTES;
  }
  const value = data && data.snapshot_max_bytes;
  return Number.isInteger(value) && value > 0 ? value : DEFAULT_SNAPSHOT_MAX_BYTES;
}

// Cut text to at most maxBytes of UTF-8 without splitting a character (R2, R21).
function truncateUtf8(text, maxBytes) {
  const buf = Buffer.from(text, "utf8");
  if (buf.length <= maxBytes) {
    return { text, bytes: buf.length, truncated: false };
  }
  let end = maxBytes;
  // A continuation byte (10xxxxxx) at the cut means a character would be split; back off.
  while (end > 0 && (buf[end] & 0xc0) === 0x80) end -= 1;
  return { text: buf.subarray(0, end).toString("utf8"), bytes: end, truncated: true };
}

// selection: { text, startLine, startCharacter, endLine, endCharacter } (0-based, as VS Code
// reports) or null when nothing is selected. Output positions are 1-based.
function buildSelection(selection, maxBytes) {
  if (!selection || !selection.text) return null;
  const cut = truncateUtf8(selection.text, maxBytes);
  return {
    text: cut.text,
    bytes: cut.bytes,
    truncated: cut.truncated,
    start: { line: selection.startLine + 1, column: selection.startCharacter + 1 },
    end: { line: selection.endLine + 1, column: selection.endCharacter + 1 },
  };
}

// diagnostics: VS Code-shaped { severity (0-3), message, source, code, line, character }
// with 0-based positions. Keeps diagnostics in order while their JSON size fits maxBytes.
// Once one does not fit, it and every later one are dropped and diagnostics_truncated is set,
// so the drop is never silent (R21).
function buildDiagnostics(diagnostics, maxBytes) {
  const kept = [];
  let used = 2; // "[]"
  let dropped = false;
  for (const d of diagnostics || []) {
    const item = {
      severity: SEVERITY_NAMES[d.severity] || "information",
      message: String(d.message || ""),
      source: d.source || null,
      code: d.code == null ? null : String(d.code),
      line: d.line + 1,
      column: d.character + 1,
    };
    const size = Buffer.byteLength(JSON.stringify(item), "utf8") + (kept.length ? 1 : 0);
    if (used + size > maxBytes) {
      dropped = true;
      break;
    }
    used += size;
    kept.push(item);
  }
  return { diagnostics: kept, diagnostics_truncated: dropped };
}

// T007 capture: workspace, file, version, dirty, selection, diagnostics, size limits.
// HIVE apply_snapshot_exclusions (T014) clears secret/binary/unsaved payload on submit.
function buildContextSnapshot({
  workspaceRoot,
  activeDocument,
  selection = null,
  diagnostics = [],
  maxBytes = DEFAULT_SNAPSHOT_MAX_BYTES,
}) {
  if (!workspaceRoot) {
    return { workspace: null, file: null, reason: "no_workspace" };
  }
  if (!activeDocument) {
    // R28: no active editor yields file null with reason no_active_file.
    return { workspace: workspaceRoot, file: null, reason: "no_active_file" };
  }
  const relative = path.relative(workspaceRoot, activeDocument.fileName);
  if (!isInsideWorkspace(workspaceRoot, relative)) {
    return { workspace: workspaceRoot, file: null, reason: "path_outside_workspace" };
  }
  const diag = buildDiagnostics(diagnostics, maxBytes);
  const dirty = Boolean(activeDocument.isDirty);
  let file_content = "";
  let file_truncated = false;
  if (!dirty && typeof activeDocument.text === "string") {
    const cut = truncateUtf8(activeDocument.text, maxBytes);
    file_content = cut.text;
    file_truncated = cut.truncated;
  }
  return {
    workspace: workspaceRoot,
    file: relative.split(path.sep).join("/"),
    document_version: activeDocument.version,
    dirty,
    selection: buildSelection(selection, maxBytes),
    file_content,
    file_truncated,
    diagnostics: diag.diagnostics,
    diagnostics_truncated: diag.diagnostics_truncated,
    reason: null,
  };
}

// Approval UI stub. Only an explicit "approve" answer approves.
// Anything else (deny, dismiss, no UI answer) is denied, and no answer before
// the timeout is timed_out. Nothing executes unless the outcome is approved.
async function requestApprovalStub({ kind, action }, ui, timeoutMs = DEFAULT_APPROVAL_TIMEOUT_MS) {
  let timer;
  const timeout = new Promise((resolve) => {
    timer = setTimeout(() => resolve({ outcome: APPROVAL_OUTCOMES.TIMED_OUT }), timeoutMs);
  });
  const answer = Promise.resolve()
    .then(() => ui.showPrompt({ kind, action }))
    .then((choice) => ({
      outcome: choice === "approve" ? APPROVAL_OUTCOMES.APPROVED : APPROVAL_OUTCOMES.DENIED,
    }))
    .catch(() => ({ outcome: APPROVAL_OUTCOMES.DENIED }));
  try {
    const result = await Promise.race([answer, timeout]);
    return { kind, action, outcome: result.outcome, executes: result.outcome === APPROVAL_OUTCOMES.APPROVED };
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Bridge client (T017 host side). Talks to the loopback `voice-bot bridge` listener that the
// Python side owns. Every request carries the per-session bearer token and the bound workspace,
// because the bridge validates both (R18, R23). The client never executes anything itself.
// ---------------------------------------------------------------------------

const BRIDGE_ENDPOINT_RELPATH = path.join(".hive", "voice-bot", "bridge.json");
const BRIDGE_TOKEN_RELPATH = path.join(".hive", "voice-bot", "bridge-token");
const TERMINAL_TASK_STATES = Object.freeze(["completed", "failed", "cancelled"]);

// Reads the bridge endpoint and token the Python side wrote. Missing or malformed files mean
// no live bridge, so the result is null rather than a guessed connection.
function readBridgeConnection(workspaceRoot, readFile) {
  let endpoint;
  let token;
  try {
    endpoint = JSON.parse(readFile(path.join(workspaceRoot, BRIDGE_ENDPOINT_RELPATH)));
    token = String(readFile(path.join(workspaceRoot, BRIDGE_TOKEN_RELPATH))).trim();
  } catch (_err) {
    return null;
  }
  if (!endpoint || typeof endpoint.host !== "string" || !Number.isInteger(endpoint.port) || !token) {
    return null;
  }
  return { host: endpoint.host, port: endpoint.port, token };
}

// The first stdout line of `voice-bot bridge` is the ready record. It never contains the token.
function parseReadyLine(line) {
  let data;
  try {
    data = JSON.parse(String(line));
  } catch (_err) {
    throw new Error("bridge did not report ready (unparsable first line)");
  }
  if (!data || data.ok !== true || typeof data.host !== "string" || !Number.isInteger(data.port)) {
    throw new Error("bridge did not report ready");
  }
  return { host: data.host, port: data.port };
}

// One client per workspace. `fetchImpl` is injected so tests can observe the exact requests.
function createBridgeClient({ host, port, token, workspace, fetchImpl = globalThis.fetch }) {
  async function request(method, route, { query = null, body = null } = {}) {
    let url = `http://${host}:${port}${route}`;
    if (query) {
      url += "?" + new URLSearchParams({ workspace, ...query }).toString();
    }
    const init = { method, headers: { Authorization: `Bearer ${token}` } };
    if (body) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify({ workspace, ...body });
    }
    const res = await fetchImpl(url, init);
    let payload = {};
    try {
      payload = await res.json();
    } catch (_err) {
      payload = {};
    }
    return { status: res.status, body: payload };
  }

  return {
    approval: () => request("GET", "/v1/approval", { query: {} }),
    submission: (clientRequestId) =>
      request("GET", "/v1/submission", { query: { client_request_id: clientRequestId } }),
    task: (taskId, contextSnapshotId) =>
      request("GET", "/v1/task", {
        query: { task_id: taskId, context_snapshot_id: contextSnapshotId },
      }),
    submit: ({
      instruction,
      clientRequestId,
      mode = "ask",
      filePath = "",
      selectionText = "",
      fileContent = "",
      editorSnapshot = null,
    }) =>
      request("POST", "/v1/submit", {
        body: {
          instruction,
          client_request_id: clientRequestId,
          mode,
          file_path: filePath,
          selection_text: selectionText,
          file_content: fileContent,
          ...(editorSnapshot && typeof editorSnapshot === "object" ? { editor_snapshot: editorSnapshot } : {}),
        },
      }),
    editor: () => request("GET", "/v1/editor", { query: {} }),
    ackEditor: (actionId) =>
      request("POST", "/v1/editor", { body: { action_id: actionId } }),
    reply: ({ requestId, taskId, text }) =>
      request("POST", "/v1/reply", { body: { request_id: requestId, task_id: taskId, text } }),
  };
}

// R6: only an explicit approve or deny becomes a reply. A timeout sends nothing, because the
// Python side records its own timed_out when its approval clock runs out.
function decisionForOutcome(outcome) {
  if (outcome === APPROVAL_OUTCOMES.APPROVED) return "approve";
  if (outcome === APPROVAL_OUTCOMES.DENIED) return "deny";
  return null;
}

// The reply text must contain the visible action label and an explicit yes or no, which is the
// exact-match rule the Python broker checks (R6).
function approvalReplyText(decision, action) {
  if (decision !== "approve" && decision !== "deny") {
    throw new Error("decision must be approve or deny");
  }
  return `${decision} ${action}`;
}

// Answers one pending approval from the bridge (R6). `pending` is the GET /v1/approval body.
// `ui.showPrompt({kind, action})` resolves to "approve", "deny", or nothing (approval kinds).
// `ui.askQuestion(action)` resolves to the spoken or typed answer (question kind).
// Returns the bridge reply, or null when nothing was sent (timeout or empty answer).
async function answerPendingApproval(client, pending, ui) {
  let text = null;
  if (pending.kind === "question") {
    const answer = await ui.askQuestion(pending.action);
    if (typeof answer === "string" && answer.trim()) text = answer.trim();
  } else {
    const result = await requestApprovalStub(
      { kind: pending.kind, action: pending.action },
      { showPrompt: ui.showPrompt },
    );
    const decision = decisionForOutcome(result.outcome);
    if (decision) text = approvalReplyText(decision, pending.action);
  }
  if (text === null) return null;
  return client.reply({ requestId: pending.request_id, taskId: pending.task_id, text });
}

module.exports = {
  APPROVAL_OUTCOMES,
  DEFAULT_APPROVAL_TIMEOUT_MS,
  answerPendingApproval,
  DEFAULT_SNAPSHOT_MAX_BYTES,
  VOICE_BOT_CONFIG_RELPATH,
  BRIDGE_ENDPOINT_RELPATH,
  BRIDGE_TOKEN_RELPATH,
  TERMINAL_TASK_STATES,
  isInsideWorkspace,
  loadSnapshotMaxBytes,
  truncateUtf8,
  buildSelection,
  buildDiagnostics,
  buildContextSnapshot,
  requestApprovalStub,
  readBridgeConnection,
  parseReadyLine,
  createBridgeClient,
  decisionForOutcome,
  approvalReplyText,
};
