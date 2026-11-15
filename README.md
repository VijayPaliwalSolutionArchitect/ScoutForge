# ScoutForge — AI Candidate Sourcing & Hiring-Funnel Analytics

> Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)

**ScoutForge** is a self-contained, AI-flavoured talent-acquisition platform:
post job openings, source and score candidates with a **deterministic, auditable
skill-match model**, move candidates through a hiring funnel, and watch funnel /
source / offer analytics update live. It ships as a FastAPI + SQLite backend with a
zero-build vanilla-JavaScript dashboard — one process, one database, no external
services.

> Product note: in the broader planning playbook ScoutForge is positioned as an
> agentic research & lead-intelligence product. This repository currently
> implements the **talent-acquisition engine** — job intake, sourcing,
> deterministic scoring, AI shortlisting and funnel analytics — which is the
> concrete, working foundation of that product. Everything below describes the
> code as it exists on disk.

---

## Highlights

- **Deterministic AI scoring** — no cloud LLM required. Every candidate score is a
  pure, repeatable function of their profile vs. the job (60% skills overlap,
  40% seniority fit), with a full `skills` / `seniority` breakdown returned for
  auditability.
- **AI shortlisting** — rank any job's candidates top-`k` by match score with one
  call.
- **Hiring funnel** — move candidates through `sourced → screened → interview →
  offer → hired` (or `rejected`), with a complete transition audit trail.
- **Analytics endpoint** — funnel-per-stage, time-in-stage, source effectiveness
  and offer-acceptance rate per job, all aggregated server-side.
- **Seeded sample data** — 3 jobs and 9 candidates at various funnel stages plus
  their full transition history, so the dashboard and analytics are meaningful on
  first boot.
- **Zero-build dashboard** — a single-page vanilla JS client served directly by
  FastAPI (no Node, no bundler, no CORS config).

## Quick start

```bash
# 1. Backend
cd backend
python -m venv .venv                 # or use an existing interpreter
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate
pip install -r requirements.txt

# 2. Run (creates schema + seeds sample data on first start)
uvicorn app.main:app --reload --port 8000

# 3. Open the dashboard
#    http://127.0.0.1:8000/          → dashboard (served by FastAPI)
#    http://127.0.0.1:8000/docs      → interactive OpenAPI docs
```

## Run the tests

```bash
cd backend
pip install -r requirements.txt
SCOUTFORGE_DB=%TEMP%/scoutforge_test.db python -m pytest tests -v
```

Tests run against an isolated ephemeral SQLite database and never touch your
real data (`backend/scoutforge.db`).

## Repo layout

```
ScoutForge/
├── README.md
├── .gitignore
├── docs/                    # architecture, tech stack, features, ops docs
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py          # FastAPI entrypoint, lifespan, routing, static serving
│   │   ├── database.py      # SQLite schema + connection helpers
│   │   ├── models.py        # Pydantic models + domain constants (single source of truth)
│   │   ├── scoring.py       # deterministic skill-match scoring engine
│   │   ├── seed.py          # idempotent sample-data seeder
│   │   └── routers/
│   │       ├── jobs.py          # job CRUD + close
│   │       ├── candidates.py    # candidate CRUD + score
│   │       ├── pipeline.py      # stage moves + audit trail
│   │       ├── scoring.py       # top-k shortlist
│   │       └── analytics.py     # funnel / source / offer analytics
│   └── tests/
│       └── test_api.py          # 9 end-to-end API tests (pytest)
└── frontend/
    ├── index.html           # dashboard shell
    ├── app.js               # thin vanilla-JS client
    └── style.css            # styling
```

## Key endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness probe |
| GET/POST | `/api/jobs` | List / create jobs |
| GET/PATCH | `/api/jobs/{id}` | Fetch / update a job |
| POST | `/api/jobs/{id}/close` | Close a job |
| GET/POST | `/api/candidates` | List (by `job_id`) / create candidates |
| GET/PATCH | `/api/candidates/{id}` | Fetch / update a candidate |
| GET | `/api/candidates/{id}/score` | Score a candidate against their job |
| POST | `/api/candidates/{id}/stage` | Move to a pipeline stage |
| GET | `/api/candidates/{id}/pipeline` | Full transition audit trail |
| GET | `/api/jobs/{id}/shortlist?k=N` | Top-N candidates by score |
| GET | `/api/jobs/{id}/analytics` | Funnel + source + offer stats |

Full interactive docs at `/docs` (Swagger UI) once the server is running.

## How scoring works (the "AI")

No LLM is involved. `scoring.score_candidate()` is deterministic and auditable:

```
total = 0.6 × (matched_skills / required_skills × 100)
      + 0.4 × seniority_fit(experience_years) × 100
```

- **Skills (60%)** — ratio of the job's required skills the candidate possesses
  (case/whitespace-insensitive overlap).
- **Seniority (40%)** — how the candidate's experience years fit the job's
  seniority band floor (`junior 0+`, `mid 2+`, `senior 4+`, `lead 7+`). At or above
  the floor → 1.0; below → proportional.

The response includes `matched`, `missing`, `matched_ratio`, and the seniority
fit so hiring teams can see exactly *why* a score is what it is.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — layered architecture, schema, data flow (text + Mermaid).
- [`docs/INSTALLATION.md`](docs/INSTALLATION.md) — prerequisites, venv, dependencies, DB setup.
- [`docs/RUNNING.md`](docs/RUNNING.md) — full install, run, seed and test guide.
- [`docs/API.md`](docs/API.md) — every REST endpoint with request/response examples.
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — production serving, env vars, backups, platform VPS flow.
- [`docs/FEATURES.md`](docs/FEATURES.md) — feature-by-feature reference mapped to endpoints.
- [`docs/TECH-STACK.md`](docs/TECH-STACK.md) — components and versions with rationale.
- [`docs/CODEBASE-ORGANIZATION.md`](docs/CODEBASE-ORGANIZATION.md) — per-module walkthrough and conventions.
- [`docs/env-config.md`](docs/env-config.md) — all environment variables.
- [`docs/PLAYBOOK-CROSSWALK.md`](docs/PLAYBOOK-CROSSWALK.md) — mapping to the portfolio playbook (Project 4).

## Roadmap

- LLM-assisted scoring as an opt-in layer behind the deterministic scorer (FR-S5 is local today).
- PDF/CSV shortlist export (FR-S8).
- Auth + RBAC/SSO (FR-S7) for multi-user deployments.
- Postgres migration path for multi-writer deployments.
- E-mail alerts / saved searches (MoSCoW "Could").

## Tech at a glance

- **Backend:** Python, FastAPI, Pydantic v2, uvicorn.
- **Persistence:** SQLite via the standard library (`sqlite3`) — no ORM.
- **Scoring:** pure Python deterministic function.
- **Frontend:** vanilla HTML/CSS/JS, served by FastAPI (no build step).
- **Tests:** pytest + FastAPI `TestClient` (httpx), isolated temp database.

## Status

9 end-to-end API tests pass; the app boots under uvicorn and the dashboard
serves correctly. See [`docs/RUNNING.md`](docs/RUNNING.md) for verification
steps.