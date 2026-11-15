# ScoutForge — Running, Seeding & Testing

> Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)

Practical, verified instructions for getting the app up, refreshing sample data,
and running the test suite. All commands assume you start from the repo root
(`ScoutForge/`) unless noted.

## Prerequisites

- **Python 3.11+** (verified on 3.12 and 3.14). Needs the `|` type syntax and
  `timezone.utc`.
- No other system services required — SQLite is in the standard library.

## 1. Install backend dependencies

```bash
cd backend
python -m venv .venv

# Windows (the current dev machine)
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` installs `fastapi`, `uvicorn[standard]`, `pydantic`,
`python-dotenv` (runtime) and `pytest`, `httpx` (tests).

## 2. Run the app

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Equivalent using the venv interpreter directly (no activation needed):

```bash
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

On startup you should see:

```
INFO:     Application startup complete.
[ScoutForge] Seeded sample jobs and candidates.   # only on an empty database
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### What's now available

| URL | What it is |
|-----|------------|
| `http://127.0.0.1:8000/` | The ScoutForge dashboard (served by FastAPI) |
| `http://127.0.0.1:8000/docs` | Interactive Swagger UI for the whole API |
| `http://127.0.0.1:8000/api/health` | Liveness probe |
| `http://127.0.0.1:8000/openapi.json` | Machine-readable API spec |

### Smoke-test it quickly

```bash
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/api/jobs | python -m json.tool
curl -s "http://127.0.0.1:8000/api/jobs/1/shortlist?k=3" | python -m json.tool
```

## 3. About the database & seeding

- The database lives at **`backend/scoutforge.db`** by default.
- On first boot, `init_db()` creates the schema and `seed_if_empty()` inserts
  **3 jobs and 9 candidates** (spread across funnel stages with full transition
  history) so the dashboard and analytics are meaningful immediately.
- Seeding is **idempotent** — it only runs when the database is empty, so your
  data is never overwritten on later restarts.

### Reseed to a clean demo state

Stop the server, then:

```bash
# Windows
del backend\scoutforge.db
# macOS / Linux
rm backend/scoutforge.db
```

Restart `uvicorn` — the schema and sample data are recreated fresh.

### Point the app at a different / isolated database

The location is controlled by the `SCOUTFORGE_DB` environment variable. It must
be set **before** the app package is imported (module-level read in
`database.py`):

```bash
# run against a throwaway file
SCOUTFORGE_DB=%TEMP%\sf_demo.db uvicorn app.main:app --port 8000

# or, on bash/macOS/Linux
SCOUTFORGE_DB=/tmp/sf_demo.db uvicorn app.main:app --port 8000
```

This is exactly how the test suite isolates itself from your real data.

## 4. Run the tests

```bash
cd backend
SCOUTFORGE_DB=%TEMP%\scoutforge_test.db .venv/Scripts/python.exe -m pytest tests -v
```

Expected result:

```
collected 9 items
tests/test_api.py .........                                   [100%]
========================= 9 passed in ~1.3s ==========================
```

The suite covers, end to end, the whole API contract in
`backend/tests/test_api.py`:

- `test_health`
- `test_create_and_list_job`
- `test_validate_job_required_fields`
- `test_add_and_score_candidate`
- `test_reject_unknown_source`
- `test_candidate_score_deterministic`
- `test_shortlist_orders_by_score`
- `test_pipeline_move_records_events`
- `test_dashboard_served` (index.html, app.js, style.css return 200)

### Notes

- Tests use `SCOUTFORGE_DB` to point at a **temporary** database; your real
  `backend/scoutforge.db` is never touched.
- The one benign warning emitted is an upstream Starlette `TestClient`/httpx
  deprecation inside FastAPI's test client — it does not affect results.

## 5. Verify the frontend standalone (optional)

The dashboard is plain files with no build step, so you can also open
`frontend/index.html` directly — but the API calls will only work when served by
FastAPI (same origin). Always access it via `http://127.0.0.1:8000/` for the full
experience.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: fastapi` | Activate the venv and `pip install -r requirements.txt` |
| Tests hit your real DB | Always prefix `SCOUTFORGE_DB` (or a temp file) before running pytest |
| Port in use | Pass a different `--port`, e.g. `--port 8791` |
| Old schema / seed data looks stale | Delete `backend/scoutforge.db` and restart to reseed |
| Windows git-bash path issues | Use `C:\...` or `$TEMP\...` paths for native tools (MSYS path conversion is disabled for them) |