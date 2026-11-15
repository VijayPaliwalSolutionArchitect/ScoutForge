# ScoutForge — Environment Configuration

> Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)

ScoutForge has **no config file and no python-dotenv dependency** — it reads
the process environment (plus uvicorn CLI flags). This page is the complete
reference; `.env.example` at the repo root holds the same values as
placeholders.

## Variables

| Variable | Default | Read where | Purpose |
|----------|---------|------------|---------|
| `SCOUTFORGE_DB` | `backend/scoutforge.db` (relative to the `backend/` working dir) | `backend/app/database.py` at import time | Path to the SQLite file. Created + schema-initialised + seeded on first boot. **Must be set before the app is imported** and point at persistent storage in production. |
| `PORT` | `8000` | docs / supervisor convention | TCP port (overridden by `uvicorn --port`). |
| `WORKERS` | `1` | docs / supervisor convention | uvicorn worker count. Keep at **1** with a single SQLite file — SQLite allows one writer; more workers cause `database is locked`. See `docs/DEPLOYMENT.md`. |

Related uvicorn flags (not env vars): `--host` (default `127.0.0.1` in
production behind a proxy, `0.0.0.0` in containers), `--port`, `--workers`,
`--reload` (dev only).

There are **no secrets** in this app: scoring is local and deterministic, so
no API keys/tokens are required. Never commit credentials anywhere in the
repo — if one is ever introduced, keep it in the process environment only and
redact it from docs (use `[REDACTED]`).

## Setting variables

```bash
# macOS / Linux
export SCOUTFORGE_DB=/var/lib/scoutforge/scoutforge.db
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1   # from backend/

# Windows cmd
set SCOUTFORGE_DB=C:\data\scoutforge.db
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1

# Windows PowerShell
$env:SCOUTFORGE_DB="C:\data\scoutforge.db"
uvicorn app.main:app --port 8000

# systemd (see docs/DEPLOYMENT.md)
# Environment=SCOUTFORGE_DB=/var/lib/scoutforge/scoutforge.db

# Docker / Coolify
# ENV SCOUTFORGE_DB=/data/scoutforge.db   + a persistent volume on /data
```

## Notes

- `SCOUTFORGE_DB` is read **once, at import time** — change it before
  starting the process, not during.
- Relative paths resolve against the process working directory, which is
  `backend/` in all documented run commands. An absolute path removes the
  ambiguity.
- `.env.example` is documentation only: the app does not parse it. Export
  the variables in your shell or supervisor instead.
- The database file itself is runtime state — it is covered by `*.db` in
  `.gitignore` and must be backed up (see `docs/DEPLOYMENT.md` → Backups).
