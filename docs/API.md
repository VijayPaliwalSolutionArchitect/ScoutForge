# ScoutForge — API Reference

> Base URL: `http://localhost:8000` — every API route is under `/api`.
> Interactive docs: Swagger UI at `/docs`, raw OpenAPI at `/openapi.json`.

Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)

All routes live in `backend/app/routers/`; payloads are validated by the
Pydantic models in `backend/app/models.py`.

## Conventions

- **Envelopes**: single resources are wrapped — `{"job": {...}}`,
  `{"candidate": {...}}`, `{"score": {...}}`; collections use
  `{"jobs": [...]}`, `{"candidates": [...]}`.
- **List fields** (`required_skills`, `skills`) are JSON arrays in requests
  and responses (stored as JSON text in SQLite, decoded on read).
- **Status codes**: `200` for reads/updates/actions, `201` for creates,
  `404` unknown resource, `422` validation / business rule (FastAPI also
  uses 422 for schema violations).
- **Domain enums** (single source of truth in `app/models.py`):

| Field | Values |
|-------|--------|
| job `status` | `open`, `closed` |
| job `seniority` | `junior`, `mid`, `senior`, `lead` |
| candidate `source` | `referral`, `linkedin`, `jobboard`, `agency` |
| candidate `stage` | `sourced`, `screened`, `interview`, `offer`, `hired`, `rejected` |

## Endpoint summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness probe |
| GET | `/api/jobs` | List jobs (`?status=open\|closed`) |
| POST | `/api/jobs` | Create a job (201) |
| GET | `/api/jobs/{id}` | Get one job |
| PATCH | `/api/jobs/{id}` | Partial update |
| POST | `/api/jobs/{id}/close` | Mark job closed |
| GET | `/api/jobs/{id}/shortlist?k=5` | Top-k scored candidates |
| GET | `/api/jobs/{id}/analytics` | Funnel / time-in-stage / source / offers |
| GET | `/api/candidates` | List candidates (`?job_id=`) |
| POST | `/api/candidates` | Create candidate (201, starts at `sourced`) |
| GET | `/api/candidates/{id}` | Get one candidate |
| PATCH | `/api/candidates/{id}` | Update profile (not stage) |
| GET | `/api/candidates/{id}/score` | Score vs. their job |
| POST | `/api/candidates/{id}/stage` | Move stage + audit event |
| GET | `/api/candidates/{id}/pipeline` | Full stage-transition history |

---

## System

### `GET /api/health`
Liveness probe for load balancers / uptime monitors (`app/main.py`).

```bash
curl -s http://localhost:8000/api/health
```
```json
{"status": "ok", "service": "ScoutForge", "version": "1.0.0"}
```

---

## Jobs — `backend/app/routers/jobs.py`

### `GET /api/jobs?status=open`
```json
{"jobs": [{"id": 1, "title": "...", "description": "...", "required_skills": ["python"],
           "seniority": "senior", "location": "Remote", "salary_min": 30, "salary_max": 45,
           "status": "open", "created_at": "..."}]}
```

### `POST /api/jobs` → 201
Request (`JobCreate`):
```json
{
  "title": "Senior Backend Engineer",
  "description": "Own the sourcing API...",
  "required_skills": ["python", "fastapi", "sql"],
  "seniority": "senior",
  "location": "Remote",
  "salary_min": 30,
  "salary_max": 45
}
```
Business rules (422): `seniority` must be one of the four levels;
`salary_min <= salary_max`; **at least one `required_skills` entry**
(scoring needs it). New jobs are created with `status: "open"`.

```bash
curl -s -X POST http://localhost:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{"title":"ML Engineer","required_skills":["python","pytorch"],"seniority":"mid"}'
# {"job": {"id": 4, ..., "status": "open"}}
```

### `GET /api/jobs/{id}` → `{"job": {...}}` (404 if missing)

### `PATCH /api/jobs/{id}`
Partial update (`JobUpdate` — only sent fields change). `status` must be
`open|closed`; `required_skills`, if present, replaces the whole list.

### `POST /api/jobs/{id}/close`
Sets `status = "closed"` (404 if the job does not exist). Returns the updated
job.

---

## Candidates — `backend/app/routers/candidates.py`

### `GET /api/candidates?job_id=1`
```json
{"candidates": [{"id": 1, "job_id": 1, "job_title": "Senior Backend Engineer",
                 "name": "...", "email": "...", "skills": ["python"],
                 "experience_years": 6.0, "location": "...", "notice_period_days": 30,
                 "source": "linkedin", "stage": "sourced", "created_at": "..."}]}
```

### `POST /api/candidates` → 201
Request (`CandidateCreate`):
```json
{
  "job_id": 1,
  "name": "Priya Sharma",
  "email": "priya@example.com",
  "skills": ["python", "fastapi", "sql", "docker"],
  "experience_years": 6,
  "location": "Bengaluru",
  "notice_period_days": 30,
  "source": "linkedin"
}
```
- `job_id` must exist → else 404. `source` must be one of the four values →
  else 422.
- The candidate starts at stage `sourced` **and** an initial
  `pipeline_events` row (`'' → sourced`) is written, so the audit trail
  covers the whole funnel.

### `GET /api/candidates/{id}` / `PATCH /api/candidates/{id}`
PATCH updates profile fields only (`CandidateUpdate`) — it never changes
`stage` (use the stage endpoint for that).

### `GET /api/candidates/{id}/score`
Scores the candidate against the job they belong to (deterministic scorer in
`app/scoring.py`):

```json
{"score": {
  "job_id": 1, "candidate_id": 1, "total": 82.5,
  "skills": {"candidate_skills": ["python","fastapi"], "required_skills": ["python"],
             "matched": ["python"], "missing": [], "matched_ratio": 1.0, "score": 100.0},
  "seniority": {"level": "senior", "expected_years": "5+", "candidate_years": 6.0, "score": 90.0}
}}
```
`total = 0.7 × skills.score + 0.3 × seniority.score` (both components 0–100).
404 if candidate or its job is missing.

---

## Pipeline — `backend/app/routers/pipeline.py`

### `POST /api/candidates/{id}/stage`
Request: `{"to_stage": "interview"}` — must be one of the six stages (422).
Updates the candidate's stage and appends a `pipeline_events` row
(`from_stage → to_stage`). Response:
```json
{"candidate": {...}, "from_stage": "sourced", "to_stage": "interview"}
```

### `GET /api/candidates/{id}/pipeline`
Full audit trail:
```json
{"candidate_id": 1, "events": [{"id": 1, "job_id": 1, "from_stage": "",
  "to_stage": "sourced", "changed_at": "..."}, ...]}
```

---

## Shortlist — `backend/app/routers/scoring.py`

### `GET /api/jobs/{id}/shortlist?k=5`
Scores **every** candidate for the job, sorts by `total` descending, returns
the top `k` with full breakdowns:

```json
{
  "job_id": 1, "job_title": "Senior Backend Engineer", "k": 5, "scored": 12,
  "shortlist": [
    {"candidate_id": 3, "name": "...", "stage": "screened", "source": "referral",
     "experience_years": 7.0,
     "score": {"total": 91.0, "skills": {...}, "seniority": {...}}}
  ]
}
```
404 if the job does not exist.

---

## Analytics — `backend/app/routers/analytics.py`

### `GET /api/jobs/{id}/analytics`
```json
{
  "job_id": 1,
  "funnel": [{"stage": "sourced", "count": 5}, {"stage": "screened", "count": 3},
             {"stage": "interview", "count": 2}, {"stage": "offer", "count": 1},
             {"stage": "hired", "count": 1}, {"stage": "rejected", "count": 1}],
  "time_in_stage": [{"candidate_id": 3, "name": "...", "stage": "screened",
                     "moved_at": "2026-11-10 09:00:00", "days_in_stage": 5.2}],
  "source_effectiveness": [{"source": "referral", "count": 4}, {"source": "linkedin", "count": 6},
                           {"source": "jobboard", "count": 2}, {"source": "agency", "count": 0}],
  "offer_acceptance_rate": 0.5
}
```
- `funnel`: current candidates per stage, ordered
  `sourced → screened → interview → offer → hired`, then `rejected`.
- `time_in_stage`: days since the event that landed each candidate in their
  current stage.
- `source_effectiveness`: candidate count per sourcing channel.
- `offer_acceptance_rate`: `hired / (hired + rejected)` counting only
  transitions **from** `offer`; `null` when no offers have been resolved.

404 if the job does not exist.

---

## Errors

| Code | When | Body |
|------|------|------|
| 404 | Unknown job/candidate id, scoring a candidate whose job is gone | `{"detail": "job 99 not found"}` |
| 422 | Bad enum, `salary_min > salary_max`, empty `required_skills`, bad `to_stage`, schema violation | `{"detail": "..."}` or FastAPI `{"detail": [...]}` |

## See also

- `docs/RUNNING.md` — curl recipes and ports
- `docs/ARCHITECTURE.md` — scoring formula and request lifecycle
- `backend/tests/test_api.py` — executable examples of every endpoint above
