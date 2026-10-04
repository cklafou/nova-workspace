/* @nova: Exercise updater UI metadata-only startup, training races, confirmation and recovery with an in-memory DOM and fake HTTP. */
const fs = require("fs"),
  vm = require("vm"),
  assert = require("node:assert/strict"),
  path = require("node:path");
class Element {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.dataset = {};
    this.events = {};
    this.attrs = {};
    this.className = "";
    this._text = "";
    this._value = undefined;
    this.disabled = false;
    this.checked = false;
    this.isConnected = true;
    this.classList = { add: (cls) => (this.className += " " + cls) };
  }
  get textContent() {
    return this._text + this.children.map((c) => c.textContent).join("");
  }
  set textContent(text) {
    this._text = String(text);
    this.children = [];
  }
  set innerHTML(value) {
    throw Error("HTML rendering forbidden");
  }
  get value() {
    return this._value === undefined
      ? this.tagName === "select"
        ? this.children[0]?.value || ""
        : ""
      : this._value;
  }
  set value(v) {
    this._value = String(v);
  }
  append(...nodes) {
    for (const node of nodes) {
      node.parentElement = this;
      this.children.push(node);
    }
  }
  replaceChildren(...nodes) {
    this.children = [];
    this.append(...nodes);
  }
  remove() {
    if (this.parentElement)
      this.parentElement.children = this.parentElement.children.filter(
        (x) => x !== this,
      );
    this.isConnected = false;
  }
  setAttribute(k, v) {
    this.attrs[k] = v;
  }
  addEventListener(event, fn) {
    (this.events[event] ||= []).push(fn);
  }
  removeEventListener(event, fn) {
    this.events[event] = (this.events[event] || []).filter((f) => f !== fn);
  }
  async click() {
    if (this.disabled) return;
    for (const fn of this.events.click || []) await fn({ target: this });
  }
  async fire(event) {
    for (const fn of [...(this.events[event] || [])])
      await fn({ target: this });
    if (this["on" + event]) await this["on" + event]();
    if (["input", "change"].includes(event) && this.parentElement)
      await this.parentElement.fire(event);
  }
  querySelectorAll(selector) {
    const matches = (node) =>
      selector.split(",").some((s) => {
        s = s.trim();
        if (s.startsWith("."))
          return node.className.split(" ").includes(s.slice(1));
        if (s === "details[open]")
          return node.tagName === "details" && node.open;
        return node.tagName === s;
      });
    return this.children.flatMap((node) => [
      ...(matches(node) ? [node] : []),
      ...node.querySelectorAll(selector),
    ]);
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
  getClientRects() {
    return this.visible ? [{}] : [];
  }
  scrollIntoView() {}
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
    this.fire("close");
  }
}
const body = new Element("body"),
  root = new Element("div");
body.append(root);
const calls = [];
const timers = [];
let walletJobState = "running";
let previewResolve,
  previewDeferred = false,
  lastTrain = null,
  previewCount = 0;
const previewSpecs = new Map();
let fundingReply = {
  state: "unconfigured",
  balance_usd: null,
  message:
    "Add a RunPod API key. Google browser sign-in does not configure API access.",
};
const state = {
  state: "ok",
  current: { label: "Fixture-27B", quant: "Q6_K" },
  checked_current: { label: "Previous-Fixture-27B" },
  catalog_stale: true,
  checked_at: "2026-10-04T00:00:00Z",
  candidates: [],
  pending: [],
  notify: false,
  settings: {
    enabled: true,
    ttl_hours: 12,
    min_b: 27,
    max_b: 32,
    licenses: ["mit"],
    authors: ["Fixture"],
    source: "huggingface",
  },
  credentials: {
    runpod_api_key: true,
    hf_token: false,
    pod_id: "fixture-pod",
    ssh_key_path: "fixture-key",
  },
  pending_install: { phase: "awaiting-start" },
  busy: { id: "wallet-live" },
};
const response = (result) => ({
  ok: true,
  status: 200,
  json: async () => result,
});
const context = {
  window: { addEventListener() {} },
  document: {
    body,
    hidden: false,
    createElement: (tag) => new Element(tag),
    querySelector: (selector) =>
      selector.includes("nup-dialog")
        ? body
            .querySelectorAll("dialog")
            .find((d) => d.open)
            ?.querySelector(".nup-dialog-error")
        : body.querySelector(selector),
  },
  setTimeout: (callback, delay) => {
    timers.push({ callback, delay });
    return timers.length;
  },
  clearTimeout() {},
  AbortController,
  URL,
  URLSearchParams,
  console,
  fetch: async (url, options) => {
    const payload = options.body ? JSON.parse(options.body) : undefined;
    calls.push({ url, payload });
    if (url.endsWith("/status")) return response(state);
    if (url.includes("/funding")) return response(fundingReply);
    if (url.endsWith("/jobs"))
      return response([
        {
          id: "j",
          state: "succeeded",
          title: "Fixture install",
          kind: "install",
          percent: 100,
          result: {
            installed: ["fixture-model"],
            verified: false,
            pending: "Awaiting full start",
            after: { error: "Fixture training failure" },
          },
        },
        {
          id: "download-only",
          kind: "install",
          state: "succeeded",
          title: "No adapter work recorded",
          percent: 100,
          result: {
            installed: ["models/fixture/base.gguf"],
            activated: true,
            verified: false,
            pending: "Awaiting start",
          },
        },
        {
          id: "export",
          kind: "train-export",
          state: "succeeded",
          title: "Export only",
          percent: 100,
          result: {
            zip: "models/Training Files/Fixture 27B Dense/run/bundle.zip",
            bundle: { dir: "models/Training Files/Fixture 27B Dense/run" },
            training_directory: "models/Training Files/Fixture 27B Dense/run",
            output_directory: "models/fixture",
          },
        },
        {
          id: "wallet-live",
          kind: "train",
          state: walletJobState,
          title: "Wallet-based training",
          percent: null,
          runpod_cost: {
            pod_id: "fixture-pod",
            gpu: "NVIDIA H200",
            per_hour: 4.59,
            elapsed_seconds: 120,
            estimated_gpu_cost_usd: 0.153,
            balance_usd: 4.25,
            balance_checked_at: "2026-10-04T04:00:00Z",
            funding_warning:
              "Wallet may need a manual recharge to finish this run.",
            storage_included: false,
            stop_requested: false,
          },
        },
        {
          id: "wallet-failed",
          kind: "train",
          state: "failed",
          title: "Failure with retained cost",
          percent: null,
          runpod_cost: {
            pod_id: "failed-pod",
            gpu: "NVIDIA H200",
            per_hour: 4.59,
            elapsed_seconds: 600,
            estimated_gpu_cost_usd: 0.765,
            balance_usd: null,
            balance_error: "Provider temporarily unavailable",
            stop_error: "Provider refused request",
            storage_included: false,
          },
        },
        {
          id: "retained-recovery",
          kind: "train",
          state: "failed",
          title: "Recovery pod retained",
          runpod_cost: {
            pod_id: "recovery-pod",
            stop_requested: true,
            pod_deleted: false,
            cleanup_state: "retained",
            storage_retained: true,
            cleanup_message:
              "Local output verification failed; remote checkpoints retained.",
          },
        },
        {
          id: "cleanup-failed",
          kind: "train",
          state: "succeeded",
          title: "Training succeeded but cleanup failed",
          runpod_cost: {
            pod_id: "cleanup-failed-pod",
            stop_requested: true,
            pod_deleted: false,
            delete_requested: true,
            cleanup_state: "cleanup_failed",
            storage_retained: true,
            delete_error: "Provider deletion timed out",
          },
        },
        {
          id: "cleanup-pending",
          kind: "train",
          state: "running",
          title: "Deletion awaiting confirmation",
          runpod_cost: {
            pod_id: "pending-pod",
            stop_requested: true,
            pod_deleted: false,
            delete_requested: true,
            cleanup_state: "deleting",
            storage_retained: true,
          },
        },
        {
          id: "trained",
          kind: "train",
          state: "succeeded",
          title: "Trained outputs",
          percent: 100,
          result: {
            runpod_cost: {
              pod_id: "done-pod",
              gpu: "NVIDIA H200",
              per_hour: 4.59,
              elapsed_seconds: 900,
              estimated_gpu_cost_usd: 1.1475,
              balance_usd: 8.5,
              balance_checked_at: "2026-10-04T04:30:00Z",
              stop_requested: true,
              stop_error: "Stale stop error superseded by confirmed deletion",
              cleanup_state: "terminated",
              pod_deleted: true,
              delete_requested: true,
              storage_retained: false,
              cleanup_verified_at: "2026-10-04T04:31:00Z",
              cleanup_message:
                "Verified local adapters and training records; provider confirms pod absence.",
              storage_included: false,
            },
            installed: ["models/fixture/Nova Personality - Epoch 2.gguf"],
            output_directory: "models/fixture",
            training_directory: "models/Training Files/Fixture 27B Dense/run",
            readme: "models/Training Files/Fixture 27B Dense/run/README.md",
            receipt: "models/fixture/training-receipt.json",
            run_details:
              "models/Training Files/Fixture 27B Dense/run/Run Details/fixture-job",
          },
        },
      ]);
    if (url.endsWith("/decision")) return response(state);
    if (url.includes("/candidate?"))
      return response({
        model_id: "Fixture/Base-27B",
        source: "huggingface",
        builds: [
          {
            repo: "Fixture/Base-27B-GGUF",
            quants: [{ label: "Q6_K", size: 1024, files: [] }],
            projectors: [],
          },
        ],
        suggested: { gguf_repo: "Fixture/Base-27B-GGUF", quant: "Q6_K" },
      });
    if (url.endsWith("/inventory"))
      return response({
        models: [],
        projectors: [],
        loras: [
          {
            path: "models/old/old-adapter.gguf",
            kind: "lora",
            active: true,
            bound_to: "old-base",
            size: 100,
          },
        ],
      });
    if (url.endsWith("/plan"))
      return response({
        id: "fixture-plan",
        ...payload,
        downloads: [],
        download_bytes: 1024,
        free_bytes: 10737418240,
        target_dir: "models/fixture",
        warnings: [],
        blocking: [],
        invalidated: [
          {
            path: "models/old/old-adapter.gguf",
            kind: "lora",
            active: true,
            bound_to: "old-base",
          },
        ],
        training: null,
      });
    if (url.endsWith("/train/preview")) {
      const reviewId = "fixture-review-" + ++previewCount;
      previewSpecs.set(reviewId, payload.spec);
      const result = {
        ...payload.spec,
        review_id: reviewId,
        training_directory: "models/Training Files/Fixture 27B Dense/run",
        output_directory: "models/fixture",
        output_pattern: "Nova Personality - Epoch <number>.gguf",
        rows: 2,
        ...(payload.spec.runner === "runpod"
          ? {
              cost: {
                cost_usd: 5,
                per_hour: 3,
                funding: { ...fundingReply },
                data_center_ids: payload.spec.data_center_ids,
              },
            }
          : {}),
        output_name: "fixture",
        estimate_hours: 1,
        params: {},
        data: [{ path: "fixture.jsonl", sha256: "123", rows: 2 }],
      };
      return previewDeferred
        ? await new Promise(
            (resolve) => (previewResolve = () => resolve(response(result))),
          )
        : response(result);
    }
    if (url.endsWith("/train")) {
      lastTrain = payload;
      return response({ id: "train", state: "queued" });
    }
    if (url.endsWith("/rollback"))
      return response({
        state: "restored",
        message: "Boot files restored; restart required.",
      });
    throw Error("Unexpected API: " + url);
  },
};
vm.runInNewContext(
  fs.readFileSync(path.join(__dirname, "..", "static", "updater.js"), "utf8"),
  context,
);
const flush = () => new Promise(setImmediate);
const button = (name, parent = root) =>
  parent.querySelectorAll("button").find((b) => b.textContent === name);
const input = (label, parent = root) =>
  parent
    .querySelectorAll("label")
    .find((n) => n.children[0]?.textContent === label)?.children[1];
const checkbox = (label, parent = root) =>
  parent
    .querySelectorAll("label")
    .find((n) => n.children[1]?.textContent === label)?.children[0];
(async () => {
  context.window.mountNovaUpdater(root);
  context.window.initNovaUpdaterNotifications({ showWidget() {} });
  await flush();
  await flush();
  assert.ok(
    calls.every((c) => /\/(status|jobs)$/.test(c.url)),
    "Startup may query only metadata",
  );
  assert.ok(root.textContent.includes("RunPod · Live cost"));
  assert.ok(root.textContent.includes("RunPod · Cost summary"));
  assert.ok(root.textContent.includes("$4.59/hour"));
  assert.ok(root.textContent.includes("0h 2m 0s"));
  assert.ok(root.textContent.includes("Wallet may need a manual recharge"));
  assert.ok(root.textContent.includes("Provider temporarily unavailable"));
  assert.ok(root.textContent.includes("Pod needs attention"));
  assert.ok(root.textContent.includes("RunPod accepted the stop request"));
  assert.ok(root.textContent.includes("Storage is additional"));
  const summaryFor = (title) =>
    root
      .querySelectorAll(".nup-card")
      .find((card) => card.children[0]?.textContent === title)
      .querySelector(".nup-cost-summary").textContent;
  const deletedSummary = summaryFor("Trained outputs");
  assert.ok(deletedSummary.includes("Deleted — absence confirmed"));
  assert.ok(
    deletedSummary.includes(
      "Pod-attached recovery storage is no longer retained",
    ),
  );
  assert.ok(deletedSummary.includes("Separate network volumes"));
  assert.ok(
    !deletedSummary.includes("Stale stop error"),
    "Confirmed deletion supersedes a previous stop error",
  );
  assert.ok(
    !deletedSummary.includes(
      "does not verify that the pod has finished stopping",
    ),
    "A deleted pod must not appear merely stopped",
  );
  const retainedSummary = summaryFor("Recovery pod retained");
  assert.ok(
    retainedSummary.includes(
      "storage continues billing even when the GPU is stopped",
    ),
  );
  assert.ok(!retainedSummary.includes("Deleted — absence confirmed"));
  const cleanupFailedSummary = summaryFor(
    "Training succeeded but cleanup failed",
  );
  assert.ok(cleanupFailedSummary.includes("Pod cleanup needs attention"));
  assert.ok(cleanupFailedSummary.includes("Provider deletion timed out"));
  assert.ok(cleanupFailedSummary.includes("may still be billed"));
  assert.ok(
    !cleanupFailedSummary.includes("Deleted — absence confirmed"),
    "Successful training does not prove successful cleanup",
  );
  const pendingSummary = summaryFor("Deletion awaiting confirmation");
  assert.ok(pendingSummary.includes("confirmation is still pending"));
  assert.ok(
    !pendingSummary.includes("Deleted — absence confirmed"),
    "Delete request is not proof of absence",
  );
  assert.ok(
    summaryFor("Failure with retained cost").includes(
      "Pod deletion is not recorded",
    ),
    "Old jobs with unknown cleanup must not imply free storage",
  );
  assert.equal(
    input("Maximum GPU cost in USD"),
    undefined,
    "No artificial per-run budget field",
  );
  assert.ok(root.textContent.includes("Awaiting full start"));
  assert.ok(root.textContent.includes("Fixture training failure"));
  assert.ok(root.textContent.includes("Configured model (next start)"));
  assert.ok(root.textContent.includes("Model compared by last catalog check"));
  assert.ok(
    root.textContent.includes(
      "The configured model changed after the last catalog check",
    ),
  );
  assert.ok(
    root.textContent.includes(
      "No adapter training, export or copying is recorded",
    ),
  );
  assert.ok(
    root.textContent.includes("Training files exported — no LoRA was trained"),
  );
  assert.ok(
    root.textContent.includes(
      "New adapter files trained, verified and installed",
    ),
  );
  assert.ok(
    root.textContent.includes("models/Training Files/Fixture 27B Dense/run"),
  );
  assert.ok(
    root.textContent.includes("models/fixture/Nova Personality - Epoch 2.gguf"),
  );
  const savedDetails = root
    .querySelectorAll(".nup-file-locations")
    .find((row) =>
      row.textContent.includes(
        "Saved run details — model revision, environment and tokenization",
      ),
    );
  assert.ok(
    savedDetails,
    "Persisted successful training shows its run-details location outside raw JSON",
  );
  assert.equal(
    savedDetails.querySelector("code").textContent,
    "models/Training Files/Fixture 27B Dense/run/Run Details/fixture-job",
  );
  assert.ok(
    button("Copy path", savedDetails),
    "Runtime-evidence path can be copied",
  );
  assert.ok(root.textContent.includes("Adapter activation was not requested"));
  assert.equal(
    button("Roll back pending switch").disabled,
    true,
    "Recovery disabled while job active",
  );
  for (const dropdown of root.querySelectorAll("select")) {
    assert.ok(dropdown.id, "Every select has an explicit id");
    assert.equal(
      dropdown.parentElement.htmlFor,
      dropdown.id,
      "Visible label targets select",
    );
    assert.ok(dropdown.attrs["aria-label"], "Select has an accessible name");
  }
  assert.equal(input("Run method").attrs["aria-label"], "Run method");
  input("Base model repository").value = "Fixture/Base-27B";
  input("Training JSONL files — one workspace path per line").value =
    "fixture.jsonl";
  previewDeferred = true;
  const inFlight = button("Preview training").click();
  await flush();
  assert.equal(
    input("Base model repository").disabled,
    true,
    "Preview locks fields",
  );
  input("Base model repository").value = "Fixture/Changed-27B";
  previewResolve();
  await inFlight;
  assert.equal(input("Base model repository").disabled, false);
  assert.equal(
    button("Confirm and export bundle"),
    undefined,
    "Stale preview cannot start",
  );
  assert.ok(
    root.textContent.includes("Training inputs changed during preview"),
  );
  previewDeferred = false;
  await button("Preview training").click();
  assert.equal(
    root.querySelector(".nup-notice").textContent,
    "",
    "New action clears stale error",
  );
  assert.equal(
    button("Confirm and export bundle").disabled,
    true,
    "Explicit confirmation required",
  );
  const staleRun = button("Confirm and export bundle");
  input("Base model repository").value = "Fixture/Final-27B";
  await input("Base model repository").fire("input");
  assert.equal(
    staleRun.disabled,
    true,
    "Input edits discard the previous review token",
  );
  assert.equal(button("Confirm and export bundle"), undefined);
  await staleRun.click();
  assert.equal(
    lastTrain,
    null,
    "An invalidated preview cannot issue a training request",
  );
  await button("Preview training").click();
  const confirm = checkbox("I reviewed this plan and authorize the operation.");
  confirm.checked = true;
  await confirm.fire("change");
  await button("Confirm and export bundle").click();
  assert.deepEqual(
    Object.keys(lastTrain),
    ["review_id"],
    "Only the bound review starts training",
  );
  assert.equal(lastTrain.review_id, "fixture-review-3");
  const reviewed = previewSpecs.get(lastTrain.review_id);
  assert.equal(reviewed.data_files[0], "fixture.jsonl");
  assert.equal(reviewed.base_model_id, "Fixture/Final-27B");
  assert.equal(reviewed.activate, false);
  assert.equal(
    lastTrain.spec,
    undefined,
    "No unbound raw spec is sent to start training",
  );
  assert.ok(
    root.querySelector(".nup-notice").textContent.includes("export started"),
    "Successful export shows current outcome",
  );
  // Funding checks are user-requested and never confuse unavailable credit with $0.
  await button("Check RunPod credit").click();
  assert.ok(root.textContent.includes("RunPod API access is not configured"));
  assert.ok(root.textContent.includes("Unknown — not zero"));
  assert.ok(root.textContent.includes("Google browser sign-in"));
  fundingReply = {
    state: "unavailable",
    balance_usd: null,
    message: "Balance unavailable, not zero.",
  };
  await button("Check RunPod credit").click();
  assert.ok(root.textContent.includes("RunPod balance could not be verified"));
  fundingReply = {
    state: "insufficient",
    balance_usd: 0,
    required_usd: 3,
    shortfall_usd: 3,
    message: "Add at least $3.00 in RunPod Billing.",
  };
  await button("Check RunPod credit").click();
  assert.ok(root.textContent.includes("Recharge needed before training"));
  assert.ok(
    root
      .querySelectorAll("a")
      .some((a) => a.href === "https://console.runpod.io/user/billing"),
  );
  input("Run method").value = "runpod";
  await input("Run method").fire("change");
  assert.equal(
    input("New-pod data centers (in preference order)").value,
    "AP-JP-1",
  );
  input("Installed base-model file (optional)").value =
    "models/custom/base.gguf";
  await button("Preview training").click();
  const paid = button("Confirm paid training");
  const paidApproval = checkbox(
    "I reviewed the estimate and authorize paid training using my RunPod wallet.",
  );
  paidApproval.checked = true;
  await paidApproval.fire("change");
  assert.equal(
    paid.disabled,
    true,
    "Consent cannot bypass insufficient credit",
  );
  const previousRun = lastTrain;
  await paid.click();
  assert.equal(
    lastTrain,
    previousRun,
    "Insufficient credit sends no paid request",
  );
  fundingReply = {
    state: "sufficient",
    balance_usd: 4,
    required_usd: 3,
    estimated_cost_usd: 5,
    estimate_exceeds_balance: true,
    shortfall_usd: 0,
    message: "Credit meets the provider startup minimum.",
  };
  await button("Recheck RunPod credit").click();
  assert.equal(
    paid.disabled,
    false,
    "Sufficient rechecked credit enables reviewed consent",
  );
  const fundingQuery = calls
    .filter((c) => c.url.includes("/funding?"))
    .at(-1).url;
  assert.ok(
    fundingQuery.includes("required_usd=5") &&
      fundingQuery.includes("per_hour=3"),
  );
  assert.equal(input("Maximum GPU cost in USD"), undefined);
  assert.ok(
    root.textContent.includes(
      "then deletes the training pod and confirms it is gone",
    ),
    "Paid confirmation explains verified successful-run cleanup",
  );
  assert.ok(
    root.textContent.includes(
      "retain recovery storage, which continues billing",
    ),
    "Paid confirmation discloses failed-run storage charges",
  );
  assert.ok(
    root.textContent.includes("exceeds the current wallet balance"),
    "Estimated-total shortfall is a visible warning",
  );
  assert.equal(
    paid.disabled,
    false,
    "Wallet above one-hour minimum can start even below estimated total",
  );
  await paid.click();
  assert.deepEqual(lastTrain, {
    review_id: "fixture-review-4",
    confirm: { paid: true },
  });
  const paidSpec = previewSpecs.get(lastTrain.review_id);
  assert.deepEqual(paidSpec.data_center_ids, ["AP-JP-1"]);
  assert.equal(paidSpec.base_model_path, "models/custom/base.gguf");
  assert.ok(
    root.querySelector(".nup-notice").textContent.includes("Training started"),
  );
  assert.ok(
    !root
      .querySelector(".nup-notice")
      .textContent.includes("Enter a cost ceiling"),
  );
  assert.equal(
    calls.filter((c) => /\/train$/.test(c.url)).length,
    2,
    "Only explicitly confirmed export and fake paid run were submitted",
  );
  const preservedBaseInput = input("Base model repository");
  const statusCallsBeforeCompletion = calls.filter((c) =>
    c.url.endsWith("/status"),
  ).length;
  state.busy = null;
  walletJobState = "succeeded";
  root.visible = true;
  await timers.find((timer) => timer.delay === 3500).callback();
  assert.equal(
    calls.filter((c) => c.url.endsWith("/status")).length,
    statusCallsBeforeCompletion + 1,
    "A terminal job transition refreshes stale busy status automatically",
  );
  assert.equal(
    button("Roll back pending switch").disabled,
    false,
    "Recovery unlocks without requiring manual Refresh",
  );
  assert.equal(
    input("Base model repository"),
    preservedBaseInput,
    "Completion refresh preserves editable forms",
  );
  assert.equal(preservedBaseInput.value, "Fixture/Final-27B");
  await timers
    .filter((timer) => timer.delay === 3500)
    .at(-1)
    .callback();
  assert.equal(
    calls.filter((c) => c.url.endsWith("/status")).length,
    statusCallsBeforeCompletion + 1,
    "Unchanged finished jobs do not refresh metadata repeatedly",
  );
  root.visible = false;
  await button("Refresh").click();
  await button("Roll back pending switch").click();
  const d = body.querySelectorAll("dialog").find((x) => x.open);
  const approved = checkbox("I understand and want to continue.", d);
  approved.checked = true;
  await approved.fire("change");
  await button("Roll back pending switch", d).click();
  assert.equal(d.open, true, "Recovery result remains visible");
  assert.ok(d.textContent.includes("restart required"));
  assert.ok(d.textContent.includes("Restart Nova’s model and verify"));
  assert.ok(
    !calls.some((c) => /\/(inventory|candidate|plan|install)$/.test(c.url)),
    "No model inventory read without install/adapters workflow",
  );
  state.candidates = [
    { id: "Fixture/Base-27B", source: "huggingface", license: "mit" },
  ];
  await button("Refresh").click();
  await button("Review install").click();
  const installation = body
    .querySelectorAll("dialog")
    .filter((x) => x.open)
    .at(-1);
  const mode = input("Adapter work after the model download", installation);
  mode.value = "keep";
  await mode.fire("change");
  assert.ok(
    installation.textContent.includes(
      "No LoRA files are copied and no training happens",
    ),
  );
  await button("Build dry-run plan", installation).click();
  assert.ok(
    installation.textContent.includes(
      "No adapter is copied, converted or retrained",
    ),
  );
  assert.ok(
    installation.textContent.includes(
      "Cannot keep an active adapter trained for another base",
    ),
  );
  assert.equal(
    button("Confirm and install", installation).disabled,
    true,
    "Wrong-base keep cannot be confirmed",
  );
  assert.ok(
    !calls.some((c) => /\/(install|lora\/activate)$/.test(c.url)),
    "Audit must not install or activate anything",
  );
  console.log(
    "PASS: metadata-only startup, busy recovery lock, partial job outcomes, preview race rejection, input lock restoration, explicit export confirmation, bound preview token, invalidated token rejection, separate activation default, visible recovery result, explicit export/training paths, incompatible keep blocked, unknown versus zero credit, recharge link, paid funding gate/recheck, wallet-only paid consent and live/final cost metrics, verified deletion versus billed recovery storage and failed/unconfirmed cleanup, Japan region and custom base path.",
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
