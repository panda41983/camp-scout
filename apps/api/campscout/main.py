from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Depends, FastAPI

from campscout.config import Settings, get_settings
from campscout.db import async_session_factory
from campscout.providers.recreation_gov import RecreationGovProvider
from campscout.routers.me import router as me_router
from campscout.routers.search import router as search_router
from campscout.scanner.runner import run_scan_cycle

log = structlog.get_logger()


async def _scan_tick() -> None:
    """Called by APScheduler every 60s to run due scan jobs."""
    settings = get_settings()
    provider = RecreationGovProvider(
        api_key=settings.ridb_api_key,
        user_agent=settings.scan_user_agent,
    )
    try:
        count = await run_scan_cycle(async_session_factory, provider)
        if count > 0:
            log.info("scan_tick_done", jobs_processed=count)
    except Exception:
        log.exception("scan_tick_error")
    finally:
        await provider.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_scan_tick, IntervalTrigger(seconds=60), max_instances=1)
    scheduler.start()
    log.info("scanner_started", interval_seconds=60)
    yield
    scheduler.shutdown()
    log.info("scanner_stopped")


app = FastAPI(lifespan=lifespan)
app.include_router(me_router)
app.include_router(search_router)


@app.get("/health")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {"status": "ok", "service": "campscout", "environment": settings.environment}
