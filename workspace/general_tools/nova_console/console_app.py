# Last updated: 2026-07-19 08:17:50
# @nova: Nova Console — the single window that replaces every popup cmd window.
#
# One dark, Nova-themed terminal with a tab per stream (Launcher / llama-server / Nova / Watcher).
# Reads everything from the hub's HTTP API on :8799 — the SAME API the Nova Chat widget uses, so
# the app and the widget can never disagree.
#
# Behaviour Cole asked for:
#   * Nova Chat NOT up  -> plain application window, visible (you can watch the boot).
#   * Nova Chat comes up -> auto-minimises to a tray icon. Restore it from the tray, or from the
#                           Console widget inside Nova Chat.
#   * Closing this window NEVER kills Nova. It hides to tray. The stack lifecycle belongs to
#     nova_start.py; this is only a viewer.
#
# Runs as its own process (pythonw, no console of its own) so a GUI hiccup can't take the stack
# down with it.

import os
import sys
import json
import threading
import urllib.request
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HUB = "http://127.0.0.1:8799"
CHAT_PORT = 8765

# ── Nova palette (matches the chat UI) ───────────────────────────────────────
BG        = "#0b0910"
PANEL     = "#12101b"
TAB_BG    = "#171426"
TAB_ON    = "#2a2140"
ACCENT    = "#a78bfa"
ACCENT_DIM= "#6d5f9c"
TEXT      = "#d6d3e0"
MUTED     = "#7b7590"
OK        = "#4ade80"
DEAD      = "#f87171"
MONO      = ("Cascadia Mono", 10)
try:
    import tkinter.font as tkfont
except Exception:
    tkfont = None


def _get(path: str, timeout: float = 2.0):
    try:
        with urllib.request.urlopen(HUB + path, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _chat_up() -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", CHAT_PORT), timeout=0.4):
            return True
    except OSError:
        return False


class ConsoleApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Nova Console")
        self.root.configure(bg=BG)
        self.root.geometry("1100x620")
        self.root.minsize(700, 380)

        self.tabs: dict[str, dict] = {}     # name -> {btn, text, since, alive}
        self.active: str | None = None
        self.tray = None
        self._hidden = False
        self._auto_hidden_once = False

        self._build_chrome()
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # Safety net: hide any console window Nova's process tree still manages to pop, and log it
        # to the "Strays" tab. It CANNOT capture their text (see stray_janitor.py) — it stops the
        # flashing and tells you what did it. If Strays is busy, something upstream is still wrong.
        try:
            from stray_janitor import start as _start_janitor
            _start_janitor()
        except Exception as e:
            print(f"[console] stray janitor unavailable: {e}")

        self._start_tray()
        self.root.after(300, self._poll_streams)
        self.root.after(600, self._poll_lines)
        self.root.after(2000, self._poll_chat)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_chrome(self):
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(hdr, text="◆ NOVA CONSOLE", bg=BG, fg=ACCENT,
                 font=("Segoe UI Semibold", 11)).pack(side="left")
        self.status = tk.Label(hdr, text="connecting to hub…", bg=BG, fg=MUTED,
                               font=("Segoe UI", 9))
        self.status.pack(side="right", padx=(10, 0))
        # Plain-speak toggle. Defaults ON: the whole point of this window is that you can glance
        # at it and know what's happening without reading llama.cpp internals.
        self.plain = True
        self.plainBtn = tk.Button(hdr, text="Plain English", command=self._toggle_plain,
                                  bg=TAB_ON, fg=TEXT, activebackground=TAB_ON,
                                  activeforeground=TEXT, relief="flat", bd=0,
                                  font=("Segoe UI Semibold", 8), padx=10, pady=3,
                                  cursor="hand2")
        self.plainBtn.pack(side="right")

        self.tabbar = tk.Frame(self.root, bg=BG)
        self.tabbar.pack(fill="x", padx=12, pady=(8, 0))

        self.body = tk.Frame(self.root, bg=PANEL, highlightthickness=1,
                             highlightbackground="#241d38")
        self.body.pack(fill="both", expand=True, padx=12, pady=(6, 6))

        foot = tk.Frame(self.root, bg=BG)
        foot.pack(fill="x", padx=12, pady=(0, 10))
        self.hint = tk.Label(foot, text="Closing this window hides it to the tray — Nova keeps running.",
                             bg=BG, fg=MUTED, font=("Segoe UI", 8))
        self.hint.pack(side="left")
        tk.Button(foot, text="Clear view", command=self._clear, bg=TAB_BG, fg=TEXT,
                  activebackground=TAB_ON, activeforeground=TEXT, relief="flat",
                  font=("Segoe UI", 8), padx=10, pady=2, bd=0,
                  cursor="hand2").pack(side="right")

    def _ensure_tab(self, name: str, label: str):
        if name in self.tabs:
            return
        btn = tk.Button(self.tabbar, text=f"  {label}  ", relief="flat", bd=0,
                        bg=TAB_BG, fg=MUTED, activebackground=TAB_ON,
                        activeforeground=TEXT, font=("Segoe UI Semibold", 9),
                        padx=6, pady=6, cursor="hand2",
                        command=lambda n=name: self.select(n))
        btn.pack(side="left", padx=(0, 4))

        txt = tk.Text(self.body, bg=PANEL, fg=TEXT, insertbackground=ACCENT,
                      font=MONO, relief="flat", wrap="none", padx=10, pady=8,
                      state="disabled")
        sb = tk.Scrollbar(self.body, command=txt.yview, bg=PANEL, troughcolor=PANEL,
                          activebackground=ACCENT_DIM, relief="flat", bd=0)
        txt.configure(yscrollcommand=sb.set)
        txt.tag_configure("ts", foreground=ACCENT_DIM)
        txt.tag_configure("err", foreground=DEAD)
        txt.tag_configure("warn", foreground="#fbbf24")
        txt.tag_configure("hub", foreground=ACCENT_DIM)

        self.tabs[name] = {"btn": btn, "txt": txt, "sb": sb, "since": 0,
                           "alive": False, "rows": []}
        if self.active is None:
            self.select(name)

    def select(self, name: str):
        for n, t in self.tabs.items():
            on = (n == name)
            t["btn"].configure(bg=TAB_ON if on else TAB_BG, fg=TEXT if on else MUTED)
            if on:
                t["txt"].pack(side="left", fill="both", expand=True)
                t["sb"].pack(side="right", fill="y")
            else:
                t["txt"].pack_forget()
                t["sb"].pack_forget()
        self.active = name

    def _clear(self):
        if not self.active:
            return
        self.tabs[self.active]["rows"] = []
        t = self.tabs[self.active]["txt"]
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.configure(state="disabled")

    def _toggle_plain(self):
        self.plain = not self.plain
        self.plainBtn.configure(text="Plain English" if self.plain else "Raw logs",
                                bg=TAB_ON if self.plain else TAB_BG,
                                fg=TEXT if self.plain else MUTED)
        for name in self.tabs:                 # re-render everything in the new mode
            t = self.tabs[name]["txt"]
            t.configure(state="normal")
            t.delete("1.0", "end")
            t.configure(state="disabled")
            self._render(name, self.tabs[name]["rows"])

    def _render(self, name: str, rows):
        """Draw rows into a tab. In Plain mode, show the translation when we HAVE one and fall
        back to the raw line when we don't — better an unreadable truth than a confident guess."""
        t = self.tabs[name]["txt"]
        at_bottom = t.yview()[1] > 0.995
        t.configure(state="normal")
        for r in rows:
            raw = r["text"]
            p = r.get("plain")
            body = (p or raw) if self.plain else raw
            untranslated = self.plain and not p
            tag = ""
            low = body.lower()
            if body.startswith("✗") or "[error]" in low or "traceback" in low:
                tag = "err"
            elif body.startswith("⚠") or "[warn]" in low or "warning" in low:
                tag = "warn"
            elif raw.startswith("[hub]") or untranslated:
                tag = "hub"            # dimmed: this one had no plain-English rule
            t.insert("end", r["ts"] + "  ", ("ts",))
            t.insert("end", body + "\n", (tag,) if tag else ())
        t.configure(state="disabled")
        if at_bottom:
            t.see("end")            # only autoscroll if the user hasn't scrolled up

    def _append(self, name: str, rows):
        self.tabs[name]["rows"].extend(rows)
        del self.tabs[name]["rows"][:-4000]
        self._render(name, rows)

    # ── polling ───────────────────────────────────────────────────────────────
    def _poll_streams(self):
        data = _get("/api/streams")
        if data:
            self.status.configure(text="hub connected", fg=OK)
            for s in data["streams"]:
                self._ensure_tab(s["name"], s["label"])
                self.tabs[s["name"]]["alive"] = s["alive"]
                lbl = s["label"] + ("" if s["alive"] else "  ·")
                if self.active != s["name"]:
                    self.tabs[s["name"]]["btn"].configure(text=f"  {lbl}  ")
        else:
            self.status.configure(text="hub unreachable", fg=DEAD)
        self.root.after(2000, self._poll_streams)

    def _poll_lines(self):
        for name, t in list(self.tabs.items()):
            d = _get(f"/api/log?stream={name}&since={t['since']}", timeout=3.0)
            if d and d.get("lines"):
                self._append(name, d["lines"])
                t["since"] = d["seq"]
        self.root.after(700, self._poll_lines)

    def _poll_chat(self):
        # Nova Chat is up -> this window's job is done; tuck it into the tray (once).
        if not self._auto_hidden_once and self.tray and _chat_up():
            self._auto_hidden_once = True
            self.hide()
        # The Nova Chat widget's "Open window" button pokes POST /api/show — honour it.
        d = _get("/api/show-pending", timeout=1.0)
        if d and d.get("show"):
            self.show()
        self.root.after(1500, self._poll_chat)

    # ── tray ──────────────────────────────────────────────────────────────────
    def _start_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception:
            self.hint.configure(
                text="Tray disabled (pip install pystray pillow). Close = minimise to taskbar.",
                fg="#fbbf24")
            self.root.protocol("WM_DELETE_WINDOW", self.root.iconify)
            return

        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([2, 2, 62, 62], radius=14, fill=(18, 16, 27, 255),
                            outline=(167, 139, 250, 255), width=3)
        d.polygon([(20, 46), (20, 18), (44, 46), (44, 18)], outline=(167, 139, 250, 255))
        d.line([(20, 46), (20, 18), (44, 46), (44, 18)], fill=(167, 139, 250, 255), width=5)

        menu = pystray.Menu(
            pystray.MenuItem("Show Nova Console", lambda *_: self.root.after(0, self.show),
                             default=True),
            pystray.MenuItem("Hide", lambda *_: self.root.after(0, self.hide)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Close console (Nova keeps running)",
                             lambda *_: self.root.after(0, self._quit_viewer)),
        )
        self.tray = pystray.Icon("nova_console", img, "Nova Console", menu)
        threading.Thread(target=self.tray.run, name="nova-tray", daemon=True).start()

    def show(self):
        self._hidden = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide(self):
        if self.tray:
            self._hidden = True
            self.root.withdraw()
        else:
            self.root.iconify()

    def _quit_viewer(self):
        # Only kills the VIEWER. Nova's stack is owned by nova_start.py.
        try:
            if self.tray:
                self.tray.stop()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    ConsoleApp().run()
