# Publishing Guide — Railway Template Composer

How to turn this repository into a published, one-click Railway template.
Audience: the template author (you), not end users.

## 0. Prerequisites

- Push this repository to a **public GitHub repo** (e.g. `your-org/telegram-bot-kit`).
  Two layout options:
  - **Monorepo (recommended, matches this package):** keep `app/` as the service
    root directory and docs at the top level.
  - **Flat:** publish only the contents of `app/` at the repo root; then leave
    Root Directory empty below.
- A Railway account with a verified email (required for marketplace publishing
  and kickback payouts).
- A throwaway bot token from @BotFather for smoke-testing.

## 1. Compose the template

Go to **https://railway.com/compose** (Dashboard → *Create Template*).

### Service 1 — `bot`

1. Click **Add New** → **GitHub Repo** → select `your-org/telegram-bot-kit`.
2. Rename the service to exactly `bot` (service names are referenced by
   variables; keep it lowercase).
3. **Settings → Root Directory**: `/app` (monorepo layout only).
4. Branch: `main`. Build: auto-detected from `app/railway.json`
   (Dockerfile builder, healthcheck `/healthz`, restart `ON_FAILURE` ×10).
5. **Settings → Networking → Enable "Generate Domain"** — the webhook needs a
   public HTTPS URL. Railway routes the domain to the injected `$PORT`.
6. **Variables** — add these three (paste-ready, also in
   `services/bot.env.template`):

   | Name | Value |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | *(leave empty)* |
   | `WEBHOOK_SECRET` | `${{ secret(32) }}` |
   | `DATABASE_URL` | `${{ Postgres.DATABASE_URL }}` |

7. Mark `TELEGRAM_BOT_TOKEN` as **required** and give it this description
   (shown to deployers in the config screen):

   > Your Telegram bot token. Open https://t.me/BotFather, send /newbot,
   > choose a name and a username ending in "bot", then paste the token
   > shown (looks like 123456789:AAH8x...). Keep it secret.

8. Description for `WEBHOOK_SECRET` (not user-editable conceptually, but
   document it):

   > Auto-generated secret validated on every Telegram webhook request
   > (X-Telegram-Bot-Api-Secret-Token header). Do not change.

### Service 2 — `Postgres` (optional service)

1. Click **Add New** → **Docker Image** → `ghcr.io/railwayapp-templates/postgres-ssl:17`.
2. Rename the service to exactly `Postgres` (the bot's `DATABASE_URL`
   reference uses this name).
3. **Add a volume**: right-click the service (or Settings → Volumes) →
   mount path `/var/lib/postgresql/data`.
4. **Do not** generate a public domain and do not add a TCP proxy.
5. **Variables** (paste-ready, also in `services/postgres.env.template`):

   | Name | Value |
   |---|---|
   | `PGDATA` | `/var/lib/postgresql/data/pgdata` |
   | `POSTGRES_USER` | `postgres` |
   | `POSTGRES_PASSWORD` | `${{ secret(32) }}` |
   | `POSTGRES_DB` | `railway` |
   | `SSL_CERT_DAYS` | `820` |
   | `DATABASE_URL` | `postgresql://${{ POSTGRES_USER }}:${{ POSTGRES_PASSWORD }}@${{ RAILWAY_PRIVATE_DOMAIN }}:5432/${{ POSTGRES_DB }}` |

Private networking note: `RAILWAY_PRIVATE_DOMAIN` resolves over Railway's
IPv6-only private network; asyncpg connects over IPv6 without extra config.

## 2. Publish metadata

Click **Publish** in the composer and fill in:

- **Name:** `Telegram Bot Starter Kit (Python)`
- **Category:** `Bots`
- **Description (short):**
  > Production-ready Python Telegram bot: aiogram 3 webhooks, secret-token
  > validation, optional Postgres, healthcheck, JSON logs. No polling —
  > near-zero idle compute.
- **Tags:** `telegram`, `bot`, `python`, `aiogram`, `webhook`, `postgres`, `starter`
- **Overview / readme:** paste the top sections of `README.md` (the SEO title
  "Deploy and Host a Python Telegram Bot on Railway", Features, Quickstart,
  env table). Railway renders markdown.
- **Demo GIF/screenshot (optional but converts well):** a 10-second capture of
  `/start` → inline menu → Stats popup.

## 3. Smoke-test before (and after) publishing

Deploy your own template end-to-end with a throwaway token:

1. Deploy the template; paste the throwaway `TELEGRAM_BOT_TOKEN`.
2. Watch the `bot` deploy logs. Expect, in order:
   `starting server port=...` → `storage.open backend=postgres` →
   `webhook registered bot=@yourbot url=https://...up.railway.app/telegram/webhook`.
3. Healthcheck must pass (deployment goes green). Manually:
   `curl https://<domain>/healthz` → `{"status": "ok", "storage": "postgres"}`.
4. Security check: `curl -X POST https://<domain>/telegram/webhook -d '{}'`
   → **401** (no secret header). This must never return 200.
5. In Telegram: `/start` → greeting + inline menu; tap **Stats** → popup
   "1 user(s)"; `/help` → command list; send `hello` → `You said: hello`.
6. `curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"` →
   `url` matches the Railway domain, `last_error_message` empty,
   `pending_update_count` 0.
7. Persistence: redeploy the bot service, `/start` again, Stats still counts
   you (Postgres survived). Then delete `DATABASE_URL` from the bot service,
   redeploy, confirm logs show `backend=memory` and the bot still answers —
   this validates the "works without DB" path.
8. Delete the throwaway deployment so it doesn't bill you.

## 4. Kickback checklist (earn from deploys)

Railway's template marketplace pays template authors a kickback (15% of the
usage generated by your template, as credits or cash — see
https://railway.com/open-source-kickback). Before submitting:

- [ ] Template published from an account with payout details completed
- [ ] GitHub repo is public, README present at repo root (deployers see it)
- [ ] Template name/description accurately describe what deploys (review team checks)
- [ ] `TELEGRAM_BOT_TOKEN` marked required with clear BotFather instructions —
      broken first-run experiences get templates rejected
- [ ] Healthcheck passes on a fresh deploy (reviewers deploy your template)
- [ ] No hardcoded secrets anywhere in the repo (`git grep -iE "[0-9]{8,}:AA"` finds stray bot tokens)
- [ ] Optional Postgres documented as removable (README "Remove Postgres" section)
- [ ] Pinned dependency versions still install cleanly (`pip install -r app/requirements.txt`)

## 5. Maintenance

- Bump `aiogram`/`aiohttp`/`asyncpg` pins quarterly; re-run the smoke test.
- Republishing: composer templates update from the repo automatically for
  *new* deploys (existing deployers keep their fork).
- Watch the template's deploy stats on your Railway dashboard; failed-deploy
  spikes usually mean an upstream image or dependency broke.
