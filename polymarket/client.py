import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone

import aiohttp

from polymarket.models import Trade, Position, TraderProfile

logger = logging.getLogger(__name__)

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
POLYMARKET_API = "https://polymarket.com/api"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class PolymarketClient:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def _get(self, url: str, params: dict = None) -> Optional[dict | list]:
        try:
            async with self.session.get(url, params=params, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning("GET %s returned %s", url, resp.status)
                return None
        except Exception as e:
            logger.error("Request failed for %s: %s", url, e)
            return None

    async def resolve_username(self, username: str) -> Optional[str]:
        """Resolve a Polymarket username/slug to a wallet address."""
        # Try the profile endpoint
        data = await self._get(f"{POLYMARKET_API}/profiles", {"username": username})
        if data and isinstance(data, dict) and data.get("proxyWallet"):
            return data["proxyWallet"].lower()

        # Try gamma API
        data = await self._get(f"{GAMMA_API}/users", {"username": username})
        if data and isinstance(data, list) and len(data) > 0:
            user = data[0]
            addr = user.get("proxyWallet") or user.get("address")
            if addr:
                return addr.lower()

        # Try direct profile slug lookup
        data = await self._get(f"{POLYMARKET_API}/profile/{username}")
        if data and isinstance(data, dict):
            addr = data.get("proxyWallet") or data.get("address")
            if addr:
                return addr.lower()

        logger.warning("Could not resolve username '%s' to a wallet address", username)
        return None

    async def get_profile(self, address: str) -> Optional[dict]:
        """Fetch basic profile info for a wallet address."""
        data = await self._get(f"{POLYMARKET_API}/profiles", {"id": address})
        if data and isinstance(data, dict):
            return data
        return None

    async def get_trades(self, user: str, limit: int = 50, offset: int = 0) -> list[Trade]:
        """Fetch recent trades for a wallet address."""
        data = await self._get(f"{DATA_API}/trades", {
            "user": user,
            "limit": limit,
            "offset": offset,
        })
        if not data or not isinstance(data, list):
            return []
        return [self._parse_trade(t, user) for t in data if t]

    async def get_global_trades(self, limit: int = 500) -> list[Trade]:
        """Fetch recent trades from the global feed (all users)."""
        data = await self._get(f"{DATA_API}/trades", {"limit": limit})
        if not data or not isinstance(data, list):
            return []
        return [self._parse_trade(t, t.get("maker", "")) for t in data if t]

    async def get_positions(self, user: str) -> list[Position]:
        """Fetch open positions for a wallet address."""
        data = await self._get(f"{DATA_API}/positions", {"user": user, "sizeThreshold": "0.01"})
        if not data or not isinstance(data, list):
            return []
        return [self._parse_position(p, user) for p in data if p]

    async def get_market(self, market_id: str) -> Optional[dict]:
        """Fetch market details including volume."""
        data = await self._get(f"{GAMMA_API}/markets/{market_id}")
        if data and isinstance(data, dict):
            return data
        return None

    def _parse_trade(self, raw: dict, default_user: str) -> Trade:
        trader = raw.get("maker") or raw.get("trader") or default_user
        ts_raw = raw.get("timestamp") or raw.get("createdAt") or 0
        if isinstance(ts_raw, (int, float)):
            ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
        else:
            try:
                ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            except Exception:
                ts = datetime.now(tz=timezone.utc)

        size = float(raw.get("size") or raw.get("shares") or 0)
        price = float(raw.get("price") or 0)
        usd = float(raw.get("amount") or raw.get("usdcSize") or (size * price))

        return Trade(
            id=str(raw.get("id") or raw.get("transactionHash") or ""),
            trader_address=str(trader).lower(),
            market_id=str(raw.get("market") or raw.get("conditionId") or ""),
            market_question=str(raw.get("title") or raw.get("question") or raw.get("market", "")),
            outcome=str(raw.get("outcome") or raw.get("side") or ""),
            side=str(raw.get("type") or raw.get("tradeType") or "BUY").upper(),
            size=size,
            price=price,
            usd_value=usd,
            timestamp=ts,
            transaction_hash=str(raw.get("transactionHash") or raw.get("txHash") or ""),
        )

    def _parse_position(self, raw: dict, user: str) -> Position:
        size = float(raw.get("size") or raw.get("shares") or 0)
        avg_price = float(raw.get("avgPrice") or raw.get("averagePrice") or 0)
        current_value = float(raw.get("currentValue") or raw.get("value") or (size * avg_price))
        cost_basis = float(raw.get("costBasis") or (size * avg_price))
        pnl = current_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0

        return Position(
            trader_address=user.lower(),
            market_id=str(raw.get("market") or raw.get("conditionId") or ""),
            market_question=str(raw.get("title") or raw.get("question") or ""),
            outcome=str(raw.get("outcome") or ""),
            size=size,
            average_price=avg_price,
            current_value=current_value,
            unrealized_pnl=pnl,
            unrealized_pnl_pct=pnl_pct,
        )

    async def build_trader_profile(self, address: str, trade_limit: int = 200) -> TraderProfile:
        """Build a TraderProfile with win rate / ROI from trade history."""
        profile = TraderProfile(address=address)

        user_info = await self.get_profile(address)
        if user_info:
            profile.username = user_info.get("username")
            profile.display_name = user_info.get("name") or user_info.get("displayName")

        trades = await self.get_trades(address, limit=trade_limit)
        profile.trades = trades
        profile.total_trades = len(trades)

        # Group buys and sells per market+outcome to compute P&L
        positions: dict[str, dict] = {}
        for t in sorted(trades, key=lambda x: x.timestamp):
            key = f"{t.market_id}:{t.outcome}"
            if key not in positions:
                positions[key] = {"invested": 0.0, "shares": 0.0, "returned": 0.0}
            if t.side == "BUY":
                positions[key]["invested"] += t.usd_value
                positions[key]["shares"] += t.size
            else:
                positions[key]["returned"] += t.usd_value
                positions[key]["shares"] -= t.size

        total_invested = 0.0
        total_returned = 0.0
        winning = 0

        for key, pos in positions.items():
            inv = pos["invested"]
            ret = pos["returned"]
            total_invested += inv
            total_returned += ret
            if ret > inv:
                winning += 1

        profile.total_invested = total_invested
        profile.total_returned = total_returned
        profile.winning_trades = winning

        return profile
