# ScoutForge — Deployment Guide

> Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)

ScoutForge is a single stateless-application process (all state lives in one
SQLite file), which makes deployment unusually simple: run uvicorn, point a
reverse proxy at it, and back up the one `.db` file. No database server, no
message queue, no external AI service.

## Configuration surface

| Env var | Default | Purpose |
|---------|---------|---------|
| `SCOUTFORGE_DB` | `backend/scoutforge.db` | Absolute or relative path to the SQLite file. Must be set **before** the app is imported. |
| `PORT` / `--port` | `8000` | TCP port for the ASGI server. |
| `WORKERS` / `--workers` | `1` | Number of uvicorn worker processes (see concurrency note below). |

There is no config file to edit; these are set on the command line or in your
process supervisor's environment.

## Concurrency & SQLite — read this first

SQLite allows **one writer at a time**. ScoutForge's workload (low-volume
recruiting CRUD) fits that fine, but two consequences follow:

1. **Prefer a single worker** for a single SQLite file. Multi-process
   contention on SQLite shows up as `database is locked` under load.
2. If you *must* scale reads, run uvicorn with `--workers 1` and put a
   connection-pooling reverse proxy in front, or switch the persistence layer
   to Postgres (the routers don't care — see `ARCHITECTURE.md` → "Evolution
   paths").

## Production run (plain process)

```bash
cd backend
export SCOUTFORGE_DB=/var/lib/scoutforge/scoutforge.db   # writable by the app user
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

- Bind `127.0.0.1` if a reverse proxy on the same host terminates TLS.
- `--workers 1` avoids SQLite write contention.
- Health check: `curl -s http://<host>:8000/api/health` →
  `{"status":"ok","service":"ScoutForge",...}`.

## Reverse proxy (terminate TLS / serve the dashboard)

Nginx example:

```nginx
server {
    listen 80;                          # or 443 with TLS
    server_name scoutforge.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The dashboard and `/app.js` / `/style.css` are served by FastAPI itself, so a
single `location /` block is all you need — no separate static server.

## Process supervision (systemd)

```ini
# /etc/systemd/system/scoutforge.service
[Unit]
Description=ScoutForge API
After=network.target

[Service]
WorkingDirectory=/opt/ScoutForge/backend
ExecStart=/opt/ScoutForge/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Environment=SCOUTFORGE_DB=/var/lib/scoutforge/scoutforge.db
Restart=always
User=scoutforge

[Install]
WantedBy=multi-user.target
```

## Containerising (optional)

No Dockerfile ships in-tree, but the app is trivially containerisable:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend backend
ENV SCOUTFORGE_DB=/data/scoutforge.db
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> **Mount `/data` as a persistent volume** — otherwise the SQLite file is lost
> on container recreate. This is the single most important deploy detail.

## Backups & data safety

Everything important is in one file, so backup is trivial:

- Back up `SCOUTFORGE_DB` (default `backend/scoutforge.db`) at a point of
  consistency. Use SQLite's online backup or, for simplicity, stop the app,
  `cp` the file, restart:
  ```bash
  sqlite3 scoutforge.db ".backup 'scoutforge.backup.db'"
  ```
- Remember the `jobs`/`candidates`/`pipeline_events` tables are the only
  durable state; the dashboard is static and recreated from the API.
- Restore = replace the file and start the process. Schema + seed re-run
  safely on boot (seed only runs when the DB is empty, so it won't overwrite a
  restored dataset).

## Logging & observability

- Uvicorn logs startup and every request to stdout/stderr; capture with
  systemd/journald or your container runtime.
- The app prints `[ScoutForge] Seeded ...` on first boot — a useful signal that
  seeding occurred.
- No structured-tracing setup is included; add middleware if you need request
  IDs / spans. The health endpoint is the load-balancer hook.

## Rollout & upgrades

1. Back up `scoutforge.db` (see above).
2. Ship new code (`app/`, `frontend/`).
3. Restart the process. Schema is applied idempotently at startup; a
   reseed happens **only** if you intentionally deleted the DB.
4. Smoke test: `/api/health`, list jobs, run one shortlist call, open `/`.

## Scaling checklist

- [ ] `--workers 1` for a single SQLite file (or move to Postgres before scaling up).
- [ ] TLS terminated at the reverse proxy.
- [ ] Persistent volume for the DB in containers.
- [ ] Automated DB backup.
- [ ] Health-check monitor on `/api/health`.
- [ ] `SCOUTFORGE_DB` set to a writable, *persistent* path in production.

## Platform VPS deployment (playbook flow: Coolify + Caddy + Uptime Kuma)

> Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)

Hero-project deployment on the shared VPS platform, following the portfolio
playbook's standard flow (§3.7 “Deployment on the VPS and the live demo”):

1. **Coolify** — add this repo as a service resource (or Compose) in Coolify.
   Use the Dockerfile above with `ENV SCOUTFORGE_DB=/data/scoutforge.db` and a
   **persistent volume mounted at `/data`**. Coolify handles build, deploy and
   restart-on-push.
2. **Caddy site** — create the site `scout.shivamitcs.com` in Caddy routing to
   the container's port `8000`. Caddy provisions **automatic HTTPS**
   (Let's Encrypt); verify TLS and that the dashboard loads over
   `https://scout.shivamitcs.com/`.
3. **Acceptance smoke test** — from the VPS:
   ```bash
   curl -s https://scout.shivamitcs.com/api/health        # {"status":"ok",...}
   curl -s -X POST https://scout.shivamitcs.com/api/jobs -H 'Content-Type: application/json' \
     -d '{"title":"Smoke","required_skills":["python"],"seniority":"mid"}'
   curl -s "https://scout.shivamitcs.com/api/jobs/1/shortlist?k=3"
   ```
4. **Monitoring** — Uptime Kuma HTTP monitor on
   `https://scout.shivamitcs.com/api/health`, 60 s interval, alert on non-200 /
   timeout.
5. **Backups** — nightly timer (systemd timer or Coolify cron) running:
   ```bash
   sqlite3 /data/scoutforge.db ".backup '/backups/scoutforge-$(date +%F).db'"
   ```
   Retain 30 days. Run **one timed restore drill**: restore a backup to a temp
   file, boot a throwaway instance with `SCOUTFORGE_DB=<temp file>`, confirm
   `GET /api/jobs` returns the restored rows, record the elapsed time.
6. **Rollout** — push to the repo → Coolify rebuilds and redeploys. Schema init
   is idempotent and seeding runs only when the DB is empty, so redeploys and
   restores never clobber existing data.

No external AI service is called at runtime (scoring is local), so no API keys
are needed on the VPS — if keys are ever introduced, keep them in Coolify's
env settings only and redact them from docs (`[REDACTED]`).