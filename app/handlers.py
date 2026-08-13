from __future__ import annotations

from aiogram import F, Router, html
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from db import Storage
from market_data import TwelveDataClient
from signals import build_signal


router = Router(name="starter")


HELP_TEXT = (
    "<b>Commands</b>\n"
    "/start — welcome message and menu\n"
    "/help — this message\n"
    "/signal EUR/USD — analyze a 5-minute market\n\n"
    "Example:\n"
    "<code>/signal EUR/USD</code>"
)


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ℹ️ Help",
                    callback_data="menu:help",
                ),
                InlineKeyboardButton(
                    text="📊 Stats",
                    callback_data="menu:stats",
                ),
            ],
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message, db: Storage) -> None:
    user = message.from_user

    if user is not None:
        await db.track_user(user.id, user.username)

    name = html.quote(user.full_name) if user else "there"

    await message.answer(
        f"👋 Hello, <b>{name}</b>!\n\n"
        "I'm your PO-AI market analysis bot.\n\n"
        "Use:\n"
        "<code>/signal EUR/USD</code>\n\n"
        "The analysis uses 5-minute market data.",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("signal"))
async def cmd_signal(message: Message, db: Storage) -> None:
    """
    Analyze one Forex symbol using 5-minute candles.

    Example:
        /signal EUR/USD
    """

    user = message.from_user

    if user is not None:
        await db.track_user(user.id, user.username)

    text = message.text or ""
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "⚠️ Please provide a symbol.\n\n"
            "Example:\n"
            "<code>/signal EUR/USD</code>"
        )
        return

    symbol = parts[1].strip().upper()

    # Basic safety check: keep the first version limited to Forex pairs.
    if "/" not in symbol or len(symbol) > 15:
        await message.answer(
            "⚠️ Invalid symbol.\n\n"
            "Example:\n"
            "<code>/signal EUR/USD</code>"
        )
        return

    await message.answer(
        f"🔎 Analyzing <b>{html.quote(symbol)}</b> on 5M..."
    )

    try:
        client = TwelveDataClient()

        candles = await client.get_candles(
            symbol=symbol,
            interval="5min",
            outputsize=100,
        )

        if len(candles) < 60:
            await message.answer(
                "⚠️ Not enough market data was returned for this symbol."
            )
            return

        trading_signal = build_signal(
            symbol=symbol,
            candles=candles,
            timeframe="5min",
        )

        signal_id = await db.save_signal(
            symbol=trading_signal.symbol,
            timeframe=trading_signal.timeframe,
            created_at=trading_signal.created_at,
            price=trading_signal.price,
            signal=trading_signal.signal.value,
            score=trading_signal.score,
            reasons=list(trading_signal.reasons),
            indicators=trading_signal.indicators,
        )

        if trading_signal.signal.value == "CALL":
            emoji = "🟢"
        elif trading_signal.signal.value == "PUT":
            emoji = "🔴"
        else:
            emoji = "⚪"

        reasons = "\n".join(
            f"• {html.quote(reason)}"
            for reason in trading_signal.reasons
        )

        await message.answer(
            f"{emoji} <b>{trading_signal.signal.value}</b>\n\n"
            f"📊 <b>Pair:</b> {html.quote(symbol)}\n"
            f"⏱ <b>Timeframe:</b> 5M\n"
            f"💰 <b>Price:</b> {trading_signal.price}\n"
            f"🎯 <b>Score:</b> {trading_signal.score}\n"
            f"🆔 <b>Signal:</b> #{signal_id}\n\n"
            f"<b>Reasons:</b>\n{reasons}\n\n"
            "⚠️ Experimental analysis — not a guaranteed prediction.",
        )

    except Exception as exc:
        await message.answer(
            "❌ I couldn't complete the market analysis.\n\n"
            "Check the Railway logs for the technical error."
        )

        # Keep the technical exception out of Telegram.
        import logging

        logging.getLogger("bot").exception(
            "signal analysis failed for %s: %s",
            symbol,
            exc,
        )


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.answer(HELP_TEXT)

    await callback.answer()


@router.callback_query(F.data == "menu:stats")
async def cb_stats(
    callback: CallbackQuery,
    db: Storage,
) -> None:
    count = await db.user_count()

    await callback.answer(
        f"{count} user(s) have started this bot.",
        show_alert=True,
    )


@router.message(F.text)
async def echo(message: Message, db: Storage) -> None:
    user = message.from_user

    if user is not None:
        await db.track_user(user.id, user.username)

    await message.answer(
        f"You said: {html.quote(message.text or '')}"
    )
