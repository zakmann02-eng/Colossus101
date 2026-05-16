import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Awaitable

from polymarket.client import PolymarketClient
from polymarket.models import Trade, TraderProfile
from polymarket.analyzer import score_copy_trade, format_trade_alert

logger = logging.getLogger(__name__)


class WalletWatcher:
    """Polls Polymarket for new trades from a set of watched wallet addresses."""

    def __init__(
        self,
        client: PolymarketClient,
        poll_interval: int = 30,
        copy_min_win_rate: float = 0.55,
        copy_min_volume: float = 10_000.0,
    ):
        self.client = client
        self.poll_interval = poll_interval
        self.copy_min_win_rate = copy_min_win_rate
        self.copy_min_volume = copy_min_volume

        # address -> set of seen trade IDs
        self._seen_trade_ids: dict[str, set[str]] = {}
        # address -> TraderProfile cache
        self._profiles: dict[str, TraderProfile] = {}
        # address -> set of usernames/labels
        self._labels: dict[str, str] = {}
        # callback: async fn(message: str) -> None
        self._alert_callback: Callable[[str], Awaitable[None]] | None = None

    def set_alert_callback(self, cb: Callable[[str], Awaitable[None]]):
        self._alert_callback = cb

    async def add_wallet(self, address: str, label: str = ""):
        address = address.lower()
        self._labels[address] = label or address[:8]
        if address not in self._seen_trade_ids:
            self._seen_trade_ids[address] = set()
            # Seed with current trades so we don't alert on old activity
            trades = await self.client.get_trades(address, limit=50)
            for t in trades:
                self._seen_trade_ids[address].add(t.id)
            logger.info("Watching wallet %s (%s) — seeded %d existing trades",
                        address, self._labels[address], len(trades))

    async def refresh_profile(self, address: str):
        profile = await self.client.build_trader_profile(address)
        self._profiles[address] = profile
        return profile

    async def _send_alert(self, message: str):
        if self._alert_callback:
            await self._alert_callback(message)
        else:
            logger.info("ALERT (no callback):\n%s", message)

    async def _check_wallet(self, address: str):
        trades = await self.client.get_trades(address, limit=50)
        if not trades:
            return

        new_trades = [t for t in trades if t.id not in self._seen_trade_ids[address]]
        if not new_trades:
            return

        for t in sorted(new_trades, key=lambda x: x.timestamp):
            self._seen_trade_ids[address].add(t.id)

        # Refresh profile every time there are new trades
        profile = await self.refresh_profile(address)

        for trade in new_trades:
            market_info = await self.client.get_market(trade.market_id)
            market_volume = 0.0
            market_url = None
            if market_info:
                market_volume = float(market_info.get("volume") or market_info.get("volumeNum") or 0)
                slug = market_info.get("slug") or market_info.get("marketSlug")
                if slug:
                    market_url = f"https://polymarket.com/event/{slug}"

            score, recommendation, reasons = score_copy_trade(
                trade, profile, market_volume,
                self.copy_min_win_rate, self.copy_min_volume
            )
            message = format_trade_alert(trade, profile, score, recommendation, reasons, market_url)
            await self._send_alert(message)
            logger.info("Alerted on new trade %s from %s (score=%s)", trade.id, address, score)

    async def run_forever(self):
        """Main polling loop."""
        logger.info("WalletWatcher started. Polling every %ds for %d wallets.",
                    self.poll_interval, len(self._seen_trade_ids))
        while True:
            for address in list(self._seen_trade_ids.keys()):
                try:
                    await self._check_wallet(address)
                except Exception as e:
                    logger.error("Error checking wallet %s: %s", address, e)
            await asyncio.sleep(self.poll_interval)
