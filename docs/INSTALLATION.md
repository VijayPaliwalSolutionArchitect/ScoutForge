# ScoutForge — Installation

Step-by-step setup from a clean machine to a running ScoutForge instance.

> Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ (3.10 works; the code uses `X \| None` unions) | `python --version` to check |
| pip | bundled with Python | upgraded via `python -m pip install -U pip` |
| git | any | only needed if cloning |
| Disk | ~50 MB | venv + SQLite file |
| OS | Windows / macOS / Linux | commands below show both Windows and POSIX shells |

No database server, no message queue, no external API keys — ScoutForge is
fully self-contained (SQLite + deterministic local scoring).

## 1. Get the code

```bash
# If the repo is not already on disk:
git clone <repo-url> ScoutForge
cd ScoutForge
```

## 2. Create a virtual environment

From the `backend/` directory (the app is always run from here so that
`app.main:app` is importable):

```bash
cd backend

# Windows (cmd)
python -m venv .venv
.venv\Scripts\activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` pins (see the file for exact bounds):

| Package | Purpose |
|---------|---------|
| `fastapi>=0.115,<1.0` | Web framework / routing / validation |
| `uvicorn[standard]>=0.30,<1.0` | ASGI server |
| `pydantic>=2.7,<3.0` | Request/response models (`app/models.py`) |
| `httpx>=0.27` | Test client / outbound HTTP |
| `pytest>=8,<10` | Test runner (also used in production install; harmless) |

For development/testing only, that is all — there is no separate dev file;
`pytest` is already included above.

## 4. Configure environment (optional)

Only one variable matters for local dev and it has a working default:

```bash
# Optional — defaults to backend/scoutforge.db
export SCOUTFORGE_DB=backend/scoutforge.db        # macOS/Linux
# Windows cmd:  set SCOUTFORGE_DB=backend/scoutforge.db
# Windows PS:   $env:SCOUTFORGE_DB="backend/scoutforge.db"
```

See `.env.example` (placeholders only) and `docs/env-config.md` for the full
list. Note: the app reads the **process environment** — `.env.example` is
documentation; export the variables yourself.

## 5. Database setup

Nothing to do manually. On startup the lifespan hook in
`backend/app/main.py` calls `init_db()` (creates `jobs`, `candidates`,
`pipeline_events` tables idempotently) and `seed_if_empty()` (inserts demo
jobs/candidates only when the DB is empty). You will see:

```
[ScoutForge] Seeded sample jobs and candidates.
```

## 6. First run

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Then open:

- Dashboard: http://localhost:8000/
- Swagger UI: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json
- Health: http://localhost:8000/api/health

## 7. Verify the install

```bash
curl -s http://localhost:8000/api/health
# {"status":"ok","service":"ScoutForge","version":"1.0.0"}

curl -s "http://localhost:8000/api/jobs" | head -c 400
curl -s "http://localhost:8000/api/jobs/1/shortlist?k=3" | head -c 400
```

## 8. Run the tests

```bash
cd backend
python -m pytest tests -q
```

`tests/test_api.py` exercises the full API surface with FastAPI's
`TestClient` (httpx) against a temporary database.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `ModuleNotFoundError: app` | You are not in `backend/` — uvicorn must run from there (`uvicorn app.main:app`). |
| `address already in use` | Port 8000 busy — use `--port 8001`. |
| `database is locked` | Multiple uvicorn workers writing one SQLite file — run with `--workers 1` (see `docs/DEPLOYMENT.md`). |
| Empty dashboard | DB seeded? Check stdout for the seed line; or delete `scoutforge.db` and restart. |
| 422 on job create | `required_skills` must be non-empty (scoring needs it); `seniority` must be one of junior/mid/senior/lead; `salary_min <= salary_max`. |

## Next steps

- `docs/RUNNING.md` — day-to-day run commands, ports, curl recipes
- `docs/API.md` — full REST reference
- `docs/ARCHITECTURE.md` — how the pieces fit together
- `docs/DEPLOYMENT.md` — production/VPS deployment
