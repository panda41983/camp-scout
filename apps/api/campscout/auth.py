"""JWT verification using Supabase's JWKS (ES256 asymmetric keys)."""
from __future__ import annotations

import time
import uuid
from typing import Annotated, Any

import httpx
import structlog
from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwk, jwt
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from campscout.config import get_settings
from campscout.db import get_db
from campscout.models.user import User

log = structlog.get_logger()


class JWKSFetchError(Exception):
    """Raised when the JWKS endpoint is unreachable."""


class JWKSCache:
    """Fetches and caches public keys from a JWKS endpoint.

    - Keys are cached for TTL seconds (default 10 minutes).
    - If a kid isn't found in the cache, refresh once to handle key rotation.
    - If the JWKS endpoint is down, raise JWKSFetchError → maps to HTTP 503.
    """

    TTL = 600  # 10 minutes

    def __init__(self) -> None:
        self._keys: dict[str, Any] = {}
        self._fetched_at: float = 0.0

    async def _fetch(self) -> None:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(settings.supabase_jwks_url)  # type: ignore[arg-type]
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.error("jwks_fetch_failed", url=settings.supabase_jwks_url, error=str(exc))
            raise JWKSFetchError("Could not fetch JWKS") from exc

        data = resp.json()
        self._keys = {}
        for key_data in data.get("keys", []):
            kid = key_data.get("kid")
            if kid:
                self._keys[kid] = jwk.construct(key_data)
        self._fetched_at = time.monotonic()

    def _is_stale(self) -> bool:
        return (time.monotonic() - self._fetched_at) > self.TTL

    async def get_key(self, kid: str) -> Any:
        # Refresh if cache is stale
        if self._is_stale() or not self._keys:
            await self._fetch()

        key = self._keys.get(kid)
        if key is not None:
            return key

        # kid not found — maybe key rotation happened. Refresh once.
        await self._fetch()
        key = self._keys.get(kid)
        if key is not None:
            return key

        raise JWTError(f"No key found for kid={kid}")


_jwks_cache = JWKSCache()


class CurrentUser(BaseModel):
    id: uuid.UUID
    email: str


async def get_current_user(
    authorization: Annotated[str, Header()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    # Extract Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization[7:]

    try:
        # Decode header to get kid (without verifying signature yet)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(status_code=401, detail="Token missing kid header")

        # Get the public key
        try:
            key = await _jwks_cache.get_key(kid)
        except JWKSFetchError:
            raise HTTPException(status_code=503, detail="Auth service unavailable")

        # Verify and decode the JWT
        claims = jwt.decode(
            token,
            key,
            algorithms=["ES256"],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise HTTPException(status_code=401, detail="Token missing required claims")

    user_id = uuid.UUID(sub)

    # Upsert user row — creates on first login, updates id if email already exists
    # (Supabase keeps id stable per email, but ON CONFLICT on id alone can fail
    # if the email unique constraint is hit first.)
    stmt = insert(User).values(id=user_id, email=email)
    stmt = stmt.on_conflict_do_update(
        index_elements=["email"],
        set_={"id": user_id},
    )
    await db.execute(stmt)
    await db.commit()

    return CurrentUser(id=user_id, email=email)
