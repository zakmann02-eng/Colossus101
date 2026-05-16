import os
from dotenv import load_dotenv

load_dotenv()


def require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise ValueError(f"Required environment variable '{key}' is not set. Check your .env file.")
    return val


def optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


class Config:
    # Telegram
    telegram_token: str = ""
    telegram_chat_id: str = ""

    # Wallets to watch
    watched_wallets: list[str] = []
    watched_usernames: list[str] = []

    # Polling
    poll_interval: int = 30

    # Discovery
    discovery_min_trades: int = 10
    discovery_min_win_rate: float = 0.60
    discovery_min_roi: float = 15.0
    discovery_feed_limit: int = 500
    discovery_poll_interval: int = 300

    # Copy trade thresholds
    copy_min_win_rate: float = 0.55
    copy_min_volume: float = 10_000.0

    @classmethod
    def load(cls) -> "Config":
        c = cls()
        c.telegram_token = require("TELEGRAM_BOT_TOKEN")
        c.telegram_chat_id = require("TELEGRAM_CHAT_ID")

        wallets_raw = optional("WATCHED_WALLETS", "")
        c.watched_wallets = [w.strip().lower() for w in wallets_raw.split(",") if w.strip()]

        usernames_raw = optional("WATCHED_USERNAMES", "")
        c.watched_usernames = [u.strip() for u in usernames_raw.split(",") if u.strip()]

        c.poll_interval = int(optional("POLL_INTERVAL", "30"))
        c.discovery_min_trades = int(optional("DISCOVERY_MIN_TRADES", "10"))
        c.discovery_min_win_rate = float(optional("DISCOVERY_MIN_WIN_RATE", "0.60"))
        c.discovery_min_roi = float(optional("DISCOVERY_MIN_ROI", "15.0"))
        c.discovery_feed_limit = int(optional("DISCOVERY_FEED_LIMIT", "500"))
        c.copy_min_win_rate = float(optional("COPY_TRADE_MIN_WIN_RATE", "0.55"))
        c.copy_min_volume = float(optional("COPY_TRADE_MIN_VOLUME", "10000"))

        return c
