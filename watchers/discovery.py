import asyncio
import logging
from collections import defaultdict
from typing import Callable, Awaitable

from polymarket.client import PolymarketClient
from polymarket.models import TraderProfile
from polymarket.analyzer import format_discovery_alert

logger = logging.getLogger(__name__)


class TraderDiscovery:
    """
    Scans the global Polymarket trades feed and surfaces new traders
    with strong performance metrics (win rate, ROI, trade count).
    """

    def __init__(
        self,
        client: PolymarketClient,
        poll_interval: int = 300,          # check every 5 minutes
        feed_limit: int = 500,
        min_trades: int = 10,
        min_win_rate: float = 0.60,
        min_roi: float = 15.0,
        ignored_addresses: set[str] | None = None,
    ):
        self.client = client
        self.poll_interval = poll_interval
        self.feed_limit = feed_limit
        self.min_trades = min_trades
        self.min_win_rate = min_win_rate
        self.min_roi = min_roi
        self._ignored: set[str] = ignored_addresses or set()
        self._alerted: set[str] = set()
        self._alert_callback: Callable[[str], Awaitable[None]] | None = None

    def set_alert_callback(self, cb: Callable[[str], Awaitable[None]]):
        self._alert_callback = cb

    def ignore_address(self, address: str):
        self._ignored.add(address.lower())

    async def _send_alert(self, message: str):
        if self._alert_callback:
            await self._alert_callback(message)
        else:
            logger.info("DISCOVERY ALERT:\n%s", message)

    async def _scan_feed(self):
        trades = await self.client.get_global_trades(limit=self.feed_limit)
        if not trades:
            logger.warning("Global trade feed returned no results")
            return

        # Group trades by trader address for quick pre-filtering
        by_trader: dict[str, list] = defaultdict(list)
        for t in trades:
            by_trader[t.trader_address].append(t)

        candidates = [
            addr for addr, t_list in by_trader.items()
            if len(t_list) >= max(3, self.min_trades // 5)   # at least some activity in feed
            and addr not in self._ignored
            and addr not in self._alerted
        ]

        logger.info("Discovery: %d traders in feed, %d candidates to profile",
                    len(by_trader), len(candidates))

        for addr in candidates:
            try:
                profile = await self.client.build_trader_profile(addr, trade_limit=200)
                if self._meets_criteria(profile):
                    self._alerted.add(addr)
                    message = format_discovery_alert(profile)
                    await self._send_alert(message)
                    logger.info("Discovered profitable trader %s (win_rate=%.0f%%, roi=%.1f%%)",
                                addr, profile.win_rate * 100, profile.roi)
            except Exception as e:
                logger.error("Error profiling trader %s: %s", addr, e)

    def _meets_criteria(self, profile: TraderProfile) -> bool:
        return (
            profile.total_trades >= self.min_trades
            and profile.win_rate >= self.min_win_rate
            and profile.roi >= self.min_roi
        )

    async def run_forever(self):
        logger.info("TraderDiscovery started. Scanning every %ds.", self.poll_interval)
        # Wait a bit before first scan to let wallet watcher initialize
        await asyncio.sleep(15)
        while True:
            try:
                await self._scan_feed()
            except Exception as e:
                logger.error("Discovery scan error: %s", e)
            await asyncio.sleep(self.poll_interval)
