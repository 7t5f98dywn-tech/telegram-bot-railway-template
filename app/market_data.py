from __future__ import annotations

import os
from typing import Any

import aiohttp


class MarketDataError(RuntimeError):
    """Raised when market data cannot be retrieved."""


class TwelveDataClient:
    BASE_URL = "https://api.twelvedata.com/time_series"

    def __init__(self) -> None:
        self.api_key = os.environ.get("TWELVE_DATA_API_KEY", "").strip()
        if not self.api_key:
            raise MarketDataError("TWELVE_DATA_API_KEY is not configured.")

    async def get_candles(
        self,
        symbol: str,
        interval: str = "5min",
        outputsize: int = 100,
    ) -> list[dict[str, Any]]:
        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": str(outputsize),
            "apikey": self.api_key,
            "format": "JSON",
        }

        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.BASE_URL, params=params) as response:
                if response.status != 200:
                    raise MarketDataError(
                        f"Twelve Data HTTP error: {response.status}"
                    )

                data = await response.json()

        if data.get("status") == "error":
            raise MarketDataError(
                data.get("message", "Unknown Twelve Data error")
            )

        values = data.get("values")

        if not isinstance(values, list):
            raise MarketDataError("Twelve Data returned no candle data.")

        return list(reversed(values))


# Activele inițiale pentru test.
# Le vom extinde după ce verificăm consumul API.
DEFAULT_SYMBOLS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
]


async def get_market_snapshot() -> dict[str, list[dict[str, Any]]]:
    """Return the latest 5-minute candles for the initial symbol set."""
    client = TwelveDataClient()

    result: dict[str, list[dict[str, Any]]] = {}

    for symbol in DEFAULT_SYMBOLS:
        try:
            result[symbol] = await client.get_candles(
                symbol=symbol,
                interval="5min",
                outputsize=100,
            )
        except MarketDataError:
            result[symbol] = []

    return result
