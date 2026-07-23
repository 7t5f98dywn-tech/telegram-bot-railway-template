"""Typed application configuration, loaded once from environment variables.

Railway injects `PORT` and `RAILWAY_PUBLIC_DOMAIN` automatically; everything
else comes from the service variables defined in the template. Fail fast with
actionable errors so a misconfigured deploy is obvious in the deploy logs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Raised when a required environment variable is missing or invalid."""


def _require(name: str, hint: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable {name}. {hint}")
    return value


@dataclass(frozen=True, slots=True)
class Config:
    """Immutable snapshot of everything the bot needs to run."""

    bot_token: str
    webhook_secret: str
    public_domain: str
    webhook_path: str
    port: int
    database_url: str | None
    log_level: str
    drop_pending_updates: bool

    @property
    def webhook_url(self) -> str:
        """Public HTTPS URL Telegram will POST updates to."""
        return f"https://{self.public_domain}{self.webhook_path}"


def load_config() -> Config:
    """Read and validate configuration from the process environment."""
    return Config(
        bot_token=_require(
            "TELEGRAM_BOT_TOKEN",
            "Create a bot with @BotFather on Telegram (/newbot) and paste the token.",
        ),
        webhook_secret=_require(
            "WEBHOOK_SECRET",
            "Set a random 32+ char secret (the Railway template generates one via "
            "${{ secret(32) }}). Allowed chars per Telegram: A-Z a-z 0-9 _ -",
        ),
        public_domain=_require(
            "RAILWAY_PUBLIC_DOMAIN",
            "Railway injects this when the service has a public domain. "
            "Enable public networking: service Settings -> Networking -> Generate Domain.",
        ),
        webhook_path=os.environ.get("WEBHOOK_PATH", "/telegram/webhook"),
        port=int(os.environ.get("PORT", "8080")),  # Railway injects PORT
        database_url=os.environ.get("DATABASE_URL", "").strip() or None,
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        drop_pending_updates=os.environ.get("DROP_PENDING_UPDATES", "false").lower()
        in ("1", "true", "yes"),
    )
