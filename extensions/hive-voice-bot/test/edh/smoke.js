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