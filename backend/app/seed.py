"""Sample data seeder.

Populates the database with a few jobs, candidates at every pipeline stage, and
a full audit history of stage transitions so the funnel analytics dashboard has
meaningful data out of the box. Idempotent: only seeds when the jobs table is
empty (or when ``force=True`` is passed).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.database import DB_PATH, get_connection, init_db

# (job) rows and (candidates with their stage timeline).
# Events are expressed as (from_stage, to_stage, days_ago).

_JOBS = [
    {
        "title": "Senior Backend Engineer",
        "description": "Design and ship scalable Python services powering our data platform.",
        "required_skills": ["python", "sql", "fastapi", "docker", "postgresql"],
        "seniority": "senior",
        "location": "Remote (Europe)",
        "salary_min": 90000,
        "salary_max": 130000,
    },
    {
        "title": "Data Scientist",
        "description": "Build and evaluate ML models on large customer datasets.",
        "required_skills": ["python", "machine-learning", "sql", "statistics"],
        "seniority": "mid",
        "location": "Hybrid (London)",
        "salary_min": 70000,
        "salary_max": 95000,
    },
    {
        "title": "Frontend Engineer",
        "description": "Own the product UI with clean, accessible React screens.",
        "required_skills": ["javascript", "react", "html", "css"],
        "seniority": "junior",
        "location": "Remote",
        "salary_min": 55000,
        "salary_max": 75000,
    },
]

# candidate: (job_title, name, email, skills, exp, location, notice_days, source, events)
EVENTS_KEY = "events"
_CANDIDATES = [
    {
        "job_title": "Senior Backend Engineer",
        "name": "Alice Chen", "email": "alice@example.com",
        "skills": ["Python", "SQL", "FastAPI", "Docker"], "exp": 7,
        "location": "Berlin", "notice": 30, "source": "referral",
        "events": [("", "sourced", 60), ("sourced", "screened", 50),
                   ("screened", "interview", 38), ("interview", "offer", 20),
                   ("offer", "hired", 12)],
    },
    {
        "job_title": "Senior Backend Engineer",
        "name": "Bob Martin", "email": "bob@example.com",
        "skills": ["Python", "SQL", "PostgreSQL"], "exp": 6,
        "location": "Prague", "notice": 60, "source": "linkedin",
        "events": [("", "sourced", 45), ("sourced", "screened", 33)],
    },
    {
        "job_title": "Senior Backend Engineer",
        "name": "Carol Silva", "email": "carol@example.com",
        "skills": ["Python", "Java", "Docker"], "exp": 5,
        "location": "Lisbon", "notice": 15, "source": "jobboard",
        "events": [("", "sourced", 20)],
    },
    {
        "job_title": "Senior Backend Engineer",
        "name": "Dan Patel", "email": "dan@example.com",
        "skills": ["Python", "SQL", "FastAPI", "Docker", "PostgreSQL"], "exp": 9,
        "location": "Singapore", "notice": 45, "source": "agency",
        "events": [("", "sourced", 40), ("sourced", "screened", 32),
                   ("screened", "interview", 24), ("interview", "offer", 10),
                   ("offer", "hired", 3)],
    },
    {
        "job_title": "Senior Backend Engineer",
        "name": "Eve Novak", "email": "eve@example.com",
        "skills": ["JavaScript", "Node.js"], "exp": 4,
        "location": "Warsaw", "notice": 30, "source": "linkedin",
        "events": [("", "sourced", 15), ("sourced", "screened", 12),
                   ("screened", "interview", 6), ("interview", "rejected", 2)],
    },
    {
        "job_title": "Data Scientist",
        "name": "Fatima Noor", "email": "fatima@example.com",
        "skills": ["Python", "Machine Learning", "SQL"], "exp": 5,
        "location": "London", "notice": 30, "source": "referral",
        "events": [("", "sourced", 28), ("sourced", "screened", 20),
                   ("screened", "interview", 9)],
    },
    {
        "job_title": "Data Scientist",
        "name": "George Hill", "email": "george@example.com",
        "skills": ["R", "Statistics", "SQL"], "exp": 3,
        "location": "Manchester", "notice": 0, "source": "jobboard",
        "events": [("", "sourced", 10)],
    },
    {
        "job_title": "Frontend Engineer",
        "name": "Hana Kim", "email": "hana@example.com",
        "skills": ["JavaScript", "React", "HTML", "CSS"], "exp": 2,
        "location": "Seoul", "notice": 15, "source": "referral",
        "events": [("", "sourced", 25), ("sourced", "screened", 18),
                   ("screened", "interview", 7)],
    },
    {
        "job_title": "Frontend Engineer",
        "name": "Ivan Petrov", "email": "ivan@example.com",
        "skills": ["JavaScript", "HTML"], "exp": 1,
        "location": "Sofia", "notice": 0, "source": "agency",
        "events": [("", "sourced", 8)],
    },
]


def seed_if_empty(force: bool = False) -> bool:
    """Seed sample data if the DB is empty; return True if seeding ran."""
    init_db()
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]
        if count > 0 and not force:
            return False
    _insert_seed_data()
    return True


def _insert_seed_data() -> None:
    """Insert the sample jobs, candidates and their transition history."""
    with get_connection() as conn:
        job_ids = {}
        for job in _JOBS:
            cur = conn.execute(
                """INSERT INTO jobs (title, description, required_skills, seniority,
                                     location, salary_min, salary_max, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'open')""",
                (job["title"], job["description"], json.dumps(job["required_skills"]),
                 job["seniority"], job["location"], job["salary_min"], job["salary_max"]),
            )
            job_ids[job["title"]] = cur.lastrowid

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for cand in _CANDIDATES:
            job_id = job_ids[cand["job_title"]]
            cur = conn.execute(
                """INSERT INTO candidates (job_id, name, email, skills, experience_years,
                                           location, notice_period_days, source, stage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'sourced')""",
                (job_id, cand["name"], cand["email"], json.dumps(cand["skills"]),
                 cand["exp"], cand["location"], cand["notice"], cand["source"]),
            )
            cid = cur.lastrowid
            final_stage = cand["events"][-1][1]
            conn.execute("UPDATE candidates SET stage = ? WHERE id = ?", (final_stage, cid))

            for from_stage, to_stage, days_ago in cand["events"]:
                ts = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(
                    """INSERT INTO pipeline_events (candidate_id, job_id, from_stage,
                                                    to_stage, changed_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (cid, job_id, from_stage, to_stage, ts),
                )
        conn.commit()

    print(f"[ScoutForge] Seeded {len(_JOBS)} jobs and {len(_CANDIDATES)} candidates "
          f"into {DB_PATH}")


if __name__ == "__main__":  # pragma: no cover - convenience CLI
    seeded = seed_if_empty(force=False)
    print("Seeded" if seeded else "Database already contains data; nothing to seed.")