// Runs inside a real VS Code Extension Development Host (T007 evidence).
// Launched by test/edh/run-edh.ps1 via --extensionTestsPath. Writes a JSON report and quits.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const vscode = require("vscode");

const REPORT = path.join(os.tmpdir(), "hive-voice-bot-edh-report.json");

async function run() {
  const checks = [];
  const check = (name, pass, detail) => checks.push({ name, pass: Boolean(pass), detail });
  let snap = null;
  let error = null;
  let collection = null;
  try {
    const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
    check("workspace folder open", folder, folder && folder.uri.fsPath);
    const doc = await vscode.workspace.openTextDocument(path.join(folder.uri.fsPath, "src", "a.py"));
    const editor = await vscode.window.showTextDocument(doc);
    editor.selection = new vscode.Selection(0, 0, 0, 300); // 300 chars; config limit is 256
    collection = vscode.languages.createDiagnosticCollection("hive-edh-test");
    collection.set(doc.uri, [
      new vscode.Diagnostic(new vscode.Range(1, 0, 1, 5), "short warning", vscode.DiagnosticSeverity.Warning),
      new vscode.Diagnostic(new vscode.Range(1, 0, 1, 5), "m".repeat(400), vscode.DiagnosticSeverity.Error),
    ]);
    snap = await vscode.commands.executeCommand("hive.voiceBot.getContextSnapshot");
    check("command returns a snapshot object", snap && typeof snap === "object", null);
    check("file is workspace-relative", snap.file === "src/a.py", snap.file);
    check("reason is null on success", snap.reason === null, snap.reason);
    check("selection truncated at config limit (256 bytes)", snap.selection && snap.selection.truncated === true && snap.selection.bytes === 256, snap.selection && { bytes: snap.selection.bytes, truncated: snap.selection.truncated });
    check("selection start is 1-based", snap.selection && snap.selection.start.line === 1 && snap.selection.start.column === 1, snap.selection && snap.selection.start);
    check("diagnostics under budget kept (severity mapped)", snap.diagnostics.length === 1 && snap.diagnostics[0].severity === "warning" && snap.diagnostics[0].line === 2, snap.diagnostics);
    check("oversized diagnostic dropped and flagged", snap.diagnostics_truncated === true, snap.diagnostics_truncated);

    // G4 live write path (R22): edit the live buffer in the Extension Host, re-capture, and
    // confirm the snapshot fields the HIVE stale check compares (document_version, dirty) move.
    const before = { version: snap.document_version, dirty: snap.dirty };
    const edited = await editor.edit((eb) => eb.insert(new vscode.Position(0, 0), "// hive-edh-stale\n"));
    check("live buffer edit applied", edited === true, edited);
    const after = await vscode.commands.executeCommand("hive.voiceBot.getContextSnapshot");
    check("recapture after edit: document_version increased", after.document_version > before.version, { before: before.version, after: after.document_version });
    check("recapture after edit: dirty is true", after.dirty === true, after.dirty);
    check("recapture after edit: unsaved text withheld (R28 excluded: unsaved)", after.file_content === "" && !JSON.stringify(after).includes("hive-edh-stale"), after.file_content === "");
    // Restore the fixture on disk so the repo is unchanged after the run.
    await vscode.commands.executeCommand("workbench.action.files.revert");
    const restored = await vscode.commands.executeCommand("hive.voiceBot.getContextSnapshot");
    check("revert restores clean buffer", restored.dirty === false, restored.dirty);

    // T038 chain (one run): the extension itself starts the fixture bridge, submits through
    // hive.voiceBot.submitTask (which captures the editor snapshot and POSTs /v1/submit), follows
    // the task to a terminal state, then stops the bridge. Notifications are captured, not shown.
    const notes = [];
    const realInfo = vscode.window.showInformationMessage;
    const realError = vscode.window.showErrorMessage;
    const realInput = vscode.window.showInputBox;
    const note = (level) => (msg) => {
      notes.push({ level, msg: String(msg) });
      return Promise.resolve(undefined);
    };
    vscode.window.showInformationMessage = note("info");
    vscode.window.showErrorMessage = note("error");
    vscode.window.showInputBox = async () => "EDH chain check: say done";
    const submitIdx = () => notes.findIndex((n) => /HIVE Voice_Bot: task task_/.test(n.msg));
    const terminal = () => notes.find((n, i) => i > submitIdx() && n.level === "info" && /^HIVE Voice_Bot: task (?!task_)[a-z_]+\./.test(n.msg));
    try {
      await vscode.commands.executeCommand("hive.voiceBot.startBridge");
      const bridgeUp = notes.some((n) => /HIVE Voice_Bot bridge: started\./.test(n.msg));
      check("extension starts fixture bridge (startBridge)", bridgeUp, notes.map((n) => n.msg));
      if (bridgeUp) {
        await vscode.commands.executeCommand("hive.voiceBot.submitTask");
        const submitted = submitIdx() !== -1;
        check("extension submitTask accepted (task id returned)", submitted, submitted ? notes[submitIdx()].msg : notes.map((n) => n.msg));
        if (submitted) {
          const deadline = Date.now() + 180000;
          while (!terminal() && Date.now() < deadline) {
            await new Promise((r) => setTimeout(r, 1000));
          }
          const done = terminal();
          check("runner completes the task (terminal state completed)", Boolean(done) && /^HIVE Voice_Bot: task completed\./.test(done.msg), done ? done.msg : "no terminal state within 180 s");

          // T043 live visible diff (G4): queue show_diff through the real bridge
          // (POST /v1/editor/show_diff), then wait for the extension to open it as a diff editor.
          // The ack clears GET /v1/editor pending, so the extension has consumed the action.
          const taskId = (notes[submitIdx()].msg.match(/task (task_[^\s.]+)/) || [])[1];
          const conn = require("../../src/core.js").readBridgeConnection(folder.uri.fsPath, (p) => fs.readFileSync(p, "utf8"));
          if (taskId && conn) {
            const base = `http://${conn.host}:${conn.port}`;
            const headers = { Authorization: `Bearer ${conn.token}`, "Content-Type": "application/json" };
            const res = await fetch(`${base}/v1/editor/show_diff`, {
              method: "POST",
              headers,
              body: JSON.stringify({ workspace: folder.uri.fsPath, task_id: taskId }),
            });
            const queued = { status: res.status, body: await res.json() };
            check("bridge queues show_diff for the completed task", queued.status === 200 && queued.body.queued === true, queued);
            const shownDeadline = Date.now() + 30000;
            let shown = false;
            while (!shown && Date.now() < shownDeadline) {
              const active = vscode.window.activeTextEditor;
              shown = Boolean(active && active.document.languageId === "diff" && active.document.isUntitled);
              if (!shown) await new Promise((r) => setTimeout(r, 500));
            }
            check("extension opens show_diff as a visible diff editor", shown, shown ? "languageId=diff, untitled" : "no diff editor within 30 s");
            const pendingRes = await fetch(`${base}/v1/editor?workspace=${encodeURIComponent(folder.uri.fsPath)}`, { headers });
            const pending = await pendingRes.json();
            check("extension acked show_diff (no pending editor action)", pendingRes.status === 200 && pending.pending === false, pending);
          } else {
            check("bridge discovery and task id available for show_diff", false, { taskId, bridge: Boolean(conn) });
          }
        }
      }
    } finally {
      await vscode.commands.executeCommand("hive.voiceBot.stopBridge");
      vscode.window.showInformationMessage = realInfo;
      vscode.window.showErrorMessage = realError;
      vscode.window.showInputBox = realInput;
    }
    check("bridge stopped after chain", notes.some((n) => /bridge stopped\./.test(n.msg)), null);
  } catch (err) {
    error = String(err && err.stack ? err.stack : err);
  } finally {
    if (collection) collection.dispose();
  }
  const report = {
    host: "VS Code Extension Development Host",
    vscodeVersion: vscode.version,
    passed: error === null && checks.every((c) => c.pass),
    checks,
    error,
    snapshot: snap,
  };
  fs.writeFileSync(REPORT, JSON.stringify(report, null, 2), "utf8");
  await vscode.commands.executeCommand("workbench.action.quit");
}

module.exports = { run };