"""Funnel analytics: candidates-per-stage, time-in-stage, source, offers."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException

from app.database import get_connection
from app.models import FUNNEL_ORDER, SOURCES

router = APIRouter(prefix="/api/jobs", tags=["analytics"])


def _iso_to_dt(value: str) -> datetime:
    """Parse SQLite's default ``YYYY-MM-DD HH:MM:SS`` UTC timestamps."""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


@router.get("/{job_id}/analytics")
def job_analytics(job_id: int) -> dict:
    """Return funnel, time-in-stage, source effectiveness and offer stats."""
    with get_connection() as conn:
        job = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, f"job {job_id} not found")

        # 1) Funnel: current count of candidates per stage.
        funnel_rows = conn.execute(
            "SELECT stage, COUNT(*) as c FROM candidates WHERE job_id = ? GROUP BY stage",
            (job_id,),
        ).fetchall()
        funnel = {r["stage"]: r["c"] for r in funnel_rows}

        # 2) Time-in-stage per active candidate (days since the move that
        #    landed them in their current stage).
        cands = conn.execute(
            "SELECT * FROM candidates WHERE job_id = ?", (job_id,)
        ).fetchall()
        time_in_stage = []
        now = datetime.now(timezone.utc)
        for cand in cands:
            ev = conn.execute(
                """SELECT changed_at FROM pipeline_events
                   WHERE candidate_id = ? AND to_stage = ?
                   ORDER BY changed_at DESC, id DESC LIMIT 1""",
                (cand["id"], cand["stage"]),
            ).fetchone()
            moved = ev["changed_at"] if ev else cand["created_at"]
            try:
                days = round((now - _iso_to_dt(moved)).total_seconds() / 86400.0, 2)
            except Exception:
                days = 0.0
            time_in_stage.append({
                "candidate_id": cand["id"],
                "name": cand["name"],
                "stage": cand["stage"],
                "moved_at": moved,
                "days_in_stage": max(0.0, days),
            })

        # 3) Source effectiveness: counts grouped by source.
        src_rows = conn.execute(
            "SELECT source, COUNT(*) as c FROM candidates WHERE job_id = ? GROUP BY source",
            (job_id,),
        ).fetchall()
        source_counts = {r["source"]: r["c"] for r in src_rows}
        source_effectiveness = [
            {"source": s, "count": source_counts.get(s, 0)} for s in SOURCES
        ]

        # 4) Offer acceptance rate: hired / (hired + rejected after offer).
        offer_rows = conn.execute(
            """SELECT to_stage, COUNT(*) as c FROM pipeline_events
               WHERE job_id = ? AND from_stage = 'offer' GROUP BY to_stage""",
            (job_id,),
        ).fetchall()
        accepted = 0
        declined = 0
        for r in offer_rows:
            if r["to_stage"] == "hired":
                accepted = r["c"]
            elif r["to_stage"] == "rejected":
                declined = r["c"]
        offer_total = accepted + declined
        acceptance_rate = (
            round(accepted / offer_total, 4) if offer_total > 0 else None
        )

    return {
        "job_id": job_id,
        "funnel": [
            {"stage": s, "count": funnel.get(s, 0)} for s in FUNNEL_ORDER + ["rejected"]
        ],
        "time_in_stage": time_in_stage,
        "source_effectiveness": source_effectiveness,
        "offer_acceptance_rate": acceptance_rate,
    }