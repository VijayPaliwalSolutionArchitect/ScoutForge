"""Job management endpoints: create / list / get / update / close."""
from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, HTTPException

from app.database import get_connection
from app.models import JOB_STATUSES, JobCreate, JobUpdate

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _serialize(row) -> dict:
    """Convert a job row to a plain dict, decoding its skills JSON."""
    data = dict(row)
    try:
        data["required_skills"] = json.loads(data.get("required_skills") or "[]")
    except (TypeError, json.JSONDecodeError):
        data["required_skills"] = []
    return data


@router.get("")
def list_jobs(status: str | None = None) -> dict:
    """Return all jobs, optionally filtered by status (open/closed)."""
    query = "SELECT * FROM jobs"
    params: List = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return {"jobs": [_serialize(r) for r in rows]}


@router.post("", status_code=201)
def create_job(payload: JobCreate) -> dict:
    """Create a new job opening."""
    if payload.seniority not in {"junior", "mid", "senior", "lead"}:
        raise HTTPException(422, f"seniority must be one of junior/mid/senior/lead")
    if payload.salary_min and payload.salary_max and payload.salary_min > payload.salary_max:
        raise HTTPException(422, "salary_min cannot exceed salary_max")
    if len(payload.required_skills) == 0:
        raise HTTPException(422, "at least one required_skill is needed for scoring")

    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO jobs (title, description, required_skills, seniority,
                                 location, salary_min, salary_max, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'open')""",
            (
                payload.title,
                payload.description,
                json.dumps(payload.required_skills),
                payload.seniority,
                payload.location,
                payload.salary_min,
                payload.salary_max,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"job": _serialize(row)}


@router.get("/{job_id}")
def get_job(job_id: int) -> dict:
    """Return a single job by id."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"job {job_id} not found")
    return {"job": _serialize(row)}


@router.patch("/{job_id}")
def update_job(job_id: int, payload: JobUpdate) -> dict:
    """Partially update a job (fields provided are updated)."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"job {job_id} not found")
        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"] not in JOB_STATUSES:
            raise HTTPException(422, f"status must be one of {JOB_STATUSES}")
        if "required_skills" in data:
            data["required_skills"] = json.dumps(data["required_skills"])
        if data:
            cols = ", ".join(f"{k} = ?" for k in data)
            conn.execute(f"UPDATE jobs SET {cols} WHERE id = ?", (*data.values(), job_id))
            conn.commit()
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return {"job": _serialize(row)}


@router.post("/{job_id}/close")
def close_job(job_id: int) -> dict:
    """Mark a job as closed so it stops appearing in active pipelines."""
    with get_connection() as conn:
        cur = conn.execute("UPDATE jobs SET status = 'closed' WHERE id = ?", (job_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, f"job {job_id} not found")
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return {"job": _serialize(row)}