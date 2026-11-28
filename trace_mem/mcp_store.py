"""Dedicated transactional MCP practice store. No SDK or Workspace profile dependency."""
from contextlib import closing, contextmanager
from datetime import date
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from trace_mem.memory import Fact, Source, TemporalMemory


LABEL = r"[a-z][a-z0-9 _-]{0,63}"
AGENT = r"[a-z][a-z0-9_-]{0,31}"
SCHEMA = """
BEGIN IMMEDIATE;
PRAGMA application_id=1414352973;
PRAGMA user_version=1;
CREATE TABLE grants(agent TEXT,label TEXT,can_read INTEGER,history INTEGER,propose INTEGER,
                    PRIMARY KEY(agent,label));
CREATE TABLE versions(label TEXT PRIMARY KEY, revision INTEGER NOT NULL);
CREATE TABLE facts(id TEXT PRIMARY KEY,label TEXT,value TEXT,start TEXT,end TEXT,
                   observed TEXT,source TEXT,agent TEXT,kind TEXT);
CREATE INDEX by_label ON facts(label,start);
CREATE TABLE proposals(id TEXT PRIMARY KEY,agent TEXT,label TEXT,action TEXT,value TEXT,
                       start TEXT,end TEXT,kind TEXT,source TEXT,revision INTEGER,state TEXT,
                       observed TEXT NOT NULL);
COMMIT;
"""


def initialize(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    (root / "bindings").mkdir()
    with closing(sqlite3.connect(root / "practice.sqlite3")) as db:
        db.executescript(SCHEMA)
    for agent in ("agent-a", "agent-b"):
        bind(root, agent)


def bind(root, agent):
    if not re.fullmatch(AGENT, agent):
        raise ValueError("Invalid local agent name.")
    with Practice(root).transaction():
        with (Path(root) / "bindings" / (agent + ".json")).open("x", encoding="utf-8") as output:
            json.dump({"agent": agent}, output)


class Practice:
    def __init__(self, root):
        self.file = Path(root).resolve() / "practice.sqlite3"
        if not self.file.is_file():
            raise ValueError("Initialize a dedicated practice profile first.")

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.file.as_uri() + "?mode=rw", uri=True, timeout=10)) as db:
            db.row_factory = sqlite3.Row
            if (db.execute("PRAGMA application_id").fetchone()[0],
                    db.execute("PRAGMA user_version").fetchone()[0]) != (1414352973, 1):
                raise ValueError("Unsupported practice profile.")
            db.execute("PRAGMA secure_delete=ON")
            with db:
                db.execute("BEGIN IMMEDIATE")
                yield db

    def grant(self, agent, label, read=False, history=False, propose=False):
        if not re.fullmatch(AGENT, agent) or not re.fullmatch(LABEL, label) or history and not read:
            raise ValueError("Invalid grant.")
        with self.transaction() as db:
            db.execute("INSERT OR REPLACE INTO grants VALUES(?,?,?,?,?)",
                       (agent, label, read, history, propose))
            db.execute("UPDATE proposals SET state='stale', value=NULL,source=NULL "
                       "WHERE agent=? AND label=? AND state='pending'", (agent, label))

    def read(self, agent, mode, term, as_of=None, limit=8):
        today = date.today().isoformat()
        cutoff = as_of or today
        if cutoff > today:
            raise ValueError("Future lookup unsupported.")
        with self.transaction() as db:
            # Filter permissions and validity before reading any payload into the process.
            clauses = ["g.agent=?", "g.can_read=1"]
            args = [agent]
            if mode == "history" or cutoff < today:
                clauses.append("g.history=1")
            if mode != "history":
                clauses.extend(["f.start<=?", "(f.end IS NULL OR f.end>?)"])
                args.extend([cutoff, cutoff])
            if mode == "search":
                clauses.append("(instr(f.label,lower(?))>0 OR instr(lower(f.value),lower(?))>0)")
                args.extend([term, term])
            else:
                clauses.append("f.label=?")
                args.append(term)
            rows = db.execute("SELECT f.* FROM facts f JOIN grants g ON g.label=f.label WHERE "
                              + " AND ".join(clauses) + " ORDER BY f.start DESC,f.label,f.id LIMIT ?",
                              (*args, limit)).fetchall()
        return {"status": "found" if rows else "abstain", "evidence": [dict(r) for r in rows]}

    def propose(self, agent, action, label, value, start, end, kind, source):
        with self.transaction() as db:
            grant = db.execute("SELECT propose FROM grants WHERE agent=? AND label=?",
                               (agent, label)).fetchone()
            if not grant or not grant[0]:
                return {"status": "denied"}
            if db.execute("SELECT count(*) FROM proposals WHERE state='pending'").fetchone()[0] >= 256:
                return {"status": "queue_full"}
            db.execute("INSERT OR IGNORE INTO versions VALUES(?,0)", (label,))
            rev = db.execute("SELECT revision FROM versions WHERE label=?", (label,)).fetchone()[0]
            key = uuid4().hex
            db.execute("INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (key, agent, label, action, value, start, end, kind, source, rev, "pending",
                        date.today().isoformat()))
            return {"status": "pending", "proposal_id": key}

    def status(self, agent, key):
        with self.transaction() as db:
            row = db.execute("SELECT p.state FROM proposals p JOIN grants g ON "
                             "p.label=g.label AND p.agent=g.agent WHERE p.id=? AND p.agent=? "
                             "AND g.propose=1", (key, agent)).fetchone()
            return {"status": row[0] if row else "unavailable"}

    def pending(self):
        with self.transaction() as db:
            return [dict(r) for r in db.execute(
                "SELECT p.*, (SELECT f.value FROM facts f WHERE f.label=p.label "
                "ORDER BY f.start DESC LIMIT 1) AS latest_confirmed_value "
                "FROM proposals p WHERE p.state='pending' ORDER BY p.rowid")]

    def decide(self, key, approve):
        with self.transaction() as db:
            p = db.execute("SELECT * FROM proposals WHERE id=? AND state='pending'", (key,)).fetchone()
            if not p:
                raise ValueError("Proposal unavailable or already resolved.")
            state = "rejected"
            if approve:
                rev = db.execute("SELECT revision FROM versions WHERE label=?", (p["label"],)).fetchone()[0]
                grant = db.execute("SELECT propose FROM grants WHERE agent=? AND label=?",
                                   (p["agent"], p["label"])).fetchone()
                if not grant or not grant[0] or rev != p["revision"]:
                    state = "stale"
                elif p["kind"] == "uncertain":
                    state = "deferred"
                else:
                    self.apply(db, p)
                    state = "approved"
                    db.execute("UPDATE versions SET revision=revision+1 WHERE label=?", (p["label"],))
                    db.execute("UPDATE proposals SET state='stale',value=NULL,source=NULL "
                               "WHERE label=? AND id!=? AND state='pending'", (p["label"], key))
            db.execute("UPDATE proposals SET state=?,value=NULL,source=NULL WHERE id=?", (state, key))
            return state

    @staticmethod
    def apply(db, p):
        label = p["label"]
        if p["action"] == "forget":
            db.execute("DELETE FROM facts WHERE label=?", (label,))
            db.execute("DELETE FROM proposals WHERE label=? AND id!=?", (label, p["id"]))
            return
        old = db.execute("SELECT * FROM facts WHERE label=? ORDER BY start DESC LIMIT 1",
                         (label,)).fetchone()
        correction = p["action"] == "correct"
        expired = old is not None and old["end"] is not None and old["end"] <= p["start"]
        if (correction and not old) or (not correction and old and not expired):
            raise ValueError("Use a new proposal for an empty slot and a correction for an existing slot.")
        observed = date.fromisoformat(p["observed"])
        new = Fact(uuid4().hex, "practice", label, p["value"], Source(observed, p["source"], "reported"),
                   date.fromisoformat(p["start"]), date.fromisoformat(p["end"]) if p["end"] else None)
        memory = TemporalMemory()
        if correction:
            memory.accept(Fact(old["id"], "practice", label, old["value"],
                               Source(date.fromisoformat(old["observed"]), old["source"], "reported"),
                               date.fromisoformat(old["start"]), date.fromisoformat(old["end"]) if old["end"] else None))
        memory.accept(new, replaces=old["id"] if correction else None)
        if correction:
            prior, = memory.retrieve("practice", label, as_of=date.fromisoformat(old["start"]))
            db.execute("UPDATE facts SET end=? WHERE id=?", (prior.valid_to.isoformat(), old["id"]))
        db.execute("INSERT INTO facts VALUES(?,?,?,?,?,?,?,?,?)",
                   (new.fact_id, label, new.value, p["start"], p["end"], observed.isoformat(),
                    new.source.reference, p["agent"], p["kind"]))
