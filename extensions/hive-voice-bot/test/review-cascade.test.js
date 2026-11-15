// Voice_Bot review cascade: a reply the provider could not take must reach the user (R6, R22).
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { approvalReplySpokenNotice, approvalReplySettlesHost, readBridgeConnection } = require("../src/core.js");

// The host skips a poll tick (does not stop the watcher) when this returns null. A partially
// written bridge.json must read as "no connection yet", never throw into the poller.
test("readBridgeConnection returns null for a partially written bridge.json (host skips the tick)", () => {
  const root = path.join("ws");
  const files = {
    [path.join(root, ".hive", "voice-bot", "bridge.json")]: '{"host": "127.0.0.1", "po',
    [path.join(root, ".hive", "voice-bot", "bridge-token")]: "tok",
  };
  const readFile = (p) => {
    if (!(p in files)) throw new Error("ENOENT");
    return files[p];
  };
  assert.equal(readBridgeConnection(root, readFile), null);
});

test("approvalReplySpokenNotice surfaces not_delivered so the user hears it was not answered", () => {
  const spoken = "The provider offered no way to take that answer. Nothing was answered.";
  assert.equal(
    approvalReplySpokenNotice({ status: 200, body: { status: "not_delivered", spoken } }),
    spoken,
  );
});

test("approvalReplySettlesHost treats not_delivered as a resolved reply, not a retry", () => {
  assert.equal(approvalReplySettlesHost({ status: 200, body: { status: "not_delivered" } }), true);
});
