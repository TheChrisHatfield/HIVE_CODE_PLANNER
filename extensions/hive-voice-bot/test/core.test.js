const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const {
  APPROVAL_OUTCOMES,
  isInsideWorkspace,
  pickSessionRoot,
  resolveWorkspaceRelative,
  buildContextSnapshot,
  requestApprovalStub,
} = require("../src/core");

const ROOT = path.resolve("/repo/project");

// T037 / P2-1: multi-root. The bound root is the folder holding the active file, not folder[0].
test("multi-root: active file in the second folder binds that folder, not folder[0]", () => {
  const A = path.resolve("/ws/alpha");
  const B = path.resolve("/ws/beta");
  assert.equal(pickSessionRoot([A, B], path.join(B, "src", "app.py")), B);
});

test("multi-root: active file in the first folder binds folder[0]", () => {
  const A = path.resolve("/ws/alpha");
  const B = path.resolve("/ws/beta");
  assert.equal(pickSessionRoot([A, B], path.join(A, "src", "app.py")), A);
});

test("multi-root: nested folders bind the most specific (longest) folder", () => {
  const outer = path.resolve("/ws/mono");
  const inner = path.resolve("/ws/mono/packages/core");
  assert.equal(pickSessionRoot([outer, inner], path.join(inner, "x.py")), inner);
});

test("multi-root: active file outside every folder falls back to folder[0]", () => {
  const A = path.resolve("/ws/alpha");
  const B = path.resolve("/ws/beta");
  assert.equal(pickSessionRoot([A, B], path.resolve("/elsewhere/z.py")), A);
});

test("multi-root: no active file falls back to folder[0]; a sibling prefix is not inside", () => {
  const A = path.resolve("/ws/alpha");
  assert.equal(pickSessionRoot([A], null), A);
  // "/ws/alpha-old" shares a string prefix with "/ws/alpha" but is a different folder.
  assert.equal(pickSessionRoot([A, path.resolve("/ws/alpha-old")], path.resolve("/ws/alpha-old/a.py")), path.resolve("/ws/alpha-old"));
});

test("multi-root: no folders gives null", () => {
  assert.equal(pickSessionRoot([], path.resolve("/ws/a.py")), null);
  assert.equal(pickSessionRoot(undefined, null), null);
});

test("snapshot with no workspace reports no_workspace", () => {
  const s = buildContextSnapshot({ workspaceRoot: null, activeDocument: null });
  assert.deepEqual(s, { workspace: null, file: null, reason: "no_workspace" });
});

test("snapshot with no active editor reports file null and no_active_file (R28)", () => {
  const s = buildContextSnapshot({ workspaceRoot: ROOT, activeDocument: null });
  assert.equal(s.file, null);
  assert.equal(s.reason, "no_active_file");
  assert.equal(s.workspace, ROOT);
});

test("snapshot for an in-workspace file carries relative path, version, dirty", () => {
  const s = buildContextSnapshot({
    workspaceRoot: ROOT,
    activeDocument: { fileName: path.join(ROOT, "src", "a.py"), version: 7, isDirty: true, text: "secret" },
  });
  assert.equal(s.file, "src/a.py");
  assert.equal(s.document_version, 7);
  assert.equal(s.dirty, true);
  assert.equal(s.reason, null);
  assert.equal(s.file_content, "");
});

test("saved file content is truncated and flagged, unsaved content is omitted", () => {
  const saved = buildContextSnapshot({
    workspaceRoot: ROOT,
    activeDocument: { fileName: path.join(ROOT, "src", "a.py"), version: 1, isDirty: false, text: "abc" },
  });
  assert.equal(saved.file_content, "abc");
  assert.equal(saved.file_truncated, false);
  const cut = buildContextSnapshot({
    workspaceRoot: ROOT,
    activeDocument: { fileName: path.join(ROOT, "src", "a.py"), version: 1, isDirty: false, text: "abcdefghij" },
    maxBytes: 4,
  });
  assert.equal(cut.file_truncated, true);
  assert.ok(Buffer.byteLength(cut.file_content, "utf8") <= 4);
});

test("snapshot for a file outside the workspace is refused (R23 path_outside_workspace)", () => {
  const s = buildContextSnapshot({
    workspaceRoot: ROOT,
    activeDocument: { fileName: path.resolve("/elsewhere/secret.txt"), version: 1, isDirty: false },
  });
  assert.equal(s.file, null);
  assert.equal(s.reason, "path_outside_workspace");
});

test("isInsideWorkspace rejects traversal, the root itself, and absolute escapes", () => {
  assert.equal(isInsideWorkspace(ROOT, "src/a.py"), true);
  assert.equal(isInsideWorkspace(ROOT, "../other/a.py"), false);
  assert.equal(isInsideWorkspace(ROOT, "..notes/todo.md"), true);
  assert.equal(isInsideWorkspace(ROOT, "..cache/a.py"), true);
  assert.equal(isInsideWorkspace(ROOT, "."), false);
  assert.equal(isInsideWorkspace(ROOT, path.resolve("/etc/passwd")), false);
});

test("resolveWorkspaceRelative returns an in-root path and rejects traversal (R23)", () => {
  assert.equal(resolveWorkspaceRelative(ROOT, "src/a.py"), path.resolve(ROOT, "src/a.py"));
  assert.equal(resolveWorkspaceRelative(ROOT, "../other/a.py"), null);
  assert.equal(resolveWorkspaceRelative(ROOT, "..notes/todo.md"), path.resolve(ROOT, "..notes/todo.md"));
  assert.equal(resolveWorkspaceRelative(null, "src/a.py"), null);
  assert.equal(resolveWorkspaceRelative(ROOT, ""), null);
});



test("approval: only an explicit approve executes", async () => {
  const r = await requestApprovalStub(
    { kind: "write_or_command", action: "run tests" },
    { showPrompt: async () => "approve" },
    1000
  );
  assert.equal(r.outcome, APPROVAL_OUTCOMES.APPROVED);
  assert.equal(r.executes, true);
});

test("approval: deny, dismiss, and UI errors all fail closed", async () => {
  const deny = await requestApprovalStub({ kind: "plan", action: "x" }, { showPrompt: async () => "deny" }, 1000);
  const dismiss = await requestApprovalStub({ kind: "plan", action: "x" }, { showPrompt: async () => undefined }, 1000);
  const broken = await requestApprovalStub(
    { kind: "plan", action: "x" },
    { showPrompt: async () => { throw new Error("no ui"); } },
    1000
  );
  for (const r of [deny, dismiss, broken]) {
    assert.equal(r.outcome, APPROVAL_OUTCOMES.DENIED);
    assert.equal(r.executes, false);
  }
});

test("approval: no answer before the timeout is timed_out and does not execute", async () => {
  const r = await requestApprovalStub(
    { kind: "question", action: "x" },
    { showPrompt: () => new Promise(() => {}) },
    20
  );
  assert.equal(r.outcome, APPROVAL_OUTCOMES.TIMED_OUT);
  assert.equal(r.executes, false);
});

// ---- T007: selection, diagnostics, and size limits ----

const {
  DEFAULT_SNAPSHOT_MAX_BYTES,
  loadSnapshotMaxBytes,
  truncateUtf8,
  buildSelection,
  buildDiagnostics,
} = require("../src/core");

const FILE = { fileName: path.join(ROOT, "src", "a.py"), version: 3, isDirty: false };
const sel = (text) => ({ text, startLine: 4, startCharacter: 2, endLine: 6, endCharacter: 9 });

test("no selection yields selection null (T007)", () => {
  const s = buildContextSnapshot({ workspaceRoot: ROOT, activeDocument: FILE, selection: null });
  assert.equal(s.selection, null);
  assert.deepEqual(s.diagnostics, []);
  assert.equal(s.diagnostics_truncated, false);
});

test("selection under the limit is complete with 1-based positions and no truncated flag", () => {
  const s = buildContextSnapshot({ workspaceRoot: ROOT, activeDocument: FILE, selection: sel("def foo(): pass") });
  assert.equal(s.selection.text, "def foo(): pass");
  assert.equal(s.selection.truncated, false);
  assert.equal(s.selection.bytes, 15);
  assert.deepEqual(s.selection.start, { line: 5, column: 3 });
  assert.deepEqual(s.selection.end, { line: 7, column: 10 });
});

test("limit: selection exactly at snapshot_max_bytes is not truncated", () => {
  const text = "a".repeat(64);
  const s = buildSelection(sel(text), 64);
  assert.equal(s.text, text);
  assert.equal(s.truncated, false);
  assert.equal(s.bytes, 64);
});

test("limit: selection one byte over snapshot_max_bytes is truncated, flagged, and within the limit", () => {
  const s = buildSelection(sel("a".repeat(65)), 64);
  assert.equal(s.truncated, true);
  assert.equal(s.bytes, 64);
  assert.equal(s.text.length, 64);
});

test("limit: truncation never splits a multi-byte UTF-8 character", () => {
  // "�" is 2 bytes. A 5-byte cut would split the 3rd character, so it must back off to 4 bytes.
  const e = "\u00e9"; // written as an escape so the test source stays ASCII
  const cut = truncateUtf8(e + e + e, 5);
  assert.equal(cut.text, e + e);
  assert.equal(cut.bytes, 4);
  assert.equal(cut.truncated, true);
  assert.ok(Buffer.byteLength(cut.text, "utf8") <= 5);
});

test("limit: snapshot selection cap is read from the config file, not hard-coded", () => {
  const cfg = JSON.stringify({ snapshot_max_bytes: 10 });
  const maxBytes = loadSnapshotMaxBytes(ROOT, () => cfg);
  assert.equal(maxBytes, 10);
  const s = buildContextSnapshot({ workspaceRoot: ROOT, activeDocument: FILE, selection: sel("x".repeat(11)), maxBytes });
  assert.equal(s.selection.truncated, true);
  assert.equal(s.selection.bytes, 10);
});

test("limit: missing, unreadable, invalid, or non-positive config falls back to 64 KB", () => {
  assert.equal(loadSnapshotMaxBytes(ROOT, () => { throw new Error("ENOENT"); }), DEFAULT_SNAPSHOT_MAX_BYTES);
  assert.equal(loadSnapshotMaxBytes(ROOT, () => "{not json"), DEFAULT_SNAPSHOT_MAX_BYTES);
  assert.equal(loadSnapshotMaxBytes(ROOT, () => JSON.stringify({ snapshot_max_bytes: 0 })), DEFAULT_SNAPSHOT_MAX_BYTES);
  assert.equal(loadSnapshotMaxBytes(ROOT, () => JSON.stringify({ snapshot_max_bytes: "9" })), DEFAULT_SNAPSHOT_MAX_BYTES);
  assert.equal(DEFAULT_SNAPSHOT_MAX_BYTES, 64 * 1024);
});

test("diagnostics map severity and use 1-based positions", () => {
  const d = buildDiagnostics(
    [{ severity: 0, message: "boom", source: "py", code: 42, line: 9, character: 0 }],
    1000
  );
  assert.equal(d.diagnostics_truncated, false);
  assert.deepEqual(d.diagnostics[0], {
    severity: "error",
    message: "boom",
    source: "py",
    code: "42",
    line: 10,
    column: 1,
  });
  assert.equal(buildDiagnostics([{ severity: 3, message: "h", line: 0, character: 0 }], 1000).diagnostics[0].severity, "hint");
});

test("limit: diagnostics under budget are all kept with no truncated flag", () => {
  const list = [0, 1, 2].map((i) => ({ severity: 1, message: `m${i}`, line: i, character: 0 }));
  const d = buildDiagnostics(list, 10_000);
  assert.equal(d.diagnostics.length, 3);
  assert.equal(d.diagnostics_truncated, false);
});

test("limit: diagnostics over budget keep the earliest, drop the rest, and set diagnostics_truncated", () => {
  const list = Array.from({ length: 50 }, (_, i) => ({ severity: 0, message: "x".repeat(100), line: i, character: 0 }));
  const d = buildDiagnostics(list, 1000);
  assert.ok(d.diagnostics.length > 0 && d.diagnostics.length < 50);
  assert.equal(d.diagnostics_truncated, true);
  // Kept items are the first ones, in order.
  assert.deepEqual(d.diagnostics.map((x) => x.line), d.diagnostics.map((_, i) => i + 1));
  // The serialized list fits the limit.
  assert.ok(Buffer.byteLength(JSON.stringify(d.diagnostics), "utf8") <= 1000);
});

test("limit: a single diagnostic larger than the budget is dropped and flagged, not silently cut", () => {
  const d = buildDiagnostics([{ severity: 0, message: "y".repeat(5000), line: 0, character: 0 }], 1000);
  assert.deepEqual(d.diagnostics, []);
  assert.equal(d.diagnostics_truncated, true);
});

test("snapshot carries diagnostics and their truncated flag end to end", () => {
  const s = buildContextSnapshot({
    workspaceRoot: ROOT,
    activeDocument: FILE,
    diagnostics: [{ severity: 1, message: "warn", line: 2, character: 4 }],
    maxBytes: 1000,
  });
  assert.equal(s.diagnostics[0].message, "warn");
  assert.equal(s.diagnostics_truncated, false);
  assert.equal(s.file, "src/a.py");
  assert.equal(s.reason, null);
});

test("bridgeExitError surfaces the already-running reason from the Python refusal", () => {
  const { bridgeExitError } = require("../src/core");
  const stderr =
    "Error: a voice bridge is already running for this repo (see .hive/voice-bot/bridge.json)\n";
  const err = bridgeExitError(1, stderr);
  assert.equal(
    err.message,
    "a voice bridge is already running for this repo (see .hive/voice-bot/bridge.json)",
  );
});

test("bridgeExitError keeps the generic exit text for other failures", () => {
  const { bridgeExitError } = require("../src/core");
  const err = bridgeExitError(2, "Traceback: boom");
  assert.equal(err.message, "bridge exited before ready (code 2): Traceback: boom");
});
