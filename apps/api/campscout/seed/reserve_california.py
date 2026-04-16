"""Seed the facilities table from ReserveCalifornia (Tyler Technologies API).

Usage: python -m campscout.seed.reserve_california
"""
from __future__ import annotations

import asyncio
import time

import structlog
from geoalchemy2 import Geography
from sqlalchemy import cast, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from campscout.config import get_settings
from campscout.models.facility import Facility
from campscout.providers.base import FacilityRecord, Region
from campscout.providers.reserve_california import ReserveCaliforniaProvider

log = structlog.get_logger()

BATCH_SIZE = 50


def _facility_values(rec: FacilityRecord) -> dict:
    return {
        "provider": rec.provider,
        "external_id": rec.external_id,
        "name": rec.name,
        "parent_name": rec.parent_name,
        "description": rec.description,
        "location": cast(func.ST_MakePoint(rec.lng, rec.lat), Geography),
        "state": rec.state,
        "campsite_count": rec.campsite_count,
        "photo_url": rec.photo_url,
        "booking_url": rec.booking_url,
        "amenities": rec.amenities,
    }


async def seed_facilities(session: AsyncSession, records: list[FacilityRecord]) -> int:
    total = 0
    for rec in records:
        vals = _facility_values(rec)
        stmt = insert(Facility).values(**vals)
        stmt = stmt.on_conflict_do_update(
            index_elements=["provider", "external_id"],
            set_={
                "name": stmt.excluded.name,
                "parent_name": stmt.excluded.parent_name,
                "location": stmt.excluded.location,
                "state": stmt.excluded.state,
                "campsite_count": stmt.excluded.campsite_count,
                "booking_url": stmt.excluded.booking_url,
                "amenities": stmt.excluded.amenities,
            },
        )
        await session.execute(stmt)
        total += 1

        if total % BATCH_SIZE == 0:
            await session.commit()
            log.info("seed_ca_batch_committed", total=total)

    await session.commit()
    return total


async def main() -> None:
    settings = get_settings()
    t0 = time.monotonic()

    log.info("seed_ca_starting")

    provider = ReserveCaliforniaProvider(user_agent=settings.scan_user_agent)

    try:
        raw_records = await provider.list_facilities(Region(state="CA"))

        # Deduplicate by external_id
        seen: set[str] = set()
        records: list[FacilityRecord] = []
        for r in raw_records:
            if r.external_id not in seen:
                seen.add(r.external_id)
                records.append(r)

        log.info("seed_ca_facilities_fetched", raw=len(raw_records), deduplicated=len(records))

        engine = create_async_engine(settings.database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            total = await seed_facilities(session, records)

        await engine.dispose()
    finally:
        await provider.aclose()

    elapsed = time.monotonic() - t0
    log.info("seed_ca_complete", total=total, elapsed_seconds=round(elapsed, 1))


if __name__ == "__main__":
    asyncio.run(main())
