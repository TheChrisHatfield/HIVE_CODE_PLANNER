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
  TERMINAL_TASK_STATES,
  answerPendingApproval,
  buildContextSnapshot,
  createBridgeClient,
  loadSnapshotMaxBytes,
  parseReadyLine,
  readBridgeConnection,
  requestApprovalStub,
} = require("./core");

const APPROVAL_POLL_MS = 1500;
const TASK_POLL_MS = 1000;
const READY_TIMEOUT_MS = 30000;

let bridgeProc = null;
let approvalTimer = null;
let editorTimer = null;
let approvalBusy = false;
let editorBusy = false;
let shownRequestId = null;
let shownEditorActionId = null;

function captureSnapshot() {
  const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  const workspaceRoot = folder ? folder.uri.fsPath : null;
  const editor = vscode.window.activeTextEditor;

  let selection = null;
  let diagnostics = [];
  if (editor) {
    const sel = editor.selection;
    if (!sel.isEmpty) {
      selection = {
        text: editor.document.getText(sel),
        startLine: sel.start.line,
        startCharacter: sel.start.character,
        endLine: sel.end.line,
        endCharacter: sel.end.character,
      };
    }
    diagnostics = vscode.languages.getDiagnostics(editor.document.uri).map((d) => ({
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

  return buildContextSnapshot({
    workspaceRoot,
    activeDocument: editor
      ? {
          fileName: editor.document.uri.fsPath,
          version: editor.document.version,
          isDirty: editor.document.isDirty,
          text: editor.document.getText(),
        }
      : null,
    selection,
    diagnostics,
    maxBytes,
  });
}

function workspaceRoot() {
  const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  return folder ? folder.uri.fsPath : null;
}

// Connection from the files the bridge wrote. Null when no live bridge has written them.
function connectionClient() {
  const root = workspaceRoot();
  if (!root) return null;
  const conn = readBridgeConnection(root, (p) => fs.readFileSync(p, "utf8"));
  if (!conn) return null;
  return createBridgeClient({ ...conn, workspace: root });
}

function pythonInvocation() {
  const settings = vscode.workspace.getConfiguration("hive.voiceBot");
  const command = String(settings.get("pythonCommand") || "py -3.11").trim().split(/\s+/);
  const srcDir = String(settings.get("hivePlannerSrc") || "").trim();
  return { command, srcDir };
}

// Start `voice-bot bridge` for the workspace. Resolves after the ready line; the bridge stops
// when its stdin closes, which stopBridge does.
function startBridge() {
  if (bridgeProc) {
    return Promise.resolve("already running");
  }
  const root = workspaceRoot();
  if (!root) {
    return Promise.reject(new Error("open a workspace folder first"));
  }
  const { command, srcDir } = pythonInvocation();
  const env = { ...process.env };
  if (srcDir) {
    env.PYTHONPATH = srcDir + path.delimiter + (env.PYTHONPATH || "");
  }
  const args = [...command.slice(1), "-m", "hive_planner", "--root", root, "voice-bot", "bridge"];
  const proc = spawn(command[0], args, { cwd: root, env, stdio: ["pipe", "pipe", "pipe"] });
  bridgeProc = proc;
  proc.on("exit", () => {
    if (bridgeProc === proc) {
      bridgeProc = null;
      stopApprovalWatch();
      stopEditorWatch();
    }
  });

  return new Promise((resolve, reject) => {
    let buffer = "";
    let stderr = "";
    const timer = setTimeout(() => {
      proc.kill();
      reject(new Error("bridge did not report ready in time"));
    }, READY_TIMEOUT_MS);
    proc.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    proc.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`bridge exited before ready (code ${code}): ${stderr.trim()}`));
    });
    proc.stdout.on("data", (chunk) => {
      buffer += chunk.toString();
      const newline = buffer.indexOf("\n");
      if (newline === -1) return;
      clearTimeout(timer);
      try {
        parseReadyLine(buffer.slice(0, newline));
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
  stopApprovalWatch();
  stopEditorWatch();
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
}

async function applyEditorAction(action) {
  if (action.kind === "navigate" && action.file_path) {
    const root = workspaceRoot();
    if (!root) return false;
    const uri = vscode.Uri.file(path.join(root, action.file_path));
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

async function pollEditorActions() {
  if (editorBusy) return;
  editorBusy = true;
  try {
    const client = connectionClient();
    if (!client) {
      stopEditorWatch();
      return;
    }
    const { status, body } = await client.editor();
    if (status !== 200 || !body.pending || body.action_id === shownEditorActionId) return;
    shownEditorActionId = body.action_id;
    const opened = await applyEditorAction(body);
    if (opened) {
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

async function pollApprovals() {
  if (approvalBusy) return;
  approvalBusy = true;
  try {
    const client = connectionClient();
    if (!client) {
      stopApprovalWatch();
      return;
    }
    const { status, body } = await client.approval();
    if (status !== 200 || !body.pending || body.request_id === shownRequestId) return;
    shownRequestId = body.request_id;

    const reply = await answerPendingApproval(client, body, approvalUi);
    if (reply && reply.status !== 200) {
      vscode.window.showErrorMessage(`HIVE approval not applied: ${reply.body.status || reply.body.error}`);
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
  const { status, body } = await client.submit({
    instruction: instruction.trim(),
    clientRequestId: crypto.randomUUID(),
    mode: "ask",
    filePath: snapshot.file || "",
    selectionText: snapshot.selection ? snapshot.selection.text : "",
    fileContent: snapshot.file_content || "",
    editorSnapshot: snapshot,
  });
  if (status !== 200) {
    vscode.window.showErrorMessage(`HIVE Voice_Bot refused: ${body.error || status} ${body.message || ""}`.trim());
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
  const timer = setInterval(async () => {
    const { status, body } = await client.task(taskId, contextSnapshotId);
    if (status !== 200 || !TERMINAL_TASK_STATES.includes(body.state)) return;
    clearInterval(timer);
    const tests = body.tests_status ? ` Tests: ${body.tests_status}.` : "";
    vscode.window.showInformationMessage(`HIVE Voice_Bot: task ${body.state}.${tests} ${body.spoken || ""}`.trim());
  }, TASK_POLL_MS);
}

function activate(context) {
  context.subscriptions.push(
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

    vscode.commands.registerCommand("hive.voiceBot.navigateTo", async () => {
      const snapshot = captureSnapshot();
      if (!snapshot.file) {
        vscode.window.showErrorMessage("HIVE Voice_Bot: no active file to navigate.");
        return;
      }
      const uri = vscode.Uri.file(path.join(snapshot.workspace, snapshot.file));
      await vscode.window.showTextDocument(uri, { preview: false });
    }),

    { dispose: () => stopBridge() }
  );
}

function deactivate() {
  stopBridge();
}

module.exports = { activate, deactivate };
