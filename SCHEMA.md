# CampScout — Database Schema

Postgres 16 + PostGIS. All tables use `id BIGSERIAL PRIMARY KEY` unless noted. Timestamps are `TIMESTAMPTZ` and default to `NOW()`.

## Design principles

1. **Facilities are the unit of caching.** A facility is one campground. Multiple users watching the same facility share the same scrape.
2. **Availability is a snapshot, not the source of truth.** The booking system is the source of truth; we cache snapshots to power search and detect diffs for alerts.
3. **Watches are saved searches.** A watch is a parametrized query that the scanner re-runs on a schedule. The same watch object powers both "saved search in UI" and "alert me on changes."
4. **Provider-agnostic from day one.** `provider` enum on every external-id column. Recreation.gov first, ReserveCalifornia second.
5. **Area-watch coverage follows facility syncs.** When the weekly facility-sync job adds or removes facilities, it recomputes `scan_jobs` for all active area-based watches (those with `center` + `radius_meters`). This keeps scan coverage in sync with the facility catalog without requiring on-demand recomputation on every search.

---

## Tables

### `providers` (enum, not a table)
```sql
CREATE TYPE provider AS ENUM ('recreation_gov', 'reserve_california');
```

### `facilities`
One row per campground. Seeded from RIDB (Recreation.gov) and scraped from UseDirect (ReserveCalifornia). Re-synced weekly.

```sql
CREATE TABLE facilities (
  id              BIGSERIAL PRIMARY KEY,
  provider        provider NOT NULL,
  external_id     TEXT NOT NULL,            -- e.g. "231958" for Arroyo Seco
  name            TEXT NOT NULL,
  parent_name     TEXT,                     -- "Los Padres National Forest"
  description     TEXT,
  location        GEOGRAPHY(POINT, 4326),   -- PostGIS, lat/lng
  state           TEXT,                     -- "CA", "NV", etc.
  nearest_town    TEXT,
  campsite_count  INT,
  amenities       JSONB,                    -- {hookups: bool, showers: bool, ...}
  photo_url       TEXT,
  booking_url     TEXT NOT NULL,            -- deep link back to provider
  last_synced_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (provider, external_id)
);

CREATE INDEX facilities_location_gix ON facilities USING GIST (location);
CREATE INDEX facilities_state_idx ON facilities (state);
CREATE INDEX facilities_name_trgm ON facilities USING GIN (name gin_trgm_ops);
```

The `location` GIST index is what makes "within 50mi of (37.7, -122.4)" fast. The trigram index on `name` powers fuzzy text search.

### `campsites`
Optional. Sites within a facility. **Not populated for v1** — search results show facility-level site counts and deep-link to the provider for site-level detail. The table stays in the schema so it's ready when per-campsite filtering is added post-MVP.

```sql
CREATE TABLE campsites (
  id              BIGSERIAL PRIMARY KEY,
  facility_id     BIGINT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
  external_id     TEXT NOT NULL,
  name            TEXT,                     -- site number/name like "A-12"
  site_type       TEXT,                     -- "tent", "rv", "group", "walk_in"
  attributes      JSONB,                    -- {max_vehicles: 2, hookups: "30amp", ...}
  UNIQUE (facility_id, external_id)
);

CREATE INDEX campsites_facility_idx ON campsites (facility_id);
```

### `availability_snapshots`
The output of one scrape of one facility for one month. We keep these so we can diff for alerts and answer "was X available yesterday?"

```sql
CREATE TABLE availability_snapshots (
  id              BIGSERIAL PRIMARY KEY,
  facility_id     BIGINT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
  scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  month           DATE NOT NULL,            -- first day of month
  -- {campsite_external_id: {date: status}}
  -- status: "available" | "reserved" | "not_reservable" | "closed"
  grid            JSONB NOT NULL,
  UNIQUE (facility_id, month, scraped_at)
);

CREATE INDEX snapshots_facility_month_idx
  ON availability_snapshots (facility_id, month, scraped_at DESC);
```

For the search feature you only need the **latest** snapshot per `(facility, month)`. A materialized view or a `current_availability` table updated on each scrape keeps reads fast:

```sql
CREATE TABLE current_availability (
  facility_id     BIGINT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
  month           DATE NOT NULL,
  scraped_at      TIMESTAMPTZ NOT NULL,
  grid            JSONB NOT NULL,
  -- denormalized for fast filtering: which dates have ANY available site
  available_dates DATE[] NOT NULL,
  PRIMARY KEY (facility_id, month)
);

CREATE INDEX current_avail_dates_gin ON current_availability USING GIN (available_dates);
```

`available_dates` lets you write `WHERE available_dates && ARRAY['2026-06-13', '2026-06-14']::DATE[]` to find facilities with any availability on those dates — fast.

### `users`
Owned by your auth provider (Supabase Auth or Clerk). This is the local mirror.

```sql
CREATE TABLE users (
  id              UUID PRIMARY KEY,         -- match auth provider's id
  email           TEXT NOT NULL UNIQUE,
  phone           TEXT,                     -- E.164, optional, for SMS
  notify_email    BOOLEAN NOT NULL DEFAULT TRUE,
  notify_sms      BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `watches`
A saved search. Doubles as the alert subscription.

```sql
CREATE TABLE watches (
  id              BIGSERIAL PRIMARY KEY,
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name            TEXT,                     -- "Big Sur weekend", user-set
  -- Search criteria
  facility_ids    BIGINT[],                 -- explicit list, OR
  center          GEOGRAPHY(POINT, 4326),   -- + radius for area search
  radius_meters   INT,
  date_start      DATE NOT NULL,
  date_end        DATE NOT NULL,
  nights          INT NOT NULL DEFAULT 1,
  -- "any contiguous N nights between start and end" if flexible
  flexible        BOOLEAN NOT NULL DEFAULT FALSE,
  weekdays        INT[],                    -- 0=Sun..6=Sat, NULL = any day OK
  site_filters    JSONB,                    -- {site_type: ["tent"], hookups: false}
  -- Behavior
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  scan_interval_minutes INT NOT NULL DEFAULT 15,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at      TIMESTAMPTZ,              -- auto-disable after trip date
  CHECK (
    (facility_ids IS NOT NULL AND array_length(facility_ids, 1) > 0)
    OR (center IS NOT NULL AND radius_meters IS NOT NULL)
  )
);

CREATE INDEX watches_active_idx ON watches (is_active) WHERE is_active;
CREATE INDEX watches_user_idx ON watches (user_id);
```

### `notifications`
A log of every alert sent. Used for dedup ("don't notify about the same opening twice within an hour") and a UI history.

```sql
CREATE TABLE notifications (
  id              BIGSERIAL PRIMARY KEY,
  watch_id        BIGINT NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  facility_id     BIGINT NOT NULL REFERENCES facilities(id),
  available_dates DATE[] NOT NULL,
  campsite_external_ids TEXT[],
  channel         TEXT NOT NULL,            -- 'email' | 'sms'
  sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  -- For dedup:
  dedup_key       TEXT NOT NULL,            -- hash(watch_id, facility_id, dates)
  UNIQUE (dedup_key, sent_at)               -- with cleanup job, see below
);

CREATE INDEX notifications_watch_idx ON notifications (watch_id, sent_at DESC);
CREATE INDEX notifications_dedup_idx ON notifications (dedup_key, sent_at DESC);
```

Dedup logic: before sending, check `SELECT 1 FROM notifications WHERE dedup_key = ? AND sent_at > NOW() - INTERVAL '1 hour'`. If found, skip.

### `scan_jobs`
Scheduler bookkeeping. The worker reads this to know what to scrape next, grouped by facility (not by watch — see fan-in pattern).

```sql
CREATE TABLE scan_jobs (
  id              BIGSERIAL PRIMARY KEY,
  facility_id     BIGINT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
  month           DATE NOT NULL,
  -- min interval across all active watches that need this (facility, month)
  interval_minutes INT NOT NULL,
  next_run_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_run_at     TIMESTAMPTZ,
  last_status     TEXT,                     -- 'ok' | 'rate_limited' | 'error'
  consecutive_failures INT NOT NULL DEFAULT 0,
  UNIQUE (facility_id, month)
);

CREATE INDEX scan_jobs_due_idx ON scan_jobs (next_run_at) WHERE consecutive_failures < 5;
```

Whenever a watch is created/updated/deleted, recompute the relevant `scan_jobs` rows: which `(facility, month)` pairs do active watches need, and at what min interval. The worker pulls due jobs, scrapes once, fans results out to all watches that intersect.

---

## Query examples

**Geographic search (the headline feature):**
```sql
SELECT f.id, f.name, f.parent_name, ca.available_dates
FROM facilities f
JOIN current_availability ca ON ca.facility_id = f.id
WHERE ST_DWithin(
    f.location,
    ST_MakePoint(-119.5383, 37.8651)::geography,  -- Yosemite Valley
    80467  -- 50mi in meters
  )
  AND ca.month = '2026-06-01'
  AND ca.available_dates && ARRAY['2026-06-13','2026-06-14']::DATE[]
ORDER BY array_length(ca.available_dates, 1) DESC;
```

**Flexible date search ("any Fri-Sun in June at these facilities"):**
Filter `available_dates` in app code after pulling the months — Postgres array ops handle the heavy lifting, app handles the weekday/contiguity logic.

**Diff for alerts:**
```sql
-- Pull the two most recent snapshots, diff in app code
SELECT scraped_at, grid
FROM availability_snapshots
WHERE facility_id = $1 AND month = $2
ORDER BY scraped_at DESC
LIMIT 2;
```

---

## Retention

- `availability_snapshots`: keep 7 days, then delete. The diff for alerts compares the two most recent *successful* snapshots regardless of time gap; the dedup table prevents notification spam if a long gap produces a noisy diff. `current_availability` covers reads.
- `notifications`: keep 90 days for user history.
- Cleanup job runs nightly via the same scheduler.

## Migrations

Use Alembic. Initial migration creates everything above plus extensions:
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;
```
