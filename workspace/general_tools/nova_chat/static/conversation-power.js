/* @nova: Start and stop Nova through the owning launcher while preserving the controller, composer draft and layout. */
(() => {
  "use strict";
  const DRAFT_KEY = "nova.conversation.lifecycle-draft.v1";
  const TRANSITIONS = new Set(["starting", "stopping"]);
  const STATES = new Set(["off", "starting", "on", "stopping", "error"]);
  window.initNovaConversationPower = function () {
    const chat = document.getElementById("chat-main");
    if (!chat || document.getElementById("conversation-nova-toggle"))
      return null;
    const row = document.createElement("div");
    row.className = "nc-conversation-power";
    const detail = document.createElement("span");
    detail.id = "conversation-nova-state";
    detail.setAttribute("role", "status");
    detail.setAttribute("aria-live", "polite");
    const toggle = document.createElement("button");
    toggle.id = "conversation-nova-toggle";
    toggle.type = "button";
    toggle.textContent = "Checking Nova…";
    toggle.disabled = true;
    toggle.setAttribute("aria-describedby", detail.id);
    row.append(detail, toggle);
    const tabs = document.getElementById("session-tabs");
    if (tabs?.parentElement === chat) chat.insertBefore(row, tabs.nextSibling);
    else chat.prepend(row);
    let state = null,
      pageChatOnly = null,
      fetching = false,
      acting = false;
    let disposed = false,
      reloading = false,
      timer = null,
      rememberedAction = null,
      actionError = null;
    const disabledBeforeTransition = new Map();

    function preserveDraft() {
      const input = document.getElementById("input");
      const draft = {
        text: input?.value || "",
        start: input?.selectionStart,
        end: input?.selectionEnd,
        images: typeof pendingImages !== "undefined" ? pendingImages : [],
        files: typeof _mentionedFiles !== "undefined" ? _mentionedFiles : [],
      };
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    }
    function restoreDraft() {
      try {
        const raw = sessionStorage.getItem(DRAFT_KEY);
        if (!raw) return;
        const draft = JSON.parse(raw);
        const input = document.getElementById("input");
        if (input?.value && input.value !== draft.text) return;
        if (input && !input.value && typeof draft.text === "string") {
          input.value = draft.text;
          if (typeof input.setSelectionRange === "function")
            input.setSelectionRange(
              draft.start ?? draft.text.length,
              draft.end ?? draft.text.length,
            );
          if (typeof window.autoResize === "function") window.autoResize(input);
        }
        if (
          Array.isArray(draft.images) &&
          typeof window.addPending === "function" &&
          typeof pendingImages !== "undefined" &&
          !pendingImages.length
        )
          draft.images.forEach((item) => {
            if (typeof item?.dataUrl === "string")
              window.addPending(item.dataUrl);
          });
        if (
          Array.isArray(draft.files) &&
          typeof _mentionedFiles !== "undefined" &&
          !_mentionedFiles.length
        ) {
          _mentionedFiles = draft.files;
          if (typeof window.renderFileChips === "function")
            window.renderFileChips();
        }
        sessionStorage.removeItem(DRAFT_KEY);
      } catch (_) {
        detail.textContent =
          "A saved draft could not be restored; it remains in this window’s storage.";
      }
    }
    async function request(path, post = false) {
      const response = await fetch(path, {
        method: post ? "POST" : "GET",
        cache: "no-store",
        ...(post
          ? { headers: { "Content-Type": "application/json" }, body: "{}" }
          : {}),
        signal: AbortSignal.timeout(12000),
      });
      const data = await response.json().catch(() => ({}));
      // A terminal launcher failure is still a valid, actionable status.
      // HTTP failures and unknown/unavailable states must not be mistaken for off.
      const lifecycleState =
        !post &&
        path === "/api/nova/lifecycle" &&
        data.available !== false &&
        STATES.has(data.state);
      if (!response.ok || (data.ok === false && !lifecycleState)) {
        const error = Error(
          data.error ||
            data.message ||
            "Nova control is unavailable (" + response.status + ").",
        );
        error.status = response.status;
        error.data = data;
        throw error;
      }
      return data;
    }
    function syncOtherControls(busy) {
      for (const id of [
        "llama-start-btn",
        "llama-stop-btn",
        "pb-auto",
        "pb-wake",
        "reinject-btn",
      ]) {
        const control = document.getElementById(id);
        if (!control) continue;
        if (busy) {
          if (!disabledBeforeTransition.has(control))
            disabledBeforeTransition.set(control, control.disabled);
          control.disabled = true;
        } else if (disabledBeforeTransition.has(control)) {
          control.disabled =
            control.dataset.chatOnlyBlocked === "true" ||
            disabledBeforeTransition.get(control);
          disabledBeforeTransition.delete(control);
        }
      }
    }
    function paint() {
      const busy =
        acting ||
        !!state?.pending ||
        !!state?.busy ||
        TRANSITIONS.has(state?.state);
      const target =
        state?.target ||
        (state?.target_enabled === true
          ? "on"
          : state?.target_enabled === false
            ? "off"
            : rememberedAction);
      const on =
        state?.state === "on" ||
        (state?.state === "error" && state?.chat_only === false);
      toggle.textContent = busy
        ? target === "off" || state?.state === "stopping"
          ? "Stopping Nova…"
          : "Starting Nova…"
        : on
          ? "Stop Nova"
          : "Start Nova";
      toggle.disabled =
        busy || !state || state.available === false || !STATES.has(state.state);
      toggle.dataset.state = busy ? "busy" : on ? "on" : "off";
      toggle.title = on
        ? "Stop Nova and keep this controller open"
        : "Start Nova and keep this controller open";
      toggle.setAttribute("aria-busy", String(busy));
      detail.textContent =
        actionError ||
        state?.error ||
        state?.message ||
        (state?.state === "on"
          ? "Nova is on"
          : state?.state === "off"
            ? "Nova is off · Controller stays open"
            : busy
              ? "Waiting for Nova’s services…"
              : "Checking Nova’s launcher…");
      syncOtherControls(busy);
    }
    async function accept(next) {
      if (!next || !STATES.has(next.state))
        throw Error(
          "Nova’s launcher returned an unrecognized lifecycle state.",
        );
      if (state && next.state !== state.state && !next.error)
        actionError = null;
      state = next;
      if (!next.pending && !TRANSITIONS.has(next.state))
        rememberedAction = null;
      window.novaLifecycleState = { ...next };
      paint();
      window.dispatchEvent(
        new CustomEvent("nova:lifecycle", { detail: { ...next } }),
      );
      if (
        typeof next.chat_only === "boolean" &&
        pageChatOnly !== null &&
        next.chat_only !== pageChatOnly &&
        !reloading
      ) {
        // Launcher state can change before the replacement worker is ready. Only
        // reload after that worker confirms its actual mode, preventing loops.
        let version;
        try {
          version = await request("/api/version");
        } catch (_) {
          detail.textContent =
            "Nova changed modes. Waiting for the controller to reconnect…";
          return;
        }
        if (version.chat_only !== next.chat_only) return;
        try {
          preserveDraft();
        } catch (_) {
          detail.textContent =
            "Nova changed modes. This draft is too large to save automatically. Save it before reloading the interface.";
          return;
        }
        reloading = true;
        // Existing beforeunload handlers persist the named widget layout.
        window.location.reload();
      }
    }
    async function refresh() {
      if (fetching || disposed || reloading) return;
      fetching = true;
      try {
        if (pageChatOnly === null) {
          const version = await request("/api/version");
          if (typeof version.chat_only === "boolean")
            pageChatOnly = version.chat_only;
        }
        await accept(await request("/api/nova/lifecycle"));
      } catch (error) {
        if (error.status === 404) {
          state = {
            state: "error",
            available: false,
            message: "Restart Nova Chat to enable control",
          };
          paint();
        } else {
          if (
            state?.pending ||
            TRANSITIONS.has(state?.state) ||
            rememberedAction
          ) {
            state = {
              ...state,
              pending: true,
              target: state?.target || rememberedAction,
            };
            paint();
            detail.textContent = "Reconnecting while Nova changes state…";
          } else {
            state = { ...state, available: false };
            paint();
            detail.textContent =
              error.message || "Nova’s launcher is unreachable.";
          }
        }
      } finally {
        fetching = false;
      }
    }
    toggle.addEventListener("click", async () => {
      if (toggle.disabled || acting || disposed) return;
      const action =
        state.state === "on" ||
        (state.state === "error" && state.chat_only === false)
          ? "stop"
          : "start";
      acting = true;
      actionError = null;
      rememberedAction = action === "start" ? "on" : "off";
      paint();
      try {
        await accept(await request("/api/nova/" + action, true));
      } catch (error) {
        if (error.data && STATES.has(error.data.state)) {
          await accept(error.data);
        } else {
          state = { ...state, available: false };
        }
        actionError = error.message;
      } finally {
        acting = false;
        paint();
        await refresh();
        if (typeof window.pollServices === "function") window.pollServices();
      }
    });
    const tick = async () => {
      await refresh();
      if (!disposed && !reloading)
        timer = setTimeout(
          tick,
          state?.pending || TRANSITIONS.has(state?.state) ? 1200 : 4000,
        );
    };
    function destroy() {
      disposed = true;
      clearTimeout(timer);
      syncOtherControls(false);
    }
    restoreDraft();
    tick();
    window.addEventListener("pagehide", destroy, { once: true });
    return { refresh, destroy, button: toggle, detail };
  };
  const init = () => window.initNovaConversationPower();
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
