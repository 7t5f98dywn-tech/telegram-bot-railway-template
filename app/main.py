"""Entrypoint: aiohttp web server + aiogram webhook bot.

Flow:
  1. Telegram POSTs updates to https://$RAILWAY_PUBLIC_DOMAIN/telegram/webhook.
  2. aiogram's SimpleRequestHandler verifies the X-Telegram-Bot-Api-Secret-Token
     header against WEBHOOK_SECRET and rejects non-matching requests (401).
  3. The dispatcher routes the update to a handler in handlers.py.

Webhook mode means the container is idle (near-zero CPU) between messages —
no long-polling loop burning compute 24/7.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import Config, load_config
from db import Storage, create_storage
from handlers import router

logger = logging.getLogger("bot")


class JsonFormatter(logging.Formatter):
    """One JSON object per line — plays nicely with Railway's log explorer."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler])


async def healthz(request: web.Request) -> web.Response:
    """Railway healthcheck endpoint (configured in railway.json)."""
    db: Storage = request.app["db"]
    return web.json_response({"status": "ok", "storage": db.backend})


def build_app(config: Config) -> web.Application:
    """Wire up bot, dispatcher, storage, and the aiohttp application."""
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    storage = create_storage(config.database_url)
    # Workflow data: injected into any handler declaring a `db` parameter.
    dispatcher["db"] = storage

    async def on_startup(bot: Bot) -> None:
        """Open storage, then register the webhook with Telegram.

        set_webhook is idempotent, so re-registering on every deploy is safe
        and keeps the webhook pointed at the current Railway domain.
        """
        await storage.open()
        await bot.set_webhook(
            url=config.webhook_url,
            secret_token=config.webhook_secret,
            drop_pending_updates=config.drop_pending_updates,
            allowed_updates=["message", "callback_query"],  # Extend as needed.
        )
        me = await bot.get_me()
        logger.info(
            "webhook registered bot=@%s url=%s storage=%s",
            me.username, config.webhook_url, storage.backend,
        )

    async def on_shutdown(bot: Bot) -> None:
        """Graceful shutdown on SIGTERM (Railway redeploys/restarts).

        We intentionally do NOT delete the webhook: Telegram queues updates
        while the new deploy comes up, so no messages are lost.
        """
        await storage.close()
        await bot.session.close()
        logger.info("shutdown complete")

    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    app = web.Application()
    app["db"] = storage
    app.router.add_get("/healthz", healthz)

    # Handles POSTs from Telegram; validates the secret token header for us.
    SimpleRequestHandler(
        dispatcher=dispatcher, bot=bot, secret_token=config.webhook_secret
    ).register(app, path=config.webhook_path)

    # Binds dispatcher startup/shutdown to the aiohttp app lifecycle.
    setup_application(app, dispatcher, bot=bot)
    return app


def main() -> None:
    config = load_config()
    setup_logging(config.log_level)
    logger.info("starting server port=%d domain=%s", config.port, config.public_domain)
    # run_app installs SIGINT/SIGTERM handlers and runs cleanup on exit.
    web.run_app(build_app(config), host="0.0.0.0", port=config.port, print=None)


if __name__ == "__main__":
    main()
