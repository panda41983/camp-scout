from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI

from campscout.config import Settings, get_settings

app = FastAPI()


@app.get("/health")
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {"status": "ok", "service": "campscout", "environment": settings.environment}
