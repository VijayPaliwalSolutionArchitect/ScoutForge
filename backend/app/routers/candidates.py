"""Candidate management endpoints: create / list / get / update / score."""
from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, HTTPException

from app.database import get_connection
from app.models import CandidateCreate, CandidateUpdate, SOURCES
from app.scoring import score_candidate

router = APIRouter(prefix="/api/candidates", tags=["candidates"])
_routers_candidates = router  # alias kept for clarity in imports elsewhere


def _serialize(row, include_job: bool = True) -> dict:
    """Convert a candidate row to a dict, decoding its skills JSON."""
    data = dict(row)
    try:
        data["skills"] = json.loads(data.get("skills") or "[]")
    except (TypeError, json.JSONDecodeError):
        data["skills"] = []
    if include_job:
        with get_connection() as conn:
            job = conn.execute("SELECT id, title FROM jobs WHERE id = ?", (data["job_id"],)).fetchone()
        data["job_title"] = job["title"] if job else None
    return data


@router.get("")
def list_candidates(job_id: int | None = None) -> dict:
    """Return candidates, optionally filtered by the job they are sourced for."""
    query = "SELECT * FROM candidates"
    params: List = []
    if job_id is not None:
        query += " WHERE job_id = ?"
        params.append(job_id)
    query += " ORDER BY created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return {"candidates": [_serialize(r) for r in rows]}


@router.post("", status_code=201)
def create_candidate(payload: CandidateCreate) -> dict:
    """Create a candidate tied to a job.

    Registers an initial pipeline event so the audit trail spans the entire
    funnel from the moment the candidate enters it.
    """
    if payload.source not in SOURCES:
        raise HTTPException(422, f"source must be one of {SOURCES}")

    with get_connection() as conn:
        job = conn.execute("SELECT id FROM jobs WHERE id = ?", (payload.job_id,)).fetchone()
        if not job:
            raise HTTPException(404, f"job {payload.job_id} not found")
        cur = conn.execute(
            """INSERT INTO candidates (job_id, name, email, skills, experience_years,
                                       location, notice_period_days, source, stage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'sourced')""",
            (
                payload.job_id,
                payload.name,
                payload.email,
                json.dumps(payload.skills),
                payload.experience_years,
                payload.location,
                payload.notice_period_days,
                payload.source,
            ),
        )
        cid = cur.lastrowid
        conn.execute(
            """INSERT INTO pipeline_events (candidate_id, job_id, from_stage, to_stage)
               VALUES (?, ?, '', 'sourced')""",
            (cid, payload.job_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (cid,)).fetchone()
    return {"candidate": _serialize(row)}


@router.get("/{candidate_id}")
def get_candidate(candidate_id: int) -> dict:
    """Return a single candidate by id."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"candidate {candidate_id} not found")
    return {"candidate": _serialize(row)}


@router.patch("/{candidate_id}")
def update_candidate(candidate_id: int, payload: CandidateUpdate) -> dict:
    """Partially update a candidate profile (does not change pipeline stage)."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"candidate {candidate_id} not found")
        data = payload.model_dump(exclude_unset=True)
        if "skills" in data:
            data["skills"] = json.dumps(data["skills"])
        if data:
            cols = ", ".join(f"{k} = ?" for k in data)
            conn.execute(f"UPDATE candidates SET {cols} WHERE id = ?", (*data.values(), candidate_id))
            conn.commit()
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    return {"candidate": _serialize(row)}


@router.get("/{candidate_id}/score")
def score_candidate_endpoint(candidate_id: int) -> dict:
    """Score a stored candidate against the job they are sourcing for."""
    with get_connection() as conn:
        cand = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not cand:
            raise HTTPException(404, f"candidate {candidate_id} not found")
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (cand["job_id"],)).fetchone()
        if not job:
            raise HTTPException(404, f"job {cand['job_id']} not found")

    try:
        cand_skills = json.loads(cand["skills"] or "[]")
    except json.JSONDecodeError:
        cand_skills = []
    try:
        req_skills = json.loads(job["required_skills"] or "[]")
    except json.JSONDecodeError:
        req_skills = []

    result = score_candidate(
        job_id=job["id"],
        candidate_id=cand["id"],
        candidate_skills=cand_skills,
        required_skills=req_skills,
        seniority=job["seniority"],
        experience_years=cand["experience_years"],
    )
    return {"score": result}