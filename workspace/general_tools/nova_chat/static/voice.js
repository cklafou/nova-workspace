/* @nova: Provide explicit voice controls inside Conversation without starting audio or changing layouts on page load. */
(() => {
  "use strict";
  const ACTIVE = new Set(["starting", "listening", "waiting", "thinking", "speaking", "testing", "stopping"]);
  const LABELS = {off: "Off", stopped: "Off", idle: "Ready", ready: "Ready", starting: "Starting…",
    listening: "Listening", waiting: "Waiting for Nova", thinking: "Nova is thinking", speaking: "Speaking",
    testing: "Testing audio", stopping: "Stopping…", error: "Needs attention"};
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const button = (label, id, action) => {
    const node = element("button", "nv-button", label);
    node.id = id;
    node.type = "button";
    node.addEventListener("click", action);
    return node;
  };
  const errorText = (data, fallback) => {
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) return data.detail.map(item => item.msg || String(item)).join("; ");
    return data?.error || data?.message || fallback;
  };

  window.initNovaConversationVoice = function () {
    const chat = document.getElementById("chat-main");
    if (!chat || document.getElementById("conversation-voice")) return null;
    const root = element("section", "nc-conversation-voice");
    root.id = "conversation-voice";
    root.setAttribute("aria-label", "Conversation voice controls");
    let status = null, lifecycle = window.novaLifecycleState || null;
    let acting = false, fetching = false, devicesLoading = false, disposed = false;
    let stale = false, unavailable = false, actionError = "", revision = 0, timer = null;
    let configurationDirty = false, deviceLists = null;

    const bar = element("div", "nv-bar");
    const identity = element("div", "nv-identity");
    const stateText = element("span", "nv-state", "Checking voice…");
    stateText.id = "voice-state";
    stateText.setAttribute("role", "status");
    stateText.setAttribute("aria-live", "polite");
    identity.append(element("strong", "nv-title", "Voice"), stateText);
    const toggle = button("Start voice", "voice-toggle", () => {
      if (!toggle.disabled) runAction(active() ? "/stop" : "/start", {});
    });
    const microphone = button("Mute mic", "voice-microphone-mute", () => {
      if (!microphone.disabled) runAction("/mute", {microphone: !status.microphone_muted});
    });
    const output = button("Mute voice", "voice-output-mute", () => {
      if (!output.disabled) runAction("/mute", {output: !status.output_muted});
    });
    microphone.title = "Pause conversation microphone input; use Stop voice to cancel an audio test";
    output.title = "Mute spoken output during a voice conversation; use Stop voice to cancel an audio test";
    bar.append(identity, toggle, microphone, output);

    const notice = element("p", "nv-notice");
    notice.id = "voice-notice";
    notice.setAttribute("role", "status");
    toggle.setAttribute("aria-describedby", notice.id);
    const caption = element("div", "nv-caption");
    const captionText = element("span", "nv-caption-text");
    const audit = element("span", "nv-audit");
    caption.append(captionText, audit);

    const details = element("details", "nv-details");
    details.append(element("summary", "", "Devices & tests"));
    const detailsBody = element("div", "nv-details-body");
    const help = element("p", "nv-help", "Audio starts only when requested. Apply device changes while voice is stopped.");
    const backend = element("p", "nv-help");
    backend.id = "voice-backend";
    const devices = element("div", "nv-device-grid");
    function selector(title, id) {
      const label = element("label", "nv-device", title);
      label.setAttribute("for", id);
      const select = element("select");
      select.id = id;
      select.setAttribute("aria-label", title);
      select.addEventListener("change", () => {configurationDirty = true; paint();});
      label.append(select);
      devices.append(label);
      return select;
    }
    const inputDevice = selector("Microphone", "voice-input-device");
    const outputDevice = selector("Speakers / headphones", "voice-output-device");
    const deviceActions = element("div", "nv-device-actions");
    const findDevices = button("Find audio devices", "voice-find-devices", loadDevices);
    const applyDevices = button("Apply devices", "voice-apply-devices", () => {
      if (!applyDevices.disabled) runAction("/config", {
        input_device: Number(inputDevice.value), output_device: Number(outputDevice.value)
      }, true);
    });
    deviceActions.append(findDevices, applyDevices);
    const testActions = element("div", "nv-tests");
    const testMic = button("Test microphone", "voice-test-microphone", () => {
      if (!testMic.disabled) runAction("/test", {kind: "microphone"});
    });
    const testSpeaker = button("Test speaker", "voice-test-speaker", () => {
      if (!testSpeaker.disabled) runAction("/test", {kind: "speaker"});
    });
    testMic.title = "Record a short microphone test; Stop voice ends the test early";
    testSpeaker.title = "Play a short test through the selected output";
    testActions.append(testMic, testSpeaker);
    const testResult = element("p", "nv-test-result");
    testResult.id = "voice-test-result";
    testResult.setAttribute("role", "status");
    const diagnostic = element("p", "nv-test-result");
    diagnostic.id = "voice-diagnostic";
    diagnostic.setAttribute("role", "status");
    const transcript = element("p", "nv-transcript");
    transcript.id = "voice-transcript";
    const audioActions = element("div", "nv-audio-actions");
    audioActions.append(deviceActions, testActions);
    detailsBody.append(help, backend, devices, audioActions, testResult, diagnostic, transcript);
    details.append(detailsBody);
    root.append(bar, notice, caption, details);
    const composer = document.getElementById("input-area");
    if (composer?.parentElement === chat) chat.insertBefore(root, composer);
    else chat.append(root);

    function active() {
      return !!status?.running || ACTIVE.has(status?.state);
    }
    function novaOn() {
      return lifecycle?.state === "on" && !lifecycle.pending && !lifecycle.busy;
    }
    function setDeviceOptions(select, list, selected) {
      const wanted = Number.isInteger(Number(selected)) ? Number(selected) : -1;
      select.replaceChildren();
      const add = (value, label) => {
        const option = element("option", "", label);
        option.value = String(value);
        select.append(option);
      };
      const defaultDevice = (list || []).find(device => device.default);
      add(-1, defaultDevice ? "System default — " + defaultDevice.name : "System default");
      for (const device of list || []) {
        if (Number.isInteger(device.id) && device.id !== -1)
          add(device.id, device.name + (device.default ? " (default)" : ""));
      }
      if (wanted !== -1 && !(list || []).some(device => device.id === wanted))
        add(wanted, "Configured device #" + wanted + " (refresh to verify)");
      select.value = String(wanted);
    }
    function syncDevices() {
      if (configurationDirty) return;
      setDeviceOptions(inputDevice, deviceLists?.inputs, status?.settings?.input_device ?? -1);
      setDeviceOptions(outputDevice, deviceLists?.outputs, status?.settings?.output_device ?? -1);
    }
    function paint() {
      const inUse = active();
      const caps = status?.capabilities || {};
      const busy = acting || status?.state === "stopping";
      root.dataset.state = stale ? "unavailable" : status?.state || "off";
      stateText.textContent = stale ? "Status unavailable" : unavailable ? "Voice unavailable" :
        LABELS[status?.state] || (status?.state ? String(status.state) : "Checking voice…");
      if (!stale && status?.state === "listening" && status.microphone_muted) stateText.textContent = "Mic muted";
      toggle.textContent = acting ? "Working…" : inUse ? "Stop voice" : "Start voice";
      toggle.disabled = busy || !status || unavailable || (!inUse && (stale || !status.available || !novaOn() || configurationDirty));
      toggle.setAttribute("aria-busy", String(acting));
      microphone.hidden = caps.microphone_mute !== true;
      output.hidden = caps.output_mute !== true;
      microphone.textContent = status?.microphone_muted ? "Unmute mic" : "Mute mic";
      output.textContent = status?.output_muted ? "Unmute voice" : "Mute voice";
      microphone.setAttribute("aria-pressed", String(!!status?.microphone_muted));
      output.setAttribute("aria-pressed", String(!!status?.output_muted));
      microphone.disabled = output.disabled = busy || stale || !inUse || unavailable || status?.state === "testing";
      testMic.disabled = busy || inUse || stale || unavailable || caps.microphone_test !== true || configurationDirty;
      testSpeaker.disabled = busy || inUse || stale || unavailable || caps.speaker_test !== true || configurationDirty;
      inputDevice.disabled = outputDevice.disabled = busy || inUse;
      findDevices.disabled = busy || devicesLoading || unavailable;
      findDevices.textContent = devicesLoading ? "Finding devices…" : deviceLists ? "Refresh devices" : "Find audio devices";
      applyDevices.disabled = busy || inUse || !status || !configurationDirty || stale || unavailable;
      const reason = actionError || (configurationDirty ? "Apply device changes before starting voice or testing audio." : "") || (stale ? "Voice status could not be refreshed. The last known state is " +
        (LABELS[status?.state] || status?.state || "unknown") + "." : "") || status?.error ||
        (!inUse && status?.available && !novaOn() ? "Start Nova above to talk with her. Audio tests can run while she is off." : "") || status?.reason ||
        (!inUse && !novaOn() ? "Start Nova above to talk with her. Audio tests can run while she is off." : "");
      notice.textContent = reason;
      notice.hidden = !reason;
      notice.dataset.error = String(!!actionError || !!status?.error || stale);
      const voiceName = {windows: "Windows system voice (temporary)", chatterbox: "Chatterbox", llamacpp: "Local model voice"}[status?.backends?.output];
      backend.textContent = voiceName ? "Speaking voice: " + voiceName : "";
      backend.hidden = !voiceName;
      const latest = status?.last_caption;
      caption.hidden = !latest?.text;
      captionText.textContent = latest?.text || "";
      const auditState = latest?.audit?.status || "NOT_RUN";
      audit.textContent = "Audit: " + auditState;
      audit.dataset.status = auditState;
      audit.title = latest?.audit?.reason || "Delivered text is not necessarily witness-approved.";
      const result = status?.test_result;
      const metrics = [];
      if (Number.isFinite(result?.peak)) metrics.push("Peak: " + result.peak.toFixed(3));
      if (Number.isFinite(result?.rms)) metrics.push("RMS: " + result.rms.toFixed(3));
      testResult.textContent = result ? [result.message || result.state || "", ...metrics,
        result.transcript ? "Heard: " + result.transcript : ""].filter(Boolean).join(" · ") : "";
      testResult.hidden = !testResult.textContent;
      const diagnostics = status?.diagnostics;
      diagnostic.textContent = Array.isArray(diagnostics) && diagnostics.length ? "Audio note: " + diagnostics[diagnostics.length - 1] : "";
      diagnostic.hidden = !diagnostic.textContent;
      transcript.textContent = status?.last_transcript ? "Last heard: " + status.last_transcript : "";
      transcript.hidden = !transcript.textContent;
    }
    async function request(path, body) {
      const response = await fetch("/api/voice" + path, {
        method: body === undefined ? "GET" : "POST", cache: "no-store",
        ...(body === undefined ? {} : {headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)}),
        signal: AbortSignal.timeout(15000)
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = Error(errorText(data, "Voice request failed (" + response.status + ")."));
        error.status = response.status;
        throw error;
      }
      return data;
    }
    function accept(next) {
      if (!next || typeof next.state !== "string") throw Error("Voice service returned an invalid status.");
      status = next;
      if (stale) actionError = "";
      stale = unavailable = false;
      syncDevices();
      paint();
    }
    async function refresh() {
      if (fetching || disposed || acting) return;
      const currentRevision = revision;
      fetching = true;
      try {
        const next = await request("/status");
        if (!disposed && revision === currentRevision) accept(next);
      } catch (error) {
        if (disposed || revision !== currentRevision) return;
        stale = true;
        unavailable = error.status === 404;
        actionError = unavailable ? "Restart Nova Chat to enable voice controls." : error.message;
        paint();
      } finally {
        fetching = false;
      }
    }
    async function runAction(path, body, applied = false) {
      if (acting || disposed) return;
      acting = true;
      actionError = "";
      revision += 1;
      paint();
      try {
        const next = await request(path, body);
        if (disposed) return;
        if (applied) configurationDirty = false;
        accept(next);
      } catch (error) {
        if (!disposed) actionError = error.message;
      } finally {
        acting = false;
        if (!disposed) paint();
      }
    }
    async function loadDevices() {
      if (devicesLoading || disposed || findDevices.disabled) return;
      devicesLoading = true;
      actionError = "";
      paint();
      try {
        const next = await request("/devices");
        if (next.error) throw Error(next.error);
        if (!Array.isArray(next.inputs) || !Array.isArray(next.outputs)) throw Error("Audio device list is unavailable.");
        if (disposed) return;
        deviceLists = next;
        const input = configurationDirty ? inputDevice.value : status?.settings?.input_device ?? -1;
        const output = configurationDirty ? outputDevice.value : status?.settings?.output_device ?? -1;
        setDeviceOptions(inputDevice, next.inputs, input);
        setDeviceOptions(outputDevice, next.outputs, output);
      } catch (error) {
        if (!disposed) actionError = error.message;
      } finally {
        devicesLoading = false;
        if (!disposed) paint();
      }
    }
    const onLifecycle = event => {lifecycle = event.detail; paint();};
    window.addEventListener("nova:lifecycle", onLifecycle);
    const tick = async () => {
      await refresh();
      if (!disposed) timer = setTimeout(tick, active() ? 1200 : 5000);
    };
    function destroy() {
      disposed = true;
      clearTimeout(timer);
      window.removeEventListener("nova:lifecycle", onLifecycle);
    }
    syncDevices();
    paint();
    tick();
    window.addEventListener("pagehide", destroy, {once: true});
    return {refresh, destroy, root, controls: {toggle, microphone, output, findDevices, applyDevices,
      inputDevice, outputDevice, testMic, testSpeaker, stateText, notice, captionText, audit, testResult, transcript}};
  };
  const init = () => window.initNovaConversationVoice();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, {once: true});
  else init();
})();
