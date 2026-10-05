/* @nova: Verify Conversation power controls, launcher reconnects and draft-preserving mode changes without running Nova or touching the desktop. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(
  path.join(__dirname, "../static/conversation-power.js"),
  "utf8",
);
const draftKey = "nova.conversation.lifecycle-draft.v1";
class Element {
  constructor(tag, id = "") {
    Object.assign(this, {
      tagName: tag,
      id,
      children: [],
      events: {},
      attrs: {},
      dataset: {},
      value: "",
      disabled: false,
      textContent: "",
    });
  }
  append(...nodes) {
    for (const node of nodes) {
      node.parentElement = this;
      this.children.push(node);
    }
  }
  prepend(node) {
    node.parentElement = this;
    this.children.unshift(node);
  }
  insertBefore(node, next) {
    node.parentElement = this;
    const index = this.children.indexOf(next);
    this.children.splice(index < 0 ? this.children.length : index, 0, node);
  }
  get nextSibling() {
    return (
      this.parentElement?.children[
        this.parentElement.children.indexOf(this) + 1
      ] || null
    );
  }
  setAttribute(key, value) {
    this.attrs[key] = value;
  }
  addEventListener(name, callback) {
    (this.events[name] ||= []).push(callback);
  }
  async click() {
    if (!this.disabled)
      for (const callback of this.events.click || []) await callback();
  }
  setSelectionRange(start, end) {
    this.selectionStart = start;
    this.selectionEnd = end;
  }
}
const settle = async () => {
  for (let i = 0; i < 16; i++) await Promise.resolve();
};
function fixture(options = {}) {
  const body = new Element("body"),
    chat = new Element("div", "chat-main"),
    tabs = new Element("div", "session-tabs"),
    input = new Element("textarea", "input");
  body.append(chat);
  const controls = new Element("div", "conversation-controls");
  chat.append(tabs, input, controls);
  for (const id of [
    "llama-start-btn",
    "llama-stop-btn",
    "pb-auto",
    "pb-wake",
    "reinject-btn",
  ])
    chat.append(new Element("button", id));
  const find = (id, root = body) =>
    root.id === id
      ? root
      : root.children.map((node) => find(id, node)).find(Boolean) || null;
  const calls = [],
    storage = options.storage || new Map(),
    timers = [],
    events = {};
  const f = {
    chatOnly: options.chatOnly ?? true,
    status: options.status || {
      ok: true,
      state: "off",
      pending: false,
      target: null,
      chat_only: true,
      available: true,
      message: "Nova is off",
    },
    statusCode: 200,
    networkDown: false,
    post: null,
    reloads: 0,
    storageFailure: false,
    calls,
    storage,
    timers,
    input,
    chat,
    controls,
    tabs,
    find,
  };
  const context = {
    document: {
      readyState: "loading",
      createElement: (tag) => new Element(tag),
      getElementById: find,
      addEventListener() {},
    },
    sessionStorage: {
      getItem: (key) => storage.get(key) || null,
      setItem: (key, value) => {
        if (f.storageFailure) throw Error("Quota exceeded");
        storage.set(key, value);
      },
      removeItem: (key) => storage.delete(key),
    },
    fetch: async (url, request) => {
      calls.push({ url, ...request });
      if (f.networkDown || (f.versionDown && url === "/api/version"))
        throw Error("Worker reconnecting");
      let data,
        code = 200;
      if (url === "/api/version") data = { chat_only: f.chatOnly };
      else if (url === "/api/nova/lifecycle") {
        data = f.status;
        code = f.statusCode;
      } else if (
        request.method === "POST" &&
        ["/api/nova/start", "/api/nova/stop"].includes(url)
      ) {
        assert.equal(request.body, "{}");
        const result = await f.post(url);
        data = result.data;
        code = result.code ?? 202;
      } else throw Error("Unexpected route: " + url);
      return { ok: code < 400, status: code, json: async () => data };
    },
    AbortSignal: { timeout: () => ({}) },
    setTimeout: (fn, delay) => {
      timers.push({ fn, delay });
      return timers.length;
    },
    clearTimeout() {},
    CustomEvent: class {
      constructor(type, args) {
        this.type = type;
        this.detail = args.detail;
      }
    },
    pendingImages: [],
    _mentionedFiles: [],
  };
  context.window = {
    addEventListener: (name, callback) => (events[name] ||= []).push(callback),
    dispatchEvent: (event) =>
      (events[event.type] || []).forEach((fn) => fn(event)),
    location: { reload: () => f.reloads++ },
    addPending: (dataUrl) => context.pendingImages.push({ dataUrl }),
    renderFileChips() {},
    autoResize() {},
    pollServices() {},
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  f.context = context;
  f.ui = context.window.initNovaConversationPower();
  return f;
}
(async () => {
  const f = fixture();
  await settle();
  assert.equal(f.ui.button.attrs["aria-label"], "Start Nova");
  assert.equal(
    f.ui.button.disabled,
    false,
    "Chat-only must still offer genuine Start Nova",
  );
  assert.equal(
    f.controls.children[0].className,
    "nc-conversation-power",
    "Power lives inline in the composer controls rather than a Conversation banner",
  );
  assert.equal(f.ui.button.textContent, "⏻", "Only the compact power icon is visible");
  assert.match(f.ui.button.title, /Start Nova.*Nova is off/);
  assert.equal(f.ui.button.attrs["aria-describedby"], f.ui.detail.id);
  assert.equal(f.ui.detail.attrs["role"], "status");
  assert.ok(
    f.calls.every((call) => call.method === "GET"),
    "Opening Conversation never starts Nova",
  );
  assert.equal(
    f.context.window.initNovaConversationPower(),
    null,
    "Repeated init must not duplicate controls or pollers",
  );
  let release;
  f.post = () =>
    new Promise((resolve) => {
      release = resolve;
    });
  const click = f.ui.button.click();
  await settle();
  assert.equal(f.ui.button.attrs["aria-label"], "Starting Nova…");
  assert.equal(f.find("pb-auto").disabled, true);
  assert.equal(f.find("llama-start-btn").disabled, true);
  await f.ui.button.click();
  assert.equal(
    f.calls.filter((call) => call.method === "POST").length,
    1,
    "Double-click cannot duplicate transition",
  );
  f.status = {
    ok: true,
    state: "starting",
    pending: true,
    target: "on",
    chat_only: true,
    message: "Starting services",
  };
  release({ data: f.status });
  await click;
  f.networkDown = true;
  await f.ui.refresh();
  assert.equal(f.ui.button.attrs["aria-label"], "Starting Nova…");
  assert.match(f.ui.detail.textContent, /Reconnecting/);
  assert.equal(
    f.ui.button.disabled,
    true,
    "A disconnected worker must never look safely off",
  );
  f.networkDown = false;
  f.status = {
    ok: true,
    state: "on",
    pending: false,
    target: null,
    chat_only: false,
  };
  await f.ui.refresh();
  assert.equal(
    f.reloads,
    0,
    "Launcher mode alone cannot reload before replacement worker is ready",
  );
  assert.equal(
    f.find("pb-auto").disabled,
    false,
    "Formerly enabled controls recover after transition",
  );
  f.input.value = "Unsent Nova draft";
  f.input.setSelectionRange(2, 6);
  f.context.pendingImages = [{ dataUrl: "data:image/png;base64,TEST" }];
  f.context._mentionedFiles = [
    { path: "workspace/example.py", name: "example.py" },
  ];
  f.chatOnly = false;
  await f.ui.refresh();
  assert.equal(f.reloads, 1);
  const saved = JSON.parse(f.storage.get(draftKey));
  assert.equal(saved.text, f.input.value);
  assert.equal(saved.start, 2);
  assert.equal(saved.images.length, 1);
  assert.equal(saved.files.length, 1);
  await f.ui.refresh();
  assert.equal(f.reloads, 1, "Mode change triggers only one reload");
  assert.ok(
    f.calls.every((call) => !call.url.includes("llama")),
    "No model-only fallback may start Nova",
  );

  const next = fixture({
    storage: f.storage,
    chatOnly: false,
    status: f.status,
  });
  await settle();
  assert.equal(next.input.value, "Unsent Nova draft");
  assert.equal(next.input.selectionStart, 2);
  assert.equal(next.context.pendingImages.length, 1);
  assert.equal(next.context._mentionedFiles.length, 1);
  assert.equal(
    next.storage.has(draftKey),
    false,
    "Restored draft is consumed once",
  );
  assert.equal(next.reloads, 0);
  assert.equal(next.ui.button.attrs["aria-label"], "Stop Nova");
  next.post = async () => ({
    code: 409,
    data: {
      ...next.status,
      ok: false,
      error: "Finish the current update first",
    },
  });
  await next.ui.button.click();
  assert.match(next.ui.detail.textContent, /Finish the current update first/);
  assert.equal(
    next.ui.button.disabled,
    false,
    "A rejected request must remain retryable after refresh",
  );
  assert.equal(next.find("pb-auto").disabled, false);
  next.post = async (url) => {
    assert.equal(url, "/api/nova/stop");
    next.status = {
      ok: true,
      state: "stopping",
      pending: true,
      target: "off",
      chat_only: false,
    };
    return { data: next.status };
  };
  await next.ui.button.click();
  assert.equal(next.ui.button.attrs["aria-label"], "Stopping Nova…");
  next.status = {
    ok: true,
    state: "off",
    pending: false,
    target: null,
    chat_only: true,
  };
  next.chatOnly = true;
  await next.ui.refresh();
  assert.equal(next.reloads, 1);

  const failedStart = fixture();
  await settle();
  failedStart.post = async () => {
    failedStart.status = {
      ok: true,
      state: "starting",
      pending: true,
      target: "on",
      chat_only: true,
    };
    return { data: failedStart.status };
  };
  await failedStart.ui.button.click();
  failedStart.status = {
    ok: false,
    state: "error",
    pending: false,
    target: null,
    chat_only: true,
    available: true,
    error: "Model startup failed; controller restored",
  };
  await failedStart.ui.refresh();
  assert.equal(failedStart.ui.button.attrs["aria-label"], "Start Nova");
  assert.equal(
    failedStart.ui.button.disabled,
    false,
    "Terminal startup failure must release pending state and allow retry",
  );
  assert.match(failedStart.ui.detail.textContent, /Model startup failed/);
  assert.equal(
    failedStart.reloads,
    0,
    "Rollback to original chat-only mode needs no reload",
  );
  assert.equal(failedStart.find("pb-auto").disabled, false);
  failedStart.status = {
    ...failedStart.status,
    chat_only: false,
    error: "Shutdown failed; full mode restored",
  };
  failedStart.chatOnly = false;
  failedStart.versionDown = true;
  await failedStart.ui.refresh();
  assert.equal(
    failedStart.reloads,
    0,
    "Wait through version-endpoint downtime before reloading",
  );
  assert.match(
    failedStart.ui.detail.textContent,
    /Waiting for the controller to reconnect/,
  );
  failedStart.versionDown = false;
  await failedStart.ui.refresh();
  assert.equal(failedStart.ui.button.attrs["aria-label"], "Stop Nova");
  assert.equal(
    failedStart.reloads,
    1,
    "An error state with a genuinely changed worker mode still reloads safely",
  );

  const unavailable = fixture();
  unavailable.statusCode = 503;
  unavailable.status = {
    ok: false,
    state: "unavailable",
    available: false,
    error: "Launcher unavailable",
  };
  await settle();
  assert.equal(unavailable.ui.button.disabled, true);
  assert.match(unavailable.ui.detail.textContent, /Launcher unavailable/);
  assert.equal(unavailable.reloads, 0);

  const old = fixture();
  old.statusCode = 404;
  old.status = { detail: "Not found" };
  await settle();
  assert.equal(old.ui.button.disabled, true);
  assert.match(
    old.ui.detail.textContent,
    /Restart Nova Chat to enable control/,
  );
  await old.ui.button.click();
  assert.ok(old.calls.every((call) => call.method === "GET"));

  const quota = fixture();
  await settle();
  quota.input.value = "Keep this draft";
  quota.storageFailure = true;
  quota.chatOnly = false;
  quota.status = { ok: true, state: "on", chat_only: false };
  await quota.ui.refresh();
  assert.equal(quota.reloads, 0);
  assert.equal(quota.input.value, "Keep this draft");
  assert.match(quota.ui.detail.textContent, /too large to save/);
  for (const item of [f, next, failedStart, unavailable, old, quota])
    item.ui.destroy();
  console.log(
    "Conversation power UI: 8 scenarios passed (startup, transition/reconnect, draft reload/restore, rejection/retry, failed startup/rollback, unavailable launcher, legacy backend, full storage).",
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
