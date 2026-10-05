// @nova: Mount a dockable voice call widget with explicit audio controls and truthful call, delivery and playback status.
(() => {
  "use strict";
  const ACTIVE = new Set(["starting", "listening", "hearing", "finishing_turn", "recognizing", "transcribing", "waiting", "thinking", "speaking", "testing", "stopping"]);
  const LABELS = {off: "Ready to call", stopped: "Ready to call", idle: "Ready", ready: "Ready", starting: "Connecting…",
    listening: "Listening", hearing: "Hearing you", finishing_turn: "Finishing your turn", microphone_muted: "Microphone muted", output_muted: "Speaker muted", recognizing: "Recognizing speech", transcribing: "Recognizing speech", waiting: "Waiting for Nova",
    thinking: "Nova is thinking", speaking: "Speaking", testing: "Testing audio", stopping: "Ending…", error: "Needs attention"};
  const mounts = new WeakMap();
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

  window.mountNovaVoice = function (host) {
    if (!host) return null;
    if (mounts.has(host)) return mounts.get(host);
    const root = element("section", "nv-voice");
    root.id = "nova-voice";
    root.setAttribute("aria-label", "Voice call with Nova");
    let status = null, lifecycle = window.novaLifecycleState || null;
    let acting = false, fetching = false, devicesLoading = false, disposed = false;
    let stale = false, unavailable = false, actionError = "", revision = 0, timer = null;
    let configurationDirty = false, deviceLists = null;

    const call = element("div", "nv-call");
    const identity = element("div", "nv-identity");
    const orb = element("div", "nv-orb", "✦");
    orb.setAttribute("aria-hidden", "true");
    const hint = element("p", "nv-call-hint", "Start a call when you are ready.");
    const bar = element("div", "nv-call-actions");
    const muteStates = element("div", "nv-mute-states");
    muteStates.setAttribute("role", "status");
    muteStates.setAttribute("aria-live", "polite");
    const microphoneState = element("span", "nv-mute-state");
    microphoneState.id = "voice-microphone-state";
    const outputState = element("span", "nv-mute-state");
    outputState.id = "voice-output-state";
    muteStates.append(microphoneState, outputState);
    const muteWarning = element("p", "nv-mute-warning");
    muteWarning.id = "voice-mute-warning";
    const pauseAllowance = element("p", "nv-pause-allowance");
    pauseAllowance.id = "voice-pause-allowance";
    const stateText = element("span", "nv-state", "Checking voice…");
    stateText.id = "voice-state";
    stateText.setAttribute("role", "status");
    stateText.setAttribute("aria-live", "polite");
    identity.append(element("span", "nv-eyebrow", "VOICE CALL"), orb, element("h2", "nv-title", "Nova"), stateText, hint);
    const toggle = button("Call Nova", "voice-toggle", () => {
      if (!toggle.disabled) runAction(active() ? "/stop" : "/start", {});
    });
    const microphone = button("Mute mic", "voice-microphone-mute", () => {
      if (!microphone.disabled) runAction("/mute", {microphone: !status.microphone_muted});
    });
    const output = button("Mute speaker", "voice-output-mute", () => {
      if (!output.disabled) runAction("/mute", {output: !status.output_muted});
    });
    microphone.title = "Pause conversation microphone input; use Stop test to cancel an audio test";
    output.title = "Mute spoken output during a voice conversation; use Stop test to cancel an audio test";
    bar.append(microphone, toggle, output);
    call.append(identity, muteStates, muteWarning, bar, pauseAllowance);

    const notice = element("p", "nv-notice");
    notice.id = "voice-notice";
    notice.setAttribute("role", "status");
    toggle.setAttribute("aria-describedby", notice.id);
    const caption = element("div", "nv-caption");
    const captionText = element("span", "nv-caption-text");
    const audit = element("span", "nv-audit");
    caption.append(captionText, audit);

    const details = element("details", "nv-details");
    details.append(element("summary", "", "Settings & tests"));
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
    testMic.title = "Record a short microphone test; Stop test ends the test early";
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
    const trace = element("pre", "nv-trace");
    trace.id = "voice-trace";
    const traceDetails = element("details", "nv-trace-details");
    traceDetails.append(element("summary", "", "Delivery & playback details"), trace, diagnostic);
    detailsBody.append(help, backend, devices, audioActions, testResult, traceDetails);
    details.append(detailsBody);
    const conversation = element("details", "nv-captions");
    conversation.append(element("summary", "", "Latest words"), transcript, caption);
    const delivery = element("p", "nv-delivery");
    delivery.id = "voice-delivery";
    delivery.setAttribute("role", "status");
    root.append(call, notice, delivery, conversation, details);
    host.replaceChildren(root);

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
    function presentation() {
      let state = status?.state || "off";
      const turn = status?.last_turn, playback = status?.last_playback;
      const sameRequest = playback && (!turn?.request_id || playback.request_id === turn.request_id);
      // Old-turn playback must not relabel a newer request. API submission is not proof of audibility.
      const relevantPlayback = sameRequest && (!turn?.message_id || !playback.message_id || playback.message_id === turn.message_id);
      const capturing = ["hearing", "finishing_turn", "recognizing", "transcribing"].includes(state);
      let progress = "";
      if (turn?.phase === "delayed") progress = "Nova is taking longer than usual. Your request is still waiting for a reply.";
      else if (turn?.phase === "queued") progress = "Your turn is queued. " + (turn.why || "Nova is finishing another task.");
      else if (turn?.phase === "segment") progress = turn.eligible === false
        ? "Delivered part was not spoken: " + (turn.why || "not eligible for speech")
        : "Part " + (turn.segment_index || "") + " delivered · Nova is continuing";
      else if (turn?.phase === "end" && turn.segment_count > 0) progress = "Turn complete · " + turn.segment_count + " delivered parts (not replayed)";
      else if (turn?.phase === "end" && turn.eligible === false) progress = "Reply was not spoken: " + (turn.why || turn.delivery || "not eligible for speech");
      else if (["interrupted", "expired", "dropped"].includes(turn?.phase)) progress = "Turn ended: " + (turn.why || turn.phase);
      else if (turn?.phase === "end" && turn.queued_units > 0) progress = "Reply received · preparing spoken output";
      if (!capturing && relevantPlayback && turn?.eligible !== false) {
        if (playback.phase === "requested") {progress = "Preparing voice output…"; if (state === "speaking") state = "preparing";}
        if (playback.phase === "start") {
          progress = playback.clock === "playback" ? "Audio sent to the selected output" : "Voice playback process started";
          if (active() && !["testing", "stopping"].includes(state)) state = playback.clock === "playback" ? "speaking" : "output_requested";
        }
        if (playback.phase === "end") {
          const outcomes = {played: "Audio playback completed", completed: "Voice process completed", cut: "Spoken output interrupted",
            skipped: "Spoken output skipped", no_audio: "No audio was produced", error: "Spoken output failed"};
          progress = outcomes[playback.outcome] || "Playback ended: " + (playback.outcome || "unknown outcome");
          if (turn?.phase === "segment") progress += " · Nova is continuing";
          if (state === "speaking") state = ["error", "no_audio"].includes(playback.outcome) ? "error" : "listening";
        }
      }
      // Mute is acknowledged service state, never an optimistic button toggle. A retained
      // playback-start event cannot imply sound after the output has been muted.
      if (capturing) progress = "";
      if (status?.output_muted && active() && state !== "testing") {
        if (["speaking", "preparing", "output_requested"].includes(state)) {
          state = "output_muted";
          progress = "Speaker is muted. Nova's spoken output is disabled.";
        } else if (progress.includes("preparing spoken output")) {
          progress = "Reply received while the speaker is muted.";
        }
      }
      if (status?.microphone_muted && ["listening", "hearing", "finishing_turn", "recognizing", "transcribing"].includes(state))
        state = "microphone_muted";
      if (!active() || stale || unavailable) state = stale || unavailable ? "unavailable" : status?.state || "off";
      if (status?.error) state = "error";
      return {state, progress};
    }
    function paint() {
      const inUse = active();
      const caps = status?.capabilities || {};
      const busy = acting || status?.state === "stopping";
      const view = presentation();
      root.dataset.state = view.state;
      root.dataset.active = String(inUse);
      stateText.textContent = stale ? "Status unavailable" : unavailable ? "Voice unavailable" :
        ({preparing: "Preparing speech", output_requested: "Output requested"}[view.state] || LABELS[view.state] || (status?.state ? String(status.state) : "Checking voice…"));
      hint.textContent = !status ? "Checking the voice service…" : stale ? "The call’s current state could not be confirmed." :
        status.microphone_muted && inUse ? "Your microphone is muted." : view.state === "listening" ? "Speak naturally. Nova is listening." :
        ["recognizing", "transcribing"].includes(view.state) ? "Turning your words into text." : view.state === "hearing" ? "Listening to your utterance." :
        view.state === "finishing_turn" ? "You can keep talking; your turn has not been sent yet." :
        view.state === "output_muted" ? "Spoken replies are muted. Unmute the speaker to hear Nova." :
        view.state === "thinking" ? "Nova is working on your reply." : view.state === "waiting" ? "Your words were sent to Nova." :
        view.state === "speaking" ? "Output is playing on the selected device." : view.state === "starting" ? "Loading audio and connecting to Nova." :
        inUse ? "End the call any time." : "Start a call when you are ready.";
      delivery.textContent = view.progress;
      delivery.hidden = !view.progress;
      const confirmed = !!status && !stale && !unavailable;
      for (const [indicator, control, label, muted] of [
        [microphoneState, microphone, "Microphone", status?.microphone_muted],
        [outputState, output, "Speaker", status?.output_muted]
      ]) {
        const known = confirmed && typeof muted === "boolean";
        indicator.textContent = label + (known ? muted ? " muted" : " on" : " status unknown");
        indicator.dataset.muted = known ? String(muted) : "unknown";
        control.setAttribute("aria-describedby", indicator.id);
      }
      const warnings = [];
      if (confirmed && inUse && status?.state !== "testing") {
        if (status.microphone_muted) warnings.push("Microphone muted — your speech is not sent.");
        if (status.output_muted) warnings.push("Speaker muted — Nova's replies will be silent.");
      }
      muteWarning.textContent = warnings.join(" ");
      muteWarning.hidden = !warnings.length;
      const pauseMs = status?.settings?.end_of_turn_silence_ms;
      pauseAllowance.hidden = !confirmed || !Number.isFinite(pauseMs) || pauseMs <= 0;
      pauseAllowance.textContent = pauseAllowance.hidden ? "" :
        "Pause allowance: " + (pauseMs / 1000).toLocaleString(undefined, {maximumFractionDigits: 2}) + " s of quiet before recognizing your turn.";
      toggle.textContent = acting ? "Working…" : status?.state === "testing" ? "Stop test" : inUse ? "End call" : "Call Nova";
      toggle.disabled = busy || !status || unavailable || (!inUse && (stale || !status.available || !novaOn() || configurationDirty));
      toggle.setAttribute("aria-busy", String(acting));
      microphone.hidden = caps.microphone_mute !== true;
      output.hidden = caps.output_mute !== true;
      microphone.textContent = !confirmed ? "Mic status unknown" : status?.microphone_muted ? "Mic muted · Unmute" : "Mic on · Mute";
      output.textContent = !confirmed ? "Speaker status unknown" : status?.output_muted ? "Speaker muted · Unmute" : "Speaker on · Mute";
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
        (!inUse && status?.available && !novaOn() ? "Start Nova with the power button in Conversation to talk with her. Audio tests can run while she is off." : "") || status?.reason ||
        (!inUse && !novaOn() ? "Start Nova with the power button in Conversation to talk with her. Audio tests can run while she is off." : "");
      notice.textContent = reason;
      notice.hidden = !reason;
      notice.dataset.error = String(!!actionError || !!status?.error || stale);
      const voiceName = {windows: "Windows system voice (temporary)", chatterbox: "Chatterbox", llamacpp: "Local model voice"}[status?.backends?.output];
      backend.textContent = [voiceName ? "Speaking voice: " + voiceName : "", status?.backends?.input ? "Speech recognition: " + status.backends.input : ""].filter(Boolean).join(" · ");
      backend.hidden = !backend.textContent;
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
      const fields = [];
      for (const [name, event] of [["Turn", status?.last_turn], ["Playback", status?.last_playback]]) {
        if (!event) continue;
        fields.push(name + ": " + (event.phase || "unknown") + (event.outcome ? " · " + event.outcome : ""));
        for (const key of ["request_id", "message_id", "run_id", "delivery", "why", "backend", "output_device", "clock", "elapsed_s", "synthesis_ms", "playback_ms", "duration_ms"])
          if (event[key] !== undefined && event[key] !== null) fields.push("  " + key + ": " + String(event[key]));
        if (event.audit) fields.push("  audit: " + (event.audit.status || "NOT_RUN"));
      }
      trace.textContent = fields.join("\n") || "No voice turn has been recorded in this call.";
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
      mounts.delete(host);
      // Closing a widget or popout only disposes its UI. End call owns audio shutdown.
    }
    syncDevices();
    paint();
    tick();
    window.addEventListener("pagehide", destroy, {once: true});
    const ui = {refresh, destroy, root, controls: {toggle, microphone, output, findDevices, applyDevices,
      inputDevice, outputDevice, testMic, testSpeaker, stateText, notice, captionText, audit, testResult, transcript,
      hint, delivery, trace, details, conversation, microphoneState, outputState, muteWarning, pauseAllowance}};
    mounts.set(host, ui);
    return ui;
  };
})();
