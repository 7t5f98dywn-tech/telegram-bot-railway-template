"""Optional persistence layer.

The bot works with or without a database:

* ``DATABASE_URL`` set  -> ``PostgresStorage`` (asyncpg connection pool).
* ``DATABASE_URL`` unset -> ``MemoryStorage`` (in-process dict, resets on deploy).

Handlers only depend on the ``Storage`` protocol, so you can swap in Redis,
SQLite, or an ORM without touching handler code. To remove persistence
entirely, delete this file, the ``db=`` wiring in ``main.py``, and the
``db`` parameters in ``handlers.py``.
"""

from __future__ import annotations

import logging
from typing import Protocol

import asyncpg

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bot_users (
    user_id    BIGINT PRIMARY KEY,
    username   TEXT,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


class Storage(Protocol):
    """Minimal persistence interface used by the handlers."""

    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def track_user(self, user_id: int, username: str | None) -> None: ...
    async def user_count(self) -> int: ...
    @property
    def backend(self) -> str: ...


class MemoryStorage:
    """No-op fallback so the template runs without a database attached."""

    def __init__(self) -> None:
        self._users: dict[int, str | None] = {}

    @property
    def backend(self) -> str:
        return "memory (no DATABASE_URL set — data resets on restart)"

    async def open(self) -> None:
        logger.info("storage.open backend=memory")

    async def close(self) -> None:  # Nothing to release.
        return None

    async def track_user(self, user_id: int, username: str | None) -> None:
        self._users[user_id] = username

    async def user_count(self) -> int:
        return len(self._users)


class PostgresStorage:
    """asyncpg-backed storage. Works over Railway's IPv6 private network."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    @property
    def backend(self) -> str:
        return "postgres"

    async def open(self) -> None:
        # Small pool: a webhook bot rarely needs more than a few connections.
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
        async with self._pool.acquire() as conn:
            await conn.execute(_SCHEMA)
        logger.info("storage.open backend=postgres")

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def track_user(self, user_id: int, username: str | None) -> None:
        assert self._pool is not None, "PostgresStorage used before open()"
        await self._pool.execute(
            """
            INSERT INTO bot_users (user_id, username) VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO UPDATE SET username = EXCLUDED.username, last_seen = now()
            """,
            user_id,
            username,
        )

    async def user_count(self) -> int:
        assert self._pool is not None, "PostgresStorage used before open()"
        return await self._pool.fetchval("SELECT count(*) FROM bot_users")


def create_storage(database_url: str | None) -> Storage:
    """Pick the storage backend based on configuration."""
    if database_url:
        return PostgresStorage(database_url)
    return MemoryStorage()
