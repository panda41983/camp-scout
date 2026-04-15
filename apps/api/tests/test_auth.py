from __future__ import annotations

import json
import time
import uuid

import httpx
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from jose import jwt
from jose.utils import long_to_base64

from campscout.auth import _jwks_cache
from campscout.config import get_settings

# --- Test key pair (ES256 / P-256) ---

_ec_private_key = ec.generate_private_key(ec.SECP256R1())
_ec_public_key = _ec_private_key.public_key()
_kid = "test-kid-001"

# Build the private key dict for python-jose signing
_ec_public_numbers = _ec_public_key.public_numbers()
_ec_private_numbers = _ec_private_key.private_numbers()

_private_jwk = {
    "kty": "EC",
    "crv": "P-256",
    "x": long_to_base64(_ec_public_numbers.x).decode(),
    "y": long_to_base64(_ec_public_numbers.y).decode(),
    "d": long_to_base64(_ec_private_numbers.private_value).decode(),
    "kid": _kid,
}

# Build JWKS response (public key only)
_public_jwk = {
    "kty": "EC",
    "crv": "P-256",
    "x": _private_jwk["x"],
    "y": _private_jwk["y"],
    "kid": _kid,
    "use": "sig",
    "alg": "ES256",
}
FAKE_JWKS = {"keys": [_public_jwk]}


def _make_token(
    sub: str | None = None,
    email: str | None = None,
    kid: str | None = None,
    exp_offset: int = 3600,
    key=None,
) -> str:
    """Sign a test JWT with the test private key."""
    now = int(time.time())
    claims = {
        "sub": sub or str(uuid.uuid4()),
        "email": email or "test@example.com",
        "iat": now,
        "exp": now + exp_offset,
    }
    headers = {"kid": kid or _kid}
    return jwt.encode(
        claims,
        key or _private_jwk,
        algorithm="ES256",
        headers=headers,
    )


@pytest.fixture(autouse=True)
def _reset_jwks_cache():
    """Reset the JWKS cache before each test."""
    _jwks_cache._keys = {}
    _jwks_cache._fetched_at = 0.0


@pytest.fixture
def _mock_jwks():
    """Mock the JWKS endpoint to return our test public key."""
    settings = get_settings()
    with respx.mock:
        respx.get(settings.supabase_jwks_url).mock(
            return_value=httpx.Response(200, json=FAKE_JWKS)
        )
        yield


@pytest.fixture
def _mock_jwks_down():
    """Mock the JWKS endpoint to return a 500 error."""
    settings = get_settings()
    with respx.mock:
        respx.get(settings.supabase_jwks_url).mock(
            return_value=httpx.Response(500)
        )
        yield


# --- Use httpx async client against the FastAPI app ---

from httpx import ASGITransport, AsyncClient
from campscout.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_valid_token(client: AsyncClient, _mock_jwks: None) -> None:
    token = _make_token(email="camper@example.com")
    resp = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "camper@example.com"
    assert "id" in data


async def test_missing_token(client: AsyncClient) -> None:
    resp = await client.get("/api/me")
    assert resp.status_code == 422  # FastAPI returns 422 for missing required header


async def test_malformed_token(client: AsyncClient, _mock_jwks: None) -> None:
    resp = await client.get("/api/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


async def test_expired_token(client: AsyncClient, _mock_jwks: None) -> None:
    token = _make_token(exp_offset=-3600)  # expired 1 hour ago
    resp = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_wrong_signing_key(client: AsyncClient, _mock_jwks: None) -> None:
    # Sign with a different key than what JWKS returns
    wrong_ec = ec.generate_private_key(ec.SECP256R1())
    wrong_pub = wrong_ec.public_key().public_numbers()
    wrong_priv = wrong_ec.private_numbers()
    wrong_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": long_to_base64(wrong_pub.x).decode(),
        "y": long_to_base64(wrong_pub.y).decode(),
        "d": long_to_base64(wrong_priv.private_value).decode(),
        "kid": _kid,
    }
    token = _make_token(key=wrong_jwk)
    resp = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_jwks_endpoint_down(client: AsyncClient, _mock_jwks_down: None) -> None:
    token = _make_token()
    resp = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503
