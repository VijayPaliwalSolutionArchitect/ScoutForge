"""Pipeline endpoints: move candidates between stages + full audit trail."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.database import get_connection
from app.models import PipelineMove, STAGES

router = APIRouter(prefix="/api/candidates", tags=["pipeline"])


@router.post("/{candidate_id}/stage")
def move_stage(candidate_id: int, payload: PipelineMove) -> dict:
    """Move a candidate to a new pipeline stage and record the transition.

    Valid target stages: sourced, screened, interview, offer, hired, rejected.
    Every move is written to ``pipeline_events`` for full auditability.
    """
    if payload.to_stage not in STAGES:
        raise HTTPException(422, f"to_stage must be one of {STAGES}")

    with get_connection() as conn:
        cand = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not cand:
            raise HTTPException(404, f"candidate {candidate_id} not found")
        prev = cand["stage"]
        conn.execute(
            "UPDATE candidates SET stage = ? WHERE id = ?", (payload.to_stage, candidate_id)
        )
        conn.execute(
            """INSERT INTO pipeline_events (candidate_id, job_id, from_stage, to_stage)
               VALUES (?, ?, ?, ?)""",
            (candidate_id, cand["job_id"], prev, payload.to_stage),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    return {"candidate": dict(row), "from_stage": prev, "to_stage": payload.to_stage}


@router.get("/{candidate_id}/pipeline")
def pipeline_history(candidate_id: int) -> dict:
    """Return the full stage-transition audit trail for a candidate."""
    with get_connection() as conn:
        cand = conn.execute("SELECT id FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not cand:
            raise HTTPException(404, f"candidate {candidate_id} not found")
        rows = conn.execute(
            """SELECT id, job_id, from_stage, to_stage, changed_at
               FROM pipeline_events WHERE candidate_id = ? ORDER BY changed_at, id""",
            (candidate_id,),
        ).fetchall()
    return {"candidate_id": candidate_id, "events": [dict(r) for r in rows]}