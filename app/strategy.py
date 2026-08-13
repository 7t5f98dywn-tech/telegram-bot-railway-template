from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Signal(str, Enum):
    CALL = "CALL"
    PUT = "PUT"
    NO_TRADE = "NO TRADE"


@dataclass(frozen=True)
class StrategyResult:
    signal: Signal
    score: int
    reasons: tuple[str, ...]


def analyze(indicators: dict[str, float]) -> StrategyResult:
    """
    First PO-AI ruleset.

    The score represents the number and strength of conditions
    currently aligned. It is NOT a probability of winning.
    """

    price = indicators["price"]

    ema9 = indicators["ema9"]
    ema21 = indicators["ema21"]
    ema50 = indicators["ema50"]

    rsi14 = indicators["rsi14"]

    macd_value = indicators["macd"]
    macd_signal = indicators["macd_signal"]
    macd_histogram = indicators["macd_histogram"]

    volatility_value = indicators["volatility"]

    call_score = 0
    put_score = 0

    call_reasons: list[str] = []
    put_reasons: list[str] = []

    # ---------------------------------------------------------
    # TREND
    # ---------------------------------------------------------

    if ema9 > ema21 > ema50:
        call_score += 2
        call_reasons.append("EMA trend bullish")

    elif ema9 < ema21 < ema50:
        put_score += 2
        put_reasons.append("EMA trend bearish")

    # ---------------------------------------------------------
    # PRICE POSITION
    # ---------------------------------------------------------

    if price > ema21 and price > ema50:
        call_score += 1
        call_reasons.append("Price above EMA21/EMA50")

    elif price < ema21 and price < ema50:
        put_score += 1
        put_reasons.append("Price below EMA21/EMA50")

    # ---------------------------------------------------------
    # RSI
    # ---------------------------------------------------------

    if 50 <= rsi14 <= 68:
        call_score += 1
        call_reasons.append("RSI supports bullish momentum")

    elif 32 <= rsi14 <= 50:
        put_score += 1
        put_reasons.append("RSI supports bearish momentum")

    # Avoid chasing extreme RSI conditions.
    if rsi14 > 72:
        call_score -= 2
        call_reasons.append("RSI extremely high")

    if rsi14 < 28:
        put_score -= 2
        put_reasons.append("RSI extremely low")

    # ---------------------------------------------------------
    # MACD
    # ---------------------------------------------------------

    if macd_value > macd_signal and macd_histogram > 0:
        call_score += 2
        call_reasons.append("MACD bullish")

    elif macd_value < macd_signal and macd_histogram < 0:
        put_score += 2
        put_reasons.append("MACD bearish")

    # ---------------------------------------------------------
    # VOLATILITY FILTER
    # ---------------------------------------------------------

    # Very low volatility can produce weak/noisy signals.
    if volatility_value <= 0:
        return StrategyResult(
            signal=Signal.NO_TRADE,
            score=0,
            reasons=("Invalid volatility data",),
        )

    # ---------------------------------------------------------
    # FINAL DECISION
    # ---------------------------------------------------------

    minimum_score = 5
    minimum_difference = 2

    if (
        call_score >= minimum_score
        and call_score - put_score >= minimum_difference
    ):
        return StrategyResult(
            signal=Signal.CALL,
            score=call_score,
            reasons=tuple(call_reasons),
        )

    if (
        put_score >= minimum_score
        and put_score - call_score >= minimum_difference
    ):
        return StrategyResult(
            signal=Signal.PUT,
            score=put_score,
            reasons=tuple(put_reasons),
        )

    return StrategyResult(
        signal=Signal.NO_TRADE,
        score=max(call_score, put_score, 0),
        reasons=("Conditions are not sufficiently aligned",),
    )
