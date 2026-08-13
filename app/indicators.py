from __future__ import annotations

from math import sqrt
from typing import Any


def _closes(candles: list[dict[str, Any]]) -> list[float]:
    return [float(c["close"]) for c in candles]


def _highs(candles: list[dict[str, Any]]) -> list[float]:
    return [float(c["high"]) for c in candles]


def _lows(candles: list[dict[str, Any]]) -> list[float]:
    return [float(c["low"]) for c in candles]


def ema(values: list[float], period: int) -> float:
    if len(values) < period:
        raise ValueError(f"Need at least {period} values for EMA.")

    multiplier = 2 / (period + 1)
    result = sum(values[:period]) / period

    for value in values[period:]:
        result = (value - result) * multiplier + result

    return result


def sma(values: list[float], period: int) -> float:
    if len(values) < period:
        raise ValueError(f"Need at least {period} values for SMA.")

    return sum(values[-period:]) / period


def rsi(values: list[float], period: int = 14) -> float:
    if len(values) < period + 1:
        raise ValueError(f"Need at least {period + 1} values for RSI.")

    gains = []
    losses = []

    for i in range(1, len(values)):
        change = values[i] - values[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    relative_strength = avg_gain / avg_loss
    return 100 - (100 / (1 + relative_strength))


def true_ranges(candles: list[dict[str, Any]]) -> list[float]:
    if len(candles) < 2:
        raise ValueError("Need at least 2 candles for ATR.")

    result = []

    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        previous_close = float(candles[i - 1]["close"])

        result.append(
            max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        )

    return result


def atr(candles: list[dict[str, Any]], period: int = 14) -> float:
    ranges = true_ranges(candles)

    if len(ranges) < period:
        raise ValueError(f"Need at least {period + 1} candles for ATR.")

    return sum(ranges[-period:]) / period


def macd(
    values: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> dict[str, float]:
    if len(values) < slow_period + signal_period:
        raise ValueError("Not enough values for MACD.")

    fast = ema(values, fast_period)
    slow = ema(values, slow_period)
    macd_line = fast - slow

    # For the first version we calculate a stable signal estimate
    # from rolling MACD values.
    macd_values = []

    start = slow_period

    for i in range(start, len(values) + 1):
        subset = values[:i]

        fast_value = ema(subset, fast_period)
        slow_value = ema(subset, slow_period)
        macd_values.append(fast_value - slow_value)

    signal_line = ema(macd_values, signal_period)

    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": macd_line - signal_line,
    }


def volatility(candles: list[dict[str, Any]], period: int = 20) -> float:
    closes = _closes(candles)

    if len(closes) < period + 1:
        raise ValueError("Not enough data for volatility.")

    returns = []

    for i in range(1, len(closes)):
        previous = closes[i - 1]

        if previous == 0:
            continue

        returns.append((closes[i] - previous) / previous)

    recent = returns[-period:]

    if len(recent) < 2:
        return 0.0

    mean = sum(recent) / len(recent)
    variance = sum((x - mean) ** 2 for x in recent) / len(recent)

    return sqrt(variance)


def calculate_indicators(
    candles: list[dict[str, Any]],
) -> dict[str, float]:
    """Calculate the indicators used by the PO-AI strategy."""

    closes = _closes(candles)

    if len(closes) < 60:
        raise ValueError("At least 60 candles are recommended.")

    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)

    rsi14 = rsi(closes, 14)
    atr14 = atr(candles, 14)
    macd_data = macd(closes)

    return {
        "price": closes[-1],
        "ema9": ema9,
        "ema21": ema21,
        "ema50": ema50,
        "rsi14": rsi14,
        "atr14": atr14,
        "macd": macd_data["macd"],
        "macd_signal": macd_data["signal"],
        "macd_histogram": macd_data["histogram"],
        "volatility": volatility(candles, 20),
    }
