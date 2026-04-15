from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from campscout.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/api")


@router.get("/me")
async def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    return user
