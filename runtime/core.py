"""Branch-Aware Hierarchical Memory System (BAHMS) — reference MVP.

A single-process/small-team prototype. Authoritative memory is in SQLite; L2/L3
cache rows and Markdown exports are reproducible projections. No model calls.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
WORD = re.compile(r"[\w]+", re.UNICODE)
DEPENDENCY_RELATIONS = {"supports", "derived_from", "depends_on"}
VALID_RELATIONS = DEPENDENCY_RELATIONS | {"contradicts", "relates_to", "supersedes", "tests"}
VALID_KINDS = {"project", "constraint", "hypothesis", "experiment", "claim", "decision", "finding", "checkpoint", "note"}
VALID_STATUSES = {"draft", "active", "paused", "accepted", "rejected", "superseded"}


class ConflictError(Exception):
    """Optimistic-lock violation."""


def estimate_tokens(s: str) -> int:
    """Very rough placeholder: not model-tokenizer accurate. Replace in production."""
    return max(1, (len(s.encode("utf-8")) + 3) // 4)


def now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def valid_id(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid identifier: {value!r}")
    return value


class MemoryStore:
    def __init__(self, db_path: str | Path, l2_budget: int = 8000, l3_budget: int = 40000):
        self.db_path = str(db_path)
        self.l2_budget, self.l3_budget = l2_budget, l3_budget
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self):
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS branches (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                parent_id TEXT REFERENCES branches(id), status TEXT NOT NULL DEFAULT 'active',
                checkpoint_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                branch_id TEXT REFERENCES branches(id),
                title TEXT NOT NULL, summary TEXT NOT NULL, body TEXT NOT NULL,
                status TEXT NOT NULL, review_state TEXT NOT NULL DEFAULT 'valid',
                version INTEGER NOT NULL DEFAULT 1, pinned INTEGER NOT NULL DEFAULT 0,
                source_uri TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_records_branch ON records(branch_id);
            CREATE TABLE IF NOT EXISTS edges (
                source_id TEXT NOT NULL REFERENCES records(id),
                target_id TEXT NOT NULL REFERENCES records(id),
                relation TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(source_id,target_id,relation)
            );
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
                subject_id TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cache (
                tier TEXT NOT NULL CHECK(tier IN ('L2','L3')),
                scope TEXT NOT NULL, record_id TEXT NOT NULL,
                source_version INTEGER NOT NULL, representation TEXT NOT NULL,
                token_cost INTEGER NOT NULL, hits INTEGER NOT NULL DEFAULT 0,
                last_access REAL NOT NULL,
                PRIMARY KEY (tier, scope, record_id)
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
                record_id UNINDEXED, title, summary, body, tokenize='unicode61'
            );
            """)

    @staticmethod
    def _event(db, actor: str, action: str, subject: str, payload: dict):
        db.execute("INSERT INTO events(ts,actor,action,subject_id,payload) VALUES (?,?,?,?,?)",
                   (now(), actor, action, subject, json.dumps(payload, sort_keys=True)))

    @staticmethod
    def _fts_update(db, record_id: str, title: str, summary: str, body: str):
        db.execute("DELETE FROM records_fts WHERE record_id=?", (record_id,))
        db.execute("INSERT INTO records_fts(record_id,title,summary,body) VALUES (?,?,?,?)",
                   (record_id, title, summary, body))

    def create_branch(self, branch_id: str, name: str, parent_id: str | None = None,
                      actor: str = "human") -> dict:
        valid_id(branch_id)
        if parent_id:
            valid_id(parent_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ts = now()
            db.execute("INSERT INTO branches(id,name,parent_id,created_at,updated_at) VALUES(?,?,?,?,?)",
                       (branch_id, name, parent_id, ts, ts))
            self._event(db, actor, "branch.created", branch_id,
                        {"name": name, "parent_id": parent_id})
            db.commit()
        return self.get_branch(branch_id)

    def get_branch(self, branch_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM branches WHERE id=?", (branch_id,)).fetchone()
            if not row:
                raise KeyError(branch_id)
            return dict(row)

    def branch_chain(self, branch_id: str) -> list[str]:
        """Active branch followed by ancestor branches, nearest first."""
        chain, visited = [], set()
        with self.connect() as db:
            node = branch_id
            while node is not None:
                if node in visited:
                    raise ValueError("Branch parent cycle")
                visited.add(node)
                row = db.execute("SELECT parent_id FROM branches WHERE id=?", (node,)).fetchone()
                if row is None:
                    raise KeyError(node)
                chain.append(node)
                node = row["parent_id"]
        return chain

    def put_record(self, *, record_id: str, kind: str, title: str, summary: str,
                   body: str = "", branch_id: str | None = None, status: str = "draft",
                   pinned: bool = False, source_uri: str | None = None,
                   actor: str = "agent") -> dict:
        valid_id(record_id)
        if kind not in VALID_KINDS or status not in VALID_STATUSES:
            raise ValueError("Invalid kind or status")
        if status == "accepted" and kind in {"decision", "constraint"} and actor != "human":
            raise PermissionError("An accepted decision/constraint needs human approval")
        if branch_id:
            self.get_branch(branch_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            ts = now()
            db.execute("""INSERT INTO records(id,kind,branch_id,title,summary,body,status,pinned,source_uri,created_at,updated_at)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                       (record_id, kind, branch_id, title, summary, body, status, int(pinned), source_uri, ts, ts))
            self._fts_update(db, record_id, title, summary, body)
            self._event(db, actor, "record.created", record_id,
                        {"kind": kind, "branch_id": branch_id, "source_uri": source_uri})
            db.commit()
        return self.get_record(record_id)

    def get_record(self, record_id: str) -> dict:
        with self.connect() as db:
            r = db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
            if r is None:
                raise KeyError(record_id)
            return dict(r)

    @staticmethod
    def _dependent_ids(db, source_record_id: str) -> set[str]:
        """Traverse scientific dependencies: evidence --supports--> claim;
        derived --derived_from/depends_on--> its source.
        """
        seen, frontier = {source_record_id}, [source_record_id]
        affected: set[str] = set()
        while frontier:
            changed = frontier.pop()
            rows = db.execute("""
                SELECT target_id AS dependent FROM edges WHERE source_id=? AND relation='supports'
                UNION
                SELECT source_id AS dependent FROM edges
                WHERE target_id=? AND relation IN ('derived_from','depends_on')
            """, (changed, changed)).fetchall()
            for row in rows:
                dependent = row["dependent"]
                if dependent not in seen:
                    seen.add(dependent)
                    affected.add(dependent)
                    frontier.append(dependent)
        return affected

    def _invalidate(self, db, changed: str, actor: str):
        impacted = self._dependent_ids(db, changed)
        all_ids = {changed} | impacted
        db.executemany("DELETE FROM cache WHERE record_id=?", [(x,) for x in all_ids])
        for dep in impacted:
            db.execute("UPDATE records SET review_state='needs_review', updated_at=? WHERE id=?",
                       (now(), dep))
        self._event(db, actor, "memory.invalidated", changed,
                    {"cache_records": sorted(all_ids), "review_required": sorted(impacted)})
        return sorted(impacted)

    def update_record(self, record_id: str, expected_version: int, *, title: str | None = None,
                      summary: str | None = None, body: str | None = None,
                      status: str | None = None, source_uri: str | None = None,
                      actor: str = "agent") -> dict:
        if status is not None and status not in VALID_STATUSES:
            raise ValueError("Invalid status")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
            if row is None:
                raise KeyError(record_id)
            r = dict(row)
            if r["version"] != expected_version:
                raise ConflictError(f"Expected version {expected_version}, current version {r['version']}")
            if status == "accepted" and r["kind"] in {"decision", "constraint"} and actor != "human":
                raise PermissionError("An accepted decision/constraint needs human approval")
            new = {k: (r[k] if v is None else v) for k, v in
                   {"title": title, "summary": summary, "body": body,
                    "status": status, "source_uri": source_uri}.items()}
            db.execute("""UPDATE records SET title=?,summary=?,body=?,status=?,source_uri=?,
                          review_state='valid',version=version+1,updated_at=? WHERE id=?""",
                       (new["title"], new["summary"], new["body"], new["status"],
                        new["source_uri"], now(), record_id))
            self._fts_update(db, record_id, new["title"], new["summary"], new["body"])
            impacted = self._invalidate(db, record_id, actor)
            self._event(db, actor, "record.updated", record_id,
                        {"from_version": expected_version, "to_version": expected_version + 1,
                         "affected": impacted, "fields": [k for k,v in
                            {"title":title,"summary":summary,"body":body,"status":status,"source_uri":source_uri}.items() if v is not None]})
            db.commit()
        return self.get_record(record_id)

    def link(self, source_id: str, target_id: str, relation: str, actor: str = "agent") -> dict:
        if relation not in VALID_RELATIONS:
            raise ValueError(f"Relation must be one of {sorted(VALID_RELATIONS)}")
        if source_id == target_id and relation in DEPENDENCY_RELATIONS:
            raise ValueError("Self-referential dependencies are not supported")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO edges(source_id,target_id,relation,created_at) VALUES(?,?,?,?)",
                       (source_id,target_id,relation,now()))
            self._event(db, actor, "edge.created", source_id,
                        {"target":target_id,"relation":relation})
            db.commit()
        return {"source_id":source_id,"target_id":target_id,"relation":relation}

    def search(self, query: str, limit: int = 15) -> list[dict]:
        terms = WORD.findall(query.lower())[:16]
        if not terms:
            return []
        fts_query = " OR ".join(f'"{t}"' for t in terms)
        with self.connect() as db:
            rows = db.execute("""
                SELECT records.*, bm25(records_fts) AS bm25_rank
                FROM records_fts JOIN records ON records.id=records_fts.record_id
                WHERE records_fts MATCH ? ORDER BY bm25_rank LIMIT ?
            """, (fts_query, max(1, min(100, limit)))).fetchall()
        return [dict(r) for r in rows]

    def _load_cached(self, db, record: dict, tier: str, scope: str) -> tuple[str, str]:
        cache = db.execute("SELECT * FROM cache WHERE tier=? AND scope=? AND record_id=?",
                           (tier, scope, record["id"])).fetchone()
        if cache and cache["source_version"] == record["version"]:
            db.execute("UPDATE cache SET hits=hits+1,last_access=? WHERE tier=? AND scope=? AND record_id=?",
                       (time.time(), tier, scope, record["id"]))
            return cache["representation"], "hit"
        if cache:
            db.execute("DELETE FROM cache WHERE tier=? AND scope=? AND record_id=?",
                       (tier, scope, record["id"]))
        summary = record["summary"]
        db.execute("""INSERT INTO cache(tier,scope,record_id,source_version,representation,token_cost,last_access)
                      VALUES(?,?,?,?,?,?,?)""",
                   (tier, scope, record["id"], record["version"], summary,
                    estimate_tokens(summary), time.time()))
        self._evict_if_needed(db, tier, scope)
        return summary, "miss"

    def _evict_if_needed(self, db, tier: str, scope: str):
        budget = self.l2_budget if tier == "L2" else self.l3_budget
        total = db.execute("SELECT COALESCE(SUM(token_cost),0) AS total FROM cache WHERE tier=? AND scope=?",
                           (tier,scope)).fetchone()["total"]
        while total > budget:
            victim = db.execute("""SELECT record_id,token_cost FROM cache
                                  WHERE tier=? AND scope=?
                                  ORDER BY hits ASC,last_access ASC LIMIT 1""",
                                (tier,scope)).fetchone()
            if victim is None: break
            db.execute("DELETE FROM cache WHERE tier=? AND scope=? AND record_id=?",
                       (tier,scope,victim["record_id"]))
            total -= victim["token_cost"]

    def prefetch(self, branch_id: str, record_ids: Iterable[str]) -> dict:
        """Stage external L2/L3 representations; does NOT load any LLM context."""
        chain = self.branch_chain(branch_id)
        outcomes = []
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for record_id in record_ids:
                r = db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
                if r is None: raise KeyError(record_id)
                rec = dict(r)
                tier, scope = ("L2",branch_id) if rec["branch_id"] in chain else ("L3","global")
                _, state = self._load_cached(db, rec, tier, scope)
                outcomes.append({"id":record_id,"tier":tier,"result":state})
            db.commit()
        return {"prefetched": outcomes}

    def get_context(self, branch_id: str, task: str, token_budget: int = 1200,
                    include_related: bool = True, max_items: int = 24) -> dict:
        """Select a bounded L1 representation; L2/L3 stay outside model context."""
        if token_budget < 100:
            raise ValueError("token_budget must be at least 100")
        chain = self.branch_chain(branch_id)
        with self.connect() as db:
            candidates: dict[str, dict] = {}
            def consider(row, relevance=0.0):
                if not row: return
                r = dict(row)
                if r["status"] == "superseded": return
                cid = r["id"]
                base = 6 if r["branch_id"] == branch_id else 3 if r["branch_id"] in chain else 0
                if r["pinned"]: base += 100
                if r["review_state"] == "needs_review": base -= 8
                score = base + relevance
                if cid not in candidates or score > candidates[cid]["score"]:
                    candidates[cid] = {"record":r,"score":score}
            # Bounded candidate generation: never scan the entire record corpus
            # or every record on an old research branch into the candidate set.
            # The full-text index supplies older query-relevant evidence.
            for row in db.execute("SELECT * FROM records WHERE pinned=1 ORDER BY updated_at DESC LIMIT 128"):
                consider(row)
            for index, item in enumerate(chain):
                row = db.execute("SELECT checkpoint_id FROM branches WHERE id=?", (item,)).fetchone()
                if row and row["checkpoint_id"]:
                    checkpoint = db.execute("SELECT * FROM records WHERE id=?", (row["checkpoint_id"],)).fetchone()
                    consider(checkpoint, 14 if index == 0 else 6)
                for row in db.execute("SELECT * FROM records WHERE branch_id=? ORDER BY updated_at DESC LIMIT 48", (item,)):
                    consider(row)
            hits = self.search(task, limit=30)
            for rank, rec in enumerate(hits):
                if not include_related and rec["branch_id"] not in chain:
                    continue
                consider(rec, 15 - 0.3 * rank)
            # One-hop graph neighborhood, only from already retrieved candidates.
            seeds = list(candidates)[:60]
            if include_related and seeds:
                for sid in seeds:
                    for row in db.execute("""SELECT records.* FROM edges JOIN records
                        ON records.id=CASE WHEN edges.source_id=? THEN edges.target_id ELSE edges.source_id END
                        WHERE edges.source_id=? OR edges.target_id=?""", (sid,sid,sid)):
                        consider(row, 2)
            ordered = sorted(candidates.values(), key=lambda x: (-x["score"], x["record"]["id"]))
            selected, used, skipped = [], 0, []
            db.execute("BEGIN IMMEDIATE")
            for c in ordered:
                if len(selected) >= max_items: break
                r = c["record"]
                tier, scope = ("L2",branch_id) if r["branch_id"] in chain else ("L3","global")
                # Exact provenance and warning are part of each L1 cache representation.
                overhead = f"[{r['id']}@v{r['version']} | {r['kind']} | {r['review_state']} | {tier}] {r['title']}\n"
                text = overhead + r["summary"] + ("\nSOURCE: " + r["source_uri"] if r["source_uri"] else "")
                cost = estimate_tokens(text)
                if used + cost > token_budget:
                    skipped.append(r["id"])
                    if r["pinned"]:
                        db.rollback()
                        raise ValueError("Insufficient budget for mandatory pinned context")
                    continue
                rep, outcome = self._load_cached(db, r, tier, scope)
                selected.append({"id":r["id"],"title":r["title"],"version":r["version"],
                                 "tier":tier,"cache":outcome,"tokens_est":cost,
                                 "review_state":r["review_state"],"text":overhead+rep+
                                 ("\nSOURCE: " + r["source_uri"] if r["source_uri"] else "")})
                used += cost
            db.commit()
            return {"branch":branch_id,"task":task,"budget_est_tokens":token_budget,
                    "used_est_tokens":used,"items":selected,"skipped":skipped,
                    "assembled_text":"\n\n".join(r["text"] for r in selected)}

    def checkpoint(self, branch_id: str, summary: str, actor: str = "agent") -> dict:
        self.get_branch(branch_id)
        record_id = f"CKPT-{uuid.uuid4().hex[:12]}"
        r = self.put_record(record_id=record_id, kind="checkpoint", branch_id=branch_id,
                            title=f"Checkpoint for {branch_id}", summary=summary, body=summary,
                            status="active", actor=actor)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE branches SET checkpoint_id=?,updated_at=? WHERE id=?",
                       (record_id,now(),branch_id))
            self._event(db, actor, "branch.checkpointed", branch_id, {"checkpoint_id":record_id})
            db.commit()
        return r

    def cache_stats(self) -> list[dict]:
        with self.connect() as db:
            return [dict(x) for x in db.execute("""SELECT tier,scope,COUNT(*) AS entries,
                    SUM(token_cost) AS est_tokens,SUM(hits) AS hits FROM cache
                    GROUP BY tier,scope ORDER BY tier,scope""")]

    def recent_events(self, limit: int = 30) -> list[dict]:
        with self.connect() as db:
            return [dict(x) for x in db.execute("SELECT * FROM events ORDER BY seq DESC LIMIT ?", (limit,))]

    def render_markdown(self, target_dir: str | Path) -> int:
        """Human-readable read-only projections; do not edit these files as authority."""
        out = Path(target_dir)
        out.mkdir(parents=True, exist_ok=True)
        n = 0
        with self.connect() as db:
            for r in db.execute("SELECT * FROM records ORDER BY kind,id"):
                kind_path = out / r["kind"]
                kind_path.mkdir(parents=True, exist_ok=True)
                metadata = {"id":r["id"],"kind":r["kind"],"branch_id":r["branch_id"],
                            "status":r["status"],"review_state":r["review_state"],
                            "version":r["version"],"source_uri":r["source_uri"]}
                edges = [dict(x) for x in db.execute(
                    "SELECT target_id,relation FROM edges WHERE source_id=?", (r["id"],))]
                content = f"# {r['title']}\n\n> GENERATED VIEW — update through API/CLI, not by editing this file.\n\n"
                content += "```json\n"+json.dumps(metadata,indent=2)+"\n```\n\n"
                content += "## Summary\n\n"+r["summary"]+"\n\n## Detail\n\n"+r["body"]+"\n\n"
                content += "## Outgoing edges\n\n"+("\n".join(f"- {x['relation']} → {x['target_id']}" for x in edges) or "None")+"\n"
                (kind_path / (r["id"] + ".md")).write_text(content, encoding="utf-8")
                n+=1
        return n
