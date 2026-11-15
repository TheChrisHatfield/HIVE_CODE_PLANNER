// Regression tests from the Voice_Bot two-pass code review (2026-11-13).
// - liveFeedRelative: a real file whose name starts with ".." (for example "..notes.md") is fed to
//   the R22 live buffer. The old startsWith("..") check dropped it, so the stale check was skipped.
// - liveFeedRelative: paths outside the workspace are still refused.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const {
  liveFeedRelative,
  createTimerRegistry,
  createReadyLineReader,
  createSingleFlight,
  editorActionAdvance,
  EDITOR_ACTION_MAX_ATTEMPTS,
  appendBoundedTail,
} = require("../src/core");

// - createSingleFlight: followTask polls on an interval. A tick that fires while the previous
//   lookup is still awaiting must be skipped, or the terminal task message can show twice.
test("single-flight skips ticks while a call is still in flight", async () => {
  let calls = 0;
  let release;
  const gate = new Promise((resolve) => (release = resolve));
  const poll = createSingleFlight(async () => {
    calls += 1;
    await gate;
  });
  const first = poll();
  poll();
  poll();
  assert.equal(calls, 1);
  release();
  await first;
  await poll();
  assert.equal(calls, 2);
});

test("single-flight recovers after the in-flight call throws", async () => {
  let calls = 0;
  const poll = createSingleFlight(async () => {
    calls += 1;
    if (calls === 1) throw new Error("lookup failed");
  });
  await assert.rejects(poll(), /lookup failed/);
  await poll();
  assert.equal(calls, 2);
});

// - createReadyLineReader: the host must act on the bridge ready line once. Stdout after it must
//   not re-run ready handling, which re-armed the approval poll and cleared shown-request state.
test("ready reader returns the first complete line once and ignores later stdout", () => {
  const feed = createReadyLineReader();
  assert.equal(feed('{"ok":true,"host":"127.0.0.1"'), null);
  assert.equal(feed(',"port":61490}\n'), '{"ok":true,"host":"127.0.0.1","port":61490}');
  assert.equal(feed("some later stdout line\n"), null);
  assert.equal(feed("another\n"), null);
});

test("ready reader returns null until a newline arrives", () => {
  const feed = createReadyLineReader();
  assert.equal(feed("partial"), null);
  assert.equal(feed(" line"), null);
});

// - createTimerRegistry: stopping the bridge must end every followTask timer. A network error
//   keeps a poll alive until its 15-minute deadline, so untracked timers hit a dead bridge.
test("stopAll clears every tracked task-follow timer and empties the registry", () => {
  const cleared = [];
  const reg = createTimerRegistry((t) => cleared.push(t));
  reg.add("timer-a");
  reg.add("timer-b");
  assert.equal(reg.size(), 2);
  reg.stopAll();
  assert.deepEqual(cleared.sort(), ["timer-a", "timer-b"]);
  assert.equal(reg.size(), 0);
});

test("release clears one timer and stops tracking it", () => {
  const cleared = [];
  const reg = createTimerRegistry((t) => cleared.push(t));
  reg.add("t1");
  reg.add("t2");
  reg.release("t1");
  assert.deepEqual(cleared, ["t1"]);
  assert.equal(reg.size(), 1);
  reg.stopAll();
  assert.deepEqual(cleared, ["t1", "t2"]);
});

const root = path.resolve("/work/repo");

test("a file whose name starts with '..' inside the workspace is fed", () => {
  const abs = path.join(root, "..notes.md");
  assert.equal(liveFeedRelative(root, abs), "..notes.md");
});

test("a nested file inside the workspace is fed with forward slashes", () => {
  const abs = path.join(root, "src", "app.py");
  assert.equal(liveFeedRelative(root, abs), "src/app.py");
});

test("a file outside the workspace is not fed", () => {
  assert.equal(liveFeedRelative(root, path.resolve("/work/other/a.py")), null);
});

test("the workspace root itself is not fed as a file", () => {
  assert.equal(liveFeedRelative(root, root), null);
});

test("a parent-escaping path is not fed", () => {
  assert.equal(liveFeedRelative(root, path.join(root, "..", "secret.txt")), null);
});

test("missing root or path yields null", () => {
  assert.equal(liveFeedRelative("", "/x"), null);
  assert.equal(liveFeedRelative(root, ""), null);
});

// - editorActionAdvance: a permanently failing editor action (deleted file, unknown kind) used to
//   retry every poll forever and never ack. It now gives up after a bounded number of attempts and
//   acks, so the bridge clears it. A transient failure still recovers on a later attempt.
function simulateEditorPolls(outcomes) {
  const pending = { pending: true, action_id: "ed_1", kind: "navigate", file_path: "src/gone.py" };
  let shownActionId = null;
  let failures = 0;
  const actions = [];
  for (const opened of outcomes) {
    const next = editorActionAdvance({ shownActionId, pending, opened, failures });
    actions.push(next.action);
    shownActionId = next.shownActionId;
    if (next.action === "retry") failures += 1;
    if (next.action === "give_up" || next.action === "opened") failures = 0;
    if (next.action === "give_up" || next.action === "opened") break;
  }
  return actions;
}

test("a permanently failing editor action gives up within the attempt bound and acks", () => {
  const actions = simulateEditorPolls(Array(50).fill(false));
  assert.equal(actions.length, EDITOR_ACTION_MAX_ATTEMPTS);
  assert.equal(actions[actions.length - 1], "give_up");
  const last = editorActionAdvance({
    shownActionId: null,
    pending: { pending: true, action_id: "ed_1" },
    opened: false,
    failures: EDITOR_ACTION_MAX_ATTEMPTS - 1,
  });
  assert.equal(last.ack, true);
});

test("a transient editor failure recovers on a later attempt without giving up", () => {
  assert.deepEqual(simulateEditorPolls([false, false, true]), ["retry", "retry", "opened"]);
});

test("the first failed attempt is still a retry, not a give-up", () => {
  const next = editorActionAdvance({
    shownActionId: null,
    pending: { pending: true, action_id: "ed_1" },
    opened: false,
  });
  assert.deepEqual(next, { action: "retry", shownActionId: null, ack: false });
});

// - appendBoundedTail: the bridge stderr tail must never grow past its cap, and must keep the
//   newest text (the part that explains a failed start).
test("appendBoundedTail keeps only the newest characters up to the cap", () => {
  let tail = "";
  for (let i = 0; i < 100; i += 1) tail = appendBoundedTail(tail, "line-" + i + "\n", 40);
  assert.ok(tail.length <= 40);
  assert.ok(tail.endsWith("line-99\n"));
});

test("appendBoundedTail returns short text unchanged", () => {
  assert.equal(appendBoundedTail("ab", "cd", 40), "abcd");
});
