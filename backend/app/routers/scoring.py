"""AI shortlisting: return the top-k candidates for a job by match score."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.database import get_connection
from app.scoring import score_candidate

router = APIRouter(tags=["shortlist"])


def _load_skills(text: str) -> list:
    try:
        return json.loads(text or "[]")
    except (json.JSONDecodeError, TypeError):
        return []


@router.get("/api/jobs/{job_id}/shortlist")
def shortlist(job_id: int, k: int = 5) -> dict:
    """Return the top-k candidates for a job ranked by AI match score.

    Passthrough scoring: nonzero scoring candidates sorted by ``total``
    descending, truncated to ``k``, with their full breakdown included.
    """
    with get_connection() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, f"job {job_id} not found")
        cands = conn.execute(
            "SELECT * FROM candidates WHERE job_id = ?", (job_id,)
        ).fetchall()

    req_skills = _load_skills(job["required_skills"])
    ranked = []
    for cand in cands:
        result = score_candidate(
            job_id=job_id,
            candidate_id=cand["id"],
            candidate_skills=_load_skills(cand["skills"]),
            required_skills=req_skills,
            seniority=job["seniority"],
            experience_years=cand["experience_years"],
        )
        ranked.append({
            "candidate_id": cand["id"],
            "name": cand["name"],
            "stage": cand["stage"],
            "source": cand["source"],
            "experience_years": cand["experience_years"],
            "score": result,
        })

    ranked.sort(key=lambda r: r["score"]["total"], reverse=True)
    return {
        "job_id": job_id,
        "job_title": job["title"],
        "k": k,
        "scored": len(ranked),
        "shortlist": ranked[: max(0, int(k))],
    }