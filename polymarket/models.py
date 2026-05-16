from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Trade:
    id: str
    trader_address: str
    market_id: str
    market_question: str
    outcome: str          # "Yes" or "No"
    side: str             # "BUY" or "SELL"
    size: float           # shares
    price: float          # price per share (0-1)
    usd_value: float      # total USD value
    timestamp: datetime
    transaction_hash: str

    @property
    def outcome_label(self) -> str:
        return f"{self.outcome} @ {self.price:.3f} ({self.price * 100:.1f}¢)"

    @property
    def implied_probability(self) -> float:
        return self.price


@dataclass
class Position:
    trader_address: str
    market_id: str
    market_question: str
    outcome: str
    size: float
    average_price: float
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


@dataclass
class TraderProfile:
    address: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    total_trades: int = 0
    winning_trades: int = 0
    total_invested: float = 0.0
    total_returned: float = 0.0
    trades: list = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    @property
    def roi(self) -> float:
        if self.total_invested == 0:
            return 0.0
        return ((self.total_returned - self.total_invested) / self.total_invested) * 100

    @property
    def profit(self) -> float:
        return self.total_returned - self.total_invested

    def short_address(self) -> str:
        return f"{self.address[:6]}...{self.address[-4:]}"
