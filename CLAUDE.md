# CLAUDE.md — CampScout

This file orients Claude Code (and you) when working on this repo. Read top-to-bottom before making changes.

## What this is

CampScout is a web app for finding available campsites across **Recreation.gov** and **ReserveCalifornia** with two headline features:

1. **Geographic + flexible-date search.** Find campgrounds within a radius of a point (or in a region) that have availability on a date or date range. Recreation.gov's own search is text-based and inflexible; this is the differentiator.
2. **Saved-search alerts.** Same query, but persisted — re-run on a schedule and notify the user via email/SMS when new availability appears (the Campnab use case).

Status: pre-MVP. Solo project, portfolio-grade. Target: working demo in ~3 weeks.

## Non-goals (be ruthless)

- **Auto-booking.** Never. Unethical, against ToS, and the existing tools all decline to do it for good reason.
- **Hotels, private campgrounds, Hipcamp inventory.** Public lands only.
- **Mobile app.** Responsive web is enough.
- **Payments / accounts beyond auth.** Free tool. No Stripe.
- **Every state's parks system.** Recreation.gov + ReserveCalifornia only for v1.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12 + FastAPI | Async-friendly, clean docs, good for both API and worker |
| ORM | SQLAlchemy 2.x (async) + Alembic | Standard, async support is mature |
| DB | Postgres 16 + PostGIS | Geographic queries are the headline; PostGIS is the only sane choice |
| Cache/queue | Redis (Upstash free tier) | Rate limiting + dedup |
| Worker | APScheduler in-process for v1; split to separate process if it grows | One fewer thing to deploy |
| Frontend | Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui | Mainstream, fast to build, looks good |
| Map | MapLibre GL JS + react-map-gl | Free, no Mapbox token needed |
| Auth | Supabase Auth | Free tier, handles email magic links |
| Email | Resend | Cleanest API, generous free tier |
| SMS (v2) | Twilio | Standard |
| Backend host | Fly.io | Free allowance, single-region is fine |
| Frontend host | Vercel | Hobby tier |
| DB host | Supabase or Neon | Free Postgres with PostGIS |

Don't substitute these without a reason. If a substitution is needed, document why in this file.

## Repo layout

```
campscout/
├── apps/
│   ├── api/                 # FastAPI app
│   │   ├── campscout/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── db.py
│   │   │   ├── models/      # SQLAlchemy models
│   │   │   ├── schemas/     # Pydantic schemas
│   │   │   ├── routers/     # search, watches, facilities, auth_callback
│   │   │   ├── providers/   # recreation_gov.py, reserve_ca.py, base.py
│   │   │   ├── scanner/     # job_planner.py, runner.py, diff.py
│   │   │   ├── notify/      # email.py, sms.py, dedup.py
│   │   │   └── seed/        # facility seed scripts
│   │   ├── alembic/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── web/                 # Next.js
│       ├── app/
│       ├── components/
│       ├── lib/
│       └── package.json
├── infra/
│   ├── fly.toml
│   └── docker-compose.yml   # local Postgres + Redis
├── SCHEMA.md                # database schema reference (READ THIS)
├── CLAUDE.md                # this file
└── README.md
```

## Key architectural decisions

### 1. Provider abstraction

All upstream calls go through a `Provider` interface:

```python
class Provider(Protocol):
    name: ProviderName
    async def list_facilities(self, region: Region) -> list[FacilityRecord]: ...
    async def fetch_availability(
        self, facility_external_id: str, month: date
    ) -> AvailabilityGrid: ...
    def booking_url(self, facility_external_id: str) -> str: ...
```

Recreation.gov uses RIDB for facility metadata + the internal `/api/camps/availability/campground/{id}/month` endpoint for grids. ReserveCalifornia uses `calirdr.usedirect.com/rdr/rdr/search/grid`.

When adding a third provider later, only `providers/` changes.

### 2. Scanner fans in by `(facility, month)`, not by watch

If 50 users watch Big Sur for June 2026, the scanner makes **one** request per cycle, not 50. See `scanner/job_planner.py`:

- On any watch create/update/delete, recompute affected `scan_jobs` rows.
- Each `scan_jobs` row's `interval_minutes` is the **min** across all active watches that need it.
- Worker loop: pull due jobs → scrape → upsert `availability_snapshots` and `current_availability` → diff against previous snapshot → fan results out to matching watches → enqueue notifications.

This is the most important non-obvious piece of the design. Don't break it.

### 3. Search is served from `current_availability`, not live

User search hits Postgres only. We never call upstream APIs in a request handler. Freshness comes from the scanner; UI shows "updated N min ago" per result.

Exception: a "search this region" with no existing scan coverage triggers a one-off scrape on miss, then caches. This is rare and rate-limited per IP.

### 4. Rate limiting is sacred

We are guests on Recreation.gov and UseDirect's servers. Rules:

- Default scan interval: 15 minutes per (facility, month).
- Min allowed: 5 minutes (only for explicitly hot facilities).
- Exponential backoff on 429/5xx: 2x, max 4 hours.
- After 5 consecutive failures, mark the job dead and alert the operator (you).
- Global concurrency cap on outbound HTTP per provider (semaphore in `providers/base.py`).
- User-Agent string identifies the project and includes a contact email. We are not pretending to be a browser.

### 5. Dedup notifications

Before sending, hash `(watch_id, facility_id, sorted available_dates)` and check `notifications` for a matching `dedup_key` in the last hour. Skip if found. This prevents storms when the scanner's interval is shorter than the booking-and-cancel cycle.

## Development workflow

### First-time setup

```bash
# Postgres + Redis locally
docker compose -f infra/docker-compose.yml up -d

# API
cd apps/api
uv sync                                     # or: pip install -e .[dev]
cp .env.example .env                        # fill in
alembic upgrade head
python -m campscout.seed.recreation_gov     # one-time, ~10min, populates facilities
uvicorn campscout.main:app --reload

# Web
cd apps/web
pnpm install
cp .env.example .env.local
pnpm dev
```

### Environment variables

API (`apps/api/.env`):
```
DATABASE_URL=postgresql+asyncpg://campscout:campscout@localhost:5432/campscout
REDIS_URL=redis://localhost:6379/0
RIDB_API_KEY=...                            # https://ridb.recreation.gov/
RESEND_API_KEY=...
TWILIO_*=...                                # v2 only
SUPABASE_JWT_SECRET=...
SCAN_USER_AGENT=CampScout/0.1 (riley@example.com)
ENVIRONMENT=local                           # local|prod
```

Web (`apps/web/.env.local`):
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

### Code conventions

- **Python**: ruff for lint+format. Type hints everywhere. `from __future__ import annotations` at top of every file. Async by default for I/O. No sync DB calls.
- **TypeScript**: strict mode on. No `any` without a `// TODO` and a reason. Server components by default; `'use client'` only when needed.
- **Commits**: conventional commits (`feat:`, `fix:`, `chore:`...). Small commits.
- **Tests**: pytest + httpx async client for the API. Vitest + Playwright for web. Aim for tests on the scanner diff logic and the dedup logic — those are where bugs hurt users.
- **Don't catch broad exceptions** in scanner/notify code. Let them bubble; the worker logs and moves to the next job. Silent failures here mean missed alerts, which destroys trust.

### Migrations

```bash
cd apps/api
alembic revision --autogenerate -m "describe change"
# Inspect the generated file. Always.
alembic upgrade head
```

Never edit a migration after it's been applied to prod.

## Build order (3-week MVP)

**Week 1 — Backend foundation, no UI**
- Day 1–2: Repo skeleton, docker-compose, alembic init, models matching SCHEMA.md.
- Day 3: Recreation.gov provider — `list_facilities` via RIDB, seed script.
- Day 4: Recreation.gov provider — `fetch_availability`. Manual scrape of 5 facilities.
- Day 5: Search endpoint (`POST /search`) reading from `current_availability`. Test via curl.
- Day 6–7: Scanner job_planner + runner. Run for 24h locally watching ~20 facilities.

**Week 2 — Frontend + alerts**
- Day 8–9: Next.js scaffold, Supabase auth, basic layout.
- Day 10–11: Map-based search UI (MapLibre + radius circle + date picker). List + map sync.
- Day 12: Watch creation flow ("save this search → alert me").
- Day 13: Notification pipeline (Resend) + dedup. Test by manually toggling availability rows.
- Day 14: User dashboard — list watches, pause/edit/delete, notification history.

**Week 3 — Polish + deploy**
- Day 15: ReserveCalifornia provider. Same interface, second `seed` script.
- Day 16: Deploy API to Fly.io, web to Vercel, DB to Supabase. End-to-end smoke test.
- Day 17: Error handling, structured logging (structlog), Sentry.
- Day 18: Empty states, loading states, error UIs. Mobile responsive pass.
- Day 19: README with screenshots, demo video, project page on personal site.
- Day 20–21: Buffer. There is always something.

## Things I will probably get wrong (pre-mortem)

- **Underestimating frontend.** The map + date picker UX is most of week 2. If it slips, ship a list-only v0 and add the map later.
- **RIDB rate limits or auth weirdness.** Have a backup plan: scrape the public facility pages once if RIDB is down.
- **ReserveCalifornia request format changes.** Pin the exact payload shape in `providers/reserve_ca.py` with a fixture-based test so breakage is loud.
- **Notification spam.** Test dedup hard before letting any real user sign up. The fastest way to get blocked by Resend is sending 100 identical emails in an hour.

## Working with Claude Code on this repo

When asking Claude Code for changes:

1. **Read SCHEMA.md before touching any model, migration, or query.** The schema doc is the spec.
2. **Provider code (`providers/*`) is the highest-risk area.** Always include a fixture-based test when modifying a provider. Real upstream calls in tests are forbidden.
3. **The scanner is concurrent and stateful.** Changes to `scanner/` need a written explanation of how the new behavior interacts with `scan_jobs`, `current_availability`, and the dedup table. No "looks good" merges.
4. **UI changes should ship behind no flags** — small enough to review in one sitting.
5. **If a task would require >5 file changes, stop and propose a plan first.** Do not just start editing.
6. **Don't add dependencies without justification.** This stack is already chosen. New libraries need a one-line "why not stdlib / why not existing dep" in the commit message.

## Useful references

- RIDB API docs: https://ridb.recreation.gov/landing
- Recreation.gov data terms: https://www.recreation.gov/use-our-data
- camply (prior art, Python, MIT): https://github.com/juftin/camply
- ggydush/campsites (prior art, Python): https://github.com/ggydush/campsites

## License + ethics

MIT. The README must include a clearly worded notice: this is an unofficial tool, all bookings happen on the official sites, scan intervals are set conservatively to avoid burdening upstream systems, and reservation reselling/transfer is not supported.
