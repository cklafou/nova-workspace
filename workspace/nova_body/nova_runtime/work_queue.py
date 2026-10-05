# @nova: Persists leased events and memory work with bounded retries and visible failures.
# Last updated: 2026-10-05 18:23:37
"""Durable, leased work queue. UI notifications remain a separate, lossy stream."""
import json
from pathlib import Path
import sqlite3
import time
import uuid
from contextlib import contextmanager
from nova_paths import body_path


class WorkQueue:
    def __init__(self, name='events', path=None):
        self.path = Path(path) if path else body_path('memory', 'runtime_work.sqlite3')
        self.name = name

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, queue TEXT, key TEXT, payload TEXT, state TEXT,
            attempts INTEGER DEFAULT 0, due REAL, lease REAL DEFAULT 0,
            created REAL, error TEXT DEFAULT '', UNIQUE(queue,key))''')
        try:
            with db:
                yield db
        finally:
            db.close()

    def put(self, payload, key=None, delay=0):
        key = key or uuid.uuid4().hex
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT id,state FROM jobs WHERE queue=? AND key=?', (self.name,key)).fetchone()
            if existing and existing['state'] != 'done':
                # Failed work stays visible until the explicit retry action.
                return existing['id']
            if existing:
                # Retain the completed receipt while freeing the event key to recur.
                db.execute("UPDATE jobs SET key=? WHERE id=?",
                           (key + ':done:' + existing['id'], existing['id']))
            pending = db.execute("SELECT COUNT(*) FROM jobs WHERE queue=? AND state IN ('pending','leased','failed')", (self.name,)).fetchone()[0]
            if pending >= 10000:
                raise RuntimeError(f'{self.name} queue full; work was not accepted')
            jid = uuid.uuid4().hex
            db.execute('INSERT INTO jobs(id,queue,key,payload,state,due,created) VALUES(?,?,?,?,?,?,?)',
                       (jid,self.name,key,json.dumps(payload), 'pending',time.time()+delay,time.time()))
            return jid

    def claim(self, lease_seconds=300):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE jobs SET state='failed',lease=0,error='Worker lease expired after 5 attempts' "
                       "WHERE queue=? AND state='leased' AND lease<=? AND attempts>=5",
                       (self.name,time.time()))
            row = db.execute("SELECT * FROM jobs WHERE queue=? AND ((state='pending' AND due<=?) OR (state='leased' AND lease<=?)) ORDER BY created LIMIT 1",
                             (self.name,time.time(),time.time())).fetchone()
            if not row: return None
            db.execute("UPDATE jobs SET state='leased',lease=?,attempts=attempts+1 WHERE id=?", (time.time()+lease_seconds,row['id']))
            return {**dict(row), 'payload':json.loads(row['payload']), 'attempts':row['attempts']+1}

    def finish(self, jid, error=None):
        with self.connect() as db:
            if not error:
                db.execute("UPDATE jobs SET state='done',lease=0,error='' WHERE id=? AND queue=?",(jid,self.name))
                # Keep a bounded recent audit/dedup window; failed/pending work is never discarded.
                db.execute("DELETE FROM jobs WHERE queue=? AND state='done' AND id NOT IN (SELECT id FROM jobs WHERE queue=? AND state='done' ORDER BY created DESC LIMIT 1000)", (self.name,self.name))
            else:
                row=db.execute('SELECT attempts FROM jobs WHERE id=? AND queue=?',(jid,self.name)).fetchone()
                if not row: return
                state='failed' if row['attempts']>=5 else 'pending'
                db.execute('UPDATE jobs SET state=?,lease=0,error=?,due=? WHERE id=?',
                           (state,str(error)[:1000],time.time()+min(300,2**row['attempts']),jid))

    def retry_failed(self):
        with self.connect() as db:
            return db.execute("UPDATE jobs SET state='pending',attempts=0,due=? WHERE queue=? AND state='failed'", (time.time(),self.name)).rowcount

    def snapshot(self):
        with self.connect() as db:
            counts=dict(db.execute('SELECT state,COUNT(*) FROM jobs WHERE queue=? GROUP BY state',(self.name,)).fetchall())
            errors=[dict(r) for r in db.execute("SELECT id,state,attempts,error FROM jobs WHERE queue=? AND error!='' ORDER BY created DESC LIMIT 5",(self.name,))]
            return {'counts':counts,'errors':errors}

    def ready(self):
        with self.connect() as db:
            return bool(db.execute("SELECT 1 FROM jobs WHERE queue=? AND ((state='pending' AND due<=?) OR (state='leased' AND lease<=?)) LIMIT 1", (self.name,time.time(),time.time())).fetchone())
