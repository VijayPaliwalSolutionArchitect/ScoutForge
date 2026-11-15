# ScoutForge — Codebase Organization

A map of every meaningful file, its responsibility, and the conventions the
code follows. Read this before editing.

## Directory tree (populated state)

```
ScoutForge/
├── README.md                         # landing page, quick start
├── .gitignore
├── docs/                             # this documentation set
│   ├── ARCHITECTURE.md
│   ├── TECH-STACK.md
│   ├── FEATURES.md
│   ├── RUNNING.md
│   ├── DEPLOYMENT.md
│   └── CODEBASE-ORGANIZATION.md
├── backend/
│   ├── requirements.txt              # pinned runtime + test deps
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # entrypoint: app, lifespan, routing, static serving, health
│   │   ├── models.py                 # Pydantic models + domain constants (single source of truth)
│   │   ├── database.py               # SQLite schema + connection helpers
│   │   ├── scoring.py                # deterministic skill-match scoring engine
│   │   ├── seed.py                   # idempotent sample-data seeder
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── jobs.py               # job CRUD + close
│   │       ├── candidates.py         # candidate CRUD + score endpoint
│   │       ├── pipeline.py           # stage moves + audit trail
│   │       ├── scoring.py            # top-k shortlist
│   │       └── analytics.py          # funnel / source / offer analytics
│   └── tests/
│       ├── __init__.py
│       └── test_api.py               # 9 end-to-end API tests
└── frontend/
    ├── index.html                    # dashboard shell
    ├── app.js                        # thin vanilla-JS JSON client
    └── style.css                     # dashboard styling
```

> `backend/scoutforge.db` is created at runtime and git-ignored. `.venv/`,
> `node_modules/`, `__pycache__/`, `*.pyc` and `.env` are also git-ignored.

## Module responsibilities

### `backend/app/main.py` — entrypoint
- Builds the FastAPI `app` (`title="ScoutForge"`, `version="1.0.0"`).
- `lifespan`: calls `init_db()` then `seed_if_empty()` on startup — the app is
  self-bootstrapping.
- `include_router(...)` for all five routers.
- Defines `GET /api/health`.
- Serves the dashboard via `FileResponse` from `frontend/` at `/`, `/app.js`,
  `/style.css` (no build step, no CORS needed).

### `backend/app/models.py` — schemas & domain constants
- **The single source of truth** for enumerations consumed everywhere:
  `JOB_STATUSES`, `SENIORITIES`, `SOURCES`, `STAGES`, `FUNNEL_ORDER`.
- Request models: `JobCreate`, `JobUpdate`, `CandidateCreate`,
  `CandidateUpdate`, `PipelineMove`.
- Response models: `ScoreResponse` (with `ScoreBreakdownSkills` /
  `ScoreBreakdownSeniority`), `AnalyticsResponse`, `FunnelBucket`,
  `TimeInStageEntry`.
- Rule of thumb: **if a value must be shared or validated, it is declared
  here.**

### `backend/app/database.py` — persistence
- Reads `DB_PATH` from `SCOUTFORGE_DB` (module-level, so env must be set before
  import).
- `_SCHEMA`: three tables (`jobs`, `candidates`, `pipeline_events`) with FKs and
  covering indexes, written idempotently (`IF NOT EXISTS`).
- `get_connection()` → `sqlite3.Connection` with `row_factory=sqlite3.Row` and
  `PRAGMA foreign_keys = ON`.
- `init_db()` → `executescript(_SCHEMA)`.
- No ORM: raw SQL only.

### `backend/app/scoring.py` — the "AI" engine
- `SENIORITY_BANDS` (`junior 0+`, `mid 2+`, `senior 4+`, `lead 7+`),
  `SKILLS_WEIGHT = 0.6`, `SENIORITY_WEIGHT = 0.4`.
- Pure, deterministic `score_candidate(...)` → `ScoreResponse` with a full
  `skills` / `seniority` breakdown (matched, missing, ratio).
- Private helpers `_normalize_skills`, `_skills_component`,
  `_seniority_component`. **No I/O, no randomness, no side effects** — this is
  what makes scores auditable and the module trivially testable.

### `backend/app/seed.py` — sample data
- `seed_if_empty()` → `bool`; inserts **3 jobs + 9 candidates** across funnel
  stages plus their full `pipeline_events` history, but only when the DB has no
  jobs (idempotent).
- Uses only `datetime.now(timezone.utc)` for timestamps (no deprecated
  `utcnow`).

### Routers (`backend/app/routers/`)
Thin HTTP layer: validate via models, do the work with `get_connection()`, return
JSON. All read/write go through the DB module; none touch `scoring` internals
directly.

| File | Prefix | Endpoints | Responsibility |
|------|--------|-----------|----------------|
| `jobs.py` | `/api/jobs` | GET/POST list+create, GET/PATCH one, POST `/{id}/close` | Job lifecycle; job-existence guard |
| `candidates.py` | `/api/candidates` | GET/POST (filter by `job_id`), GET/PATCH one, GET `/{id}/score` | Candidate CRUD + one-off scoring; transactional initial-pipeline-event |
| `pipeline.py` | `/api/candidates` | POST `/{id}/stage`, GET `/{id}/pipeline` | Stage validation, no-op guard, atomic move + audit append, ordered history |
| `scoring.py` | `/api/jobs` | GET `/{job_id}/shortlist?k=` | Scores all active candidates, returns top-k with breakdowns |
| `analytics.py` | `/api/jobs` | GET `/{job_id}/analytics` | Funnel, time-in-stage, source effectiveness, offer acceptance rate |

### `frontend/` — dashboard
- `index.html` — semantic skeleton (jobs, candidates, shortlist, analytics).
- `app.js` — one `api()` fetch wrapper + render/event functions; **no business
  logic**; talks to `/api/*` on the same origin.
- `style.css` — dark theme, CSS grid two-column layout, responsive stack under
  860px.
- Kept deliberately build-free: served verbatim by FastAPI.

### `backend/tests/test_api.py` — contract tests
- Sets `SCOUTFORGE_DB` to a temp file **at module top**, before `app.main` is
  imported, so tests never see the real DB.
- 9 tests via FastAPI `TestClient` covering the whole API + dashboard serving.

## Conventions & invariants

1. **Domain enums live in `models.py`** — never hard-code a stage/source string
   in a router.
2. **Business logic stays server-side** — the frontend renders, it does not
   decide.
3. **Deterministic everywhere** — no `random`, no wall-clock math in scoring;
   ordering in shortlist is by score desc with a stable tiebreak.
4. **Timestamps are naive UTC** (`datetime('now')` / `YYYY-MM-DD HH:MM:SS`);
   avoid `datetime.utcnow()` (deprecated in 3.12+).
5. **Routers are thin and do not mix** — each router owns one concern; shared
   logic (scoring, analytics) is factored into modules.
6. **Transactional** — candidate creation and stage moves insert the data *and*
   the audit event atomically.
7. **Idempotent boot** — schema `IF NOT EXISTS`, seed only-on-empty, close &
   health are all safe to repeat.
8. **`relation`-ordered shortlist** — a candidate whose `score.total` equals
   another's sorts deterministically by `name` (ties are stable).

## Extending the code

- **New endpoint** → add to the matching router (or a new file in
  `routers/`), declare models in `models.py`, wire in `main.py`,
  add a test in `test_api.py`.
- **New domain enum** → extend the constant in `models.py`; routers/analytics
  pick it up automatically.
- **New analytic metric** → add it to `routers/analytics.py` and the
  `AnalyticsResponse` model.
- **Swap storage or scoring** → implement behind `database.get_connection()` /
  `scoring.score_candidate()`; callers stay unchanged.
- **Update docs** → keep this file and `TECH-STACK.md` in sync whenever the
  layout or dependencies change.