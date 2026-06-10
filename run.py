#!/usr/bin/env python3
"""CS2 Update Notifier — entry point.

Usage:
  python run.py                 Check for a new update; notify via Telegram if found.
  python run.py --force         Re-process the latest update even if already seen.
  python run.py --dry-run       Print the message instead of sending (also implies --force).
  python run.py --get-chat-id   List Telegram chat ids that have messaged your bot.
  python run.py --test-telegram Send a test message to confirm Telegram is wired up.
  python run.py --check-config  Show which features are enabled.
"""
import argparse
import sys

# Ensure emoji/unicode print correctly on Windows consoles (cp1252 default).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from cs2notifier.config import Config
from cs2notifier.main import check
from cs2notifier.notify import get_chat_ids, send_telegram


def main():
    parser = argparse.ArgumentParser(description="CS2 update notifier with price-impact analysis.")
    parser.add_argument("--force", action="store_true", help="Process latest update even if seen.")
    parser.add_argument("--dry-run", action="store_true", help="Print message, do not send (implies --force).")
    parser.add_argument("--get-chat-id", action="store_true", help="List chat ids that messaged the bot.")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test Telegram message.")
    parser.add_argument("--check-config", action="store_true", help="Show enabled features and exit.")
    args = parser.parse_args()

    cfg = Config()

    if args.check_config:
        print("CS2 Update Notifier — configuration")
        print(f"  Steam app id      : {cfg.app_id}")
        print(f"  Telegram enabled  : {cfg.telegram_enabled}")
        print(f"  Claude AI enabled : {cfg.claude_enabled} (model: {cfg.anthropic_model})")
        print(f"  Live price lookups: {cfg.fetch_prices}")
        print(f"  State file        : {cfg.state_file}")
        return 0

    if args.get_chat_id:
        if not cfg.telegram_token:
            print("Set TELEGRAM_BOT_TOKEN first (in .env or environment).")
            return 1
        chats = get_chat_ids(cfg.telegram_token)
        if not chats:
            print("No chats found. Open Telegram, send any message to your bot, then re-run.")
            return 1
        print("Chats that have messaged your bot:")
        for cid, name in chats:
            print(f"  chat_id={cid}   {name}")
        return 0

    if args.test_telegram:
        if not cfg.telegram_enabled:
            print("Telegram not configured (need TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID).")
            return 1
        ok = send_telegram(
            cfg.telegram_token,
            cfg.telegram_chat_id,
            "✅ <b>CS2 Update Notifier</b>\nTest message — your bot is wired up correctly.",
        )
        print("Sent." if ok else "Failed — check token/chat id.")
        return 0 if ok else 1

    return check(force=args.force or args.dry_run, dry_run=args.dry_run, cfg=cfg)


if __name__ == "__main__":
    sys.exit(main())
