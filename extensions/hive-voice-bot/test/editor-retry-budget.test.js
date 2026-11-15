// Regression test (Voice_Bot UI code review, 2026-11-13): the editor-open retry budget was one
// global counter. A failure on one action leaked into the next action, so the next action gave
// up after fewer attempts than EDITOR_ACTION_MAX_ATTEMPTS.
const test = require("node:test");
const assert = require("node:assert/strict");
const {
  editorActionAdvance,
  editorRetryBudget,
  EDITOR_ACTION_MAX_ATTEMPTS,
} = require("../src/core");

// Mirrors the host loop in src/extension.js pollEditorActions. `polls` is a list of
// { pending action or null, opened } per tick.
function runHostPolls(polls) {
  let shownActionId = null;
  let editorFailures = 0;
  let editorFailureId = null;
  const actions = [];
  for (const { pending, opened } of polls) {
    const body = pending ? { pending: true, action_id: pending, kind: "navigate" } : { pending: false };
    const budget = editorRetryBudget({ failures: editorFailures, failureActionId: editorFailureId, pending: body });
    const next = editorActionAdvance({ shownActionId, pending: body, opened, failures: budget.failures });
    actions.push(`${pending || "-"}:${next.action}`);
    shownActionId = next.shownActionId;
    if (next.action === "retry") {
      editorFailures = budget.failures + 1;
      editorFailureId = budget.failureActionId;
    } else if (next.action === "give_up" || next.action === "opened") {
      editorFailures = 0;
      editorFailureId = null;
    }
  }
  return actions;
}

test("a failure on an earlier action does not shorten the next action's attempts", () => {
  // ed_1 fails once, then the bridge clears it (idle). ed_2 then fails every time.
  const polls = [
    { pending: "ed_1", opened: false }, // retry, count 1
    { pending: null, opened: false }, // idle, count must reset
  ];
  for (let i = 0; i < EDITOR_ACTION_MAX_ATTEMPTS; i += 1) polls.push({ pending: "ed_2", opened: false });
  const actions = runHostPolls(polls);
  const ed2 = actions.filter((a) => a.startsWith("ed_2:"));
  // Full budget: retries first, then exactly one give_up on the final attempt.
  assert.equal(ed2.length, EDITOR_ACTION_MAX_ATTEMPTS);
  assert.equal(ed2[ed2.length - 1], "ed_2:give_up");
});

test("switching the pending action mid-retry restarts the budget for the new action", () => {
  const polls = [
    { pending: "ed_1", opened: false }, // retry, count 1
    { pending: "ed_2", opened: false }, // new action, must start at zero: retry, not give_up
  ];
  const actions = runHostPolls(polls);
  assert.deepEqual(actions, ["ed_1:retry", "ed_2:retry"]);
});

test("a permanently failing action still gives up within the bound for the same action", () => {
  const polls = Array.from({ length: 10 }, () => ({ pending: "ed_9", opened: false }));
  const actions = runHostPolls(polls);
  assert.equal(actions.filter((a) => a === "ed_9:retry").length, EDITOR_ACTION_MAX_ATTEMPTS - 1);
  assert.equal(actions.filter((a) => a === "ed_9:give_up").length, 1);
});

test("editorRetryBudget keeps the count for the same action and clears it when idle", () => {
  const pending = { pending: true, action_id: "ed_1" };
  assert.deepEqual(editorRetryBudget({ failures: 2, failureActionId: "ed_1", pending }), {
    failures: 2,
    failureActionId: "ed_1",
  });
  assert.deepEqual(editorRetryBudget({ failures: 2, failureActionId: "ed_1", pending: { pending: false } }), {
    failures: 0,
    failureActionId: null,
  });
});
