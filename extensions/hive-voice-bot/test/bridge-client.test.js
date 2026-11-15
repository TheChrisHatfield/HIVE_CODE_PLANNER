// Bridge client unit tests (T017 host side). The fetch is a fake that records each request,
// so these tests check the exact URL, bearer token, and bound workspace the client sends.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const {
  APPROVAL_OUTCOMES,
  readBridgeConnection,
  parseReadyLine,
  createBridgeClient,
  decisionForOutcome,
  approvalReplyText,
} = require("../src/core");

const ROOT = path.resolve("/repo/project");

function fakeFiles(files) {
  return (p) => {
    if (!(p in files)) throw new Error(`ENOENT ${p}`);
    return files[p];
  };
}

function recordingFetch(reply) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    return {
      status: reply.status,
      json: async () => reply.body,
    };
  };
  return { calls, fetchImpl };
}

test("readBridgeConnection reads host, port, and token the bridge wrote", () => {
  const endpoint = path.join(ROOT, ".hive", "voice-bot", "bridge.json");
  const token = path.join(ROOT, ".hive", "voice-bot", "bridge-token");
  const conn = readBridgeConnection(ROOT, fakeFiles({
    [endpoint]: JSON.stringify({ host: "127.0.0.1", port: 5123, started_at: "x" }),
    [token]: "tok-abc",
  }));
  assert.deepEqual(conn, { host: "127.0.0.1", port: 5123, token: "tok-abc" });
});

test("readBridgeConnection is null when the endpoint or token is missing or malformed", () => {
  const endpoint = path.join(ROOT, ".hive", "voice-bot", "bridge.json");
  const token = path.join(ROOT, ".hive", "voice-bot", "bridge-token");
  assert.equal(readBridgeConnection(ROOT, fakeFiles({})), null);
  assert.equal(readBridgeConnection(ROOT, fakeFiles({ [endpoint]: "{not json" })), null);
  assert.equal(readBridgeConnection(ROOT, fakeFiles({
    [endpoint]: JSON.stringify({ host: "127.0.0.1", port: 5123 }),
  })), null);
  assert.equal(readBridgeConnection(ROOT, fakeFiles({
    [endpoint]: JSON.stringify({ host: "127.0.0.1", port: 5123 }),
    [token]: "   ",
  })), null);
});

test("parseReadyLine accepts the ready record and rejects anything else", () => {
  assert.deepEqual(
    parseReadyLine(JSON.stringify({ ok: true, host: "127.0.0.1", port: 9000, token_file: "x" })),
    { host: "127.0.0.1", port: 9000 },
  );
  assert.throws(() => parseReadyLine("Traceback (most recent call last):"), /unparsable/);
  assert.throws(() => parseReadyLine(JSON.stringify({ ok: false })), /did not report ready/);
  assert.throws(() => parseReadyLine(JSON.stringify({ ok: true, host: "127.0.0.1" })), /did not report ready/);
});

test("every request carries the bearer token and the bound workspace", async () => {
  const { calls, fetchImpl } = recordingFetch({ status: 200, body: { pending: false } });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  const { status, body } = await client.approval();
  assert.equal(status, 200);
  assert.deepEqual(body, { pending: false });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init.method, "GET");
  assert.equal(calls[0].init.headers.Authorization, "Bearer tok-1");
  const url = new URL(calls[0].url);
  assert.equal(url.pathname, "/v1/approval");
  assert.equal(url.searchParams.get("workspace"), ROOT);
});

test("submit posts the R18 fields with the workspace and the client request id", async () => {
  const { calls, fetchImpl } = recordingFetch({ status: 200, body: { task_id: "task_1" } });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  await client.submit({ instruction: "explain add", clientRequestId: "cr-1", filePath: "src/app.py" });
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.headers["Content-Type"], "application/json");
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    workspace: ROOT,
    instruction: "explain add",
    client_request_id: "cr-1",
    mode: "ask",
    file_path: "src/app.py",
    selection_text: "",
    file_content: "",
  });
});

test("submit posts the T007 editor snapshot when the host captured one", async () => {
  const { calls, fetchImpl } = recordingFetch({ status: 200, body: { task_id: "task_2" } });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  const editorSnapshot = {
    file: "src/app.py",
    document_version: 3,
    dirty: false,
    selection: { text: "def add(a, b):" },
    diagnostics: [{ severity: "error", message: "oops" }],
  };
  await client.submit({
    instruction: "explain add",
    clientRequestId: "cr-2",
    filePath: "src/app.py",
    editorSnapshot,
  });
  const posted = JSON.parse(calls[0].init.body);
  assert.deepEqual(posted.editor_snapshot, editorSnapshot);
  assert.equal(posted.file_path, "src/app.py");
});

test("submitSpoken posts the WAV path, client request id, and workspace to /v1/submit/spoken (C3)", async () => {
  const { calls, fetchImpl } = recordingFetch({ status: 200, body: { task_id: "task_3" } });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  const editorSnapshot = { file: "src/app.py", document_version: 2, dirty: false };
  const res = await client.submitSpoken({
    wavPath: "audio/clip.wav",
    clientRequestId: "cr-spoken-1",
    filePath: "src/app.py",
    editorSnapshot,
  });
  assert.equal(res.status, 200);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.headers.Authorization, "Bearer tok-1");
  assert.equal(new URL(calls[0].url).pathname, "/v1/submit/spoken");
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    workspace: ROOT,
    wav_path: "audio/clip.wav",
    client_request_id: "cr-spoken-1",
    mode: "ask",
    file_path: "src/app.py",
    editor_snapshot: editorSnapshot,
  });
});

test("task and submission lookups bind the task, the snapshot, and the workspace", async () => {
  const { calls, fetchImpl } = recordingFetch({ status: 200, body: {} });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  await client.task("task_1", "ctx_9");
  await client.submission("cr-2");
  const task = new URL(calls[0].url);
  assert.equal(task.pathname, "/v1/task");
  assert.equal(task.searchParams.get("task_id"), "task_1");
  assert.equal(task.searchParams.get("context_snapshot_id"), "ctx_9");
  assert.equal(task.searchParams.get("workspace"), ROOT);
  const sub = new URL(calls[1].url);
  assert.equal(sub.pathname, "/v1/submission");
  assert.equal(sub.searchParams.get("client_request_id"), "cr-2");
});

test("a missing query value is omitted, never sent as the string 'undefined'", async () => {
  const { calls, fetchImpl } = recordingFetch({ status: 200, body: {} });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  // A submit reply without context_snapshot_id hands the poll an undefined id.
  await client.task("task_1", undefined);
  const url = new URL(calls[0].url);
  assert.equal(url.searchParams.get("task_id"), "task_1");
  assert.equal(url.searchParams.has("context_snapshot_id"), false);
  assert.equal(url.searchParams.get("workspace"), ROOT);
  assert.ok(!calls[0].url.includes("undefined"));
});

test("editor poll and ack bind workspace and action id", async () => {
  const { calls, fetchImpl } = recordingFetch({ status: 200, body: { pending: true, action_id: "ed_1" } });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  await client.editor();
  await client.ackEditor("ed_1");
  const get = new URL(calls[0].url);
  assert.equal(get.pathname, "/v1/editor");
  assert.equal(get.searchParams.get("workspace"), ROOT);
  assert.equal(calls[1].init.method, "POST");
  assert.deepEqual(JSON.parse(calls[1].init.body), { workspace: ROOT, action_id: "ed_1" });
});

test("live buffer feed posts the file, document version, and dirty flag (T029)", async () => {
  const { calls, fetchImpl } = recordingFetch({ status: 200, body: { status: "recorded" } });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  const res = await client.liveBuffer({ filePath: "src/app.py", documentVersion: 8, dirty: true });
  assert.equal(res.status, 200);
  assert.equal(calls[0].init.method, "POST");
  assert.equal(new URL(calls[0].url).pathname, "/v1/live");
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    workspace: ROOT, file_path: "src/app.py", document_version: 8, dirty: true,
  });
});

test("interrupt and end-call post to their bridge routes with the bound workspace (T031)", async () => {
  const { calls, fetchImpl } = recordingFetch({ status: 200, body: { session_state: "interrupted" } });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  const interrupted = await client.interruptPlayback();
  const ended = await client.endCall();
  assert.equal(interrupted.body.session_state, "interrupted");
  assert.equal(ended.status, 200);
  assert.equal(calls[0].init.method, "POST");
  assert.equal(new URL(calls[0].url).pathname, "/v1/playback/interrupt");
  assert.equal(calls[0].init.headers.Authorization, "Bearer tok-1");
  assert.deepEqual(JSON.parse(calls[0].init.body), { workspace: ROOT });
  assert.equal(calls[1].init.method, "POST");
  assert.equal(new URL(calls[1].url).pathname, "/v1/call/end");
  assert.equal(calls[1].init.headers.Authorization, "Bearer tok-1");
  assert.deepEqual(JSON.parse(calls[1].init.body), { workspace: ROOT });
});

test("reply sends the request id, the task id, and the exact approval text", async () => {
  const { calls, fetchImpl } = recordingFetch({ status: 200, body: { status: "approved" } });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  const out = await client.reply({
    requestId: "apr_1", taskId: "task_1", text: approvalReplyText("approve", "edit src/app.py"),
  });
  assert.equal(out.body.status, "approved");
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    workspace: ROOT, request_id: "apr_1", task_id: "task_1", text: "approve edit src/app.py",
  });
});

test("reply posts the live editor snapshot captured at approval time (R22)", async () => {
  const { calls, fetchImpl } = recordingFetch({ status: 200, body: { status: "approved" } });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  const editorSnapshot = { file: "src/app.py", document_version: 9, dirty: true };
  await client.reply({
    requestId: "apr_2", taskId: "task_2", text: "approve edit src/app.py", editorSnapshot,
  });
  assert.deepEqual(JSON.parse(calls[0].init.body).editor_snapshot, editorSnapshot);
});

test("a non-JSON reply body becomes an empty object rather than a thrown error", async () => {
  const fetchImpl = async () => ({ status: 500, json: async () => { throw new Error("html"); } });
  const client = createBridgeClient({
    host: "127.0.0.1", port: 9000, token: "tok-1", workspace: ROOT, fetchImpl,
  });
  assert.deepEqual(await client.approval(), { status: 500, body: {} });
});

test("only an explicit approve or deny outcome becomes a reply; a timeout sends nothing (R6)", () => {
  assert.equal(decisionForOutcome(APPROVAL_OUTCOMES.APPROVED), "approve");
  assert.equal(decisionForOutcome(APPROVAL_OUTCOMES.DENIED), "deny");
  assert.equal(decisionForOutcome(APPROVAL_OUTCOMES.TIMED_OUT), null);
  assert.throws(() => approvalReplyText("maybe", "edit"), /approve or deny/);
});
