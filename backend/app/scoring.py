"""Deterministic, local AI skill-match scoring.

No cloud LLM is involved: every score is a pure function of a candidate's
profile and a job's requirements, so results are repeatable and auditable.

Scoring model (normalized to 0-100):

* ``skills`` component  (60% weight)
    Ratio of the job's *required* skills that the candidate possesses.
    A candidate with all required skills scores 1.0 here.

* ``seniority`` component (40% weight)
    How well the candidate's years of experience fit the job's seniority
    band. A candidate at or above the band floor scores 1.0.

The returned breakdown lets hiring teams see *why* a candidate scored the way
they did, which supports auditability and rejection feedback.
"""
from __future__ import annotations

from typing import Dict, List

# Expected experience bands (inclusive floors) per seniority level.
SENIORITY_BANDS: Dict[str, tuple[int, float]] = {
    "junior": (0, 3.0),
    "mid": (2, 6.0),
    "senior": (4, 12.0),
    "lead": (7, 20.0),
}

SKILLS_WEIGHT = 0.6
SENIORITY_WEIGHT = 0.4


def _normalize_skills(raw: List[str]) -> List[str]:
    """Lowercase and strip skill tags for robust overlap comparison."""
    return [s.strip().lower() for s in raw if s and s.strip()]


def _skills_component(candidate_skills: List[str], required_skills: List[str]) -> tuple[float, List[str], List[str]]:
    """Compute the skills overlap ratio and the matched/missing lists."""
    cand = set(_normalize_skills(candidate_skills))
    req = set(_normalize_skills(required_skills))
    matched = sorted(cand & req)
    if not req:
        # No required skills -> nothing to miss.
        ratio, missing = 1.0, []
    else:
        ratio = len(matched) / len(req)
        missing = sorted(req - cand)
    return ratio, matched, missing


def _seniority_component(seniority: str, experience_years: float) -> tuple[float, str]:
    """Compute the seniority fit score (0-1) for a candidate's experience."""
    floor, _ceil = SENIORITY_BANDS.get(seniority, SENIORITY_BANDS["mid"])
    expected = f"{floor}+ years"
    match = 1.0 if experience_years >= floor else max(0.0, experience_years / floor)
    return round(match, 4), expected


def score_candidate(
    job_id: int,
    candidate_id: int,
    candidate_skills: List[str],
    required_skills: List[str],
    seniority: str,
    experience_years: float,
) -> dict:
    """Score a single candidate against a job.

    Returns a serializable dict matching :class:`app.models.ScoreResponse`.
    """
    skills_ratio, matched, missing = _skills_component(candidate_skills, required_skills)
    skills_score = skills_ratio * 100.0

    seniority_score_01, expected = _seniority_component(seniority, experience_years)
    seniority_score = seniority_score_01 * 100.0

    total = round(
        SKILLS_WEIGHT * skills_score + SENIORITY_WEIGHT * seniority_score,
        2,
    )

    return {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "total": total,
        "skills": {
            "candidate_skills": _normalize_skills(candidate_skills),
            "required_skills": _normalize_skills(required_skills),
            "matched": matched,
            "missing": missing,
            "matched_ratio": round(skills_ratio, 4),
            "score": round(skills_score, 2),
        },
        "seniority": {
            "level": seniority,
            "expected_years": expected,
            "candidate_years": experience_years,
            "score": round(seniority_score, 2),
        },
    }