from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from indicators import calculate_indicators
from strategy import Signal, StrategyResult, analyze


@dataclass(frozen=True)
class TradingSignal:
    symbol: str
    timeframe: str
    created_at: datetime
    price: float
    signal: Signal
    score: int
    reasons: tuple[str, ...]
    indicators: dict[str, float]


def build_signal(
    symbol: str,
    candles: list[dict[str, Any]],
    timeframe: str = "5min",
) -> TradingSignal:
    """
    Convert market candles into one PO-AI analysis result.

    This function does not place trades.
    """

    if len(candles) < 60:
        raise ValueError(
            f"{symbol}: at least 60 candles are required for analysis."
        )

    indicators = calculate_indicators(candles)
    result: StrategyResult = analyze(indicators)

    return TradingSignal(
        symbol=symbol,
        timeframe=timeframe,
        created_at=datetime.now(timezone.utc),
        price=indicators["price"],
        signal=result.signal,
        score=result.score,
        reasons=result.reasons,
        indicators=indicators,
    )


def signal_to_dict(signal: TradingSignal) -> dict[str, Any]:
    """Convert a signal to a JSON-friendly dictionary."""

    return {
        "symbol": signal.symbol,
        "timeframe": signal.timeframe,
        "created_at": signal.created_at.isoformat(),
        "price": signal.price,
        "signal": signal.signal.value,
        "score": signal.score,
        "reasons": list(signal.reasons),
        "indicators": signal.indicators,
    }
