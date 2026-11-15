// VS Code / Cursor activation host for the HIVE Voice_Bot editor adapter (T007a, T007, T008).
// Thin wiring only; logic lives in core.js and is tested there.
//
// The bridge process is the Python `voice-bot bridge` command. This host starts it, reads its
// ready line, polls its approval endpoint, and shows each pending approval as a modal. The
// modal's answer is sent back as an exact approve/deny reply. Nothing runs in this host.

const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const crypto = require("node:crypto");
const vscode = require("vscode");
const {
  TASK_POLL_MAX_MS,
  answerPendingApproval,
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
  pickSessionRoot,
  sameFsPath,
  matchOpenFsPath,
  resolveHivePlannerSrc,
  buildContextSnapshot,
  createBridgeClient,
  loadSnapshotMaxBytes,
  parseReadyLine,
  createReadyLineReader,
  readBridgeConnection,
  requestApprovalStub,
  resolveWorkspaceRelative,
  liveFeedRelative,
  taskPollDecision,
  createTimerRegistry,
  createSingleFlight,
} = require("./core");

const APPROVAL_POLL_MS = 1500;
const TASK_POLL_MS = 1000;
const READY_TIMEOUT_MS = 30000;
// Newest bridge stderr kept for a failed-start message. The child runs for the whole session.
const STDERR_TAIL_MAX = 4000;

let bridgeProc = null;
// T037 / R28: the workspace folder this session bound at bridge start. Null until a bridge runs.
let sessionRoot = null;
let approvalTimer = null;
let editorTimer = null;
let approvalBusy = false;
let editorBusy = false;
let shownRequestId = null;
let approvalLocallySettled = false;
let shownEditorActionId = null;
// Failed open attempts for the editor action currently at the head of the queue (R18 bounded retry).
let editorFailures = 0;
// The action those failures belong to. The budget resets when the pending action changes.
let editorFailureId = null;
// Live `followTask` timers. Tracked so stopping the bridge ends them: a network error keeps polling
// until the 15-minute deadline, which would otherwise hit a dead bridge long after the call ended.
const taskFollowers = createTimerRegistry();

function captureSnapshot(preferredRelative) {
  const workspaceRoot = sessionWorkspaceRoot();
  const editor = vscode.window.activeTextEditor;
  const activeRelative =
    workspaceRoot && editor && editor.document.uri.scheme === "file"
      ? path.relative(workspaceRoot, editor.document.uri.fsPath).split(path.sep).join("/")
      : "";
  const targetRelative = pickLiveDocumentRelative({
    pendingFile: preferredRelative,
    activeRelative,
  });

  // R22: an unresolvable bound file reads no document. The active editor is a different file.
  let document = null;
  if (!boundFileUnresolved({ root: workspaceRoot, pendingFile: preferredRelative })) {
    document = editor ? editor.document : null;
  }
  if (workspaceRoot && targetRelative) {
    const abs = resolveWorkspaceRelative(workspaceRoot, targetRelative);
    if (abs) {
      const openPaths = vscode.workspace.textDocuments
        .filter((d) => d.uri.scheme === "file")
        .map((d) => d.uri.fsPath);
      const matched = matchOpenFsPath(abs, openPaths);
      const open = matched
        ? vscode.workspace.textDocuments.find(
            (d) => d.uri.scheme === "file" && sameFsPath(d.uri.fsPath, matched),
          )
        : null;
      if (open) {
        document = open;
      } else {
        document = {
          uri: { fsPath: abs, scheme: "file" },
          version: 0,
          isDirty: false,
          getText: () => readDiskText(abs, (p) => fs.readFileSync(p, "utf8")),
        };
      }
    }
  }

  let selection = null;
  let diagnostics = [];
  if (document && editor && editor.document === document && !editor.selection.isEmpty) {
    const sel = editor.selection;
    selection = {
      text: editor.document.getText(sel),
      startLine: sel.start.line,
      startCharacter: sel.start.character,
      endLine: sel.end.line,
      endCharacter: sel.end.character,
    };
  }
  if (document && document.uri && typeof document.uri.with === "function") {
    diagnostics = vscode.languages.getDiagnostics(document.uri).map((d) => ({
      severity: d.severity,
      message: d.message,
      source: d.source,
      code: typeof d.code === "object" && d.code !== null ? d.code.value : d.code,
      line: d.range.start.line,
      character: d.range.start.character,
    }));
  }

  const maxBytes = workspaceRoot
    ? loadSnapshotMaxBytes(workspaceRoot, (p) => fs.readFileSync(p, "utf8"))
    : undefined;

  const scheme = document && document.uri ? document.uri.scheme : null;
  return buildContextSnapshot({
    workspaceRoot,
    activeDocument: document
      ? {
          fileName: document.uri.fsPath,
          scheme,
          version: document.version,
          isDirty: document.isDirty,
          text: scheme === "file" && typeof document.getText === "function" ? document.getText() : "",
        }
      : null,
    selection,
    diagnostics,
    maxBytes,
  });
}

// R28: the bound root once a bridge has started; before that, the folder holding the active file.
function sessionWorkspaceRoot() {
  if (sessionRoot) return sessionRoot;
  const folders = (vscode.workspace.workspaceFolders || []).map((f) => f.uri.fsPath);
  const editor = vscode.window.activeTextEditor;
  const activeFs = editor && editor.document.uri.scheme === "file" ? editor.document.uri.fsPath : null;
  return pickSessionRoot(folders, activeFs);
}

// Connection from the files the bridge wrote. Null when no live bridge has written them.
function connectionClient() {
  const root = sessionWorkspaceRoot();
  if (!root) return null;
  const conn = readBridgeConnection(root, (p) => fs.readFileSync(p, "utf8"));
  if (!conn) return null;
  return createBridgeClient({ ...conn, workspace: root });
}

function pythonInvocation(root) {
  const settings = vscode.workspace.getConfiguration("hive.voiceBot");
  const command = String(settings.get("pythonCommand") || "py -3.11").trim().split(/\s+/);
  const srcDir = resolveHivePlannerSrc(root, settings.get("hivePlannerSrc"), (p) => fs.existsSync(p));
  return { command, srcDir };
}

// Start `voice-bot bridge` for the workspace. Resolves after the ready line; the bridge stops
// when its stdin closes, which stopBridge does.
function startBridge() {
  if (bridgeProc) {
    return Promise.resolve("already running");
  }
  const root = sessionWorkspaceRoot();
  if (!root) {
    return Promise.reject(new Error("open a workspace folder first"));
  }
  sessionRoot = root;
  const { command, srcDir } = pythonInvocation(root);
  const env = { ...process.env };
  if (srcDir) {
    env.PYTHONPATH = srcDir + path.delimiter + (env.PYTHONPATH || "");
  }
  const args = [...command.slice(1), "-m", "hive_planner", "--root", root, "voice-bot", "bridge"];
  const proc = spawn(command[0], args, { cwd: root, env, stdio: ["pipe", "pipe", "pipe"] });
  bridgeProc = proc;
  const clearIfCurrent = () => {
    if (bridgeProc === proc) {
      bridgeProc = null;
      sessionRoot = null;
      stopApprovalWatch();
      stopEditorWatch();
      taskFollowers.stopAll();
    }
  };
  proc.on("exit", clearIfCurrent);

  return new Promise((resolve, reject) => {
    let stderr = "";
    const timer = setTimeout(() => {
      proc.kill();
      clearIfCurrent();
      reject(new Error("bridge did not report ready in time"));
    }, READY_TIMEOUT_MS);
    // A missing interpreter (ENOENT) emits 'error' and no 'exit'. Without this listener the
    // error is uncaught and bridgeProc stays set, so later starts would report "already running".
    proc.on("error", (err) => {
      clearTimeout(timer);
      clearIfCurrent();
      reject(new Error(`could not start the bridge process: ${err.message}`));
    });
    proc.stderr.on("data", (chunk) => {
      stderr = appendBoundedTail(stderr, chunk.toString(), STDERR_TAIL_MAX);
    });
    proc.on("exit", (code) => {
      clearTimeout(timer);
      reject(bridgeExitError(code, stderr));
    });
    // Only the first stdout line is the ready record. Later stdout must not re-run this handler,
    // which would re-arm the pollers and clear the shown-approval state.
    const readReadyLine = createReadyLineReader();
    proc.stdout.on("data", (chunk) => {
      const line = readReadyLine(chunk);
      if (line === null) return;
      clearTimeout(timer);
      try {
        parseReadyLine(line);
        startApprovalWatch();
        startEditorWatch();
        resolve("started");
      } catch (err) {
        proc.kill();
        reject(err);
      }
    });
  });
}

function stopBridge() {
  const proc = bridgeProc;
  bridgeProc = null;
  // Drop the bound root with the process. Otherwise a later editor call would read the old folder's
  // bridge files (the exit handler only clears state while it still owns bridgeProc).
  sessionRoot = null;
  stopApprovalWatch();
  stopEditorWatch();
  taskFollowers.stopAll();
  if (proc) {
    proc.stdin.end();
  }
  return Boolean(proc);
}

function startApprovalWatch() {
  stopApprovalWatch();
  approvalTimer = setInterval(pollApprovals, APPROVAL_POLL_MS);
}

function stopApprovalWatch() {
  if (approvalTimer) {
    clearInterval(approvalTimer);
    approvalTimer = null;
  }
  shownRequestId = null;
  approvalLocallySettled = false;
}

function startEditorWatch() {
  stopEditorWatch();
  editorTimer = setInterval(pollEditorActions, APPROVAL_POLL_MS);
}

function stopEditorWatch() {
  if (editorTimer) {
    clearInterval(editorTimer);
    editorTimer = null;
  }
  shownEditorActionId = null;
  editorFailures = 0;
  editorFailureId = null;
}

async function applyEditorAction(action) {
  if (action.kind === "navigate" && action.file_path) {
    const root = sessionWorkspaceRoot();
    const abs = root ? resolveWorkspaceRelative(root, action.file_path) : null;
    if (!abs) return false;
    const uri = vscode.Uri.file(abs);
    await vscode.window.showTextDocument(uri, { preview: false });
    return true;
  }
  if (action.kind === "show_diff") {
    const doc = await vscode.workspace.openTextDocument({
      content: action.text || "(no diff evidence)",
      language: "diff",
    });
    await vscode.window.showTextDocument(doc, { preview: true });
    return true;
  }
  return false;
}

// A thrown open (for example a deleted file) counts as a failed attempt, not a poll crash.
async function tryApplyEditorAction(action) {
  try {
    return await applyEditorAction(action);
  } catch (err) {
    return false;
  }
}

async function pollEditorActions() {
  if (editorBusy) return;
  editorBusy = true;
  try {
    const client = connectionClient();
    // A missing or partial bridge.json/token is usually the Python side mid-rewrite (write_text
    // truncates first). Skip this tick only; stopping here would end editor polling for the session.
    // stopBridge and the process exit handler still stop the timer.
    if (!client) return;
    const { status, body } = await client.editor();
    if (status !== 200) return;
    const opened =
      body.pending && body.action_id !== shownEditorActionId
        ? await tryApplyEditorAction(body)
        : body.pending && body.action_id === shownEditorActionId;
    const budget = editorRetryBudget({
      failures: editorFailures,
      failureActionId: editorFailureId,
      pending: body,
    });
    const next = editorActionAdvance({
      shownActionId: shownEditorActionId,
      pending: body,
      opened: Boolean(opened),
      failures: budget.failures,
    });
    shownEditorActionId = next.shownActionId;
    if (next.action === "retry") {
      editorFailures = budget.failures + 1;
      editorFailureId = budget.failureActionId;
    } else if (next.action === "give_up") {
      editorFailures = 0;
      editorFailureId = null;
      vscode.window.showWarningMessage(
        `HIVE Voice_Bot: could not open the requested editor view after ${EDITOR_ACTION_MAX_ATTEMPTS} tries; giving up on it.`,
      );
    } else if (next.action === "opened") {
      editorFailures = 0;
      editorFailureId = null;
    }
    if (next.ack) {
      await client.ackEditor(body.action_id);
    }
  } catch (_err) {
    // Bridge gone: the next start re-reads the files.
  } finally {
    editorBusy = false;
  }
}

// Visible approval UI (R6). Only an explicit "approve" approves; anything else denies or times out.
const approvalUi = {
  showPrompt: ({ kind, action }) =>
    vscode.window.showWarningMessage(
      `HIVE Voice_Bot (${kind}): approve "${action}"?`,
      { modal: true },
      "approve",
      "deny"
    ),
  // Question kind: the answer is free text, not an approval. Empty answers send nothing.
  askQuestion: (action) => vscode.window.showInputBox({ prompt: `HIVE Voice_Bot question: ${action}` }),
};

// T029 producer feed: send the active editor's workspace-relative file, version, and dirty flag
// so the bridge's R22 live lookup is fresh. Non-file editors and paths outside the workspace send nothing.
async function feedLiveBuffer(client) {
  const root = sessionWorkspaceRoot();
  const editor = vscode.window.activeTextEditor;
  if (!root || !editor || editor.document.uri.scheme !== "file") return;
  const rel = liveFeedRelative(root, editor.document.uri.fsPath);
  if (!rel) return;
  await client.liveBuffer({
    filePath: rel,
    documentVersion: editor.document.version,
    dirty: editor.document.isDirty,
  });
}

async function pollApprovals() {
  if (approvalBusy) return;
  approvalBusy = true;
  try {
    const client = connectionClient();
    // Same as pollEditorActions: a transient unreadable connection skips this tick, it does not
    // end approval polling for the session. stopBridge and the process exit handler stop the timer.
    if (!client) return;
    await feedLiveBuffer(client).catch(() => {});
    const { status, body } = await client.approval();
    if (status !== 200) return;
    const watch = approvalWatchDecision(shownRequestId, body, approvalLocallySettled);
    if (watch.action === "expired") {
      shownRequestId = null;
      approvalLocallySettled = false;
      vscode.window.showWarningMessage(approvalExpiredNotice());
      return;
    }
    if (watch.action === "cleared") {
      shownRequestId = null;
      approvalLocallySettled = false;
      return;
    }
    if (watch.action !== "show") return;
    shownRequestId = body.request_id;
    try {
      const reply = await answerPendingApproval(client, body, approvalUi, () =>
        captureSnapshot(body.file_path),
      );
      if (approvalReplySettlesHost(reply)) {
        approvalLocallySettled = true;
      } else {
        shownRequestId = null;
        approvalLocallySettled = false;
      }
      if (reply && reply.status !== 200) {
        vscode.window.showErrorMessage(`HIVE approval not applied: ${reply.body.status || reply.body.error}`);
      } else {
        const notice = approvalReplySpokenNotice(reply);
        if (notice) {
          vscode.window.showWarningMessage(`HIVE Voice_Bot: ${notice}`);
        }
      }
    } catch (_err) {
      shownRequestId = null;
      approvalLocallySettled = false;
    }
  } catch (_err) {
    // Bridge gone or unreachable: the next start re-reads the files. Nothing executes here.
  } finally {
    approvalBusy = false;
  }
}

// Submit one instruction. The client request id is generated here once, so a retry of this
// same submit cannot start a second task (R18, SC-012).
async function submitTask() {
  const client = connectionClient();
  if (!client) {
    vscode.window.showErrorMessage("HIVE Voice_Bot: the bridge is not running. Run Start Bridge first.");
    return;
  }
  const instruction = await vscode.window.showInputBox({ prompt: "HIVE Voice_Bot: instruction" });
  if (!instruction || !instruction.trim()) return;
  const snapshot = captureSnapshot();
  let status;
  let body;
  try {
    ({ status, body } = await client.submit({
      instruction: instruction.trim(),
      clientRequestId: crypto.randomUUID(),
      mode: "ask",
      filePath: snapshot.file || "",
      // The editor snapshot already carries the selection and file content. Sending them again
      // top-level doubled the body size and was ignored by the bridge when a snapshot is present.
      editorSnapshot: snapshot,
    }));
  } catch (err) {
    // Bridge dropped mid-call: say so instead of leaving an unhandled rejection with no feedback.
    vscode.window.showErrorMessage(`HIVE Voice_Bot: could not reach the bridge (${err.message}). Nothing was submitted.`);
    return;
  }
  if (status !== 200) {
    const spoken = body.spoken ? ` ${body.spoken}` : "";
    vscode.window.showErrorMessage(
      `HIVE Voice_Bot refused: ${body.error || status} ${body.message || ""}${spoken}`.trim(),
    );
    return;
  }
  if (!body.task_id) {
    vscode.window.showInformationMessage(`HIVE Voice_Bot: queued (${body.state}). It will run after the active task.`);
    return;
  }
  vscode.window.showInformationMessage(`HIVE Voice_Bot: task ${body.task_id} ${body.state}.`);
  followTask(client, body.task_id, body.context_snapshot_id);
}

// C3: submit a workspace-relative WAV through the bridge's spoken route. The extension does not
// record the mic; the operator supplies a WAV already inside the workspace. The bridge decides
// whether STT is configured (400 stt_not_configured while stt_provider is null).
async function submitSpoken() {
  const client = connectionClient();
  if (!client) {
    vscode.window.showErrorMessage("HIVE Voice_Bot: the bridge is not running. Run Start Bridge first.");
    return;
  }
  const wavPath = await vscode.window.showInputBox({
    prompt: "HIVE Voice_Bot: workspace-relative WAV path",
    placeHolder: "audio/clip.wav",
  });
  if (!wavPath || !wavPath.trim()) return;
  const snapshot = captureSnapshot();
  let status;
  let body;
  try {
    ({ status, body } = await client.submitSpoken({
      wavPath: wavPath.trim(),
      clientRequestId: crypto.randomUUID(),
      mode: "ask",
      filePath: snapshot.file || "",
      editorSnapshot: snapshot,
    }));
  } catch (err) {
    vscode.window.showErrorMessage(`HIVE Voice_Bot: could not reach the bridge (${err.message}). Nothing was submitted.`);
    return;
  }
  if (status !== 200) {
    const spoken = body.spoken ? ` ${body.spoken}` : "";
    vscode.window.showErrorMessage(
      `HIVE Voice_Bot refused: ${body.error || status} ${body.message || ""}${spoken}`.trim(),
    );
    return;
  }
  if (!body.task_id) {
    vscode.window.showInformationMessage(`HIVE Voice_Bot: queued (${body.state}). It will run after the active task.`);
    return;
  }
  vscode.window.showInformationMessage(`HIVE Voice_Bot: task ${body.task_id} ${body.state}.`);
  followTask(client, body.task_id, body.context_snapshot_id);
}

// Poll one task to a terminal state and report the grounded result (R8, R14).
function followTask(client, taskId, contextSnapshotId) {
  const started = Date.now();
  // Single-flight: a lookup slower than TASK_POLL_MS must not overlap the next tick, or the
  // terminal message could be shown twice.
  const poll = createSingleFlight(async () => {
    try {
      const { status, body } = await client.task(taskId, contextSnapshotId);
      const decision = taskPollDecision({
        status,
        state: body && body.state,
        elapsedMs: Date.now() - started,
        maxMs: TASK_POLL_MAX_MS,
      });
      if (!decision.stop) return;
      taskFollowers.release(timer);
      if (decision.reason === "terminal") {
        const tests = body.tests_status ? ` Tests: ${body.tests_status}.` : "";
        vscode.window.showInformationMessage(`HIVE Voice_Bot: task ${body.state}.${tests} ${body.spoken || ""}`.trim());
        return;
      }
      if (decision.reason === "poll_timeout") {
        vscode.window.showErrorMessage(`HIVE Voice_Bot: task ${taskId} is still running; stopped waiting.`);
        return;
      }
      vscode.window.showErrorMessage(`HIVE Voice_Bot: task lookup failed (${status}).`);
    } catch (_err) {
      const decision = taskPollDecision({
        status: 0,
        state: "",
        elapsedMs: Date.now() - started,
        maxMs: TASK_POLL_MAX_MS,
        networkError: true,
      });
      if (!decision.stop) return;
      taskFollowers.release(timer);
      if (decision.reason === "poll_timeout") {
        vscode.window.showErrorMessage(`HIVE Voice_Bot: task ${taskId} is still running; stopped waiting.`);
      }
    }
  });
  const timer = setInterval(poll, TASK_POLL_MS);
  taskFollowers.add(timer);
}

// T031 host commands: stop playback or end the call through the bridge. Each sends one request
// and reports the bridge result; neither cancels a coding task.
async function sendCallControl(method) {
  const client = connectionClient();
  if (!client) {
    vscode.window.showErrorMessage("HIVE Voice_Bot: the bridge is not running. Run Start Bridge first.");
    return;
  }
  let status;
  let body;
  try {
    ({ status, body } = await client[method]());
  } catch (err) {
    vscode.window.showErrorMessage(`HIVE Voice_Bot: could not reach the bridge (${err.message}).`);
    return;
  }
  if (status !== 200) {
    vscode.window.showErrorMessage(`HIVE Voice_Bot: ${body.error || status} ${body.message || ""}`.trim());
    return;
  }
  const session = body.session_state || "ended";
  vscode.window.showInformationMessage(`HIVE Voice_Bot: session ${session}.`);
}

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand("hive.voiceBot.interruptPlayback", () => sendCallControl("interruptPlayback")),
    vscode.commands.registerCommand("hive.voiceBot.endCall", () => sendCallControl("endCall")),
    vscode.commands.registerCommand("hive.voiceBot.getContextSnapshot", () => captureSnapshot()),

    vscode.commands.registerCommand("hive.voiceBot.approvalStub", async () => {
      // Stub UI kept for manual checks: shows the prompt and reports the outcome. Never executes.
      const result = await requestApprovalStub(
        { kind: "write_or_command", action: "stub action (no execution)" },
        { showPrompt: approvalUi.showPrompt },
      );
      vscode.window.showInformationMessage(`HIVE approval outcome: ${result.outcome}`);
      return result;
    }),

    vscode.commands.registerCommand("hive.voiceBot.startBridge", async () => {
      try {
        const result = await startBridge();
        vscode.window.showInformationMessage(`HIVE Voice_Bot bridge: ${result}.`);
      } catch (err) {
        vscode.window.showErrorMessage(`HIVE Voice_Bot bridge did not start: ${err.message}`);
      }
    }),

    vscode.commands.registerCommand("hive.voiceBot.stopBridge", () => {
      const stopped = stopBridge();
      vscode.window.showInformationMessage(stopped ? "HIVE Voice_Bot bridge stopped." : "HIVE Voice_Bot bridge was not running.");
    }),

    vscode.commands.registerCommand("hive.voiceBot.submitTask", () => submitTask()),
    vscode.commands.registerCommand("hive.voiceBot.submitSpoken", () => submitSpoken()),

    vscode.commands.registerCommand("hive.voiceBot.navigateTo", async () => {
      const snapshot = captureSnapshot();
      if (!snapshot.file) {
        vscode.window.showErrorMessage("HIVE Voice_Bot: no active file to navigate.");
        return;
      }
      const abs = resolveWorkspaceRelative(snapshot.workspace, snapshot.file);
      if (!abs) {
        vscode.window.showErrorMessage("HIVE Voice_Bot: file is outside the workspace.");
        return;
      }
      const uri = vscode.Uri.file(abs);
      await vscode.window.showTextDocument(uri, { preview: false });
    }),

    { dispose: () => stopBridge() }
  );
}

function deactivate() {
  stopBridge();
}

module.exports = { activate, deactivate };
