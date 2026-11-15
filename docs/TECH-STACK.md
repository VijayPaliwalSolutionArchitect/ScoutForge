# ScoutForge — Technology Stack

> Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)

Verified against the installed environment in `backend/.venv` at the time of
writing.

## Runtime versions

| Component | Version | Role |
|-----------|---------|------|
| Python | 3.12 (dev venv; also runs on system Python 3.14) | Interpreter |
| FastAPI | 0.162.4 | Web framework / REST API |
| Starlette | 1.10.0 | ASGI layer under FastAPI |
| Pydantic | 2.14.3 | Request/response validation & models |
| Uvicorn | 0.54.0 | ASGI server |
| SQLite | stdlib (`sqlite3`) | Persistence |
| anyio | 4.16.0 | Async runtime used by Starlette |
| httpx | 0.28.1 | HTTP client for API tests |
| pytest | 9.2.0 | Test runner |

> `requirements.txt` pins floor versions (`fastapi>=0.110`, `uvicorn>=0.29`,
> `pydantic>=2.6`, `pytest>=8`, `httpx>=0.27`); the exact figures above are what
> the working `.venv` resolves to.

## The stack, chosen deliberately

| Concern | Choice | Why |
|---------|--------|-----|
| **API framework** | FastAPI | Async-native, automatic OpenAPI docs (`/docs`), Pydantic validation out of the box, tiny surface. |
| **Validation** | Pydantic v2 | Single source of truth for request/response schemas; Rust-core validation is fast. |
| **Server** | Uvicorn | Reference ASGI server for FastAPI; `--reload` for dev, `workers` for prod. |
| **Database** | SQLite (stdlib) | Zero install, transactional, portable — perfect for a self-contained product and for tests via file injection. No ORM keeps the SQL legible. |
| **Scoring engine** | Pure Python (no ML lib) | Auditable, deterministic, dependency-free. No model downloads, no GPU, no cloud. |
| **Frontend** | Vanilla HTML/CSS/JS | No Node, no bundler, no CORS, no build step. Serves directly from FastAPI. |
| **Tests** | pytest + FastAPI `TestClient` (httpx) | In-process HTTP tests; isolated temp DB via `SCOUTFORGE_DB`. |
| **Config** | Environment variable (`SCOUTFORGE_DB`) | Simple, standard, test-friendly. |

### Deliberate non-choices

- **No ORM** — the schema is three small tables; raw `sqlite3` with
  `row_factory=sqlite3.Row` keeps queries explicit and fast to reason about.
- **No async DB driver** — the dataset is small and the workload is low-concurrency;
  FastAPI's sync views run in a threadpool comfortably.
- **No frontend framework / build tooling** — the dashboard does not need it, and
  its absence means one fewer moving part to deploy.
- **No cloud LLM for scoring** — "AI" here means a deterministic, explainable
  scoring model. This can be swapped for a hosted model later behind the same
  `scoring.score_candidate()` contract without touching callers.
- **No Dockerfile ships in-tree** — deployment is a plain `uvicorn` process; see
  `DEPLOYMENT.md` for containerising it if needed.

## Source compatibility

- Recommended: Python **3.11+** (needs the `|` union syntax, `tuple[int, ...]`
  generics and `timezone.utc`).
- Confirmed working on the project `.venv` (Python **3.12.13**) and on the host
  system Python **3.14** for import/lint. Python 3.10 will not run the typed
  syntax without changes.

## Validation layers

1. **Pydantic** — rejects malformed/missing payloads before any SQL (`Field(...)`
   required fields, `ge=` bounds).
2. **Routers** — job existence, source whitelist, stage whitelist, foreign-key
   integrity, and idempotency guards (e.g. same-stage moves are rejected).
3. **Tests** — 9 end-to-end API tests lock the whole surface (see `RUNNING.md`).

## If you add something

- Add the new runtime dependency to `backend/requirements.txt` with a floor
  version, and only after confirming it in the `.venv`.
- Keep the frontend build-free unless the product genuinely outgrows it.
- Extend `docs/TECH-STACK.md` version table when you upgrade the lockfile.