from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Protocol

import asyncpg

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bot_users (
    user_id    BIGINT PRIMARY KEY,
    username   TEXT,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trading_signals (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    price           DOUBLE PRECISION NOT NULL,
    signal          TEXT NOT NULL,
    score           INTEGER NOT NULL,
    reasons         JSONB NOT NULL DEFAULT '[]'::jsonb,
    indicators      JSONB NOT NULL DEFAULT '{}'::jsonb,
    result          TEXT,
    result_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_trading_signals_created_at
    ON trading_signals (created_at);

CREATE INDEX IF NOT EXISTS idx_trading_signals_symbol
    ON trading_signals (symbol);
"""


class Storage(Protocol):
    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def track_user(self, user_id: int, username: str | None) -> None: ...
    async def user_count(self) -> int: ...
    async def save_signal(
        self,
        symbol: str,
        timeframe: str,
        created_at: datetime,
        price: float,
        signal: str,
        score: int,
        reasons: list[str],
        indicators: dict[str, float],
    ) -> int: ...
    async def update_signal_result(
        self,
        signal_id: int,
        result: str,
    ) -> None: ...
    @property
    def backend(self) -> str: ...


class MemoryStorage:
    def __init__(self) -> None:
        self._users: dict[int, str | None] = {}
        self._signals: list[dict[str, Any]] = []
        self._next_signal_id = 1

    @property
    def backend(self) -> str:
        return "memory (no DATABASE_URL set — data resets on restart)"

    async def open(self) -> None:
        logger.info("storage.open backend=memory")

    async def close(self) -> None:
        return None

    async def track_user(
        self,
        user_id: int,
        username: str | None,
    ) -> None:
        self._users[user_id] = username

    async def user_count(self) -> int:
        return len(self._users)

    async def save_signal(
        self,
        symbol: str,
        timeframe: str,
        created_at: datetime,
        price: float,
        signal: str,
        score: int,
        reasons: list[str],
        indicators: dict[str, float],
    ) -> int:
        signal_id = self._next_signal_id
        self._next_signal_id += 1

        self._signals.append(
            {
                "id": signal_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "created_at": created_at,
                "price": price,
                "signal": signal,
                "score": score,
                "reasons": reasons,
                "indicators": indicators,
                "result": None,
            }
        )

        return signal_id

    async def update_signal_result(
        self,
        signal_id: int,
        result: str,
    ) -> None:
        for signal in self._signals:
            if signal["id"] == signal_id:
                signal["result"] = result
                return


class PostgresStorage:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    @property
    def backend(self) -> str:
        return "postgres"

    async def open(self) -> None:
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=1,
            max_size=5,
        )

        async with self._pool.acquire() as conn:
            await conn.execute(_SCHEMA)

        logger.info("storage.open backend=postgres")

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def track_user(
        self,
        user_id: int,
        username: str | None,
    ) -> None:
        assert self._pool is not None

        await self._pool.execute(
            """
            INSERT INTO bot_users (user_id, username)
            VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                last_seen = now()
            """,
            user_id,
            username,
        )

    async def user_count(self) -> int:
        assert self._pool is not None

        return await self._pool.fetchval(
            "SELECT count(*) FROM bot_users"
        )

    async def save_signal(
        self,
        symbol: str,
        timeframe: str,
        created_at: datetime,
        price: float,
        signal: str,
        score: int,
        reasons: list[str],
        indicators: dict[str, float],
    ) -> int:
        assert self._pool is not None

        return await self._pool.fetchval(
            """
            INSERT INTO trading_signals (
                symbol,
                timeframe,
                created_at,
                price,
                signal,
                score,
                reasons,
                indicators
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)
            RETURNING id
            """,
            symbol,
            timeframe,
            created_at,
            price,
            signal,
            score,
            json.dumps(reasons),
            json.dumps(indicators),
        )

    async def update_signal_result(
        self,
        signal_id: int,
        result: str,
    ) -> None:
        assert self._pool is not None

        await self._pool.execute(
            """
            UPDATE trading_signals
            SET result = $2,
                result_at = now()
            WHERE id = $1
            """,
            signal_id,
            result,
        )


def create_storage(database_url: str | None) -> Storage:
    if database_url:
        return PostgresStorage(database_url)

    return MemoryStorage()
