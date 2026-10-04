/* @nova: Present model discovery, reviewed installation, adapter training and recovery without starting work automatically. */
(() => {
  "use strict";
  const API = "/api/updater/",
    listeners = new Set();
  let status = null,
    widget = null,
    pollTimer = null,
    noticeRoot = null,
    showWidget = null,
    noticeKey = "",
    uid = 0,
    stopped = false;
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = String(text);
    return n;
  };
  const bytes = (n) =>
    n !== null && n !== undefined && Number.isFinite(Number(n))
      ? (Number(n) / 1073741824).toFixed(2) + " GiB"
      : "Size unavailable";
  const money = (n) =>
    n !== null && n !== undefined && Number.isFinite(Number(n))
      ? "$" + Number(n).toFixed(2)
      : "Cost unavailable";
  const date = (value) =>
    value && !Number.isNaN(new Date(value).getTime())
      ? new Date(value).toLocaleString()
      : "Not checked yet";
  const list = (value) => (Array.isArray(value) ? value : []);
  function button(text, action, cls = "nup-button") {
    const b = el("button", cls, text);
    b.type = "button";
    b.addEventListener("click", async () => {
      if (b.disabled) return;
      if (widget?.notice) widget.notice.textContent = "";
      const dialogError = document.querySelector(
        "dialog.nup-dialog[open] .nup-dialog-error",
      );
      if (dialogError) dialogError.textContent = "";
      b.disabled = true;
      try {
        await action();
      } catch (error) {
        report(error);
      } finally {
        b.disabled = false;
      }
    });
    return b;
  }
  function field(parent, label, type = "text", value = "") {
    const wrap = el("label", "nup-field"),
      input = el(type === "textarea" ? "textarea" : "input");
    input.id = "nup-" + ++uid;
    if (type !== "textarea") input.type = type;
    input.value = value;
    wrap.append(el("span", "", label), input);
    parent.append(wrap);
    return input;
  }
  function select(parent, label, options, value) {
    const wrap = el("label", "nup-field"),
      input = el("select");
    input.id = "nup-" + ++uid;
    wrap.htmlFor = input.id;
    input.setAttribute("aria-label", label);
    for (const [key, text] of options) {
      const o = el("option", "", text);
      o.value = key;
      input.append(o);
    }
    if (value !== undefined) input.value = value;
    wrap.append(el("span", "", label), input);
    parent.append(wrap);
    return input;
  }
  function check(parent, label, checked = false) {
    const wrap = el("label", "nup-check"),
      input = el("input");
    input.type = "checkbox";
    input.checked = checked;
    wrap.append(input, el("span", "", label));
    parent.append(wrap);
    return input;
  }
  function section(parent, title, text) {
    const box = el("section", "nup-card");
    if (title) box.append(el("h3", "", title));
    if (text) box.append(el("p", "nup-muted", text));
    parent.append(box);
    return box;
  }
  function facts(parent, values) {
    const grid = el("dl", "nup-facts");
    for (const [key, value] of values) {
      grid.append(el("dt", "", key), el("dd", "", value ?? "—"));
    }
    parent.append(grid);
  }
  function details(parent, title, value) {
    const box = el("details", "nup-details");
    box.append(
      el("summary", "", title),
      el(
        "pre",
        "",
        typeof value === "string" ? value : JSON.stringify(value, null, 2),
      ),
    );
    parent.append(box);
    return box;
  }
  function messages(parent, items, kind, title) {
    if (!items?.length) return;
    const box = el("div", "nup-" + kind);
    box.append(
      el(
        "strong",
        "",
        title ||
          (kind === "blocking"
            ? "Resolve before installing"
            : "Review carefully"),
      ),
    );
    const ul = el("ul");
    for (const value of items)
      ul.append(
        el("li", "", typeof value === "string" ? value : JSON.stringify(value)),
      );
    box.append(ul);
    parent.append(box);
  }
  function link(parent, url, label = "View source") {
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return;
      const a = el("a", "nup-link", label);
      a.href = parsed.href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      parent.append(a);
    } catch (_) {}
  }
  function report(error) {
    const text = typeof error === "string" ? error : error.message;
    const target =
      document.querySelector("dialog.nup-dialog[open] .nup-dialog-error") ||
      widget?.notice;
    if (target) {
      target.textContent = text;
      target.scrollIntoView?.({ block: "nearest" });
      if (error?.result) {
        const parent = target.parentElement;
        parent.querySelector(".nup-error-result")?.remove();
        const extra = details(
          parent,
          "Server response and recovery status",
          error.result,
        );
        extra.classList.add("nup-error-result");
        extra.open = true;
      }
    } else if (window.toast) window.toast(text, 6500);
  }
  async function api(path, body) {
    const control = new AbortController(),
      timer = setTimeout(() => control.abort(), 120000);
    try {
      const response = await fetch(API + path, {
        method: body === undefined ? "GET" : "POST",
        headers:
          body === undefined ? {} : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
        credentials: "same-origin",
        cache: "no-store",
        signal: control.signal,
      });
      const result = await response.json();
      if (!response.ok || result?.ok === false) {
        const error = new Error(
          result.error ||
            result.detail ||
            "Updater request failed (" + response.status + ").",
        );
        error.result = result;
        throw error;
      }
      return result;
    } catch (error) {
      if (error.name === "AbortError")
        throw Error(
          "The updater did not confirm the request in time. Check Jobs before retrying an install or training run.",
        );
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }
  async function refresh() {
    try {
      status = await api("status");
      listeners.forEach((fn) => fn(status));
      renderNotification();
      return status;
    } catch (error) {
      if (widget) widget.state.textContent = "Updater unavailable";
      throw error;
    }
  }
  function dialog(title) {
    const d = el("dialog", "nup-dialog");
    d.setAttribute("aria-label", title);
    const head = el("header", "nup-dialog-head");
    head.append(
      el("h2", "", title),
      button("Close", () => d.close()),
    );
    const content = el("div", "nup-dialog-content"),
      error = el("p", "nup-dialog-error");
    error.setAttribute("role", "alert");
    d.append(head, content, error);
    document.body.append(d);
    d.addEventListener("close", () => d.remove(), { once: true });
    d.showModal();
    return { node: d, content, error };
  }
  async function confirmAction(title, description, action) {
    const d = dialog(title);
    d.content.append(el("p", "", description));
    const accepted = check(d.content, "I understand and want to continue.");
    const row = el("div", "nup-actions"),
      go = button(title, async () => {
        if (!accepted.checked) return;
        try {
          const result = await action();
          d.content.replaceChildren(el("h3", "", "Recovery result"));
          if (result.state === "restored")
            d.content.append(
              el(
                "p",
                "nup-warning",
                "Boot files were restored. Restart Nova’s model and verify it is running before treating recovery as complete.",
              ),
            );
          if (result.message) d.content.append(el("p", "", result.message));
          const outcome = details(
            d.content,
            "Returned state and verification details",
            result,
          );
          outcome.open = true;
          await refresh();
          await widget?.refreshJobs();
        } catch (error) {
          report(error);
        }
      });
    go.disabled = true;
    accepted.onchange = () => (go.disabled = !accepted.checked);
    row.append(
      button("Cancel", () => d.node.close()),
      go,
    );
    d.content.append(row);
  }
  async function chooseCandidate(
    candidate,
    remember = false,
    decision = false,
  ) {
    if (decision)
      await api("decision", {
        ids: [candidate.id],
        decision: "update",
        remember,
      });
    if (noticeRoot) noticeRoot.hidden = true;
    showWidget?.("updater");
    await openInstall(candidate);
    refresh().catch(() => {});
  }
  function candidateCard(parent, candidate, allowDecision) {
    const box = section(parent, candidate.id);
    box.append(
      el(
        "p",
        "nup-muted",
        [
          candidate.params_b || candidate.size_b
            ? String(candidate.params_b || candidate.size_b) + "B"
            : "",
          candidate.license || "License unknown",
          candidate.created ? date(candidate.created) : "",
          candidate.gated ? "Gated repository" : "",
        ]
          .filter(Boolean)
          .join(" · "),
      ),
    );
    link(box, candidate.url);
    const controls = el("div", "nup-actions");
    if (candidate.installable !== false && candidate.source !== "ollama") {
      const remember = allowDecision
        ? check(box, "Remember my decision for this version")
        : null;
      controls.append(
        button("Review install", () =>
          chooseCandidate(candidate, !!remember?.checked, allowDecision),
        ),
      );
      if (allowDecision)
        controls.append(
          button("Decline", async () => {
            await api("decision", {
              ids: [candidate.id],
              decision: "decline",
              remember: remember.checked,
            });
            await refresh();
          }),
        );
    }
    if (candidate.remembered) {
      box.append(el("p", "nup-muted", "Remembered: " + candidate.remembered));
      controls.append(
        button("Forget decision", async () => {
          await api("forget", { id: candidate.id });
          await refresh();
        }),
      );
    }
    box.append(controls);
    return box;
  }
  function fileLocations(parent, title, paths) {
    const values = [
      ...new Set(paths.filter((value) => typeof value === "string" && value)),
    ];
    if (!values.length) return;
    const box = el("div", "nup-file-locations");
    box.append(el("strong", "", title));
    const files = el("ul", "nup-paths");
    for (const path of values) {
      const row = el("li");
      row.append(
        el("code", "", path),
        button("Copy path", async () => {
          if (!navigator.clipboard)
            throw Error("Clipboard unavailable in this window.");
          await navigator.clipboard.writeText(path);
          report("Path copied.");
        }),
      );
      files.append(row);
    }
    box.append(files);
    parent.append(box);
  }
  function adapterPlanSummary(parent, plan) {
    const mode = plan.lora?.mode || "none";
    const box = section(parent, "What happens to the adapter");
    let action;
    if (mode === "keep")
      action =
        "Keep the existing adapter setting. No adapter is copied, converted or retrained.";
    else if (mode !== "train")
      action = "No adapter work: no copying, training or training-file export.";
    else if (plan.training?.runner === "runpod")
      action =
        "Run paid training for this base, then verify and install the new adapter files. They remain inactive until you explicitly activate one.";
    else
      action =
        "Export training files only. This does not run training or produce new LoRA weights. Run the bundle on a GPU, then import the completed adapter files.";
    box.append(el("p", "nup-action-summary", action));
    facts(box, [
      [
        "After the model switch",
        !plan.activate
          ? "No switch requested; the current adapter setting is unchanged."
          : mode === "keep"
            ? "Current adapter setting retained. Its base must match the new model."
            : "Personality adapter off until a compatible adapter is explicitly activated.",
      ],
    ]);
    if (plan.training?.training_directory)
      fileLocations(box, "Training inputs retained for reproduction", [
        plan.training.training_directory,
      ]);
    if (plan.training?.output_directory)
      fileLocations(
        box,
        "Finished adapter destination — beside the base model",
        [plan.training.output_directory],
      );
    if (plan.training?.output_pattern)
      facts(box, [["Final file names", plan.training.output_pattern]]);
    if (mode === "keep")
      box.append(
        el(
          "p",
          "nup-warning",
          "Keeping a LoRA does not make it compatible with a different base model. Renaming or copying its files does not retrain it.",
        ),
      );
  }
  function renderRunPodCost(parent, job) {
    const cost =
      job.runpod_cost ||
      job.result?.runpod_cost ||
      job.result?.after?.runpod_cost;
    if (!cost) return;
    const active = ["queued", "running"].includes(job.state);
    const box = section(
      parent,
      active ? "RunPod · Live cost" : "RunPod · Cost summary",
    );
    box.classList.add("nup-cost-summary");
    const seconds = Number(cost.elapsed_seconds);
    const elapsed =
      cost.elapsed_seconds != null && Number.isFinite(seconds)
        ? Math.floor(seconds / 3600) +
          "h " +
          Math.floor((seconds % 3600) / 60) +
          "m " +
          Math.floor(seconds % 60) +
          "s"
        : "Not measured";
    facts(box, [
      ["GPU", cost.gpu || "Not reported"],
      [
        "Actual GPU rate",
        cost.per_hour == null ? "Not reported" : money(cost.per_hour) + "/hour",
      ],
      ["Elapsed pod time", elapsed],
      ["Estimated GPU spend", money(cost.estimated_gpu_cost_usd)],
      [
        "Last checked wallet credit",
        cost.balance_usd == null
          ? "Unknown — not zero"
          : money(cost.balance_usd),
      ],
      ["Balance checked", date(cost.balance_checked_at)],
    ]);
    box.append(
      el(
        "p",
        "nup-muted",
        "GPU spend is estimated from the reported rate and elapsed time. Storage is additional; RunPod Billing is authoritative. Other resources may also consume wallet credit. Nova does not add funds or impose a per-run spending limit.",
      ),
    );
    if (cost.balance_error)
      messages(
        box,
        [
          "Wallet balance could not be refreshed: " +
            cost.balance_error +
            ". The last checked value above may be stale.",
        ],
        "warning",
        "Wallet check unavailable",
      );
    if (cost.funding_warning)
      messages(
        box,
        Array.isArray(cost.funding_warning)
          ? cost.funding_warning
          : [cost.funding_warning],
        "warning",
        "Check RunPod credit",
      );
    if (cost.stop_error)
      messages(
        box,
        [
          "Could not confirm the stop request: " +
            cost.stop_error +
            ". Check the pod in RunPod now; GPU charges may continue.",
        ],
        "blocking",
        "Pod needs attention",
      );
    else if (cost.stop_requested)
      box.append(
        el(
          "p",
          "nup-muted",
          "RunPod accepted the stop request. This receipt does not verify that the pod has finished stopping.",
        ),
      );
    else if (!active && cost.pod_id)
      box.append(
        el(
          "p",
          "nup-warning",
          "No accepted stop request is recorded here. Check the pod in RunPod.",
        ),
      );
    link(
      box,
      "https://console.runpod.io/user/billing",
      "Open RunPod Billing / recharge manually",
    );
    if (cost.pod_id)
      link(box, "https://console.runpod.io/pods", "Open RunPod Pods");
  }
  function renderOutcome(parent, job) {
    const result = job.result;
    if (!result) return;
    const modelInstall = job.kind === "install";
    if (modelInstall) {
      fileLocations(
        parent,
        "Downloaded model and projector files",
        list(result.installed),
      );
      if (
        !result.after &&
        ["succeeded", "failed", "cancelled"].includes(job.state)
      )
        parent.append(
          el(
            "p",
            "nup-action-summary",
            "No adapter training, export or copying is recorded for this model-install job. Downloading a base model does not create a new LoRA.",
          ),
        );
    }
    const adapter = modelInstall ? result.after : result;
    if (!adapter) return;
    if (
      (adapter.zip || job.kind === "train-export") &&
      !list(adapter.installed).length
    ) {
      parent.append(
        el(
          "p",
          "nup-action-summary",
          "Training files exported — no LoRA was trained. No new adapter was installed or activated.",
        ),
      );
      fileLocations(parent, "Exported files — run this bundle on a GPU", [
        adapter.zip,
        adapter.bundle?.dir,
        adapter.folder,
      ]);
    }
    if (list(adapter.installed).length) {
      const copied = job.kind === "import";
      parent.append(
        el(
          "p",
          "nup-action-summary",
          copied
            ? "Verified completed adapter files copied beside the base model. This import did not retrain them."
            : "New adapter files trained, verified and installed.",
        ),
      );
      fileLocations(parent, "Final adapter files", adapter.installed);
      fileLocations(parent, "Adapter folder and verification records", [
        adapter.output_directory,
        adapter.readme,
        adapter.receipt,
      ]);
      parent.append(
        el(
          "p",
          "nup-muted",
          adapter.boot_line
            ? "Adapter boot setting written; check a separate activation result to establish whether it is loaded."
            : "Adapter activation was not requested by this job. Use Installed adapters to explicitly select one after comparing the outputs.",
        ),
      );
    }
    fileLocations(
      parent,
      "Reproducibility inputs — dataset, recipe and scripts",
      [adapter.training_directory, adapter.training_readme],
    );
    if (adapter.run_details)
      fileLocations(
        parent,
        "Saved run details — model revision, environment and tokenization",
        [adapter.run_details],
      );
    if (adapter.output_directory && !list(adapter.installed).length)
      fileLocations(parent, "Destination for completed, verified adapters", [
        adapter.output_directory,
      ]);
  }
  function trainingFields(parent, base = "") {
    const grid = el("div", "nup-grid");
    parent.append(grid);
    const baseField = field(grid, "Base model repository", "text", base),
      preset = select(
        grid,
        "Recipe",
        [
          ["personality", "Personality"],
          ["specialist", "Specialist / KoELS"],
        ],
        "personality",
      );
    const data = field(
      parent,
      "Training JSONL files — one workspace path per line",
      "textarea",
    );
    data.rows = 3;
    const runner = select(
        grid,
        "Run method",
        [
          ["export", "Export training files only — does not train"],
          ["runpod", "Train on RunPod — new adapter, paid GPU time"],
        ],
        "export",
      ),
      output = field(grid, "Output name (optional)"),
      gpu = field(grid, "RunPod GPU", "text", "NVIDIA H100 80GB HBM3"),
      regions = field(
        grid,
        "New-pod data centers (in preference order)",
        "text",
        "AP-JP-1",
      ),
      installedBase = field(grid, "Installed base-model file (optional)");
    parent.append(
      el(
        "p",
        "nup-muted",
        "New pods default to AP-JP-1 (Japan, near Korea). Enter comma-separated RunPod data-center IDs to allow other locations explicitly. No automatic fallback to a distant region. A configured existing pod is reused in its current location. The optional base-model file places finished adapters beside that file.",
      ),
    );
    const methodHelp = el("p", "nup-action-summary");
    const explainMethod = () => {
      methodHelp.textContent =
        runner.value === "runpod"
          ? "RunPod trains a new adapter for this base model. You will review the cost and authorize the run separately. Downloaded adapter outputs remain inactive."
          : "Export copies the selected datasets and training scripts into a bundle. It does not train a LoRA or copy an existing LoRA to a new model.";
    };
    runner.addEventListener("change", explainMethod);
    explainMethod();
    parent.append(methodHelp);
    const advanced = el("details", "nup-details");
    advanced.append(el("summary", "", "Advanced training parameters"));
    const params = field(
      advanced,
      "Parameter overrides (JSON object)",
      "textarea",
      "{}",
    );
    params.rows = 4;
    parent.append(advanced);
    const read = () => {
      let options;
      try {
        options = JSON.parse(params.value || "{}");
      } catch (_) {
        throw Error("Training parameters must be valid JSON.");
      }
      if (!options || Array.isArray(options) || typeof options !== "object")
        throw Error("Training parameters must be a JSON object.");
      return {
        base_model_id: baseField.value.trim(),
        preset: preset.value,
        data_files: data.value
          .split(/\r?\n/)
          .map((x) => x.trim())
          .filter(Boolean),
        runner: runner.value,
        output_name: output.value.trim() || undefined,
        params: options,
        gpu: gpu.value.trim(),
        data_center_ids: regions.value
          .split(",")
          .map((value) => value.trim().toUpperCase())
          .filter(Boolean),
        ...(installedBase.value.trim()
          ? { base_model_path: installedBase.value.trim() }
          : {}),
        activate: false,
      };
    };
    return { read, base: baseField, runner };
  }
  function showTrainingPreview(parent, preview) {
    facts(parent, [
      ["Base", preview.base_model_id],
      ["Rows", preview.rows],
      [
        preview.runner === "runpod"
          ? "Estimated GPU run"
          : "Future GPU training time (not run by export)",
        preview.estimate_hours + " hours",
      ],
      ["Output", preview.output_name],
      [
        "RunPod location",
        preview.cost?.reuses_existing_pod
          ? "Reuse configured pod at its current location"
          : list(preview.data_center_ids || preview.cost?.data_center_ids).join(
              " → ",
            ) || "Not supplied",
      ],
      [
        "Method",
        preview.runner === "runpod"
          ? "Paid training — produces new adapter weights"
          : "Export files only — no training or new LoRA weights",
      ],
    ]);
    facts(parent, [
      [
        "Adapter activation",
        "Off — separate activation after reviewing the trained outputs",
      ],
    ]);
    if (preview.training_directory)
      fileLocations(
        parent,
        "Saved training inputs — dataset, recipe and scripts",
        [preview.training_directory],
      );
    if (preview.output_directory)
      fileLocations(parent, "Finished adapters — beside the base model", [
        preview.output_directory,
      ]);
    if (preview.output_pattern)
      facts(parent, [["Final file names", preview.output_pattern]]);
    if (preview.cost)
      facts(parent, [
        ["Estimated cost", money(preview.cost.cost_usd)],
        ["Hourly GPU rate", money(preview.cost.per_hour)],
        [
          "Price basis",
          preview.cost.basis ||
            "Estimate only; actual pod rate is checked before training.",
        ],
        ["Cost margin", preview.cost.margin || "Included in estimate"],
      ]);
    details(parent, "Dataset checks and training parameters", {
      data: preview.data,
      params: preview.params,
    });
  }
  function showFunding(parent, funding) {
    const value = funding || { state: "unavailable" };
    const titles = {
      sufficient: "RunPod credit meets the startup minimum",
      insufficient: "Recharge needed before training",
      unconfigured: "RunPod API access is not configured",
      unavailable: "RunPod balance could not be verified",
      available: "RunPod prepaid balance",
    };
    parent.replaceChildren();
    parent.className =
      "nup-funding " +
      (value.state === "sufficient" || value.state === "available"
        ? "nup-action-summary"
        : "nup-warning");
    parent.setAttribute("aria-live", "polite");
    parent.append(el("strong", "", titles[value.state] || titles.unavailable));
    parent.append(
      el(
        "p",
        "",
        value.message ||
          "Balance unavailable, not zero. Check the API key and retry. Paid training requires verified credit.",
      ),
    );
    facts(parent, [
      [
        "Available credit",
        value.balance_usd == null
          ? "Unknown — not zero"
          : money(value.balance_usd),
      ],
      [
        "Provider startup minimum",
        value.required_usd == null
          ? "Preview a training run first"
          : money(value.required_usd),
      ],
      ...(value.shortfall_usd > 0
        ? [["Add at least", money(value.shortfall_usd)]]
        : []),
    ]);
    parent.append(
      el(
        "p",
        "nup-muted",
        "RunPod requires at least one hour of GPU credit to start. The wallet is the spending limit; Nova adds no separate per-run limit and never recharges automatically. Other pods and storage also consume this balance.",
      ),
    );
    if (
      Number.isFinite(value.estimated_cost_usd) &&
      Number.isFinite(value.balance_usd) &&
      value.estimated_cost_usd > value.balance_usd
    ) {
      parent.append(
        el(
          "p",
          "nup-warning",
          "The estimated run cost (" +
            money(value.estimated_cost_usd) +
            ") exceeds the current wallet balance. Training can still start if the provider minimum is met, but you may need to add credit manually to finish.",
        ),
      );
    }
    link(
      parent,
      "https://console.runpod.io/user/billing",
      "Open RunPod Billing to add credit",
    );
  }
  function costApproval(parent, preview) {
    const paid = preview?.runner === "runpod";
    let funding = preview?.cost?.funding;
    let update = () => {};
    if (paid) {
      parent.append(
        el(
          "p",
          "nup-warning",
          "This starts paid GPU time using your RunPod wallet. There is no separate per-run spending limit. Watch the live cost and balance in Jobs; recharge manually in RunPod Billing if needed. The pod is stopped when the run finishes or is cancelled, while stored volumes can continue billing.",
        ),
      );
      const fundingBox = el("div");
      parent.append(fundingBox);
      showFunding(fundingBox, funding);
      parent.append(
        button("Recheck RunPod credit", async () => {
          funding = {
            state: "unavailable",
            message: "Checking current RunPod credit…",
          };
          update();
          showFunding(fundingBox, funding);
          try {
            const query = new URLSearchParams();
            if (Number.isFinite(preview.cost?.cost_usd))
              query.set("required_usd", preview.cost.cost_usd);
            if (Number.isFinite(preview.cost?.per_hour))
              query.set("per_hour", preview.cost.per_hour);
            funding = await api("funding?" + query);
          } catch (error) {
            funding = {
              state: "unavailable",
              message: "Balance unavailable, not zero. " + error.message,
            };
          }
          showFunding(fundingBox, funding);
          update();
        }),
      );
    }
    const accepted = check(
      parent,
      paid
        ? "I reviewed the estimate and authorize paid training using my RunPod wallet."
        : "I reviewed this plan and authorize the operation.",
    );
    return {
      accepted,
      bind: (action, blocked = () => false) => {
        update = () => {
          action.disabled =
            !accepted.checked ||
            (paid && funding?.state !== "sufficient") ||
            blocked();
        };
        accepted.onchange = update;
        update();
      },
      read: () => {
        if (!accepted.checked)
          throw Error("Review and confirm this operation first.");
        if (!paid) return undefined;
        if (funding?.state !== "sufficient")
          throw Error(
            "Verify the RunPod startup credit minimum before starting paid training. Add credit in RunPod Billing if needed, then recheck.",
          );
        return { paid: true };
      },
    };
  }
  async function openInstall(candidate) {
    const d = dialog("Review model installation");
    d.content.append(
      el(
        "p",
        "nup-muted",
        "Loading available builds and installed-file headers for this installation workflow…",
      ),
    );
    try {
      const [description, inventory] = await Promise.all([
        api(
          "candidate?" +
            new URLSearchParams({
              id: candidate.id,
              source: candidate.source || "huggingface",
            }),
        ),
        api("inventory"),
      ]);
      if (!d.node.isConnected) return;
      d.content.replaceChildren();
      d.content.append(
        el("h3", "", candidate.id),
        el(
          "p",
          "nup-muted",
          "Choose files, then build a dry-run plan. No download or model change happens until you confirm the reviewed plan.",
        ),
      );
      const builds = list(description.builds).filter(
        (x) => !x.error && x.quants?.length,
      );
      if (!builds.length) {
        messages(
          d.content,
          [
            "No installable GGUF builds were found. Try a different source or candidate.",
          ],
          "blocking",
        );
        details(d.content, "Catalog result", description);
        return;
      }
      const form = el("div"),
        grid = el("div", "nup-grid");
      d.content.append(form);
      form.append(grid);
      const build = select(
          grid,
          "GGUF build",
          builds.map((x) => [x.repo, x.repo]),
          description.suggested?.gguf_repo,
        ),
        quant = select(grid, "Quantization", []),
        projector = select(grid, "Vision projector", []);
      const activate = check(
        form,
        "Make this Nova’s active model after download",
        true,
      );
      form.append(
        el(
          "p",
          "nup-muted",
          "In chat-only mode activation waits for a normal model start and verification. Existing files are quarantined only after the new model is proven loaded.",
        ),
      );
      const lora = select(
          grid,
          "Adapter work after the model download",
          [
            ["none", "No adapter work — adapter off on model switch"],
            ["keep", "Keep current adapter setting — no copy or retraining"],
            ["train", "Create a training job — choose export or paid training"],
          ],
          "none",
        ),
        trainBox = section(form, "Train for the new base");
      const trainInputs = trainingFields(trainBox, candidate.id);
      trainBox.hidden = true;
      const loraHelp = el("p", "nup-action-summary");
      form.append(loraHelp);
      const explainLora = () => {
        trainBox.hidden = lora.value !== "train";
        loraHelp.textContent =
          lora.value === "keep"
            ? "Keeps the current adapter boot setting only. No LoRA files are copied and no training happens. The existing adapter must match the new base model."
            : lora.value === "train"
              ? "Choose the training method below. Export creates files to run later; RunPod actually trains a new adapter after cost confirmation."
              : "The model download performs no adapter work. If you switch models, the personality LoRA is left off; existing files stay where they are unless you explicitly select them for quarantine.";
      };
      lora.onchange = explainLora;
      explainLora();
      const replacement = el("details", "nup-details");
      replacement.append(
        el(
          "summary",
          "",
          "Optional replacements — move to quarantine after verification",
        ),
      );
      const checks = [];
      for (const item of [
        ...list(inventory.models),
        ...list(inventory.projectors),
        ...list(inventory.loras),
      ]) {
        const c = check(
          replacement,
          item.path +
            " · " +
            (item.kind || "model") +
            " · " +
            bytes(item.size) +
            (item.active ? " · active" : "") +
            (item.bound_to ? " · base " + item.bound_to : ""),
        );
        checks.push({ input: c, item });
      }
      if (!checks.length)
        replacement.append(
          el("p", "nup-muted", "No replaceable installed files found."),
        );
      form.append(replacement);
      messages(form, inventory.errors, "warning");
      function populate() {
        const b = builds.find((x) => x.repo === build.value) || builds[0];
        quant.replaceChildren();
        for (const q of b.quants) {
          const o = el("option", "", q.label + " · " + bytes(q.size));
          o.value = q.label;
          quant.append(o);
        }
        const want = description.suggested?.quant;
        if (b.quants.some((q) => q.label === want)) quant.value = want;
        projector.replaceChildren();
        const no = el("option", "", "No projector");
        no.value = "";
        projector.append(no);
        for (const p of list(b.projectors)) {
          const o = el("option", "", p.path + " · " + bytes(p.size));
          o.value = p.path;
          projector.append(o);
        }
        if (
          list(b.projectors).some(
            (p) => p.path === description.suggested?.mmproj,
          )
        )
          projector.value = description.suggested.mmproj;
      }
      build.onchange = populate;
      populate();
      const review = el("div", "nup-plan-review");
      d.content.append(review);
      let currentPlan = null,
        approval = null,
        trainingPreview = null;
      function invalidate() {
        currentPlan = null;
        review.replaceChildren(
          el(
            "p",
            "nup-muted",
            "Choices changed. Build a new plan before installing.",
          ),
        );
      }
      form.addEventListener("input", invalidate);
      form.addEventListener("change", invalidate);
      const makePlan = button("Build dry-run plan", async () => {
        d.error.textContent = "";
        review.replaceChildren(
          el(
            "p",
            "nup-muted",
            "Checking downloads, available disk and compatibility…",
          ),
        );
        currentPlan = null;
        try {
          const rawTraining =
            lora.value === "train" ? trainInputs.read() : null;
          const request = {
            source: candidate.source || "huggingface",
            model_id: candidate.id,
            gguf_repo: build.value,
            quant: quant.value,
            mmproj: projector.value || false,
            activate: activate.checked,
            replace: checks
              .filter((x) => x.input.checked)
              .map((x) => x.item.path),
            lora: {
              mode: lora.value,
              ...(rawTraining ? { train: rawTraining } : {}),
            },
          };
          const fingerprint = JSON.stringify(request);
          form
            .querySelectorAll("input,select,textarea")
            .forEach((n) => (n.disabled = true));
          const plan = await api("plan", request);
          trainingPreview = null;
          if (rawTraining) {
            const quote = await api("train/preview", {
              spec: {
                ...rawTraining,
                output_directory: plan.training?.output_directory,
              },
            });
            const signature = (spec) =>
              JSON.stringify({
                base: spec.base_model_id,
                runner: spec.runner,
                rows: spec.rows,
                hours: spec.estimate_hours,
                gpu: spec.gpu,
                params: Object.entries(spec.params || {}).sort(([a], [b]) =>
                  a.localeCompare(b),
                ),
                data_center_ids: spec.data_center_ids,
                base_model_path: spec.base_model_path,
                output_directory: spec.output_directory,
                data: list(spec.data).map((file) => [
                  file.path,
                  file.sha256,
                  file.rows,
                ]),
              });
            if (!plan.training || signature(quote) !== signature(plan.training))
              throw Error(
                "Training data or parameters changed while reviewing. Build the plan again.",
              );
            trainingPreview = { ...plan.training, cost: quote.cost };
          }
          currentPlan = { plan, fingerprint };
          review.replaceChildren();
          const summary = section(review, "Plan ready for review");
          facts(summary, [
            ["Model", plan.model_id],
            ["Build", plan.gguf_repo],
            ["Quantization", plan.quant],
            ["Download", bytes(plan.download_bytes)],
            ["Free disk", bytes(plan.free_bytes)],
            ["Disk reserve", "5 GiB required by planner"],
            [
              "Activation",
              plan.activate ? "Switch after verification" : "Download only",
            ],
            ["Destination", plan.target_dir],
          ]);
          adapterPlanSummary(summary, plan);
          const effectiveBlocking = [...list(plan.blocking)];
          if (plan.activate && plan.lora?.mode === "keep") {
            for (const item of list(plan.invalidated)) {
              if (item.kind === "lora" && item.active)
                effectiveBlocking.push(
                  "Cannot keep an active adapter trained for another base: " +
                    item.path +
                    ". Choose no adapter work or train a new compatible adapter.",
                );
            }
          }
          messages(summary, effectiveBlocking, "blocking");
          messages(summary, plan.warnings, "warning");
          details(summary, "Files to download", plan.downloads);
          details(summary, "Compatibility and boot settings", {
            compatibility: plan.compatibility,
            boot: plan.boot,
          });
          if (plan.replace?.length)
            details(summary, "Files to quarantine", plan.replace);
          if (plan.invalidated?.length) {
            details(
              summary,
              "Adapters and projectors for another base",
              plan.invalidated,
            );
            summary.append(
              button("Select old LoRAs for replacement and rebuild", () => {
                for (const c of checks)
                  if (
                    c.item.kind === "lora" &&
                    plan.invalidated.some((x) => x.path === c.item.path)
                  )
                    c.input.checked = true;
                invalidate();
                makePlan.click();
              }),
            );
          }
          if (trainingPreview) {
            const training = section(review, "Training review");
            showTrainingPreview(training, trainingPreview);
          }
          approval = costApproval(review, trainingPreview);
          const installButton = button(
            "Confirm and install",
            async () => {
              if (!currentPlan || currentPlan.plan !== plan) return;
              const trainConfirm = approval.read();
              const body = { plan_id: plan.id, confirm: true };
              if (trainConfirm) body.train_confirm = trainConfirm;
              await api("install", body);
              d.node.close();
              showWidget?.("updater");
              await refresh();
              await widget?.refreshJobs();
              report("Installation started. Follow progress in Jobs.");
            },
            "nup-button nup-primary",
          );
          approval.bind(
            installButton,
            () =>
              !!effectiveBlocking.length ||
              !currentPlan ||
              currentPlan.plan !== plan,
          );
          review.append(installButton);
          if (effectiveBlocking.length) approval.accepted.disabled = true;
        } catch (error) {
          review.replaceChildren();
          d.error.textContent = error.message;
        } finally {
          form
            .querySelectorAll("input,select,textarea")
            .forEach((n) => (n.disabled = false));
        }
      });
      form.append(makePlan);
    } catch (error) {
      d.content.replaceChildren();
      d.error.textContent = error.message;
    }
  }

  function renderNotification() {
    if (!noticeRoot || !status) return;
    const candidates = list(status.candidates).filter((c) =>
      list(status.pending).includes(c.id),
    );
    const key = candidates.map((x) => x.id).join("|");
    if (!status.notify || !candidates.length) {
      noticeRoot.hidden = true;
      noticeKey = "";
      return;
    }
    if (key === noticeKey) return;
    noticeKey = key;
    noticeRoot.replaceChildren();
    noticeRoot.hidden = false;
    const first = candidates[0];
    noticeRoot.append(
      el("strong", "", "A model update is available"),
      el(
        "p",
        "",
        first.id +
          (candidates.length > 1
            ? " and " + (candidates.length - 1) + " more"
            : ""),
      ),
    );
    const remember = check(noticeRoot, "Remember my decision");
    const row = el("div", "nup-actions");
    row.append(
      button(
        "Update",
        () => chooseCandidate(first, remember.checked, true),
        "nup-button nup-primary",
      ),
      button("Decline", async () => {
        await api("decision", {
          ids: candidates.map((c) => c.id),
          decision: "decline",
          remember: remember.checked,
        });
        await refresh();
      }),
      button("Later", () => {
        noticeRoot.hidden = true;
      }),
    );
    noticeRoot.append(row);
  }
  window.initNovaUpdaterNotifications = function (options = {}) {
    showWidget = options.showWidget || showWidget;
    if (noticeRoot) return;
    noticeRoot = el("aside", "nup-notification");
    noticeRoot.hidden = true;
    noticeRoot.setAttribute("aria-label", "Model update available");
    document.body.append(noticeRoot);
    const tick = async () => {
      try {
        await refresh();
      } catch (_) {}
      if (!stopped) pollTimer = setTimeout(tick, 30000);
    };
    tick();
    window.addEventListener(
      "pagehide",
      () => {
        stopped = true;
        clearTimeout(pollTimer);
      },
      { once: true },
    );
  };
  window.mountNovaUpdater = function (root) {
    if (root.dataset.updaterMounted) return;
    root.dataset.updaterMounted = "true";
    root.classList.add("nup-root");
    const head = el("header", "nup-head"),
      title = el("div");
    title.append(
      el("h2", "", "Model updates"),
      el(
        "p",
        "nup-muted",
        "Discover models. Review the changes. Keep recovery within reach.",
      ),
    );
    const state = el("span", "nup-state", "Connecting…");
    head.append(title, state);
    const toolbar = el("div", "nup-actions");
    toolbar.append(
      button("Check now", async () => {
        state.textContent = "Checking…";
        await api("check", { force: true });
        await refresh();
      }),
      button("Refresh", refresh),
    );
    const tabs = el("nav", "nup-tabs");
    tabs.setAttribute("aria-label", "Model updater sections");
    const body = el("div", "nup-body"),
      notice = el("p", "nup-notice");
    notice.setAttribute("role", "status");
    root.append(head, toolbar, tabs, notice, body);
    const panels = {},
      tabButtons = {};
    let selected = "updates";
    for (const [id, name] of [
      ["updates", "Updates"],
      ["search", "Find models"],
      ["training", "Train adapters"],
      ["settings", "Settings"],
    ]) {
      const tab = button(name, () => switchTab(id), "nup-tab");
      tab.setAttribute("aria-pressed", String(id === selected));
      tabButtons[id] = tab;
      tabs.append(tab);
      const panel = el("div", "nup-panel");
      panel.hidden = id !== selected;
      panels[id] = panel;
      body.append(panel);
    }
    function switchTab(id) {
      selected = id;
      Object.entries(panels).forEach(([key, p]) => (p.hidden = key !== id));
      Object.entries(tabButtons).forEach(([key, b]) =>
        b.setAttribute("aria-pressed", String(key === id)),
      );
    }
    const overview = section(panels.updates, "Current configuration"),
      recovery = el("div"),
      candidates = el("div"),
      jobList = section(panels.updates, "Jobs");
    panels.updates.append(recovery, candidates, jobList);
    let jobsTimer = null,
      jobsBusy = false,
      knownActiveJobs = new Set();
    async function refreshJobs() {
      if (jobsBusy) return;
      jobsBusy = true;
      try {
        const jobs = await api("jobs"),
          opened = new Set(
            [...jobList.querySelectorAll("details[open]")].map(
              (n) => n.dataset.job,
            ),
          );
        const terminalIds = new Set(
          list(jobs)
            .filter((job) =>
              ["succeeded", "failed", "cancelled"].includes(job.state),
            )
            .map((job) => job.id),
        );
        const refreshBusyStatus =
          [...knownActiveJobs].some((id) => terminalIds.has(id)) ||
          terminalIds.has(status?.busy?.id);
        knownActiveJobs = new Set(
          list(jobs)
            .filter((job) => ["queued", "running"].includes(job.state))
            .map((job) => job.id),
        );
        jobList.replaceChildren(el("h3", "", "Jobs"));
        if (!list(jobs).length)
          jobList.append(
            el("p", "nup-muted", "No update or training jobs yet."),
          );
        for (const job of list(jobs)) {
          const card = section(jobList, job.title || job.kind);
          facts(card, [
            ["Status", job.state],
            ["Step", job.step || "Waiting"],
            [
              "Progress",
              job.percent === null
                ? "Not measured"
                : Number(job.percent).toFixed(1) + "%",
            ],
          ]);
          if (Number.isFinite(job.percent)) {
            const bar = el("progress");
            bar.max = 100;
            bar.value = Math.min(100, Math.max(0, job.percent));
            bar.setAttribute("aria-label", job.title + " progress");
            card.append(bar);
          }
          if (job.error)
            messages(
              card,
              [job.error],
              "blocking",
              job.state === "cancelled" ? "Job cancelled" : "Job failed",
            );
          renderRunPodCost(card, job);
          renderOutcome(card, job);
          if (job.result?.pending)
            messages(card, [job.result.pending], "warning");
          if (job.result?.verified === false && job.result?.installed)
            card.append(
              el(
                "p",
                "nup-warning",
                "Files installed; running-model verification is not complete.",
              ),
            );
          if (job.result?.after?.error)
            messages(
              card,
              [
                "Model installation completed, but training failed: " +
                  job.result.after.error,
              ],
              "warning",
            );
          if (job.result?.after?.cancelled)
            messages(
              card,
              [
                "Follow-up training was cancelled. Review the model installation outcome separately.",
              ],
              "warning",
            );
          if (job.result?.after?.skipped)
            messages(
              card,
              ["Follow-up training was skipped: " + job.result.after.skipped],
              "warning",
            );
          if (["queued", "running"].includes(job.state))
            card.append(
              button("Cancel job", async () => {
                await api("jobs/" + encodeURIComponent(job.id) + "/cancel", {});
                await refreshJobs();
              }),
            );
          const log = details(card, "Log and outcome", {
            log: job.log,
            result: job.result,
          });
          log.dataset.job = job.id;
          log.open = opened.has(job.id);
          if (job.result?.rollback)
            facts(card, [
              [
                "Boot files restored",
                String(job.result.rollback.boot_files_restored),
              ],
              ["Previous restart", job.result.rollback.previous_model_restart],
              [
                "Previous model verified",
                String(job.result.rollback.previous_model_verified),
              ],
            ]);
        }
        // Recover service controls once a live job finishes. Do not rebuild forms
        // or repeat metadata refresh on every unchanged progress poll.
        if (refreshBusyStatus) await refresh();
      } catch (error) {
        if (!jobList.querySelector(".nup-job-error"))
          jobList.append(el("p", "nup-job-error", error.message));
      } finally {
        jobsBusy = false;
      }
    }
    widget = { root, notice, state, refreshJobs };
    function renderStatus(value) {
      state.textContent =
        {
          ok: "Check complete",
          offline: "Catalog offline",
          checking: "Checking…",
          disabled: "Checks disabled",
          "never-checked": "Not checked yet",
          "unknown-current": "Current model unknown",
          error: "Check failed",
        }[value.state] ||
        value.state ||
        "Ready";
      overview.replaceChildren(el("h3", "", "Current configuration"));
      facts(overview, [
        [
          "Configured model (next start)",
          value.current?.label || value.current?.model_path || "Unknown",
        ],
        ["Quantization", value.current?.quant || "Unknown"],
        ["Last check", date(value.checked_at)],
      ]);
      if (value.checked_current?.label)
        facts(overview, [
          ["Model compared by last catalog check", value.checked_current.label],
        ]);
      if (value.catalog_stale)
        messages(
          overview,
          [
            "The configured model changed after the last catalog check. Check again before deciding whether another update is available.",
          ],
          "warning",
        );
      if (value.message) overview.append(el("p", "nup-muted", value.message));
      messages(overview, value.warning ? [value.warning] : [], "warning");
      candidates.replaceChildren();
      if (!value.candidates?.length)
        candidates.append(
          el(
            "p",
            "nup-muted",
            "No candidate updates to review. Use Find models for a manual search.",
          ),
        );
      for (const candidate of list(value.candidates))
        candidateCard(candidates, candidate, true);
      recovery.replaceChildren();
      if (value.pending_install) {
        const box = section(
          recovery,
          "An installation needs verification",
          "A pending switch remains recoverable. Restored settings and a verified running model are separate outcomes.",
        );
        details(box, "Pending installation", value.pending_install);
        const row = el("div", "nup-actions");
        row.append(
          button("Verify loaded model and finish", () =>
            confirmAction(
              "Finish pending installation",
              "This verifies the selected model is loaded, then quarantines replacements. Start Nova normally first if it was installed in chat-only mode.",
              () => api("finish", {}),
            ),
          ),
          button("Roll back pending switch", () =>
            confirmAction(
              "Roll back pending switch",
              "Restore the prior boot configuration. Review the resulting restart and verification status before assuming Nova is running again.",
              () => api("rollback", {}),
            ),
          ),
        );
        if (value.busy) {
          row
            .querySelectorAll("button")
            .forEach((button) => (button.disabled = true));
          box.append(
            el(
              "p",
              "nup-warning",
              "Wait for the active update or training job to finish before using recovery controls.",
            ),
          );
        }
        box.append(row);
      }
      renderSettingsStatus(value);
    }

    const searchBox = section(
      panels.search,
      "Find a model",
      "Search metadata across sources. Ollama results are links only. Opening an install review reads installed-file headers.",
    );
    const searchGrid = el("div", "nup-grid");
    searchBox.append(searchGrid);
    const source = select(
        searchGrid,
        "Source",
        [
          ["huggingface", "Hugging Face"],
          ["modelscope", "ModelScope"],
          ["ollama", "Ollama (links only)"],
        ],
        "huggingface",
      ),
      query = field(searchGrid, "Search terms", "search", "Qwen"),
      author = field(searchGrid, "Author (optional)"),
      min = field(searchGrid, "Minimum billions of parameters", "number", "27"),
      max = field(searchGrid, "Maximum billions of parameters", "number", "32"),
      license = field(
        searchGrid,
        "Licenses (comma separated)",
        "text",
        "apache-2.0,mit",
      ),
      format = select(searchGrid, "Format", [
        ["", "Any"],
        ["gguf", "GGUF"],
        ["safetensors", "Safetensors"],
      ]),
      sort = select(searchGrid, "Sort by", [
        ["created", "Newest release"],
        ["modified", "Recently updated"],
        ["downloads", "Downloads"],
        ["likes", "Likes"],
        ["params", "Parameter count"],
      ]);
    const advanced = el("details", "nup-details");
    advanced.append(el("summary", "", "More filters"));
    const dense = check(advanced, "Dense models only", true),
      newer = check(advanced, "Newer than Nova’s current model"),
      quantized = check(advanced, "Include quantized repositories", true),
      pipeline = field(advanced, "Pipeline (optional)", "text", ""),
      limit = field(advanced, "Result limit", "number", "30");
    limit.min = "1";
    limit.max = "200";
    searchBox.append(advanced);
    const searchResults = el("div");
    panels.search.append(searchResults);
    searchBox.append(
      button("Search metadata", async () => {
        const params = new URLSearchParams({
          source: source.value,
          q: query.value.trim(),
          author: author.value.trim(),
          license: license.value.trim(),
          format: format.value,
          sort: sort.value,
          dense: String(dense.checked),
          newer: String(newer.checked),
          include_quantized: String(quantized.checked),
          pipeline: pipeline.value.trim(),
          limit: limit.value,
        });
        if (min.value) params.set("min_b", min.value);
        if (max.value) params.set("max_b", max.value);
        searchResults.replaceChildren(el("p", "nup-muted", "Searching…"));
        try {
          const results = await api("search?" + params);
          searchResults.replaceChildren(
            el("p", "nup-muted", results.count + " results"),
          );
          for (const result of list(results.results))
            candidateCard(
              searchResults,
              { ...result, source: results.source },
              false,
            );
        } catch (error) {
          searchResults.replaceChildren(el("p", "nup-blocking", error.message));
        }
      }),
    );

    const trainBox = section(
      panels.training,
      "Train a new adapter",
      "Preview the recipe and dataset checks first. Export creates a reproducible bundle without starting GPU time. Trained adapters are installed without activation so you can compare epochs.",
    );
    const training = trainingFields(trainBox),
      trainingReview = el("div");
    trainBox.append(
      button("Preview training", async () => {
        trainingReview.replaceChildren();
        const spec = training.read(),
          fingerprint = JSON.stringify(spec);
        trainBox
          .querySelectorAll("input,select,textarea")
          .forEach((n) => (n.disabled = true));
        try {
          const preview = await api("train/preview", { spec });
          if (fingerprint !== JSON.stringify(training.read()))
            throw Error(
              "Training inputs changed during preview. Preview again.",
            );
          if (typeof preview.review_id !== "string" || !preview.review_id)
            throw Error(
              "The server did not bind this preview to a training review. Update the server and preview again.",
            );
          let reviewedId = preview.review_id;
          const box = section(trainingReview, "Training preview");
          showTrainingPreview(box, preview);
          const approval = costApproval(box, preview),
            run = button(
              preview.runner === "runpod"
                ? "Confirm paid training"
                : "Confirm and export bundle",
              async () => {
                if (!reviewedId)
                  throw Error(
                    "This training review is no longer current. Preview again.",
                  );
                const confirm = approval.read();
                await api("train", {
                  review_id: reviewedId,
                  ...(confirm ? { confirm } : {}),
                });
                reviewedId = null;
                trainingReview.replaceChildren(
                  el(
                    "p",
                    "nup-muted",
                    "Job started. Follow it in Updates → Jobs.",
                  ),
                );
                switchTab("updates");
                await refreshJobs();
                report(
                  preview.runner === "runpod"
                    ? "Training started. Follow progress in Jobs."
                    : "Training bundle export started. Follow progress in Jobs.",
                );
              },
              "nup-button nup-primary",
            );
          approval.bind(run, () => !reviewedId);
          box.append(run);
          const invalidate = () => {
            reviewedId = null;
            run.disabled = true;
            trainingReview.replaceChildren(
              el(
                "p",
                "nup-muted",
                "Training inputs changed. Preview again before starting.",
              ),
            );
            trainBox.removeEventListener("input", invalidate);
            trainBox.removeEventListener("change", invalidate);
          };
          trainBox.addEventListener("input", invalidate, { once: true });
          trainBox.addEventListener("change", invalidate, { once: true });
        } finally {
          trainBox
            .querySelectorAll("input,select,textarea")
            .forEach((n) => (n.disabled = false));
        }
      }),
    );
    panels.training.append(trainingReview);
    const manual = section(
      panels.training,
      "Import already-trained adapter files",
      "Checks SHA256SUMS.txt, then copies completed GGUF adapters beside their base model. Reproducibility inputs belong in Training Files; finished adapters do not. No training or activation happens during this import. Uses the base-model specification above.",
    );
    const folder = field(manual, "Completed output folder"),
      importConfirm = check(
        manual,
        "I reviewed this folder and want to install its verified adapters.",
      );
    manual.append(
      button("Install completed adapters", async () => {
        if (!importConfirm.checked)
          throw Error("Confirm the completed-folder import first.");
        const result = await api("train/install", {
          spec: training.read(),
          folder: folder.value.trim(),
        });
        const outcome = section(manual, "Import result");
        renderOutcome(outcome, { kind: "import", state: "succeeded", result });
        details(outcome, "Verification details", result);
        importConfirm.checked = false;
      }),
    );
    const adapters = section(
      panels.training,
      "Installed adapters",
      "Inventory stays unloaded until you open this workflow. Activation is a separate explicit action.",
    );
    adapters.append(
      button("Open installed adapters", async () => {
        const inv = await api("inventory");
        const d = dialog("Activate an installed adapter");
        const choices = list(inv.loras);
        if (!choices.length) {
          d.content.append(
            el("p", "nup-muted", "No installed adapters found."),
          );
          return;
        }
        const choice = select(
            d.content,
            "Adapter",
            choices.map((x) => [
              x.path,
              x.path +
                " · base " +
                (x.bound_to || "unknown") +
                (x.active ? " · active" : ""),
            ]),
          ),
          scale = field(d.content, "Scale", "number", "1");
        scale.step = "0.1";
        const restart = check(
            d.content,
            "Restart now and verify the adapter loaded",
          ),
          confirm = check(
            d.content,
            "I checked the adapter’s base model and want to activate it.",
          );
        d.content.append(
          button("Activate adapter", async () => {
            if (!confirm.checked)
              throw Error("Confirm adapter activation first.");
            const result = await api("lora/activate", {
              path: choice.value,
              scale: Number(scale.value),
              restart: restart.checked,
            });
            d.content.append(
              el(
                "p",
                "nup-action-summary",
                result.verified
                  ? "The model server confirmed this adapter is loaded."
                  : "The adapter boot setting is saved. It has not been verified running; it takes effect at the next model start.",
              ),
            );
            fileLocations(d.content, "Selected adapter", [choice.value]);
            details(d.content, "Activation result", result);
            confirm.checked = false;
          }),
        );
      }),
    );

    const settingsBox = section(panels.settings, "Update checks"),
      settingsGrid = el("div", "nup-grid");
    settingsBox.append(settingsGrid);
    const enabled = check(
        settingsBox,
        "Check for model updates when Nova Chat starts",
        true,
      ),
      ttl = field(settingsGrid, "Cache lifetime (hours)", "number", "12"),
      settingMin = field(
        settingsGrid,
        "Minimum model size (B)",
        "number",
        "27",
      ),
      settingMax = field(
        settingsGrid,
        "Maximum model size (B)",
        "number",
        "32",
      ),
      settingLicense = field(
        settingsGrid,
        "Permitted licenses",
        "text",
        "apache-2.0,mit",
      ),
      settingAuthors = field(
        settingsGrid,
        "Authors (comma separated)",
        "text",
        "Qwen",
      ),
      settingSource = select(
        settingsGrid,
        "Check source",
        [
          ["huggingface", "Hugging Face"],
          ["modelscope", "ModelScope"],
        ],
        "huggingface",
      );
    let settingsLoaded = false;
    settingsBox.append(
      button("Save check settings", async () => {
        const cfg = {
          enabled: enabled.checked,
          ttl_hours: Number(ttl.value),
          min_b: Number(settingMin.value),
          max_b: Number(settingMax.value),
          licenses: settingLicense.value
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean),
          authors: settingAuthors.value
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean),
          source: settingSource.value,
        };
        if (
          !Number.isFinite(cfg.ttl_hours) ||
          cfg.ttl_hours <= 0 ||
          !Number.isFinite(cfg.min_b) ||
          !Number.isFinite(cfg.max_b) ||
          cfg.min_b < 0 ||
          cfg.max_b < cfg.min_b
        )
          throw Error("Check lifetime and model-size limits.");
        await api("settings", cfg);
        await refresh();
        report("Update-check settings saved.");
      }),
    );
    const credentials = section(
      panels.settings,
      "RunPod and Hugging Face credentials",
      "Values are sent only when you save and are never stored in this browser. Blank fields leave existing values unchanged; use the clear checkboxes to remove them.",
    );
    credentials.append(
      el(
        "p",
        "nup-muted",
        "A Google sign-in in your browser does not configure Nova's RunPod API access. Add your own RunPod API key here to check credit or run training. Leave Existing RunPod pod ID blank to create a new pod in the selected data centers.",
      ),
    );
    const creditCard = section(
      panels.settings,
      "RunPod funding",
      "Checks prepaid credit only when requested. It cannot recharge your account.",
    );
    const creditResult = el("div");
    creditCard.append(
      button("Check RunPod credit", async () => {
        creditResult.replaceChildren(el("p", "nup-muted", "Checking credit…"));
        try {
          showFunding(creditResult, await api("funding"));
        } catch (error) {
          showFunding(creditResult, {
            state: "unavailable",
            message: "Balance unavailable, not zero. " + error.message,
          });
        }
      }),
      creditResult,
    );
    const credentialStatus = el("p", "nup-muted");
    credentials.append(credentialStatus);
    const credentialInputs = {};
    for (const [key, label] of [
      ["runpod_api_key", "RunPod API key"],
      ["hf_token", "Hugging Face token (optional)"],
      ["ssh_key_path", "SSH private key path"],
      ["pod_id", "Existing RunPod pod ID"],
    ]) {
      const input = field(
        credentials,
        label,
        (key.includes("key") && key !== "ssh_key_path") || key === "hf_token"
          ? "password"
          : "text",
      );
      input.autocomplete = "off";
      credentialInputs[key] = {
        input,
        clear: check(credentials, "Clear saved " + label.toLowerCase()),
      };
    }
    credentials.append(
      button("Save credentials", async () => {
        const body = {};
        for (const [key, value] of Object.entries(credentialInputs)) {
          if (value.clear.checked) body[key] = "";
          else if (value.input.value.trim())
            body[key] = value.input.value.trim();
        }
        if (!Object.keys(body).length)
          throw Error("Enter a value or select a field to clear.");
        await api("credentials", body);
        for (const value of Object.values(credentialInputs)) {
          value.input.value = "";
          value.clear.checked = false;
        }
        await refresh();
        report(
          "Credential settings saved. Secret fields cleared from this form.",
        );
      }),
    );
    function renderSettingsStatus(value) {
      if (!settingsLoaded && value.settings) {
        const cfg = value.settings;
        enabled.checked = cfg.enabled !== false;
        ttl.value = cfg.ttl_hours ?? 12;
        settingMin.value = cfg.min_b ?? 27;
        settingMax.value = cfg.max_b ?? 32;
        settingLicense.value = list(cfg.licenses).join(",");
        settingAuthors.value = list(cfg.authors).join(",");
        settingSource.value = cfg.source || "huggingface";
        settingsLoaded = true;
      }
      if (value.credentials)
        credentialStatus.textContent = Object.entries({
          runpod_api_key: "RunPod key",
          hf_token: "HF token",
          ssh_key_path: "SSH key",
          pod_id: "Pod",
        })
          .map(
            ([key, label]) =>
              label +
              ": " +
              (value.credentials[key] ? "configured" : "not set"),
          )
          .join(" · ");
    }
    listeners.add(renderStatus);
    if (status) renderStatus(status);
    else refresh().catch((error) => report(error.message));
    refreshJobs();
    const tick = async () => {
      if (root.getClientRects().length && !document.hidden) await refreshJobs();
      if (!stopped) jobsTimer = setTimeout(tick, 3500);
    };
    jobsTimer = setTimeout(tick, 3500);
    window.addEventListener(
      "pagehide",
      () => {
        clearTimeout(jobsTimer);
        listeners.delete(renderStatus);
      },
      { once: true },
    );
  };
})();
