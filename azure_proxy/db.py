# db.py
from __future__ import annotations
import os, json, math, hashlib, secrets
from dataclasses import field
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Optional, Iterable, Literal
from uuid import uuid4

from sqlalchemy import (
    String, Integer, Boolean, DateTime, ForeignKey, Float, Text,
    Index, func, select, and_, or_, case
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship, declarative_base, mapped_as_dataclass
)

# ---------- DB engine ----------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./proxy.db")

engine = create_async_engine(DATABASE_URL, future=True, echo=False)
AsyncSessionMaker = async_sessionmaker(engine, expire_on_commit=False)

async def init_db() -> None:
    """Create tables if not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionMaker() as s:
        yield s

Base = declarative_base()

# ---------- Security / hashing ----------
API_KEY_PREFIX_LEN = int(os.getenv("API_KEY_PREFIX_LEN", "8"))
API_KEY_BYTES = int(os.getenv("API_KEY_BYTES", "32"))  # entropy ~ 256 bits
API_KEY_PEPPER = os.getenv("API_KEY_PEPPER", "")       # optional server-side secret for hashing

def hash_token(raw_token: str) -> str:
    # cheap & compatible; můžeš nahradit za bcrypt/argon2
    return hashlib.sha256((API_KEY_PEPPER + raw_token).encode("utf-8")).hexdigest()

def generate_api_key() -> tuple[str, str, str]:
    """Return (plaintext, prefix, hash)."""
    # URL-safe, bez oddělovačů
    raw = secrets.token_urlsafe(API_KEY_BYTES).replace("-", "").replace("_", "")
    prefix = raw[:API_KEY_PREFIX_LEN]
    return raw, prefix, hash_token(raw)

# ---------- Models ----------
@mapped_as_dataclass
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    # Entra ID object id (OID) – pro spolehlivý mapping identity
    oid: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, default=None)
    email: Mapped[Optional[str]] = mapped_column(String(320), index=True, default=None)
    display_name: Mapped[Optional[str]] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    keys: Mapped[list["ApiKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")

@mapped_as_dataclass
class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # uložený pouze hash; prefix pro rychlé hledání kandidátů
    prefix: Mapped[str] = mapped_column(String(32), index=True)
    key_hash: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(120), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)
    rate_limit_per_minute: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None)

    user: Mapped["User"] = relationship(back_populates="keys")
    usages: Mapped[list["Usage"]] = relationship(back_populates="api_key", cascade="all, delete-orphan")

Index("ix_api_keys_active_prefix", ApiKey.prefix, ApiKey.is_active)

@mapped_as_dataclass
class Usage(Base):
    __tablename__ = "usage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    api_key_id: Mapped[str] = mapped_column(ForeignKey("api_keys.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    route: Mapped[Optional[str]] = mapped_column(String(128), default=None)  # např. "openai_v1_responses"
    deployment: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    status: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    stream: Mapped[bool] = mapped_column(Boolean, default=False)

    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    stream_bytes: Mapped[Optional[int]] = mapped_column(Integer, default=None)

    # volitelná kalkulace ceny – pokud chceš
    cost_usd: Mapped[Optional[Float]] = mapped_column(Float, default=None)
    meta_json: Mapped[Optional[str]] = mapped_column(Text, default=None)

    api_key: Mapped["ApiKey"] = relationship(back_populates="usages")

Index("ix_usage_api_key_ts", Usage.api_key_id, Usage.ts)

# ---------- API key auth helpers ----------
class ApiKeyAuthError(Exception): ...

async def get_api_key_by_token(db: AsyncSession, raw_token: str) -> Optional[ApiKey]:
    """Najde aktivní ApiKey podle plaintext tokenu (prefix + hash compare)."""
    if not raw_token:
        return None
    prefix = raw_token[:API_KEY_PREFIX_LEN]
    q = await db.execute(
        select(ApiKey).where(
            ApiKey.prefix == prefix,
            ApiKey.is_active == True,  # noqa: E712
        )
    )
    candidates: Iterable[ApiKey] = q.scalars().all()
    target_hash = hash_token(raw_token)
    for k in candidates:
        # konstantní čas by tady řešil hmac.compare_digest
        if secrets.compare_digest(k.key_hash, target_hash):
            # expirace?
            if k.expires_at and k.expires_at < datetime.now(timezone.utc):
                return None
            return k
    return None

async def require_api_key(
    db: AsyncSession,
    token: Optional[str],
) -> ApiKey:
    """Ověří klíč z hlavičky a vrátí ApiKey; jinak vyhodí ApiKeyAuthError."""
    if not token:
        raise ApiKeyAuthError("Missing API key")
    key = await get_api_key_by_token(db, token)
    if not key:
        raise ApiKeyAuthError("Invalid or inactive API key")
    return key

# ---------- Usage recording ----------
async def record_usage(
    db: AsyncSession,
    *,
    api_key: ApiKey,
    ts: Optional[datetime] = None,
    route: Optional[str] = None,
    deployment: Optional[str] = None,
    status: Optional[int] = None,
    stream: bool = False,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    stream_bytes: Optional[int] = None,
    cost_usd: Optional[float] = None,
    meta: Optional[dict] = None,
) -> Usage:
    u = Usage(
        api_key_id=api_key.id,
        ts=ts or datetime.now(timezone.utc),
        route=route,
        deployment=deployment,
        status=status,
        stream=stream,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        stream_bytes=stream_bytes,
        cost_usd=cost_usd,
        meta_json=json.dumps(meta, ensure_ascii=False) if meta else None,
    )
    db.add(u)
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(u)
    return u

# ---------- Aggregations (consumption over time) ----------
Bucket = Literal["hour", "day"]

def _date_bucket_expr(bucket: Bucket):
    # portable-ish bucket expr (SQLite vs Postgres)
    if DATABASE_URL.startswith("sqlite"):
        if bucket == "hour":
            return func.strftime("%Y-%m-%dT%H:00:00Z", Usage.ts)
        return func.strftime("%Y-%m-%d", Usage.ts)
    # default: Postgres-friendly date_trunc
    return func.to_char(func.date_trunc(bucket, Usage.ts), "YYYY-MM-DD\"T\"HH24:00:00Z" if bucket=="hour" else "YYYY-MM-DD")

async def usage_timeseries_for_key(
    db: AsyncSession,
    *,
    api_key_id: str,
    since: datetime,
    until: datetime,
    bucket: Bucket = "day",
):
    b = _date_bucket_expr(bucket).label("bucket")
    q = (
        select(
            b,
            func.count().label("requests"),
            func.sum(Usage.prompt_tokens).label("prompt_tokens"),
            func.sum(Usage.completion_tokens).label("completion_tokens"),
            func.sum(Usage.total_tokens).label("total_tokens"),
            func.sum(Usage.stream_bytes).label("stream_bytes"),
            func.sum(Usage.cost_usd).label("cost_usd"),
        )
        .where(Usage.api_key_id == api_key_id, Usage.ts >= since, Usage.ts < until)
        .group_by(b)
        .order_by(b.asc())
    )
    res = await db.execute(q)
    rows = res.mappings().all()
    return [dict(r) for r in rows]
