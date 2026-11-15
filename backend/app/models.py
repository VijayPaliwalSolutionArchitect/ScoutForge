"""Pydantic models and domain constants for ScoutForge.

These models validate request/response payloads. Domain enumeration values are
kept in a single source of truth here so routers and scoring logic stay in sync.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

# ── Domain constants (single source of truth) ────────────────────────────────
JOB_STATUSES: List[str] = ["open", "closed"]
SENIORITIES: List[str] = ["junior", "mid", "senior", "lead"]
SOURCES: List[str] = ["referral", "linkedin", "jobboard", "agency"]
STAGES: List[str] = ["sourced", "screened", "interview", "offer", "hired", "rejected"]

# Ordered funnel for analytics / valid transitions.
FUNNEL_ORDER: List[str] = ["sourced", "screened", "interview", "offer", "hired"]


# ── Jobs ──────────────────────────────────────────────────────────────────────
class JobCreate(BaseModel):
    """Payload for creating a new job opening."""

    title: str = Field(..., min_length=1, description="Job title")
    description: str = Field(default="", description="Job description")
    required_skills: List[str] = Field(default_factory=list, description="Required skill tags")
    seniority: str = Field(default="mid", description="One of junior/mid/senior/lead")
    location: str = Field(default="Remote", description="Work location")
    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)


class JobUpdate(BaseModel):
    """Updatable job fields (all optional, PATCH semantics)."""

    title: Optional[str] = None
    description: Optional[str] = None
    required_skills: Optional[List[str]] = None
    seniority: Optional[str] = None
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    status: Optional[str] = None


# ── Candidates ────────────────────────────────────────────────────────────────
class CandidateCreate(BaseModel):
    """Payload for creating a new candidate (always tied to a job)."""

    job_id: int = Field(..., description="The job the candidate is being sourced for")
    name: str = Field(..., min_length=1)
    email: str = Field(default="", description="Contact email")
    skills: List[str] = Field(default_factory=list)
    experience_years: float = Field(default=0, ge=0)
    location: str = Field(default="", description="Candidate location")
    notice_period_days: int = Field(default=0, ge=0)
    source: str = Field(default="linkedin", description="One of referral/linkedin/jobboard/agency")


class CandidateUpdate(BaseModel):
    """Updatable candidate profile fields (all optional)."""

    name: Optional[str] = None
    email: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_years: Optional[float] = None
    location: Optional[str] = None
    notice_period_days: Optional[int] = None
    source: Optional[str] = None


class PipelineMove(BaseModel):
    """Payload to move a candidate to a new pipeline stage."""

    to_stage: str = Field(..., description="Target stage: sourced/screened/interview/offer/hired/rejected")


# ── Shared response envelopes ─────────────────────────────────────────────────
class ScoreBreakdownSkills(BaseModel):
    candidate_skills: List[str]
    required_skills: List[str]
    matched: List[str]
    missing: List[str]
    matched_ratio: float
    score: float


class ScoreBreakdownSeniority(BaseModel):
    level: str
    expected_years: Optional[str]
    candidate_years: float
    score: float


class ScoreResponse(BaseModel):
    job_id: int
    candidate_id: int
    total: float
    skills: ScoreBreakdownSkills
    seniority: ScoreBreakdownSeniority


class FunnelBucket(BaseModel):
    stage: str
    count: int


class TimeInStageEntry(BaseModel):
    candidate_id: int
    name: str
    stage: str
    moved_at: str
    days_in_stage: float


class AnalyticsResponse(BaseModel):
    funnel: List[FunnelBucket]
    time_in_stage: List[TimeInStageEntry]
    source_effectiveness: List[dict]
    offer_acceptance_rate: Optional[float]
    payload: dict = Field(default_factory=dict, description="Raw aggregate data")