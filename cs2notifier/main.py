"""Orchestration: check for a new CS2 update, analyze it, notify, persist state."""
import time
from datetime import datetime, timezone

from .analyze import analyze
from .config import Config
from .notify import build_message, send_telegram
from .state import load_state, save_state
from .steam import bbcode_to_text, fetch_news, latest_update


def _fmt_date(unix_ts):
    try:
        return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, OSError, TypeError):
        return ""


def check(force=False, dry_run=False, cfg=None):
    """Run one check cycle. Returns an exit-style code (0 = ok)."""
    cfg = cfg or Config()

    items = fetch_news(cfg.app_id, cfg.max_news)
    update = latest_update(items)
    if not update:
        print("[main] No update-type news item found.")
        return 0

    gid = update.get("gid")
    state = load_state(cfg.state_file)
    if gid == state.get("last_gid") and not force:
        print(f"[main] No new update (latest gid {gid} already seen).")
        return 0

    update["clean_contents"] = bbcode_to_text(update.get("contents", ""))
    update["date_str"] = _fmt_date(update.get("date"))
    print(f"[main] New update detected: {update.get('title')} (gid {gid})")

    analysis = analyze(cfg, update)
    message = build_message(update, analysis)

    if dry_run or not cfg.telegram_enabled:
        if not cfg.telegram_enabled and not dry_run:
            print("[main] Telegram not configured — printing message instead:\n")
        print(message)
    else:
        if send_telegram(cfg.telegram_token, cfg.telegram_chat_id, message):
            print("[main] Telegram notification sent.")
        else:
            print("[main] Telegram send failed — not advancing state so we retry next run.")
            return 1

    # Persist only after a successful (or dry-run) delivery.
    if not dry_run:
        save_state(
            cfg.state_file,
            {
                "last_gid": gid,
                "last_title": update.get("title"),
                "last_update_date": update.get("date"),
                "last_checked": int(time.time()),
            },
        )
        print(f"[main] State saved (last_gid={gid}).")
    return 0
