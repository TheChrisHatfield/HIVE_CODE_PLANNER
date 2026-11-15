// Regression tests from the Voice_Bot code review (2026-11-10).
// - a non-file document (untitled, diff) must not be reported as a workspace file (R28).
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const {
  buildContextSnapshot,
  taskPollDecision,
  approvalWatchDecision,
  approvalExpiredNotice,
  approvalReplySettlesHost,
  approvalReplySpokenNotice,
  editorActionAdvance,
  pickLiveDocumentRelative,
  boundFileUnresolved,
  sameFsPath,
  matchOpenFsPath,
  resolveHivePlannerSrc,
  TASK_POLL_MAX_MS,
  readDiskText,
} = require("../src/core");

test("an expired shown approval never claims nothing ran as fact (answered elsewhere is possible)", () => {
  const notice = approvalExpiredNotice();
  assert.match(notice, /no longer pending/);
  assert.match(notice, /answered elsewhere/);
  assert.doesNotMatch(notice, /Nothing was executed\./);
});

test("unopened bound file reads its text from disk, and a read failure yields empty (R22)", () => {
  const fake = (p) => {
    if (p === "/repo/project/src/app.py") return "print(1)";
    throw new Error("ENOENT");
  };
  assert.equal(readDiskText("/repo/project/src/app.py", fake), "print(1)");
  assert.equal(readDiskText("/repo/project/missing.py", fake), "");
});

const ROOT = path.resolve("/repo/project");

test("untitled document reports no_active_file, not a workspace-relative path", () => {
  const s = buildContextSnapshot({
    workspaceRoot: ROOT,
    activeDocument: { fileName: "Untitled-1", scheme: "untitled", version: 1, isDirty: true, text: "draft" },
  });
  assert.equal(s.file, null);
  assert.equal(s.reason, "no_active_file");
  assert.ok(!s.file_content, "no file content may leave for a non-file document");
});

test("task poll stops on lookup failure, terminal state, and the deadline", () => {
  assert.deepEqual(
    taskPollDecision({ status: 404, state: "running", elapsedMs: 0 }),
    { stop: true, reason: "lookup_failed" },
  );
  assert.deepEqual(
    taskPollDecision({ status: 200, state: "completed", elapsedMs: 1000 }),
    { stop: true, reason: "terminal" },
  );
  assert.deepEqual(
    taskPollDecision({ status: 200, state: "running", elapsedMs: TASK_POLL_MAX_MS }),
    { stop: true, reason: "poll_timeout" },
  );
  assert.deepEqual(
    taskPollDecision({ status: 200, state: "running", elapsedMs: 10 }),
    { stop: false, reason: "wait" },
  );
  assert.deepEqual(
    taskPollDecision({ status: 0, state: "", elapsedMs: 10, networkError: true }),
    { stop: false, reason: "wait" },
  );
  assert.deepEqual(
    taskPollDecision({
      status: 0,
      state: "",
      elapsedMs: TASK_POLL_MAX_MS,
      networkError: true,
    }),
    { stop: true, reason: "poll_timeout" },
  );
});

test("approval watch reports an expired shown request instead of ignoring it", () => {
  assert.deepEqual(approvalWatchDecision("apr_1", { pending: false }), { action: "expired" });
  assert.deepEqual(approvalWatchDecision(null, { pending: false }), { action: "idle" });
  assert.deepEqual(
    approvalWatchDecision("apr_1", { pending: true, request_id: "apr_1" }),
    { action: "already_shown" },
  );
  assert.deepEqual(
    approvalWatchDecision(null, { pending: true, request_id: "apr_2" }),
    { action: "show" },
  );
});

test("approvalReplySettlesHost is false for dismissals and reprompts", () => {
  assert.equal(approvalReplySettlesHost(null), false);
  assert.equal(approvalReplySettlesHost({ status: 200, body: { status: "reprompt" } }), false);
  assert.equal(approvalReplySettlesHost({ status: 409, body: { status: "stale_approval" } }), false);
  assert.equal(approvalReplySettlesHost({ status: 200, body: { status: "stale" } }), false);
  assert.equal(approvalReplySettlesHost({ status: 200, body: { status: "approved" } }), true);
  assert.equal(approvalReplySettlesHost({ status: 200, body: { status: "answered" } }), true);
});

test("approvalReplySpokenNotice surfaces stale and reprompt on HTTP 200", () => {
  assert.equal(
    approvalReplySpokenNotice({
      status: 200,
      body: { status: "stale", spoken: "The editor buffer changed. Re-snapshot and resubmit." },
    }),
    "The editor buffer changed. Re-snapshot and resubmit.",
  );
  assert.equal(
    approvalReplySpokenNotice({ status: 200, body: { status: "approved", spoken: "Approved." } }),
    "",
  );
});

test("dismissed approval can show the modal again on the next poll (R6)", () => {
  const pending = { pending: true, request_id: "apr_3" };
  assert.deepEqual(
    approvalWatchDecision(null, pending, false),
    { action: "show" },
    "after a dismissed modal, shownRequestId must reset so the user can retry",
  );
});

test("a locally settled approval is cleared, not reported as a timeout (R6)", () => {
  assert.deepEqual(
    approvalWatchDecision("apr_1", { pending: false }, true),
    { action: "cleared" },
  );
  assert.deepEqual(
    approvalWatchDecision("apr_1", { pending: true, request_id: "apr_1" }, true),
    { action: "already_shown" },
    "keep the id until pending clears so the modal is not shown twice",
  );
});

test("failed editor open is retried and not remembered as shown", () => {
  const pending = { pending: true, action_id: "ed_1" };
  assert.deepEqual(
    editorActionAdvance({ shownActionId: null, pending, opened: false }),
    { action: "retry", shownActionId: null, ack: false },
  );
  assert.deepEqual(
    editorActionAdvance({ shownActionId: null, pending, opened: true }),
    { action: "opened", shownActionId: "ed_1", ack: true },
  );
  assert.deepEqual(
    editorActionAdvance({ shownActionId: "ed_1", pending, opened: true }),
    { action: "already_opened", shownActionId: "ed_1", ack: true },
  );
});

test("live open-document match ignores Windows path case (R22)", () => {
  const lower = "d:\\DRIVE_DOWNLOADS\\HIVE_CODE_PLANNER\\src\\app.py";
  const mixed = "D:\\DRIVE_DOWNLOADS\\HIVE_CODE_PLANNER\\src\\app.py";
  if (process.platform === "win32") {
    assert.equal(sameFsPath(lower, mixed), true);
    assert.equal(matchOpenFsPath(mixed, [lower]), lower);
  } else {
    assert.equal(sameFsPath("/repo/src/app.py", "/repo/src/app.py"), true);
    assert.equal(sameFsPath("/repo/src/app.py", "/repo/src/other.py"), false);
    assert.equal(matchOpenFsPath("/repo/src/app.py", ["/repo/src/other.py", "/repo/src/app.py"]), "/repo/src/app.py");
  }
  assert.equal(matchOpenFsPath(mixed, []), null);
});

test("write-approval live snapshot prefers the bound task file (R22)", () => {
  assert.equal(
    pickLiveDocumentRelative({ pendingFile: "src/app.py", activeRelative: "src/other.py" }),
    "src/app.py",
  );
  assert.equal(
    pickLiveDocumentRelative({ pendingFile: "", activeRelative: "src/other.py" }),
    "src/other.py",
  );
});

test("a bound file that does not resolve in the workspace reads no document, never the active editor (R22)", () => {
  assert.equal(boundFileUnresolved({ root: ROOT, pendingFile: "../other/secret.py" }), true);
  assert.equal(boundFileUnresolved({ root: ROOT, pendingFile: "..\\other\\secret.py" }), true);
  assert.equal(boundFileUnresolved({ root: null, pendingFile: "src/app.py" }), true);
  assert.equal(boundFileUnresolved({ root: ROOT, pendingFile: "src/app.py" }), false);
  assert.equal(boundFileUnresolved({ root: ROOT, pendingFile: "" }), false);
});

test("resolveHivePlannerSrc prefers the setting then workspace src/hive_planner", () => {
  const exists = (p) => p === path.join(ROOT, "src", "hive_planner");
  assert.equal(resolveHivePlannerSrc(ROOT, "D:/custom/src", exists), "D:/custom/src");
  assert.equal(resolveHivePlannerSrc(ROOT, "  ", exists), path.join(ROOT, "src"));
  assert.equal(resolveHivePlannerSrc(ROOT, "", () => false), "");
  assert.equal(resolveHivePlannerSrc("", "", exists), "");
});

test("file-scheme document still reports its workspace file", () => {
  const s = buildContextSnapshot({
    workspaceRoot: ROOT,
    activeDocument: {
      fileName: path.join(ROOT, "src", "a.py"), scheme: "file", version: 2, isDirty: false, text: "x",
    },
  });
  assert.equal(s.file, "src/a.py");
  assert.equal(s.reason, null);
});
