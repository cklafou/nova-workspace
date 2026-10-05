// @nova: Verify dockable voice calls, device settings and honest turn/playback rendering using a fake DOM and API without audio or Nova.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {test} = require("node:test");
const source = fs.readFileSync(path.join(__dirname, "../static/voice.js"), "utf8");

class Element {
  constructor(tag, id = "") {
    Object.assign(this, {tagName: tag, id, children: [], attrs: {}, events: {}, dataset: {},
      textContent: "", value: "", disabled: false, hidden: false});
  }
  append(...nodes) { for (const node of nodes) {node.parentElement = this; this.children.push(node);} }
  insertBefore(node, next) {
    node.parentElement = this;
    const index = this.children.indexOf(next);
    this.children.splice(index < 0 ? this.children.length : index, 0, node);
  }
  replaceChildren(...nodes) {this.children = []; this.append(...nodes);}
  setAttribute(name, value) {this.attrs[name] = value;}
  addEventListener(name, callback) {(this.events[name] ||= []).push(callback);}
  async click() {if (!this.disabled && !this.hidden) for (const callback of this.events.click || []) await callback();}
  change(value) {this.value = String(value); for (const callback of this.events.change || []) callback();}
}
const settle = async () => {for (let i = 0; i < 25; i++) await Promise.resolve();};
const deferred = () => {let resolve; return {promise: new Promise(r => resolve = r), resolve};};
const baseStatus = () => ({running: false, state: "off", available: true, reason: "", error: "",
  microphone_muted: false, output_muted: false,
  capabilities: {microphone_mute: true, output_mute: true, microphone_test: true, speaker_test: true},
  settings: {input_device: -1, output_device: -1}, last_caption: null, last_transcript: ""});
function fixture(options = {}) {
  const body = new Element("body"), chat = new Element("div", "chat-main");
  const composer = new Element("div", "input-area");
  composer.value = "unsent draft";
  const host = new Element("div", "voice-host");
  body.append(chat, host); chat.append(composer);
  const events = {}, calls = [], timers = [];
  const find = (id, root = body) => root.id === id ? root : root.children.map(n => find(id, n)).find(Boolean);
  const f = {status: {...baseStatus(), ...options.status}, statusCode: options.statusCode || 200,
    down: false, calls, chat, composer, host, timers, find, post: null, pendingGet: null,
    devices: {inputs: [{id: 2, name: "USB microphone", default: true}],
      outputs: [{id: 3, name: "Headphones", default: true}]}};
  const context = {
    document: {readyState: "loading", createElement: tag => new Element(tag), getElementById: find,
      addEventListener() {}},
    AbortSignal: {timeout: () => ({})},
    setTimeout: (callback, delay) => {timers.push({callback, delay}); return timers.length;},
    clearTimeout() {},
    fetch: async (url, request) => {
      calls.push({url, ...request});
      if (f.down) throw Error("Fixture disconnected");
      let data, code = 200;
      if (url === "/api/voice/status") {
        if (f.pendingGet) return await f.pendingGet;
        data = f.status; code = f.statusCode;
      } else if (url === "/api/voice/devices") data = f.devices;
      else {
        assert.equal(request.method, "POST");
        assert.ok(f.post, "Unexpected mutation: " + url);
        const result = await f.post(url, JSON.parse(request.body));
        data = result.data; code = result.code ?? 200;
      }
      return {ok: code < 400, status: code, json: async () => data};
    }
  };
  context.window = {
    novaLifecycleState: options.lifecycle || {state: "on", pending: false},
    addEventListener: (name, callback) => (events[name] ||= []).push(callback),
    removeEventListener: (name, callback) => {events[name] = (events[name] || []).filter(item => item !== callback);}
  };
  vm.createContext(context); vm.runInContext(source, context);
  f.context = context;
  assert.equal(calls.length, 0, "Module evaluation alone performs no audio/status requests");
  f.ui = context.window.mountNovaVoice(host);
  f.controls = f.ui.controls;
  f.lifecycle = state => {for (const callback of events["nova:lifecycle"] || []) callback({detail: state});};
  return f;
}
const posts = f => f.calls.filter(call => call.method === "POST");

test("mounts only in the Voice widget and performs status-only reads", async () => {
  const f = fixture(); await settle();
  assert.equal(f.host.children[0], f.ui.root);
  assert.deepEqual(f.chat.children, [f.composer], "Conversation is untouched");
  assert.equal(f.composer.value, "unsent draft");
  assert.deepEqual(f.calls.map(call => [call.url, call.method]), [["/api/voice/status", "GET"]]);
  assert.equal(f.controls.toggle.textContent, "Call Nova");
  assert.equal(f.controls.toggle.disabled, false);
  assert.equal(f.controls.stateText.attrs["role"], "status");
  assert.equal(f.controls.inputDevice.attrs["aria-label"], "Microphone");
  assert.equal(f.context.window.mountNovaVoice(f.host), f.ui, "Remount reuses one UI and poller");
  assert.equal(f.controls.details.children[0].textContent, "Settings & tests");
  assert.ok(!f.controls.details.open && !f.controls.conversation.open, "Secondary panels start collapsed");
  f.ui.destroy();
});

test("Nova-off gates voice start, but explicit audio tests remain available and stoppable", async () => {
  const f = fixture({lifecycle: {state: "off", chat_only: true}}); await settle();
  assert.equal(f.controls.toggle.disabled, true);
  assert.equal(f.controls.testMic.disabled, false);
  f.post = async (url, body) => {
    assert.equal(url, "/api/voice/test"); assert.deepEqual(body, {kind: "microphone"});
    return {data: {...baseStatus(), state: "testing", test_result: {kind: "microphone", state: "running", message: "Listening to test clip"}}};
  };
  await f.controls.testMic.click(); await settle();
  assert.equal(f.controls.toggle.textContent, "Stop test");
  assert.equal(f.controls.toggle.disabled, false);
  assert.match(f.controls.testResult.textContent, /test clip/);
  assert.equal(f.controls.microphone.disabled, true);
  assert.equal(f.controls.output.disabled, true);
  f.post = async (url, body) => {assert.equal(url, "/api/voice/stop"); assert.deepEqual(body, {}); return {data: baseStatus()};};
  await f.controls.toggle.click(); await settle();
  assert.equal(posts(f).length, 2);
  f.ui.destroy();
});

test("explicit start avoids duplicate requests and uses server state on reload", async () => {
  const f = fixture(); await settle();
  const pending = deferred(); f.post = () => pending.promise;
  await f.controls.toggle.click(); await settle();
  assert.equal(f.controls.toggle.disabled, true);
  await f.controls.toggle.click();
  assert.equal(posts(f).length, 1);
  assert.equal(posts(f)[0].url, "/api/voice/start");
  pending.resolve({data: {...baseStatus(), running: true, state: "listening"}}); await settle();
  assert.equal(f.controls.stateText.textContent, "Listening");
  assert.equal(f.controls.toggle.textContent, "End call");
  const reopened = fixture({status: {running: true, state: "listening", output_muted: true}}); await settle();
  assert.equal(posts(reopened).length, 0);
  assert.equal(reopened.controls.output.textContent, "Unmute speaker");
  f.ui.destroy(); reopened.ui.destroy();
});

test("microphone/output mute have distinct payloads and accurate pressed state", async () => {
  const f = fixture({status: {running: true, state: "listening"}}); await settle();
  f.post = async (url, body) => {
    assert.equal(url, "/api/voice/mute");
    assert.deepEqual(body, {microphone: true});
    return {data: {...baseStatus(), running: true, state: "listening", microphone_muted: true}};
  };
  await f.controls.microphone.click(); await settle();
  assert.equal(f.controls.microphone.attrs["aria-pressed"], "true");
  assert.equal(f.controls.microphone.textContent, "Unmute mic");
  f.post = async (url, body) => {
    assert.deepEqual(body, {output: true});
    return {data: {...baseStatus(), running: true, state: "listening", output_muted: true}};
  };
  await f.controls.output.click(); await settle();
  assert.equal(f.controls.output.attrs["aria-pressed"], "true");
  f.ui.destroy();
});

test("device discovery is explicit and unapplied choices survive polling", async () => {
  const f = fixture(); await settle();
  assert.equal(f.calls.some(call => call.url.endsWith("/devices")), false);
  await f.controls.findDevices.click(); await settle();
  assert.equal(f.controls.inputDevice.children[1].textContent, "USB microphone (default)");
  f.controls.inputDevice.change(2); f.controls.outputDevice.change(3);
  await f.ui.refresh();
  assert.equal(f.controls.inputDevice.value, "2");
  assert.equal(f.controls.testSpeaker.disabled, true, "Tests must not silently use old device settings");
  f.post = async (url, body) => {
    assert.equal(url, "/api/voice/config"); assert.deepEqual(body, {input_device: 2, output_device: 3});
    return {data: {...baseStatus(), settings: body}};
  };
  await f.controls.applyDevices.click(); await settle();
  assert.equal(f.controls.applyDevices.disabled, true);
  assert.equal(f.controls.testSpeaker.disabled, false);
  f.ui.destroy();
});

test("active voice disables device changes and test collisions", async () => {
  const f = fixture({status: {running: true, state: "speaking"}}); await settle();
  assert.equal(f.controls.inputDevice.disabled, true);
  assert.equal(f.controls.testMic.disabled, true);
  assert.equal(f.controls.testSpeaker.disabled, true);
  assert.equal(f.controls.toggle.disabled, false);
  f.ui.destroy();
});

test("missing backend/capabilities never expose fake working actions", async () => {
  const old = fixture({statusCode: 404}); await settle();
  assert.equal(old.controls.toggle.disabled, true);
  assert.match(old.controls.notice.textContent, /Restart Nova Chat/);
  const unsupported = fixture({status: {available: false, reason: "Install microphone dependencies", capabilities: {}}}); await settle();
  assert.equal(unsupported.controls.microphone.hidden, true);
  assert.equal(unsupported.controls.testSpeaker.disabled, true);
  assert.match(unsupported.controls.notice.textContent, /dependencies/);
  old.ui.destroy(); unsupported.ui.destroy();
});

test("network loss preserves active uncertainty and recovery clears transport error", async () => {
  const f = fixture({status: {running: true, state: "listening"}}); await settle();
  f.down = true; await f.ui.refresh();
  assert.equal(f.controls.stateText.textContent, "Status unavailable");
  assert.equal(f.controls.toggle.textContent, "End call");
  assert.equal(f.controls.toggle.disabled, false, "An uncertain active service still needs its stop action");
  assert.equal(f.controls.microphone.disabled, true);
  f.down = false; await f.ui.refresh();
  assert.equal(f.controls.notice.textContent, "");
  assert.equal(f.controls.stateText.textContent, "Listening");
  f.ui.destroy();
});

test("action errors remain actionable and a successful retry clears them", async () => {
  const f = fixture(); await settle();
  f.post = async () => ({code: 409, data: {detail: "Stop the microphone test first"}});
  await f.controls.toggle.click(); await settle();
  assert.match(f.controls.notice.textContent, /microphone test first/);
  assert.equal(f.controls.toggle.disabled, false);
  f.post = async () => ({data: {...baseStatus(), running: true, state: "listening"}});
  await f.controls.toggle.click(); await settle();
  assert.equal(f.controls.notice.textContent, "");
  f.ui.destroy();
});

test("late pre-action status cannot overwrite accepted mutation state", async () => {
  const f = fixture(); await settle();
  const pending = deferred(); f.pendingGet = pending.promise;
  const refreshing = f.ui.refresh();
  f.post = async () => ({data: {...baseStatus(), running: true, state: "speaking"}});
  await f.controls.toggle.click(); await settle();
  pending.resolve({ok: true, status: 200, json: async () => baseStatus()}); await refreshing;
  assert.equal(f.controls.stateText.textContent, "Speaking");
  f.ui.destroy();
});

test("captions/audit and measured test results render as text, never HTML", async () => {
  const f = fixture({status: {last_caption: {text: "<img onerror=bad>", audit: {status: "INCOMPLETE", reason: "Evidence missing"}},
    last_transcript: "<script>human text</script>", test_result: {kind: "microphone", state: "done",
      message: "Captured test", peak: 0.125, rms: 0.05, transcript: "Test words"}}}); await settle();
  assert.equal(f.controls.captionText.textContent, "<img onerror=bad>");
  assert.equal(f.controls.captionText.children.length, 0);
  assert.equal(f.controls.audit.textContent, "Audit: INCOMPLETE");
  assert.equal(f.controls.audit.title, "Evidence missing");
  assert.match(f.controls.testResult.textContent, /Peak: 0.125/);
  assert.match(f.controls.testResult.textContent, /Heard: Test words/);
  f.status.last_caption.audit = null; await f.ui.refresh();
  assert.equal(f.controls.audit.textContent, "Audit: NOT_RUN");
  f.ui.destroy();
});

test("lifecycle events update start gating without triggering voice", async () => {
  const f = fixture({lifecycle: {state: "off"}}); await settle();
  f.lifecycle({state: "starting", pending: true}); assert.equal(f.controls.toggle.disabled, true);
  f.lifecycle({state: "on", pending: false}); assert.equal(f.controls.toggle.disabled, false);
  assert.equal(posts(f).length, 0);
  f.ui.destroy();
});


test("voice widget remount/popout lifecycle cannot start or stop the shared call", async () => {
  const f = fixture({status: {running: true, state: "listening"}}); await settle();
  const original = f.ui.root;
  const dock = new Element("div"); dock.append(f.host);
  assert.equal(f.ui.root, original, "Dock movement preserves controls and state");
  f.ui.destroy();
  await f.ui.refresh();
  assert.equal(posts(f).length, 0, "Closing the UI does not silently end audio");
  const reopened = f.context.window.mountNovaVoice(f.host); await settle();
  assert.notEqual(reopened, f.ui);
  assert.equal(f.host.children.length, 1);
  assert.equal(reopened.controls.toggle.textContent, "End call");
  assert.equal(posts(f).length, 0, "A new popout reads the existing call rather than creating another");
  reopened.destroy();
});

test("delayed turns, omitted speech and request IDs remain visible without pretending to speak", async () => {
  const f = fixture({status: {running: true, state: "waiting", last_turn: {phase: "delayed", request_id: "r2", message_id: "m2", run_id: "run2", elapsed_s: 312.8}}}); await settle();
  assert.equal(f.controls.stateText.textContent, "Waiting for Nova");
  assert.match(f.controls.delivery.textContent, /still waiting/);
  assert.match(f.controls.trace.textContent, /request_id: r2/);
  assert.match(f.controls.trace.textContent, /elapsed_s: 312.8/);
  f.status.last_turn = {...f.status.last_turn, phase: "end", eligible: false, delivery: "suppressed", why: "Witness audit incomplete"};
  f.status.state = "listening";
  await f.ui.refresh();
  assert.match(f.controls.delivery.textContent, /Reply was not spoken: Witness audit incomplete/);
  assert.equal(f.controls.stateText.textContent, "Listening");
  f.ui.destroy();
});

test("playback failures never show a speaking indicator; older output cannot replace current turn", async () => {
  const f = fixture({status: {running: true, state: "speaking", last_turn: {phase: "end", request_id: "r1", eligible: true},
    last_playback: {phase: "end", request_id: "r1", outcome: "error", clock: "playback"}}}); await settle();
  assert.equal(f.ui.root.dataset.state, "error");
  assert.equal(f.controls.stateText.textContent, "Needs attention");
  assert.equal(f.controls.delivery.textContent, "Spoken output failed");
  f.status.last_playback = {phase: "requested", request_id: "r1"}; await f.ui.refresh();
  assert.equal(f.controls.stateText.textContent, "Preparing speech");
  f.status.last_playback = {phase: "start", request_id: "r1", clock: "process"}; await f.ui.refresh();
  assert.equal(f.controls.stateText.textContent, "Output requested");
  f.status.last_playback = {phase: "start", request_id: "r1", clock: "playback"}; await f.ui.refresh();
  assert.equal(f.controls.stateText.textContent, "Speaking");
  assert.equal(f.controls.delivery.textContent, "Audio sent to the selected output");
  f.status.state = "thinking"; f.status.last_turn = {phase: "started", request_id: "r2"}; await f.ui.refresh();
  assert.equal(f.controls.stateText.textContent, "Nova is thinking");
  assert.equal(f.controls.delivery.hidden, true);
  f.ui.destroy();
});

test("hearing and recognition are reported only from real service states", async () => {
  const f = fixture({status: {running: true, state: "hearing"}}); await settle();
  assert.equal(f.controls.stateText.textContent, "Hearing you");
  f.status.state = "recognizing"; await f.ui.refresh();
  assert.equal(f.controls.stateText.textContent, "Recognizing speech");
  f.status.state = "transcribing"; await f.ui.refresh();
  assert.equal(f.controls.stateText.textContent, "Recognizing speech");
  assert.equal(f.ui.root.dataset.state, "transcribing");
  assert.match(f.controls.hint.textContent, /Turning your words/);
  assert.equal(posts(f).length, 0);
  f.ui.destroy();
});
