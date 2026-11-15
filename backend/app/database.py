"""SQLite persistence layer for ScoutForge.

Uses the standard-library :mod:`sqlite3` module exclusively (no ORM). The
database file location can be overridden via the ``SCOUTFORGE_DB`` environment
variable, which is useful for tests that want an isolated, ephemeral database.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent

# Path to the SQLite file. Override with SCOUTFORGE_DB for isolated test DBs.
DB_PATH = os.environ.get(
    "SCOUTFORGE_DB", str(_BASE_DIR / "scoutforge.db")
)


# Schema is written idempotently (IF NOT EXISTS) so init_db() can run safely
# on every app start without clobbering existing data.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    required_skills TEXT NOT NULL DEFAULT '[]',
    seniority       TEXT NOT NULL DEFAULT 'mid',
    location        TEXT NOT NULL DEFAULT '',
    salary_min      INTEGER,
    salary_max      INTEGER,
    status          TEXT NOT NULL DEFAULT 'open',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS candidates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id              INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    email               TEXT NOT NULL DEFAULT '',
    skills              TEXT NOT NULL DEFAULT '[]',
    experience_years    REAL NOT NULL DEFAULT 0,
    location            TEXT NOT NULL DEFAULT '',
    notice_period_days  INTEGER NOT NULL DEFAULT 0,
    source              TEXT NOT NULL DEFAULT 'linkedin',
    stage               TEXT NOT NULL DEFAULT 'sourced',
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pipeline_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    job_id       INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    from_stage   TEXT NOT NULL DEFAULT '',
    to_stage     TEXT NOT NULL,
    changed_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_candidates_job     ON candidates(job_id);
CREATE INDEX IF NOT EXISTS idx_events_candidate   ON pipeline_events(candidate_id);
CREATE INDEX IF NOT EXISTS idx_events_job         ON pipeline_events(job_id);
"""


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create the schema if it does not already exist (idempotent)."""
    with get_connection() as conn:
        conn.executescript(_SCHEMA)