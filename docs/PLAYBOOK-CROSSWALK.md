# ScoutForge — Playbook Crosswalk

How this repository maps to **Project 4 — "Agentic Research & Lead
Intelligence"** of the JARVIS AI Portfolio Playbook (the product note in
`README.md` positions ScoutForge as the concrete, working foundation of that
chapter). Numbering follows the chapter file: shared platform sections
**§3.4–3.8** (Tables 27–29) and the project chapter **§4.1–4.3** with
**Tables 30–35** (at a glance, demand, architecture, PRD/personas/MoSCoW/FRs,
NFRs, KPIs). "Evidence" points at code/docs in this repo.

> Version: v0.1 · 15-11-26 · Author: SHIVAM ITCS (JARVIS)

Legend: ✅ implemented · 🟡 partial · ⬜ planned (not in this repo yet)

## Project snapshot — Table 30 “Project 4 at a glance”

| Playbook item | Status | Evidence / note |
|---------------|--------|-----------------|
| One-liner: AI platform that turns raw market signals into ranked, actionable leads | ✅ (as talent acquisition) | `README.md` intro; FastAPI description in `backend/app/main.py` |
| Solo build, 8–10 weeks, $0 infra | ✅ | Single-process app, SQLite, no external services |
| Hero-project tier (deployed, monitored, documented) | 🟡 | Docs + tests in repo; live VPS deploy is the `docs/DEPLOYMENT.md` platform flow |

## §4.1 Why it is in demand

| Pain point in playbook | Addressed by | Status |
|------------------------|--------------|--------|
| Manual sourcing is slow | `GET /api/jobs/{id}/shortlist` returns ranked top-k instantly | ✅ `routers/scoring.py` |
| Inconsistent screening | Deterministic scorer, one formula, auditable | ✅ `app/scoring.py`, `docs/ARCHITECTURE.md` |
| No funnel visibility | Analytics endpoint + dashboard charts | ✅ `routers/analytics.py`, `frontend/app.js` |
| Channel ROI unknown | `source_effectiveness` per job | ✅ `routers/analytics.py` |

## §4.2 Reference architecture — Table 31 (4 layers)

| Playbook layer | Playbook role | In this repo | Status |
|----------------|---------------|--------------|--------|
| Acquisition | Ingest signals (webhooks, scrapers, ATS) | REST ingest + dashboard forms (`POST /api/jobs`, `POST /api/candidates`); webhooks/ATS integrations | 🟡 REST ✅, external feeds ⬜ |
| Intelligence | LLM scoring, summarization, dedup | Deterministic passthrough scorer (`app/scoring.py`); LLM-based scoring/summaries | 🟡 deterministic ✅, LLM ⬜ |
| Delivery | Shortlists, reports, human handoff | Shortlist endpoint + dashboard shortlist view; PDF/CSV export | 🟡 JSON API ✅, export ⬜ |
| Ops & governance | Audit, health, access control | `pipeline_events` audit trail, `/api/health`, SQLite backup flow; auth/SSO | 🟡 audit+health ✅, RBAC/SSO ⬜ |

## §4.3 PRD — objectives, personas, MoSCoW (Tables 32–33)

- **Objectives** (time-to-shortlist, channel effectiveness, funnel
  conversion, recruiter hours saved) → measurable via `GET
  /api/jobs/{id}/analytics` (funnel, source_effectiveness,
  offer_acceptance_rate) and shortlist latency. ✅ measurement surface
  implemented; time-saved KPI needs time-tracking → ⬜.
- **Personas** (recruiter, hiring manager, ops) → single-user dashboard
  serves recruiter + hiring manager views today; ops via health/backup docs. 🟡
- **MoSCoW (Table 35)**: Must = jobs CRUD, candidates CRUD, scoring,
  shortlist, pipeline, analytics → all ✅. Should = dashboard polish,
  export → dashboard ✅, export ⬜. Could = saved searches, email alerts → ⬜.
  Won't (this phase) = multi-tenant SaaS → ⬜ by design.

## §4.3 Functional requirements — Table 34 (FR-S1…FR-S8)

> The playbook FRs describe the full research/lead-intelligence platform; this
> repo ships the recruiting slice of it, so each FR is mapped to the closest
> implemented surface (see Status).

| FR | Requirement (playbook) | Status | Evidence |
|----|-----------------------|--------|----------|
| FR-S1 | Ingest job postings via REST or UI form | ✅ | `routers/jobs.py`, dashboard job form in `frontend/app.js` |
| FR-S2 | Maintain candidate profiles and sourcing channels | ✅ | `routers/candidates.py`, `source` enum in `app/models.py` |
| FR-S3 | Score & rank candidates against job requirements using AI | 🟡 | `app/scoring.py` (deterministic), `GET /api/candidates/{id}/score`; LLM scoring ⬜ |
| FR-S4 | Manage pipeline stages with full audit trail | ✅ | `routers/pipeline.py`, `pipeline_events` table |
| FR-S5 | Generate top-k shortlists per job | ✅ | `GET /api/jobs/{id}/shortlist?k=` |
| FR-S6 | Analytics dashboards (funnel, time-in-stage, sources, offers) | ✅ | `routers/analytics.py` + dashboard charts |
| FR-S7 | Role-based access control (SSO) | ⬜ | single-user demo; planned |
| FR-S8 | Export/share reports (PDF/CSV) | ⬜ | API returns JSON; export planned |

## §4.3 Non-functional requirements

| NFR | Status | Note |
|-----|--------|------|
| Performance (shortlist < 2 s at 10k candidates) | 🟡 | SQLite + in-memory scoring is fine at demo scale; Postgres path documented in `ARCHITECTURE.md` → evolution paths |
| Security | 🟡 | no secrets needed; auth/RBAC ⬜; TLS at proxy (`DEPLOYMENT.md`) |
| Reliability | ✅ | idempotent schema init + seed-only-if-empty on boot; `/api/health` |
| Maintainability | ✅ | thin routers over SQLite, Pydantic models as single source of truth, tests in `tests/test_api.py` |
| Observability | 🟡 | uvicorn logs + health; structured tracing ⬜ |

## §4.3 Success KPIs — Table 35 → where measured

| KPI | Surface |
|-----|---------|
| Time-to-shortlist | `GET /api/jobs/{id}/shortlist` latency (measure with curl/monitor) |
| Sourcing-channel effectiveness | `analytics.source_effectiveness` |
| Funnel conversion | `analytics.funnel`, `offer_acceptance_rate` |
| Recruiter time saved | ⬜ needs time-tracking data |

## §3.4 What you build / work breakdown (Table 27) → repo state

| Sprint | Scope | Status |
|--------|-------|--------|
| 1 | Data model + REST CRUD (jobs, candidates) | ✅ `app/models.py`, `app/database.py`, routers |
| 2 | Scoring + shortlist | ✅ `app/scoring.py`, `routers/scoring.py` |
| 3 | Pipeline + analytics | ✅ `routers/pipeline.py`, `routers/analytics.py` |
| 4 | Dashboard polish + deploy | ✅ `frontend/`, `docs/DEPLOYMENT.md` |

## §3.5 Deliverables & acceptance (Table 28)

| Deliverable | Status | Evidence |
|-------------|--------|----------|
| Working app (local + deployed) | 🟡 | local ✅; deployed via `DEPLOYMENT.md` platform section |
| Source repo with README/docs | ✅ | this repo (`README.md` + `docs/`) |
| API docs | ✅ | `docs/API.md` + `/docs` Swagger |
| Tests | ✅ | `backend/tests/test_api.py` |
| Demo video / screenshots | ⬜ | portfolio step |
| Monitoring/alerting on live URL | 🟡 | Uptime Kuma flow in `DEPLOYMENT.md` |

## §3.6 Benefits (Table 29) & §3.7 deployment on the VPS

- Benefit claims (hours saved, conversion lift) are playbook targets; the
  analytics endpoint is the in-product measurement surface.
- Platform deployment steps (Coolify compose resource, Caddy site
  `scout.shivamitcs.com` with automatic TLS, Uptime Kuma monitor on
  `/api/health`, nightly DB backup + restore drill, acceptance smoke test)
  are implemented as documentation in **`docs/DEPLOYMENT.md` → "Platform VPS
  deployment"**.

## §3.8 Portfolio angle

Positioning text lives in `README.md` → "Product note": ScoutForge is the
shipped, observable proof-of-work for the playbook's agentic-intelligence
chapter — a recruiter-facing slice of the full lead-intelligence platform.
