# management.py
import typing
import os, json, asyncio, time
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from pydantic import BaseModel, Field
from jose import jwt

from db import (
    get_session, AsyncSession, init_db,
    User, ApiKey,
    generate_api_key, hash_token,
    record_usage, usage_timeseries_for_key,
    API_KEY_PREFIX_LEN,
)

router = APIRouter(prefix="/management", tags=["management"])

# ---------- Entra ID (Azure AD) OIDC config ----------
TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID = os.getenv("AZURE_APP_CLIENT_ID", "")  # audience
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
OPENID_CONFIG_URL = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration"

_jwks_cache: dict = {}
_jwks_cache_expiry: float = 0.0
_openid_cache: Optional[dict] = None
_openid_cache_expiry: float = 0.0

async def _fetch_openid_and_jwks() -> tuple[dict, dict]:
    global _openid_cache, _openid_cache_expiry, _jwks_cache, _jwks_cache_expiry
    now = time.time()
    if not _openid_cache or now > _openid_cache_expiry:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(OPENID_CONFIG_URL)
            r.raise_for_status()
            _openid_cache = r.json()
            _openid_cache_expiry = now + 60 * 60  # 1h
    jwks_uri = _openid_cache["jwks_uri"]
    if not _jwks_cache or now > _jwks_cache_expiry:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(jwks_uri)
            r.raise_for_status()
            _jwks_cache = r.json()
            _jwks_cache_expiry = now + 60 * 30  # 30m
    return _openid_cache, _jwks_cache

class Principal(BaseModel):
    sub: str
    oid: Optional[str] = None
    upn: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    roles: list[str] = Field(default_factory=list)

async def get_principal(authorization: Annotated[Optional[str], Header(alias="Authorization")] = None) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    openid, jwks = await _fetch_openid_and_jwks()
    try:
        claims = jwt.decode(
            token,
            jwks,  # jose umí předat přímo dict s "keys"
            algorithms=["RS256", "RS512"],
            audience=CLIENT_ID,
            issuer=ISSUER,
            options={"verify_at_hash": False},
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    # map claims
    principal = Principal(
        sub=claims.get("sub"),
        oid=claims.get("oid") or claims.get("sub"),
        upn=claims.get("upn") or claims.get("preferred_username"),
        email=claims.get("email") or claims.get("preferred_username"),
        name=claims.get("name"),
        roles=list(claims.get("roles", [])),
    )
    return principal

# role helper
def require_admin(p: Principal):
    if "Proxy.Admin" not in (p.roles or []):
        raise HTTPException(status_code=403, detail="Admin role required")

# ----- Pydantic schemas -----
class CreateKeyRequest(BaseModel):
    name: Optional[str] = None
    expires_in_days: Optional[int] = Field(default=90, ge=1, le=3650)
    rate_limit_per_minute: Optional[int] = Field(default=None, ge=1)

class CreateKeyResponse(BaseModel):
    id: str
    token: str  # plaintext (once!)
    prefix: str
    name: Optional[str]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]

class ApiKeyInfo(BaseModel):
    id: str
    prefix: str
    name: Optional[str]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    rate_limit_per_minute: Optional[int]

class UsagePoint(BaseModel):
    bucket: str
    requests: int
    prompt_tokens: Optional[int] = 0
    completion_tokens: Optional[int] = 0
    total_tokens: Optional[int] = 0
    stream_bytes: Optional[int] = 0
    cost_usd: Optional[float] = 0.0

# ----- ensure user -----
async def _ensure_user(db: AsyncSession, p: Principal) -> User:
    from sqlalchemy import select
    res = await db.execute(select(User).where(or_(User.oid == p.oid, User.email == p.email)))
    user = res.scalars().first()
    if not user:
        user = User(oid=p.oid, email=p.email, display_name=p.name)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # lehký update jména/emailu
        upd = False
        if p.email and p.email != user.email:
            user.email = p.email; upd = True
        if p.name and p.name != user.display_name:
            user.display_name = p.name; upd = True
        if upd:
            await db.commit()
    return user

# ---------- Routes ----------
@router.post("/apikeys", response_model=CreateKeyResponse)
async def create_api_key(
    req: CreateKeyRequest,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_session),
):
    user = await _ensure_user(db, principal)
    plaintext, prefix, h = generate_api_key()
    expires_at = None
    if req.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_in_days)
    key = ApiKey(
        user_id=user.id,
        prefix=prefix,
        key_hash=h,
        name=req.name,
        is_active=True,
        expires_at=expires_at,
        rate_limit_per_minute=req.rate_limit_per_minute,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return CreateKeyResponse(
        id=key.id,
        token=plaintext,  # show once!
        prefix=prefix,
        name=key.name,
        is_active=key.is_active,
        created_at=key.created_at,
        expires_at=key.expires_at,
    )

@router.get("/apikeys", response_model=list[ApiKeyInfo])
async def list_my_keys(
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_session),
):
    user = await _ensure_user(db, principal)
    from sqlalchemy import select
    res = await db.execute(select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc()))
    keys = res.scalars().all()
    return [
        ApiKeyInfo(
            id=k.id, prefix=k.prefix, name=k.name, is_active=k.is_active,
            created_at=k.created_at, expires_at=k.expires_at,
            last_used_at=k.last_used_at, rate_limit_per_minute=k.rate_limit_per_minute
        )
        for k in keys
    ]

@router.post("/apikeys/{key_id}/disable")
async def disable_key(
    key_id: str,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_session),
):
    # owner-only (unless admin)
    from sqlalchemy import select
    res = await db.execute(select(ApiKey, User).join(User, ApiKey.user_id == User.id).where(ApiKey.id == key_id))
    row = res.first()
    if not row:
        raise HTTPException(404, "Key not found")
    key: ApiKey = row[0]; owner: User = row[1]
    if owner.oid != principal.oid and "Proxy.Admin" not in (principal.roles or []):
        raise HTTPException(403, "Not owner of the key")
    key.is_active = False
    await db.commit()
    return {"ok": True}

@router.post("/apikeys/{key_id}/enable")
async def enable_key(
    key_id: str,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select
    res = await db.execute(select(ApiKey, User).join(User, ApiKey.user_id == User.id).where(ApiKey.id == key_id))
    row = res.first()
    if not row:
        raise HTTPException(404, "Key not found")
    key: ApiKey = row[0]; owner: User = row[1]
    if owner.oid != principal.oid and "Proxy.Admin" not in (principal.roles or []):
        raise HTTPException(403, "Not owner of the key")
    key.is_active = True
    await db.commit()
    return {"ok": True}

class UsageQuery(BaseModel):
    key_id: str
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    bucket: Literal["hour", "day"] = "day"

@router.post("/usage", response_model=list[UsagePoint])
async def my_usage(
    q: UsageQuery,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_session),
):
    # ownership check
    from sqlalchemy import select
    res = await db.execute(select(ApiKey, User).join(User, ApiKey.user_id == User.id).where(ApiKey.id == q.key_id))
    row = res.first()
    if not row:
        raise HTTPException(404, "Key not found")
    key: ApiKey = row[0]; owner: User = row[1]
    if owner.oid != principal.oid and "Proxy.Admin" not in (principal.roles or []):
        raise HTTPException(403, "Not owner of the key")

    since = q.since or (datetime.now(timezone.utc) - timedelta(days=30))
    until = q.until or datetime.now(timezone.utc)

    rows = await usage_timeseries_for_key(
        db, api_key_id=key.id, since=since, until=until, bucket=q.bucket
    )
    # Pydantic casting
    return [UsagePoint(**r) for r in rows]
