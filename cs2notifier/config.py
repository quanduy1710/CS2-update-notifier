"""Runtime configuration, read from environment variables.

A .env file in the working directory is loaded automatically if present, so the
same code works for local runs and for CI (where vars come from secrets).
"""
import os


def _load_dotenv(path=".env"):
    """Minimal .env loader (no external dependency)."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            # Don't override anything already set in the real environment.
            os.environ.setdefault(key, val)


class Config:
    def __init__(self):
        _load_dotenv()
        self.app_id = os.environ.get("STEAM_APP_ID", "730")
        self.telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self.anthropic_model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()
        self.state_file = os.environ.get("STATE_FILE", "state.json")
        self.fetch_prices = os.environ.get("FETCH_PRICES", "true").lower() in ("1", "true", "yes", "on")
        self.currency = os.environ.get("CURRENCY", "1")
        try:
            self.max_news = int(os.environ.get("MAX_NEWS", "10"))
        except ValueError:
            self.max_news = 10

    @property
    def telegram_enabled(self):
        return bool(self.telegram_token and self.telegram_chat_id)

    @property
    def claude_enabled(self):
        return bool(self.anthropic_key)
