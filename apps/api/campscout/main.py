from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from campscout.config import Settings, get_settings
from campscout.db import async_session_factory
from campscout.providers.recreation_gov import RecreationGovProvider
from campscout.providers.reserve_california import ReserveCaliforniaProvider
from campscout.routers.facilities import router as facilities_router
from campscout.routers.me import router as me_router
from campscout.routers.notifications import router as notifications_router
from campscout.routers.search import router as search_router
from campscout.routers.watches import router as watches_router
from campscout.scanner.bulk_seed import seed_bulk_scan_jobs
from campscout.scanner.runner import run_scan_cycle

log = structlog.get_logger()


async def _scan_tick() -> None:
    """Called by APScheduler every 60s to run due scan jobs."""
    settings = get_settings()
    providers = {
        "recreation_gov": RecreationGovProvider(
            api_key=settings.ridb_api_key,
            user_agent=settings.scan_user_agent,
        ),
        "reserve_california": ReserveCaliforniaProvider(
            user_agent=settings.scan_user_agent,
        ),
    }
    try:
        count = await run_scan_cycle(async_session_factory, providers)
        if count > 0:
            log.info("scan_tick_done", jobs_processed=count)
    except Exception:
        log.exception("scan_tick_error")
    finally:
        for p in providers.values():
            await p.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if get_settings().scanner_enabled:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(_scan_tick, IntervalTrigger(seconds=60), max_instances=1)
        # Daily job: ensure all facilities have scan_jobs
        scheduler.add_job(
            lambda: seed_bulk_scan_jobs(async_session_factory),
            IntervalTrigger(hours=24),
            next_run_time=None,  # don't run immediately on startup
        )
        # Run once on startup to seed initial jobs
        await seed_bulk_scan_jobs(async_session_factory)
        scheduler.start()
        log.info("scanner_started", interval_seconds=60)
    else:
        log.info("scanner_disabled")
    yield
    if scheduler:
        scheduler.shutdown()
        log.info("scanner_stopped")


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        get_settings().frontend_url,
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(facilities_router)
app.include_router(me_router)
app.include_router(notifications_router)
app.include_router(search_router)
app.include_router(watches_router)


@app.get("/health")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {"status": "ok", "service": "campscout", "environment": settings.environment}
