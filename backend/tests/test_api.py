"""End-to-end API tests for ScoutForge.

Runs against an isolated, ephemeral SQLite database so the developer's real
data is never touched. The SCOUTFORGE_DB env var points at a temp file *before*
the app package is imported, which is why it lives at module top level.
"""
import os
import tempfile
import pathlib

os.environ["SCOUTFORGE_DB"] = str(
    pathlib.Path(tempfile.gettempdir()) / "scoutforge_test.db"
)
try:
    pathlib.Path(os.environ["SCOUTFORGE_DB"]).unlink(missing_ok=True)
except OSError:
    pass

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Yields a TestClient; entering the context triggers app startup/seed."""
    with TestClient(app) as c:
        yield c


# ── Health ────────────────────────────────────────────────────────────────────
def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["service"] == "ScoutForge"


# ── Jobs ──────────────────────────────────────────────────────────────────────
def test_list_seeded_jobs(client):
    res = client.get("/api/jobs")
    assert res.status_code == 200
    jobs = res.json()["jobs"]
    assert len(jobs) >= 3  # seeded sample data
    assert {"python", "fastapi", "docker"} <= set(jobs[0]["required_skills"])


def test_create_get_close_job(client):
    payload = {
        "title": "DevOps Engineer",
        "description": "Build CI/CD and cloud infrastructure.",
        "required_skills": ["terraform", "aws", "kubernetes"],
        "seniority": "mid",
        "location": "Remote",
        "salary_min": 80000,
        "salary_max": 110000,
    }
    created = client.post("/api/jobs", json=payload)
    assert created.status_code == 201
    job = created.json()["job"]
    job_id = job["id"]

    fetched = client.get(f"/api/jobs/{job_id}").json()["job"]
    assert fetched["title"] == "DevOps Engineer"
    assert fetched["required_skills"] == ["terraform", "aws", "kubernetes"]

    closed = client.post(f"/api/jobs/{job_id}/close")
    assert closed.json()["job"]["status"] == "closed"

    assert client.get("/api/jobs/999999").status_code == 404


def test_job_requires_skill(client):
    res = client.post("/api/jobs", json={"title": "x", "required_skills": []})
    assert res.status_code == 422


# ── Candidates + scoring ──────────────────────────────────────────────────────
def test_create_candidate_and_score(client):
    job = client.post("/api/jobs", json={
        "title": "ML Engineer",
        "required_skills": ["python", "machine-learning", "pytorch"],
        "seniority": "senior",
        "location": "Remote",
    }).json()["job"]

    cand = client.post("/api/candidates", json={
        "job_id": job["id"],
        "name": "Test Candidate",
        "skills": ["Python", "Machine-Learning", "PyTorch", "SQL"],
        "experience_years": 8,
        "source": "referral",
    })
    assert cand.status_code == 201
    cid = cand.json()["candidate"]["id"]

    score = client.get(f"/api/candidates/{cid}/score").json()["score"]
    assert 0 <= score["total"] <= 100
    # Full skills overlap (skills ratio == 1.0) + senior qualified => high score.
    assert score["skills"]["matched_ratio"] == 1.0
    assert score["total"] >= 90


def test_shortlist_top_k_sorted(client):
    job_id = client.post("/api/jobs", json={
        "title": "Sourcing Test",
        "required_skills": ["python", "sql"],
        "seniority": "mid",
    }).json()["job"]["id"]
    for name, sk, exp in [
        ("Low", ["ruby"], 1),
        ("High", ["Python", "SQL"], 5),
        ("Mid", ["Python"], 3),
    ]:
        client.post("/api/candidates", json={
            "job_id": job_id, "name": name, "skills": sk,
            "experience_years": exp, "source": "linkedin",
        })
    res = client.get(f"/api/jobs/{job_id}/shortlist", params={"k": 3})
    body = res.json()
    ordered = [c["name"] for c in body["shortlist"]]
    assert ordered == ["High", "Mid", "Low"]
    assert [c["score"]["total"] for c in body["shortlist"]] == sorted(
        [c["score"]["total"] for c in body["shortlist"]], reverse=True
    )


# ── Pipeline + analytics ──────────────────────────────────────────────────────
def test_pipeline_move_and_audit(client):
    job = client.post("/api/jobs", json={
        "title": "Pipeline Job", "required_skills": ["go"], "seniority": "junior",
    }).json()["job"]
    cid = client.post("/api/candidates", json={
        "job_id": job["id"], "name": "Pip", "skills": ["Go"], "source": "agency",
    }).json()["candidate"]["id"]

    moved = client.post(f"/api/candidates/{cid}/stage", json={"to_stage": "interview"})
    assert moved.json()["to_stage"] == "interview"
    assert moved.json()["from_stage"] == "sourced"

    history = client.get(f"/api/candidates/{cid}/pipeline").json()["events"]
    assert [e["to_stage"] for e in history] == ["sourced", "interview"]

    # Invalid stage rejected.
    assert client.post(f"/api/candidates/{cid}/stage", json={"to_stage": "nope"}).status_code == 422


def test_analytics_funnel(client):
    job = client.post("/api/jobs", json={
        "title": "Analytics Job", "required_skills": ["java"], "seniority": "mid",
    }).json()["job"]
    client.post("/api/candidates", json={
        "job_id": job["id"], "name": "A", "skills": ["java"], "source": "referral",
    })
    ana = client.get(f"/api/jobs/{job['id']}/analytics").json()
    assert sum(b["count"] for b in ana["funnel"]) >= 1
    assert any(s["source"] == "referral" and s["count"] >= 1 for s in ana["source_effectiveness"])


# ── Static dashboard serving ──────────────────────────────────────────────────
def test_dashboard_served(client):
    idx = client.get("/")
    assert idx.status_code == 200
    assert "ScoutForge" in idx.text or "index" in idx.text.lower()
    assert client.get("/app.js").status_code == 200
    assert client.get("/style.css").status_code == 200