# @nova: Local collaboration broker isolated from Nova conversation, memory and autonomy ingestion.
"""A detachable room for Cole, Codex and the actual Claude Cowork client.

This module deliberately imports no nova_body or conversation modules. Data and
client credentials live outside the project, so automatic workspace recall cannot
pick up private room text. This is routing isolation, not an OS sandbox against
Nova's intentionally trusted host tools.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from contextlib import contextmanager
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

LABELS = {"cole": "Cole", "codex": "Codex", "claude": "Claude Cowork"}


def default_directory() -> Path:
    """Use one host-user store even when desktop apps virtualize LocalAppData."""
    configured = os.environ.get("NOVA_COLLABORATION_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "ProjectNovaData" / "Collaboration"


class CollaborationStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "workshop.sqlite3"
        self.lock = threading.RLock()
        self.presence = {}
        credentials = self.directory / "credentials.json"
        if not credentials.exists():
            temporary = credentials.with_name(credentials.name + "." + uuid.uuid4().hex + ".tmp")
            temporary.write_text(json.dumps({"version": 1, "tokens": {
                key: secrets.token_urlsafe(32) for key in ("codex", "claude")
            }}), encoding="utf-8")
            os.replace(temporary, credentials)
        self.tokens = json.loads(credentials.read_text(encoding="utf-8"))["tokens"]
        if any(not isinstance(self.tokens.get(k), str) or len(self.tokens[k]) < 32
               for k in ("codex", "claude")):
            raise ValueError("Invalid collaboration credentials; refusing insecure startup")
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS messages (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL, participant TEXT NOT NULL,
                text TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(participant, id))""")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def event(row):
        result = dict(row)
        result["label"] = LABELS[result["participant"]]
        return result

    def publish(self, participant: str, text: str, message_id: str) -> dict:
        text = text.strip()
        if participant not in LABELS or not text or len(text) > 16000:
            raise ValueError("A message must contain 1 to 16000 characters")
        if not message_id or len(message_id) > 128:
            raise ValueError("A client message ID of at most 128 characters is required")
        with self.lock, self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM messages WHERE participant=? AND id=?",
                             (participant, message_id)).fetchone()
            if row is not None:
                if row["text"] != text:
                    raise ValueError("This message ID was already used for different text")
                return self.event(row)
            created = datetime.now(timezone.utc).isoformat()
            cursor = db.execute("INSERT INTO messages(id,participant,text,created_at) VALUES(?,?,?,?)",
                                (message_id, participant, text, created))
            row = db.execute("SELECT * FROM messages WHERE seq=?", (cursor.lastrowid,)).fetchone()
            self.touch(participant, "active")
            return self.event(row)

    def events(self, after: int, limit: int = 100) -> dict:
        with self.lock, self.connection() as db:
            rows = db.execute("SELECT * FROM messages WHERE seq>? ORDER BY seq LIMIT ?",
                              (after, limit + 1)).fetchall()
        page = rows[:limit]
        return {"events": [self.event(r) for r in page],
                "cursor": page[-1]["seq"] if page else after,
                "has_more": len(rows) > limit}

    def touch(self, participant: str, state: str, last_read: int | None = None):
        if state not in {"active", "waiting", "offline"}:
            raise ValueError("Unknown presence state")
        with self.lock:
            old = self.presence.get(participant, {})
            self.presence[participant] = {
                "state": state, "last_seen": time.time(),
                "last_read": max(old.get("last_read", 0), last_read or 0),
            }

    def state(self):
        now = time.time()
        with self.lock, self.connection() as db:
            latest = db.execute("SELECT COALESCE(MAX(seq),0) FROM messages").fetchone()[0]
            participants = []
            for key, label in LABELS.items():
                p = self.presence.get(key, {"state": "offline", "last_seen": None, "last_read": 0}).copy()
                if p["last_seen"] is not None and now - p["last_seen"] > 90:
                    p["state"] = "offline"
                participants.append({"id": key, "label": label, **p})
        return {"room": "workshop", "nova_access": False, "latest_seq": latest,
                "participants": participants, "wake_supported": False}


class SpoolBridge:
    """Cowork VM transport: atomic requests; the Windows broker alone writes SQLite.

    Access is the existing shared-folder capability, not cryptographic proof of the
    author. This inbox is dedicated to the authorized Cowork task and cannot label
    messages as Cole, Codex or Nova. No host HTTP credentials enter the shared mount.
    """
    def __init__(self, store, directory):
        self.store = store
        self.directory = Path(directory)
        self.requests = self.directory / "requests"
        self.replies = self.directory / "replies"
        for folder in (self.requests, self.replies):
            folder.mkdir(parents=True, exist_ok=True)

    def process(self):
        def admissible(path):
            try:
                return not path.is_symlink() and str(uuid.UUID(path.stem)) == path.stem
            except ValueError:
                return False
        candidates = (p for p in self.requests.glob("*.json") if admissible(p))
        for source in sorted(candidates)[:50]:
            try:
                request_id = source.stem
                if str(uuid.UUID(request_id)) != request_id or source.is_symlink():
                    continue
                target = self.replies / source.name
                if target.exists():
                    source.unlink(missing_ok=True)
                    continue
                if source.stat().st_size > 80000:
                    raise ValueError("Request exceeds transport size limit")
                data = json.loads(source.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or data.get("id") != request_id:
                    raise ValueError("Invalid transport request")
                result = self.dispatch(data)
                reply = {"id": request_id, "ok": True, "result": result}
            except (ValueError, TypeError, KeyError, OSError):
                if not source.exists():
                    continue
                reply = {"id": source.stem, "ok": False, "error": "Invalid collaboration request"}
                target = self.replies / source.name
            temporary = target.with_name(target.name + ".tmp")
            temporary.write_text(json.dumps(reply, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, target)
            source.unlink(missing_ok=True)
        # Replies are disposable acknowledgments; durable messages remain in SQLite.
        cutoff = time.time() - 600
        for target in self.replies.glob("*.json"):
            if not target.is_symlink() and target.stat().st_mtime < cutoff:
                target.unlink(missing_ok=True)

    def dispatch(self, data):
        action = data.get("action")
        if action == "send":
            text = data.get("text")
            message_id = data.get("client_message_id", data["id"])
            if not isinstance(text, str) or not isinstance(message_id, str):
                raise ValueError("Invalid message")
            return self.store.publish("claude", text, message_id)
        if action in {"read", "presence"}:
            cursor = data.get("after", 0) if action == "read" else data.get("last_read", 0)
            if type(cursor) is not int or cursor < 0:
                raise ValueError("Invalid cursor")
            self.store.touch("claude", data.get("state", "active"), cursor)
            return self.store.events(cursor) if action == "read" else self.store.state()
        if action == "status":
            self.store.touch("claude", "active")
            return self.store.state()
        raise ValueError("Unknown transport action")


def validate_local_request(request: Request):
    """Reject cross-site and forwarded requests even when their socket is local."""
    if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "Collaboration is available only on this computer")
    host = request.headers.get("host", "")
    try:
        parsed = urlsplit("http://" + host)
        valid = parsed.hostname in {"localhost", "127.0.0.1", "::1"} and parsed.port is not None
    except ValueError:
        valid = False
    if not valid or any(h in request.headers for h in
                        ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-real-ip")):
        raise HTTPException(403, "Direct loopback requests only")
    origin = request.headers.get("origin")
    if origin and origin != "http://" + host:
        raise HTTPException(403, "Collaboration rejects cross-origin requests")
    if request.headers.get("sec-fetch-site") not in {None, "none", "same-origin"}:
        raise HTTPException(403, "Collaboration rejects cross-site requests")
    if request.method == "POST" and request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "Send application/json")


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=16000)
    client_message_id: str = Field(min_length=1, max_length=128)


class Presence(BaseModel):
    state: str
    last_read: int = Field(default=0, ge=0)


def create_router(store: CollaborationStore | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/collaboration", tags=["Collaboration"])
    current = store
    spool_task = None

    def room():
        nonlocal current
        if current is None:
            current = CollaborationStore(default_directory())
        return current

    @router.on_event("startup")
    async def start_spool():
        nonlocal spool_task
        shared = Path(__file__).resolve().parents[2] / "Temp" / "collaboration"
        bridge = SpoolBridge(room(), shared)

        async def serve():
            while True:
                try:
                    await asyncio.to_thread(bridge.process)
                except Exception as exc:
                    print("[collaboration] shared transport error:", type(exc).__name__)
                await asyncio.sleep(1)
        spool_task = asyncio.create_task(serve())

    @router.on_event("shutdown")
    async def stop_spool():
        if spool_task:
            spool_task.cancel()
            try:
                await spool_task
            except asyncio.CancelledError:
                pass

    def participant(request):
        validate_local_request(request)
        key = request.headers.get("x-nova-collaboration-participant", "cole")
        if key not in LABELS:
            raise HTTPException(403, "Unknown collaboration participant")
        if key != "cole":
            bearer = request.headers.get("authorization", "")
            if not hmac.compare_digest(bearer, "Bearer " + room().tokens[key]):
                raise HTTPException(401, "This participant requires its local credential")
        return key

    @router.get("/state")
    async def state(request: Request):
        participant(request)
        return room().state()

    @router.get("/events")
    async def events(request: Request, after: int = 0, wait: float = 0):
        key = participant(request)
        if after < 0 or not 0 <= wait <= 45:
            raise HTTPException(422, "after must be nonnegative and wait between 0 and 45 seconds")
        deadline = time.monotonic() + wait
        room().touch(key, "waiting" if wait else "active", after)
        try:
            while True:
                result = await asyncio.to_thread(room().events, after)
                if result["events"] or time.monotonic() >= deadline or await request.is_disconnected():
                    return result
                await asyncio.sleep(min(0.25, max(0, deadline - time.monotonic())))
        finally:
            room().touch(key, "active")

    @router.post("/messages")
    async def messages(request: Request, message: Message):
        key = participant(request)
        try:
            return await asyncio.to_thread(room().publish, key, message.text, message.client_message_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.post("/presence")
    async def presence(request: Request, body: Presence):
        key = participant(request)
        try:
            room().touch(key, body.state, body.last_read)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return room().state()

    return router
