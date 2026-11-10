// Integration: the extension's bridge client against the real `voice-bot bridge` Python process.
// The Python side is production code (CLI, runner, schema, bridge). The Cursor agent path is
// deliberately missing, so a submit must end as a recorded failure, never as a success claim.
//
// Python command: $HIVE_PYTHON if set, otherwise `py -3.11`. Package source: <repo>/src.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const readline = require("node:readline");
const { spawn } = require("node:child_process");
const {
  answerPendingApproval,
  createBridgeClient,
  parseReadyLine,
  readBridgeConnection,
} = require("../src/core");

const REPO_SRC = path.resolve(__dirname, "..", "..", "..", "src");
const FIXTURE_AGENT_SERVER = path.resolve(__dirname, "..", "..", "..", "tests", "fixtures", "acp_turn_server.py");
const PYTHON = (process.env.HIVE_PYTHON || "py -3.11").trim().split(/\s+/);

function startBridge(root, agentPath = path.join(root, "no-such-agent.exe")) {
  const env = { ...process.env, PYTHONPATH: REPO_SRC + path.delimiter + (process.env.PYTHONPATH || "") };
  const args = [
    ...PYTHON.slice(1), "-m", "hive_planner", "--root", root,
    "voice-bot", "bridge", "--agent-path", agentPath,
  ];
  const proc = spawn(PYTHON[0], args, { cwd: root, env, stdio: ["pipe", "pipe", "pipe"] });
  const stderr = [];
  proc.stderr.on("data", (chunk) => stderr.push(chunk.toString()));
  const ready = new Promise((resolve, reject) => {
    const rl = readline.createInterface({ input: proc.stdout });
    rl.once("line", (line) => resolve(parseReadyLine(line)));
    proc.once("exit", (code) => reject(new Error(`bridge exited before ready (${code}): ${stderr.join("")}`)));
  });
  return { proc, ready, stderr };
}

function waitExit(proc, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("bridge did not exit after stdin closed")), ms);
    proc.once("exit", (code) => {
      clearTimeout(timer);
      resolve(code);
    });
  });
}

async function pollTask(client, taskId, contextId, ms) {
  const deadline = Date.now() + ms;
  for (;;) {
    const { status, body } = await client.task(taskId, contextId);
    if (status !== 200) throw new Error(`task lookup failed: ${status} ${JSON.stringify(body)}`);
    if (["completed", "failed", "cancelled"].includes(body.state) || Date.now() > deadline) return body;
    await new Promise((r) => setTimeout(r, 200));
  }
}

// The bridge launches `<agent-path> acp` with no shell, so the Python fixture needs a launcher.
// On Windows that is a .cmd file; elsewhere a sh script. Both run the same ACP fixture server.
function writeFixtureAgent(dir) {
  if (process.platform === "win32") {
    const file = path.join(dir, "fixture-agent.cmd");
    fs.writeFileSync(file, `@echo off\r\n${PYTHON.join(" ")} "${FIXTURE_AGENT_SERVER}" %*\r\n`);
    return file;
  }
  const file = path.join(dir, "fixture-agent");
  fs.writeFileSync(file, `#!/bin/sh\nexec ${PYTHON.join(" ")} "${FIXTURE_AGENT_SERVER}" "$@"\n`, { mode: 0o755 });
  return file;
}

// Poll the bridge until an approval is pending, then return its view (the GET /v1/approval body).
async function waitForPending(client, ms) {
  const deadline = Date.now() + ms;
  for (;;) {
    const { status, body } = await client.approval();
    if (status !== 200) throw new Error(`approval lookup failed: ${status} ${JSON.stringify(body)}`);
    if (body.pending) return body;
    if (Date.now() > deadline) throw new Error("no approval became pending in time");
    await new Promise((r) => setTimeout(r, 200));
  }
}

test("the extension client drives the real bridge: auth, schema refusals, and a grounded failure", async (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "hive-bridge-int-"));
  fs.mkdirSync(path.join(root, "src"));
  fs.writeFileSync(path.join(root, "src", "app.py"), "def add(a, b):\n    return a + b\n");

  const { proc, ready, stderr } = startBridge(root);
  t.after(() => { if (proc.exitCode === null) proc.kill(); });
  const info = await ready;
  const conn = readBridgeConnection(root, (p) => fs.readFileSync(p, "utf8"));
  assert.ok(conn, "the bridge wrote its endpoint and token");
  assert.equal(conn.port, info.port);
  const client = createBridgeClient({ ...conn, workspace: root });

  // Auth: a wrong token is refused before any runner call.
  const wrong = createBridgeClient({ ...conn, token: "wrong", workspace: root });
  assert.equal((await wrong.approval()).status, 401, stderr.join(""));

  // Authorized, nothing pending.
  const approval = await client.approval();
  assert.equal(approval.status, 200);
  assert.deepEqual(approval.body, { pending: false });

  // R18 refusals come back as structured 400s and create no task.
  const noId = await client.submit({ instruction: "hello", clientRequestId: "" });
  assert.equal(noId.status, 400);
  assert.equal(noId.body.error, "missing_client_request_id");
  const escape = await client.submit({ instruction: "hi", clientRequestId: "int-esc", filePath: "../escape.txt" });
  assert.equal(escape.status, 400);
  assert.equal(escape.body.error, "path_outside_workspace");
  const badMode = await client.submit({ instruction: "hi", clientRequestId: "int-mode", mode: "yolo" });
  assert.equal(badMode.body.error, "invalid_mode");

  // A valid submit reaches the runner. The agent binary is missing, so the task must end as a
  // recorded failure with the reason. It must not report completed.
  const submit = await client.submit({ instruction: "explain add", clientRequestId: "int-ok", filePath: "src/app.py" });
  assert.equal(submit.status, 200, JSON.stringify(submit.body));
  assert.ok(submit.body.task_id, "a valid submit issues a task_id");
  assert.ok(submit.body.context_snapshot_id, "the submit returns the snapshot the task is bound to");

  const task = await pollTask(client, submit.body.task_id, submit.body.context_snapshot_id, 30000);
  assert.equal(task.state, "failed", stderr.join(""));
  assert.match(task.reason, /coding_unavailable/);
  assert.equal(task.tests_status, "not_run");

  // Binding: a snapshot id that is not the task's is refused.
  const mismatch = await client.task(submit.body.task_id, "ctx_not_this_one");
  assert.equal(mismatch.status, 409);

  // Stop: closing stdin is the clean stop; the bridge removes its token and endpoint.
  proc.stdin.end();
  assert.equal(await waitExit(proc, 20000), 0, stderr.join(""));
  assert.equal(fs.existsSync(path.join(root, ".hive", "voice-bot", "bridge-token")), false);
  assert.equal(fs.existsSync(path.join(root, ".hive", "voice-bot", "bridge.json")), false);
});

test("a real approve and a real deny go through the extension reply logic into the fixture agent", async (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "hive-bridge-approval-int-"));
  fs.mkdirSync(path.join(root, "src"));
  fs.writeFileSync(path.join(root, "src", "app.py"), "def add(a, b):\n    return a + b\n");

  // Second bridge: same production CLI, but the agent is the ACP fixture that asks for permission.
  const { proc, ready, stderr } = startBridge(root, writeFixtureAgent(root));
  t.after(() => { if (proc.exitCode === null) proc.kill(); });
  const info = await ready;
  const conn = readBridgeConnection(root, (p) => fs.readFileSync(p, "utf8"));
  assert.ok(conn, "the bridge wrote its endpoint and token");
  assert.equal(conn.port, info.port);
  const client = createBridgeClient({ ...conn, workspace: root });
  // The UI answers are scripted here; the reply itself goes through the extension's own logic.
  const ui = (answer) => ({ showPrompt: async () => answer, askQuestion: async () => null });

  // Approve: the fixture's permission request is answered "approve" and the provider sees "selected".
  const approveSubmit = await client.submit({
    instruction: "NEEDS_APPROVAL:edit src/app.py", clientRequestId: "int-approve",
  });
  assert.equal(approveSubmit.status, 200, JSON.stringify(approveSubmit.body));
  const approvePending = await waitForPending(client, 30000);
  assert.equal(approvePending.task_id, approveSubmit.body.task_id);
  assert.equal(approvePending.kind, "write_or_command");
  assert.equal(approvePending.action, "edit src/app.py");

  const approveReply = await answerPendingApproval(client, approvePending, ui("approve"));
  assert.equal(approveReply.status, 200, JSON.stringify(approveReply.body));
  assert.equal(approveReply.body.status, "approved");
  const approved = await pollTask(client, approveSubmit.body.task_id, approveSubmit.body.context_snapshot_id, 30000);
  assert.equal(approved.state, "completed", stderr.join(""));
  assert.equal(approved.tests_status, "not_run");
  assert.match(approved.written, /"outcome": "selected"/);
  assert.match(approved.written, /"optionId": "allow"/);

  // Deny: the same path with "deny"; the provider sees "cancelled" and nothing is selected.
  const denySubmit = await client.submit({
    instruction: "NEEDS_APPROVAL:delete build dir", clientRequestId: "int-deny",
  });
  assert.equal(denySubmit.status, 200, JSON.stringify(denySubmit.body));
  const denyPending = await waitForPending(client, 30000);
  assert.equal(denyPending.task_id, denySubmit.body.task_id);
  assert.equal(denyPending.action, "delete build dir");

  const denyReply = await answerPendingApproval(client, denyPending, ui("deny"));
  assert.equal(denyReply.status, 200, JSON.stringify(denyReply.body));
  assert.equal(denyReply.body.status, "denied");
  const denied = await pollTask(client, denySubmit.body.task_id, denySubmit.body.context_snapshot_id, 30000);
  assert.equal(denied.state, "completed", stderr.join(""));
  assert.match(denied.written, /"outcome": "cancelled"/);
  assert.doesNotMatch(denied.written, /"optionId": "allow"/);

  // Nothing is left pending, and the bridge stops cleanly.
  assert.deepEqual((await client.approval()).body, { pending: false });
  proc.stdin.end();
  assert.equal(await waitExit(proc, 20000), 0, stderr.join(""));
});
