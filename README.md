# CS2 Update Notifier 🔫📈

Get a **Telegram notification on your phone the moment Counter-Strike 2 ships an
update** — with the patch title, the full patch notes, and an **analysis of how the
update is likely to move item prices** (which cases/skins/stickers should rise, which
should drop, and why).

- **Free to run 24/7** on GitHub Actions (no server, no cost).
- **Telegram** push notifications to your phone.
- **Price-impact analysis** in two layers:
  - **Heuristics** — free, rule-based (new case, drop-pool rotation, discontinued items,
    operations, tournament stickers/souvenirs, …). Always on.
  - **Claude AI** — optional, richer reasoning. Only runs if you provide an API key.
- Pulls **live Steam Market prices** for cases mentioned in the patch.

---

## How it works

```
Steam News API (appid 730)  ──►  detect "patchnotes"  ──►  new since last run?
        │                                                        │ yes
        ▼                                                        ▼
   clean BBCode  ───────────────────────────────►  price-impact analysis
                                                     (heuristics + optional Claude)
                                                              │
                                                              ▼
                                                    Telegram message to your phone
                                                              │
                                                              ▼
                                            save last-seen update id (state.json)
```

A real game patch is identified by the `patchnotes` tag on the Steam news item, so you
won't get pinged for blog posts or esports announcements.

---

## 1. Create your Telegram bot (2 minutes)

1. In Telegram, open **@BotFather** → send `/newbot` → follow prompts.
2. Copy the **bot token** it gives you (looks like `123456:ABC-DEF...`).
3. **Send any message to your new bot** (e.g. "hi") so it can see your chat.
4. Get your chat id:
   ```bash
   python run.py --get-chat-id
   ```
   Copy the `chat_id` it prints.

> Want notifications in a group? Add the bot to the group, post a message there, then
> run `--get-chat-id` and use the (negative) group chat id.

---

## 2. Run it free on GitHub Actions (recommended)

1. Push this folder to a **GitHub repository** (a private repo is fine).
2. In the repo: **Settings → Secrets and variables → Actions → New repository secret**,
   add:
   | Secret | Value | Required |
   |---|---|---|
   | `TELEGRAM_BOT_TOKEN` | your bot token | ✅ |
   | `TELEGRAM_CHAT_ID` | your chat id | ✅ |
   | `ANTHROPIC_API_KEY` | Claude API key | optional (for AI analysis) |
3. That's it. The workflow in [.github/workflows/check.yml](.github/workflows/check.yml)
   runs **every ~15 minutes**, and the first run will likely notify you about the most
   recent update. Trigger it manually anytime from the **Actions** tab → *CS2 Update
   Notifier* → *Run workflow*.

**State** (the last update already sent) is stored in `state.json`, which the workflow
commits back to the repo so you never get duplicate notifications. Those commits also
keep the scheduled workflow from being auto-disabled for inactivity.

> GitHub Actions is free for public repos and includes a generous monthly minute
> allowance for private repos — this job uses well under a minute per run.

---

## 3. Run locally (optional)

Requires Python 3.10+.

```bash
pip install -r requirements.txt
cp .env.example .env          # then edit .env with your token + chat id
python run.py --check-config  # confirm what's enabled
python run.py --test-telegram # confirm Telegram works
python run.py --dry-run       # analyze the latest update and PRINT the message
python run.py                 # real run: notify if there's a new update
```

### Schedule it on Windows (Task Scheduler)
Create a Basic Task → trigger *Daily*, repeat *every 15 minutes* → action *Start a
program*:
- Program: `python`
- Arguments: `run.py`
- Start in: `d:\Projects\cs2-updates-notifier`

(Only catches updates while your PC is on — that's why GitHub Actions is recommended.)

---

## 4. Add Claude AI analysis (optional)

Set `ANTHROPIC_API_KEY` (locally in `.env`, or as a GitHub secret). The default model is
`claude-sonnet-4-6` (good reasoning, very cheap per update — typically a fraction of a
cent). Override with `ANTHROPIC_MODEL` if you like. Without a key, the tool runs the free
heuristics only — everything still works.

---

## CLI reference

| Command | What it does |
|---|---|
| `python run.py` | Check for a new update; notify if found. |
| `python run.py --force` | Re-process the latest update even if already seen. |
| `python run.py --dry-run` | Analyze latest update and print the message (don't send). |
| `python run.py --get-chat-id` | List chat ids that have messaged your bot. |
| `python run.py --test-telegram` | Send a test message. |
| `python run.py --check-config` | Show which features are enabled. |

## Configuration (env vars / `.env`)

| Var | Default | Purpose |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | – | Bot token from @BotFather (required). |
| `TELEGRAM_CHAT_ID` | – | Where to send messages (required). |
| `ANTHROPIC_API_KEY` | – | Enables Claude AI analysis (optional). |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Model for AI analysis. |
| `STEAM_APP_ID` | `730` | CS2's Steam app id. |
| `FETCH_PRICES` | `true` | Look up live Steam Market prices for mentioned cases. |
| `CURRENCY` | `1` | Steam currency code (1 = USD, 3 = EUR, …). |
| `MAX_NEWS` | `10` | How many recent news items to scan. |
| `STATE_FILE` | `state.json` | Where the last-seen update id is stored. |

---

## Notes & limitations

- **Detection** relies on Steam's official news feed `patchnotes` tag — the same source
  as the in-game update notes.
- **Price predictions are directional heuristics/AI opinion, not financial advice.** CS2
  item prices depend on supply, drop-pool rotation, scarcity and demand; this tool flags
  *likely* direction and reasoning, not guaranteed outcomes.
- Live price lookups use the unofficial Steam Market endpoint and are best-effort
  (skipped silently if rate-limited).
