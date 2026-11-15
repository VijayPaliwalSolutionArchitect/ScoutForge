# ScoutForge — Feature Reference

> Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)

Every feature below exists in the running code and is reachable through the API
documents at `/docs` (and manifested in the dashboard served at `/`).

## 1. Health / liveness

`GET /api/health`

```json
{ "status": "ok", "service": "ScoutForge", "version": "1.0.0" }
```

The dashboard shows the service name + version in the top bar and marks itself
"backend unreachable" if this call fails. Used by the frontend on boot and by
load balancers in production.

## 2. Job intake & lifecycle

| Operation | Endpoint | Behavior |
|-----------|----------|----------|
| List jobs | `GET /api/jobs` | All jobs (open + closed), each with parsed `required_skills` |
| Create job | `POST /api/jobs` | Validates `title` (required), `required_skills`, `seniority ∈ {junior,mid,senior,lead}`, non-negative salaries; returns the created job |
| Fetch one | `GET /api/jobs/{id}` | Single job or 404 |
| Update | `PATCH /api/jobs/{id}` | Partial update of any mutable field (PATCH semantics) |
| Close | `POST /api/jobs/{id}/close` | Sets `status = closed` |

**Rules enforced in `routers/jobs.py`:**

- `required_skills` is stored as a JSON array and returned parsed.
- Job existence is checked before any candidate/analytics operation depends on it.
- Closing is idempotent (closing a closed job is harmless).

**Dashboard:** post a job from the form; open jobs appear in the "Open jobs"
panel with a *Select* (to focus candidates/analytics) and *Close* action.

## 3. Candidate sourcing

| Operation | Endpoint | Behavior |
|-----------|----------|----------|
| List | `GET /api/candidates?job_id=N` | Filter to a job (the dashboard always passes `job_id`). Optional: filter by `stage`/`source` if provided |
| Create | `POST /api/candidates` | Requires `job_id`, `name`; validates `source ∈ {referral,linkedin,jobboard,agency}`; **auto-creates the initial `sourced` pipeline event** in the same transaction |
| Fetch one | `GET /api/candidates/{id}` | Candidate + its job id |
| Update | `PATCH /api/candidates/{id}` | Partial profile update |

Creating a candidate is transactional: if the job doesn't exist (foreign key
violation) the whole insert, including the pipeline event, is rolled back.

**Dashboard:** select a job, then add candidates with skills, experience, source
and notice period.

## 4. Deterministic AI scoring

| Operation | Endpoint | Behavior |
|-----------|----------|----------|
| Score one | `GET /api/candidates/{id}/score` | Score the candidate against their job |
| Shortlist | `GET /api/jobs/{job_id}/shortlist?k=N` | Rank **active** candidates of the job by score, top `N` (defaults sane), each with full score breakdown |

The model (see `ARCHITECTURE.md` for the formula graph):

```
total = 0.6 × skills_overlap_score  +  0.4 × seniority_fit_score
```

Example response (one shortlist entry):

```json
{
  "candidate": { "id": 1, "name": "Alice Chen", "skills": ["Python","FastAPI"] },
  "score": {
    "total": 88.0,
    "skills": {
      "candidate_skills": ["python", "fastapi"],
      "required_skills": ["python", "fastapi", "sql"],
      "matched": ["fastapi", "python"],
      "missing": ["sql"],
      "matched_ratio": 0.6667,
      "score": 66.67
    },
    "seniority": {
      "level": "mid",
      "expected_years": "2+ years",
      "candidate_years": 5.0,
      "score": 100.0
    }
  }
}
```

The `matched` / `missing` lists are what make scoring **explainable** — a hiring
team can see exactly which required skills are absent and how far a candidate is
from the seniority band floor.

## 5. Pipeline & audit trail

| Operation | Endpoint | Behavior |
|-----------|----------|----------|
| Move stage | `POST /api/candidates/{id}/stage` «`{to_stage}`» | Update `stage` + append a `pipeline_events` row atomically |
| History | `GET /api/candidates/{id}/pipeline` | Ordered list of all `from → to` transitions with timestamps |

**Stages:** `sourced → screened → interview → offer → hired` (plus `rejected`).

**Rules enforced in `routers/pipeline.py`:**

- `to_stage` must be one of the `STAGES`.
- A move to the *current* stage is rejected (no-op).
- Every move records `from_stage` and `changed_at`, making the funnel analytics
  and time-in-stage possible.

**Dashboard:** each candidate row shows six stage buttons; clicking one moves the
candidate and refreshes both the pipeline and analytics panels.

## 6. Hiring-funnel analytics

`GET /api/jobs/{job_id}/analytics` returns four aggregates:

| Field | Content |
|-------|---------|
| `funnel` | `[{stage, count}]` — current headcount per stage, in funnel order, then `rejected` |
| `time_in_stage` | Per active candidate: `moved_at` and `days_in_stage` (days since entering their current stage) |
| `source_effectiveness` | `[{source, count}]` for `referral, linkedin, jobboard, agency` (zero-filled) |
| `offer_acceptance_rate` | `hired / (hired + rejected-after-offer)`, or `null` when no offers were decided |

All computed server-side with a handful of grouped queries — no client-side
loop logic — so the numbers are always consistent with the data in SQLite.

**Dashboard:** the right column renders the funnel bars, per-source counts, and
the offer acceptance rate, all live.

## 7. Dashboard (the delivered frontend)

| Element | Feature |
|--------|---------|
| Header | Service name + live health/version indicator |
| Jobs panel | Create-job form (title, location, skills, seniority, salary band, description); open-job list with Select/Close |
| Candidates panel | Add-candidate form (skills, years, source, notice); pipeline list with one-tap stage moves |
| Shortlist panel | Top-5 ranked by score with score bars and skill/seniority reasoning |
| Analytics panel | Funnel per stage, source effectiveness, offer acceptance rate |

The UI is a thin JSON client — it renders server results and issues moves but
holds **no** business logic, so it can't disagree with the API.

## 8. Sample data (seeding)

On first boot the app auto-seeds **3 jobs and 9 candidates** at various stages
(including their full transition history), so every feature above is
immediately demonstrable. Seeding is idempotent — it only runs when the database
is empty. See `backend/app/seed.py`.

## Feature → endpoint quick map

```text
Jobs            GET/POST  /api/jobs
                GET/PATCH /api/jobs/{id}
                POST      /api/jobs/{id}/close
Candidates      GET/POST  /api/candidates (?job_id=)
                GET/PATCH /api/candidates/{id}
Scoring         GET       /api/candidates/{id}/score
                GET       /api/jobs/{id}/shortlist?k=N
Pipeline        POST      /api/candidates/{id}/stage
                GET       /api/candidates/{id}/pipeline
Analytics       GET       /api/jobs/{id}/analytics
System          GET       /api/health
Dashboard       GET       /       (index.html)
                GET       /app.js, /style.css
OpenAPI docs    GET       /docs, /openapi.json
```