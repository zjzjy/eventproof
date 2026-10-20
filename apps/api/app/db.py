from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
DEFAULT_DB = DATA_DIR / "eventproof.db"
PRECOMPUTED = ROOT / "fixtures" / "tongyu" / "precomputed.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  storyline_id TEXT,
  title TEXT,
  event_type TEXT,
  primary_entity TEXT,
  security_code TEXT,
  exchange TEXT,
  occurred_at TEXT,
  occurred_precision TEXT,
  disclosed_at TEXT,
  disclosed_precision TEXT,
  first_ingested_at TEXT,
  updated_at TEXT,
  verification_status TEXT,
  lifecycle_status TEXT,
  impact_status TEXT,
  status_detail TEXT,
  evidence_strength REAL,
  summary TEXT,
  current_revision_id TEXT,
  data_as_of TEXT
);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  event_id TEXT,
  title TEXT,
  doc_type TEXT,
  sort_order INTEGER,
  source TEXT,
  source_tier TEXT,
  published_at TEXT,
  occurred_at TEXT,
  time_precision TEXT,
  url TEXT,
  ingested_at TEXT,
  data_origin TEXT,
  claim_count INTEGER,
  snippets TEXT
);

CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY,
  event_id TEXT,
  document_id TEXT,
  text TEXT,
  claim_type TEXT,
  claim_role TEXT,
  subject TEXT,
  predicate TEXT,
  object TEXT,
  slot TEXT,
  value TEXT,
  unit TEXT,
  quote TEXT,
  hedge TEXT,
  confidence REAL,
  status TEXT,
  strength REAL,
  strength_band TEXT,
  strength_json TEXT,
  strength_explanation TEXT,
  introduced_at TEXT,
  is_inferred INTEGER,
  source_tier TEXT
);

CREATE TABLE IF NOT EXISTS revisions (
  id TEXT PRIMARY KEY,
  event_id TEXT,
  version INTEGER,
  knowledge_at TEXT,
  summary TEXT,
  verification_status TEXT,
  lifecycle_status TEXT,
  impact_status TEXT,
  evidence_strength REAL,
  status_detail TEXT,
  claim_ids TEXT,
  changed_fields TEXT,
  reason TEXT,
  trigger_document_id TEXT,
  is_inferred INTEGER,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS merge_decisions (
  id TEXT PRIMARY KEY,
  event_id TEXT,
  document_id TEXT,
  relation TEXT,
  score REAL,
  decision TEXT,
  shared_slots TEXT,
  differences TEXT,
  reason TEXT,
  model TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
  id TEXT PRIMARY KEY,
  event_id TEXT,
  revision_id TEXT,
  level TEXT,
  title TEXT,
  body TEXT,
  why TEXT,
  created_at TEXT,
  read_at TEXT,
  diff_json TEXT
);

CREATE TABLE IF NOT EXISTS llm_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task TEXT,
  model TEXT,
  prompt_version TEXT,
  input_hash TEXT,
  output_json TEXT,
  valid INTEGER,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  cost_cny REAL,
  document_id TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS app_meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


def db_path() -> Path:
    return Path(os.getenv("EVENTPROOF_DB", str(DEFAULT_DB)))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _insert(conn: sqlite3.Connection, table: str, row: dict[str, Any]) -> None:
    columns = list(row.keys())
    placeholders = ",".join("?" for _ in columns)
    values = [
        json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
        for value in row.values()
    ]
    sql = f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
    conn.execute(sql, values)


def init_db(force: bool = False) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        claim_columns = {row[1] for row in conn.execute("PRAGMA table_info(claims)").fetchall()}
        if "slot" not in claim_columns:
            conn.execute("ALTER TABLE claims ADD COLUMN slot TEXT")
        count = conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
        if count and not force:
            return
        if force:
            for table in (
                "events",
                "documents",
                "claims",
                "revisions",
                "merge_decisions",
                "notifications",
                "llm_calls",
                "app_meta",
            ):
                conn.execute(f"DELETE FROM {table}")

        data = json.loads(PRECOMPUTED.read_text(encoding="utf-8"))
        _insert(conn, "events", data["event"])
        for doc in data["documents"]:
            _insert(conn, "documents", doc)
        for claim in data["claims"]:
            row = dict(claim)
            if row.get("value") is not None:
                row["value"] = str(row["value"])
            row["is_inferred"] = 1 if row.get("is_inferred") else 0
            _insert(conn, "claims", row)
        for revision in data["revisions"]:
            row = dict(revision)
            row["is_inferred"] = 1 if row.get("is_inferred") else 0
            _insert(conn, "revisions", row)
        for merge in data["merge_decisions"]:
            _insert(conn, "merge_decisions", merge)
        for notification in data["notifications"]:
            _insert(conn, "notifications", notification)
        for call in data["llm_calls"]:
            row = dict(call)
            row.pop("id", None)
            row["valid"] = 1 if row.get("valid") else 0
            _insert(conn, "llm_calls", row)
        _insert(
            conn,
            "app_meta",
            {"key": "app_meta", "value": json.dumps(data["meta"], ensure_ascii=False)},
        )
        conn.commit()
    finally:
        conn.close()


def rows(table: str, where: str = "", params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = connect()
    try:
        sql = f"SELECT * FROM {table}"
        if where:
            sql += " WHERE " + where
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def row(table: str, where: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    conn = connect()
    try:
        found = conn.execute(f"SELECT * FROM {table} WHERE {where}", params).fetchone()
        return dict(found) if found else None
    finally:
        conn.close()


def mark_notification_read(notification_id: str, read_at: str) -> bool:
    conn = connect()
    try:
        cur = conn.execute(
            "UPDATE notifications SET read_at = ? WHERE id = ?",
            (read_at, notification_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def reset_db() -> None:
    init_db(force=True)
