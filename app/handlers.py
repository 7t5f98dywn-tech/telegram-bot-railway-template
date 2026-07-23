"""Update handlers. Add your own commands here — see README "Extending the bot".

The ``db: Storage`` argument is injected by aiogram's dependency injection:
``main.py`` puts the storage into the dispatcher's workflow data under the
key ``db``, and any handler that declares a parameter with that name gets it.
"""

from __future__ import annotations

from aiogram import F, Router, html
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from db import Storage

router = Router(name="starter")

HELP_TEXT = (
    "<b>Commands</b>\n"
    "/start — welcome message and menu\n"
    "/help — this message\n\n"
    "Anything else you send is echoed back. "
    "Fork the repo and edit <code>handlers.py</code> to make it yours."
)


def main_menu() -> InlineKeyboardMarkup:
    """Example inline keyboard. Callback data is namespaced as 'menu:<action>'."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="ℹ️ Help", callback_data="menu:help"),
                InlineKeyboardButton(text="📊 Stats", callback_data="menu:stats"),
            ],
            [
                InlineKeyboardButton(
                    text="🚂 Deploy your own", url="https://railway.com/deploy"
                )
            ],
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message, db: Storage) -> None:
    """/start — greet the user, remember them, show the menu."""
    user = message.from_user
    if user is not None:
        await db.track_user(user.id, user.username)
    name = html.quote(user.full_name) if user else "there"
    await message.answer(
        f"👋 Hello, <b>{name}</b>!\n\n"
        "I'm a webhook-powered starter bot running on Railway.\n"
        "Pick an option below or just send me a message.",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """/help — list available commands."""
    await message.answer(HELP_TEXT)


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery) -> None:
    """Inline 'Help' button — same text as /help, sent as a new message."""
    if isinstance(callback.message, Message):
        await callback.message.answer(HELP_TEXT)
    await callback.answer()  # Always answer, or the button spinner hangs.


@router.callback_query(F.data == "menu:stats")
async def cb_stats(callback: CallbackQuery, db: Storage) -> None:
    """Inline 'Stats' button — demonstrates reading from the storage layer."""
    count = await db.user_count()
    await callback.answer(f"{count} user(s) have started this bot.", show_alert=True)


@router.message(F.text)
async def echo(message: Message, db: Storage) -> None:
    """Fallback: echo any plain-text message. Replace with your own logic."""
    user = message.from_user
    if user is not None:
        await db.track_user(user.id, user.username)
    await message.answer(f"You said: {html.quote(message.text or '')}")
