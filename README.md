# Deploy and Host a Python Telegram Bot on Railway

Self-host a production-ready Python Telegram bot on Railway in one click — webhook mode, aiogram 3, optional Postgres, near-zero idle cost.

A production-grade **Telegram Bot Starter Kit** built with [aiogram 3](https://docs.aiogram.dev/) — the modern, fully asynchronous Python framework for the Telegram Bot API. Deploy in one click, message your bot within two minutes, then extend it into anything: support bot, alerts bot, mini-app backend, AI assistant.

**Why this starter is cheap to run:** it uses **webhook mode**, not long-polling. Telegram pushes updates to your bot over HTTPS; between messages the container sits idle at near-zero CPU. A polling bot burns compute 24/7 asking "any updates yet?" — a webhook bot only wakes when someone actually talks to it.

## Features

- **aiogram 3.30 webhook mode** on aiohttp, bound to `0.0.0.0:$PORT` (Railway convention)
- **Webhook auto-registration** on startup using `RAILWAY_PUBLIC_DOMAIN` — zero manual `setWebhook` calls, survives domain changes and redeploys
- **Secret-token validation**: every incoming request must carry the correct `X-Telegram-Bot-Api-Secret-Token` header ([Telegram docs](https://core.telegram.org/bots/api#setwebhook)); anything else gets a 401
- `/start` + `/help` commands, an **inline-keyboard menu** with callback handlers, and an echo fallback — the three patterns 90% of bots are built from
- **Optional Postgres persistence** (asyncpg pool over Railway's private network); cleanly abstracted behind a `Storage` protocol and the bot **works without a database too**
- `/healthz` endpoint wired to Railway's healthcheck, **JSON structured logging**, **graceful shutdown** on SIGTERM (no lost updates — Telegram queues them during redeploys)
- Hardened Dockerfile: `python:3.12-slim`, non-root user, pinned dependencies, no pip cache

## Quickstart (BotFather → Deploy → Chat)

1. **Create a bot**: open [@BotFather](https://t.me/BotFather) in Telegram, send `/newbot`, pick a name and a username ending in `bot`. Copy the token (`123456789:AAH8x...`).
2. **Deploy**: click *Deploy on Railway*, paste the token into `TELEGRAM_BOT_TOKEN` when prompted. Everything else (webhook secret, Postgres wiring) is generated automatically.
3. **Chat**: wait for the deploy to go green (the healthcheck on `/healthz` gates it), open your bot in Telegram, and send `/start`. You should get a greeting with an inline menu. Done.

## Architecture

| Service | Source | Networking | Purpose |
|---|---|---|---|
| `bot` | This repo (`app/`, Dockerfile) | Public HTTPS domain | aiohttp server: webhook receiver + healthcheck |
| `Postgres` *(optional)* | `ghcr.io/railwayapp-templates/postgres-ssl:17` | Private only (IPv6) + volume | Persists users across restarts |

```
Telegram ──HTTPS POST + secret header──▶ bot (aiohttp on $PORT)
                                          │ /telegram/webhook  → aiogram Dispatcher → handlers.py
                                          │ /healthz           → Railway healthcheck
                                          └──private IPv6──▶ Postgres (optional)
```

## Environment Variables

| Variable | Required | Default / template value | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | **Yes** | *(you supply it)* | Bot token from [@BotFather](https://t.me/BotFather) |
| `WEBHOOK_SECRET` | **Yes** | `${{ secret(32) }}` (auto) | Validated against the `X-Telegram-Bot-Api-Secret-Token` header on every update |
| `PORT` | auto | injected by Railway | Port the server binds to on `0.0.0.0` |
| `RAILWAY_PUBLIC_DOMAIN` | auto | injected by Railway | Used to build the webhook URL at startup |
| `DATABASE_URL` | No | `${{ Postgres.DATABASE_URL }}` | If unset, the bot runs with in-memory storage |
| `WEBHOOK_PATH` | No | `/telegram/webhook` | URL path Telegram posts to |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `DROP_PENDING_UPDATES` | No | `false` | Set `true` to discard updates queued while the bot was down |

## Extending the Bot

All handlers live in [`app/handlers.py`](app/handlers.py). aiogram routes updates by decorator filters, top to bottom.

**Add a command** — e.g. `/ping`:

```python
@router.message(Command("ping"))
async def cmd_ping(message: Message) -> None:
    await message.answer("pong 🏓")
```

**Add an inline button + callback** — extend `main_menu()` and handle it:

```python
# In main_menu(): add to the keyboard
InlineKeyboardButton(text="🎲 Roll", callback_data="menu:roll")

@router.callback_query(F.data == "menu:roll")
async def cb_roll(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.answer_dice("🎲")
    await callback.answer()
```

**Use the database in a handler** — declare a `db: Storage` parameter and aiogram injects it:

```python
@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Storage) -> None:
    await message.answer(f"👥 {await db.user_count()} users so far")
```

**Add a new table / queries**: extend `PostgresStorage` in [`app/db.py`](app/db.py) (and mirror the method on `MemoryStorage` so the bot still works without a DB). New update types (edited messages, inline queries, ...)? Add them to `allowed_updates` in `app/main.py`.

**Remove Postgres entirely**: delete the `Postgres` service in Railway, remove the `DATABASE_URL` variable from the `bot` service, and (optionally) delete `db.py` plus the `db` parameters. The bot auto-falls back to in-memory storage — nothing breaks.

## Run Locally

Webhooks need a public HTTPS URL, so local runs use a tunnel:

```bash
cd app && pip install -r requirements.txt
# In another terminal: ngrok http 8080  (or `railway run`, cloudflared, etc.)
TELEGRAM_BOT_TOKEN=123:ABC WEBHOOK_SECRET=dev_secret_123 \
RAILWAY_PUBLIC_DOMAIN=your-tunnel.ngrok.app PORT=8080 python main.py
```

## FAQ

**Why webhooks instead of long-polling?** Cost and latency. Polling keeps the container busy 24/7; webhooks are push-based, so you pay for CPU only when messages arrive, and delivery is instant. Railway gives every service a free HTTPS domain — the one thing polling bots exist to avoid needing.

**Why aiogram and not python-telegram-bot?** Both are excellent and actively maintained (PTB v22.8, June 2026). aiogram won here because its `SimpleRequestHandler` embeds directly into an aiohttp app — webhook validation, dispatcher lifecycle, and the `/healthz` route all live in one small server. PTB's built-in webhook mode runs its own separate webserver, which makes adding a healthcheck endpoint clumsier. Migrating is easy; the Docker/Railway scaffolding is framework-agnostic.

**Do I have to run setWebhook myself?** No. The bot calls `set_webhook` on every startup with the current `RAILWAY_PUBLIC_DOMAIN`. It's idempotent.

**Can several people use the bot at once?** Yes — everything is async; aiohttp handles concurrent updates. For heavy workloads, offload slow work to a queue rather than blocking handlers.

**Where do logs go?** stdout as one JSON object per line — Railway's log explorer parses and filters them.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Deploy fails healthcheck | Bot crashed on startup | Check logs: missing `TELEGRAM_BOT_TOKEN` and invalid tokens raise clear errors |
| Bot deployed but silent | Webhook not registered | Logs should show `webhook registered bot=@...`; verify the service has a public domain (Settings → Networking → Generate Domain) |
| `401 Unauthorized` in logs on every update | `WEBHOOK_SECRET` changed after webhook registration | Redeploy — startup re-registers the webhook with the current secret |
| `Unauthorized` from Telegram at startup | Token revoked or wrong | Get a fresh token from @BotFather (`/token`) and update the variable |
| DB connection errors | `DATABASE_URL` points at removed service | Delete the variable (bot falls back to memory) or re-add Postgres |
| Old messages flood in after downtime | Telegram queued them (by design) | Set `DROP_PENDING_UPDATES=true` for one deploy |
| Check webhook state directly | — | `curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"` shows the registered URL and last error |

## Repository Layout

```
app/            # Deployable service (Dockerfile context)
  main.py       # Server, lifecycle, webhook registration, /healthz
  handlers.py   # Commands, callbacks, echo — extend here
  db.py         # Storage protocol: Postgres or in-memory
  config.py     # Typed env config with fail-fast validation
services/       # Paste-ready composer variables per service
SECURITY.md     # Threat model and hardening notes
RAILWAY-PUBLISH-GUIDE.md  # How to publish this as a Railway template
```

## License

MIT — fork it, ship it, sell it.
