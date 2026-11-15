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
  // Only a leading ".." path segment escapes the root; a name like "..notes" stays inside.
  const escapes = rel === ".." || rel.startsWith(".." + path.sep);
  return rel !== "" && !escapes && !path.isAbsolute(rel);
}

// T037 / R28: the folder a session binds. The most specific workspace folder that contains the
// active file wins (nested folders: longest match). With no active file, or a file outside every
// folder, fall back to the first folder. No folders gives null.
function pickSessionRoot(folderPaths, activeFsPath) {
  const folders = (folderPaths || []).filter((f) => f);
  if (folders.length === 0) return null;
  let best = null;
  if (activeFsPath) {
    for (const folder of folders) {
      const rel = path.relative(path.resolve(folder), path.resolve(String(activeFsPath)));
      if (!isInsideWorkspace(folder, rel)) continue;
      if (best === null || path.resolve(folder).length > path.resolve(best).length) best = folder;
    }
  }
  return best || folders[0];
}

// Same on-disk file. Windows drive and path letters are not significant (R22 live buffer).
function sameFsPath(left, right) {
  if (!left || !right) return false;
  const a = path.normalize(String(left));
  const b = path.normalize(String(right));
  return process.platform === "win32" ? a.toLowerCase() === b.toLowerCase() : a === b;
}

// First open editor path that is the same file as `targetAbs`, or null.
function matchOpenFsPath(targetAbs, openAbsPaths) {
  const target = String(targetAbs || "");
  for (const candidate of openAbsPaths || []) {
    if (sameFsPath(target, candidate)) return candidate;
  }
  return null;
}

// PYTHONPATH folder for `-m hive_planner`. An explicit setting wins. Otherwise `<workspace>/src`
// when that tree contains hive_planner, so Start Bridge works without a Cursor setting (T017, R30).
function resolveHivePlannerSrc(workspaceRoot, setting, exists) {
  const explicit = String(setting || "").trim();
  if (explicit) return explicit;
  if (!workspaceRoot) return "";
  const srcDir = path.join(workspaceRoot, "src");
  try {
    if (exists(path.join(srcDir, "hive_planner"))) return srcDir;
  } catch (_err) {
    return "";
  }
  return "";
}

// T029 live feed: the workspace-relative, forward-slash path of an editor file, or null when it
// is not inside the root. Uses the same fence as isInsideWorkspace, so a real file named
// "..notes.md" is still fed (a bare startsWith("..") check silently dropped it).
function liveFeedRelative(rootPath, fsPath) {
  if (!rootPath || !fsPath) return null;
  const rel = path.relative(path.resolve(rootPath), path.resolve(String(fsPath)));
  if (!isInsideWorkspace(rootPath, rel)) return null;
  return rel.split(path.sep).join("/");
}

// Absolute path for a workspace-relative file, or null when the path would leave the root (R23).
function resolveWorkspaceRelative(rootPath, filePath) {
  if (!rootPath || !filePath || !isInsideWorkspace(rootPath, filePath)) return null;
  return path.resolve(rootPath, filePath);
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
  // R28: no active editor, or a non-file document (untitled, diff, output), yields file null
  // with reason no_active_file. Its fsPath is not a workspace path.
  if (!activeDocument || (activeDocument.scheme && activeDocument.scheme !== "file")) {
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

// R22: a write-approval snapshot must name the bound task file, not whichever editor is
// active. When the approval names a file, that path wins even if another document is focused.
// R22: a bound file that is not open in an editor reads its text from disk, not an empty stub.
// A read failure yields "" so the snapshot carries no content instead of throwing.
function readDiskText(absPath, readFile) {
  try {
    return String(readFile(absPath));
  } catch (_err) {
    return "";
  }
}

function pickLiveDocumentRelative({ pendingFile = "", activeRelative = "" } = {}) {
  const bound = String(pendingFile || "").replace(/\\/g, "/");
  if (bound) return bound;
  return String(activeRelative || "").replace(/\\/g, "/");
}

// R22: a bound approval file that does not resolve inside the workspace must not fall back to
// the active editor (a different file). True means the snapshot reads no document at all.
function boundFileUnresolved({ root = null, pendingFile = "" } = {}) {
  const bound = String(pendingFile || "").replace(/\\/g, "/");
  if (!bound) return false;
  return resolveWorkspaceRelative(root, bound) === null;
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
const TASK_POLL_MAX_MS = 15 * 60 * 1000;

// Host poll for GET /v1/task. Stops on a terminal state, a failed lookup, or the deadline.
function taskPollDecision({ status, state, elapsedMs, maxMs = TASK_POLL_MAX_MS, networkError = false }) {
  if (networkError) {
    if (elapsedMs >= maxMs) return { stop: true, reason: "poll_timeout" };
    return { stop: false, reason: "wait" };
  }
  if (status !== 200) return { stop: true, reason: "lookup_failed" };
  if (TERMINAL_TASK_STATES.includes(state)) return { stop: true, reason: "terminal" };
  if (elapsedMs >= maxMs) return { stop: true, reason: "poll_timeout" };
  return { stop: false, reason: "wait" };
}

// Runs `fn` at most once at a time. A tick that arrives while the previous call is still awaiting
// is skipped. A plain setInterval fires on schedule even when the last async poll has not returned,
// so a slow lookup could overlap and report the same terminal state twice.
function createSingleFlight(fn) {
  let running = false;
  return async function singleFlight(...args) {
    if (running) return undefined;
    running = true;
    try {
      return await fn(...args);
    } finally {
      running = false;
    }
  };
}

// Timer bookkeeping for host polls (`followTask`). Each live timer is tracked so stopping the bridge
// ends every poll; a network error otherwise keeps polling a dead bridge until the deadline.
// `clear` is injectable so the registry is testable without the vscode host.
function createTimerRegistry(clear = clearInterval) {
  const timers = new Set();
  return {
    add(timer) {
      timers.add(timer);
      return timer;
    },
    release(timer) {
      clear(timer);
      timers.delete(timer);
    },
    stopAll() {
      for (const timer of timers) clear(timer);
      timers.clear();
    },
    size() {
      return timers.size;
    },
  };
}

// Host poll for GET /v1/approval. A previously shown request that is no longer pending
// expired or was answered elsewhere — the modal click must not be treated as success.
// After this host finishes its own attempt, forget the id (`cleared`) so the next poll
// cannot report a successful approve/deny as a timeout (R6).
function approvalWatchDecision(shownRequestId, body, locallySettled = false) {
  if (!body || !body.pending) {
    if (!shownRequestId) return { action: "idle" };
    if (locallySettled) return { action: "cleared" };
    return { action: "expired" };
  }
  if (shownRequestId && body.request_id === shownRequestId) return { action: "already_shown" };
  return { action: "show" };
}

// Warning shown when a shown approval is no longer pending without a local reply. The bridge
// does not say whether it timed out or was answered elsewhere, so the text must not claim either
// one as fact (an approval answered elsewhere may already have run).
function approvalExpiredNotice() {
  return "HIVE Voice_Bot: the approval is no longer pending (it timed out or was answered elsewhere). Check the task before assuming nothing ran.";
}

// True only when the bridge accepted a reply that resolved or clearly closed the pending
// approval. Dismissals, empty answers, and reprompts must return false so the host can
// show the modal again (R6).
function approvalReplySettlesHost(reply) {
  if (!reply || reply.status !== 200) return false;
  const status = reply.body && reply.body.status;
  if (typeof status !== "string" || !status) return false;
  return !["reprompt", "stale", "no_pending_approval", "stale_approval", "task_mismatch"].includes(status);
}

// Spoken line the host should surface for bridge replies (R6, R22). HTTP 200 replies such
// as stale buffer, reprompt, or deny carry `spoken` but are not bridge failures.
function approvalReplySpokenNotice(reply) {
  if (!reply || reply.status !== 200 || !reply.body) return "";
  const status = reply.body.status;
  const spoken = typeof reply.body.spoken === "string" ? reply.body.spoken.trim() : "";
  if (!spoken) return "";
  if (status === "stale" || status === "reprompt" || status === "denied" || status === "not_delivered") {
    return spoken;
  }
  return "";
}

// Attempts before an editor action is given up. A failed open is retried so a transient error
// (file briefly locked, editor busy) is not lost (R18), but a permanent one (deleted file, unknown
// kind) must not retry every poll forever. Giving up acks the action so the bridge clears it.
const EDITOR_ACTION_MAX_ATTEMPTS = 3;

// Host poll for GET /v1/editor. Remember an action only after it opened. `failures` counts the
// failed attempts already made for this action; the attempt that reaches `maxFailures` gives up.
function editorActionAdvance({
  shownActionId,
  pending,
  opened,
  failures = 0,
  maxFailures = EDITOR_ACTION_MAX_ATTEMPTS,
}) {
  if (!pending || !pending.pending) {
    return { action: "idle", shownActionId: null, ack: false };
  }
  if (shownActionId === pending.action_id) {
    return { action: "already_opened", shownActionId, ack: true };
  }
  if (!opened) {
    if (failures + 1 >= maxFailures) {
      return { action: "give_up", shownActionId: pending.action_id, ack: true };
    }
    return { action: "retry", shownActionId, ack: false };
  }
  return { action: "opened", shownActionId: pending.action_id, ack: true };
}

// The retry budget belongs to one editor action. `failures` is only meaningful for the action
// named by `failureActionId`. When the pending action changes, or nothing is pending, the count
// starts from zero, so a failure on an earlier action cannot shorten the next action's attempts.
function editorRetryBudget({ failures = 0, failureActionId = null, pending }) {
  if (!pending || !pending.pending) {
    return { failures: 0, failureActionId: null };
  }
  if (failureActionId !== pending.action_id) {
    return { failures: 0, failureActionId: pending.action_id };
  }
  return { failures, failureActionId };
}

// Keeps only the newest `max` characters of a stream so a long-running child cannot grow an
// unbounded string in the host. Used for the bridge stderr tail shown on a failed start.
function appendBoundedTail(text, chunk, max) {
  const joined = String(text || "") + String(chunk);
  return joined.length > max ? joined.slice(joined.length - max) : joined;
}

// Error for a bridge process that exited before reporting ready. When the Python side refused
// because another live bridge owns the repo, its stderr says so; surface that reason directly
// instead of the generic exit text.
function bridgeExitError(code, stderr) {
  const tail = String(stderr || "").trim();
  if (tail.includes("already running")) {
    const line = tail.split(/\r?\n/).find((l) => l.includes("already running")) || tail;
    return new Error(line.replace(/^Error:\s*/, "").trim());
  }
  return new Error(`bridge exited before ready (code ${code}): ${tail}`);
}

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

// Collects bridge stdout until the first complete line, then returns that line exactly once.
// Every later chunk returns null, so the host cannot run ready handling again (and re-arm its
// approval and editor pollers, which clears shown-request state) on unrelated stdout.
function createReadyLineReader() {
  let buffer = "";
  let done = false;
  return function feed(chunk) {
    if (done) return null;
    buffer += String(chunk);
    const newline = buffer.indexOf("\n");
    if (newline === -1) return null;
    done = true;
    return buffer.slice(0, newline);
  };
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
      // URLSearchParams turns undefined/null into the text "undefined"/"null". Drop those keys so a
      // missing id is absent (the bridge then answers 400) rather than a false context_mismatch.
      const params = { workspace };
      for (const [key, value] of Object.entries(query)) {
        if (value !== undefined && value !== null) params[key] = value;
      }
      url += "?" + new URLSearchParams(params).toString();
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
    // T042 slice 3 / C3: submit a workspace-relative WAV. The bridge transcribes it with the pinned
    // STT adapter and the transcript becomes the instruction. Live mic capture is not done here.
    submitSpoken: ({ wavPath, clientRequestId, mode = "ask", filePath = "", editorSnapshot = null }) =>
      request("POST", "/v1/submit/spoken", {
        body: {
          wav_path: wavPath,
          client_request_id: clientRequestId,
          mode,
          file_path: filePath,
          ...(editorSnapshot && typeof editorSnapshot === "object" ? { editor_snapshot: editorSnapshot } : {}),
        },
      }),
    editor: () => request("GET", "/v1/editor", { query: {} }),
    ackEditor: (actionId) =>
      request("POST", "/v1/editor", { body: { action_id: actionId } }),
    // T031: stop playback (session `interrupted`, task state unchanged) and end the call
    // (session `ended`, active task keeps running, queued follow-ups discarded).
    interruptPlayback: () => request("POST", "/v1/playback/interrupt", { body: {} }),
    endCall: () => request("POST", "/v1/call/end", { body: {} }),
    // T029 producer feed: the active editor's workspace-relative file, version, and dirty flag.
    liveBuffer: ({ filePath, documentVersion, dirty }) =>
      request("POST", "/v1/live", {
        body: { file_path: filePath, document_version: documentVersion, dirty: Boolean(dirty) },
      }),
    reply: ({ requestId, taskId, text, editorSnapshot = null }) =>
      request("POST", "/v1/reply", {
        body: {
          request_id: requestId,
          task_id: taskId,
          text,
          ...(editorSnapshot && typeof editorSnapshot === "object" ? { editor_snapshot: editorSnapshot } : {}),
        },
      }),
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
async function answerPendingApproval(client, pending, ui, editorSnapshot = null) {
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
  const live = typeof editorSnapshot === "function" ? editorSnapshot() : editorSnapshot;
  return client.reply({
    requestId: pending.request_id,
    taskId: pending.task_id,
    text,
    editorSnapshot: live,
  });
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
  TASK_POLL_MAX_MS,
  taskPollDecision,
  createTimerRegistry,
  createSingleFlight,
  approvalWatchDecision,
  approvalExpiredNotice,
  approvalReplySettlesHost,
  approvalReplySpokenNotice,
  editorActionAdvance,
  EDITOR_ACTION_MAX_ATTEMPTS,
  editorRetryBudget,
  appendBoundedTail,
  bridgeExitError,
  pickLiveDocumentRelative,
  boundFileUnresolved,
  readDiskText,
  isInsideWorkspace,
  pickSessionRoot,
  sameFsPath,
  matchOpenFsPath,
  resolveHivePlannerSrc,
  resolveWorkspaceRelative,
  liveFeedRelative,
  loadSnapshotMaxBytes,
  truncateUtf8,
  buildSelection,
  buildDiagnostics,
  buildContextSnapshot,
  requestApprovalStub,
  readBridgeConnection,
  parseReadyLine,
  createReadyLineReader,
  createBridgeClient,
  decisionForOutcome,
  approvalReplyText,
};
