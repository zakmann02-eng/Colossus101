import logging
from typing import Optional

from polymarket.models import Trade, TraderProfile

logger = logging.getLogger(__name__)

# Simple heuristic scoring for copy trade recommendations
SCORE_WIN_RATE_WEIGHT = 0.4
SCORE_ROI_WEIGHT = 0.3
SCORE_VOLUME_WEIGHT = 0.2
SCORE_TRADE_COUNT_WEIGHT = 0.1


def score_copy_trade(
    trade: Trade,
    trader_profile: TraderProfile,
    market_volume_usd: float = 0.0,
    copy_min_win_rate: float = 0.55,
    copy_min_volume: float = 10_000.0,
) -> tuple[float, str, list[str]]:
    """
    Returns (score 0-100, recommendation label, reasons list).
    Score > 70 => STRONG BUY, 50-70 => CONSIDER, <50 => SKIP
    """
    score = 0.0
    reasons: list[str] = []

    # Win rate component (0-40 pts)
    wr = trader_profile.win_rate
    wr_score = min(wr / 1.0, 1.0) * 40
    score += wr_score
    if wr >= copy_min_win_rate:
        reasons.append(f"Win rate {wr:.0%} meets threshold ({copy_min_win_rate:.0%})")
    else:
        reasons.append(f"Win rate {wr:.0%} below threshold ({copy_min_win_rate:.0%})")

    # ROI component (0-30 pts)
    roi = trader_profile.roi
    roi_normalized = min(max(roi, 0) / 100.0, 1.0)
    roi_score = roi_normalized * 30
    score += roi_score
    if roi > 0:
        reasons.append(f"Trader ROI: +{roi:.1f}%")
    else:
        reasons.append(f"Trader ROI: {roi:.1f}% (negative)")

    # Market volume component (0-20 pts)
    vol_score = min(market_volume_usd / 100_000.0, 1.0) * 20
    score += vol_score
    if market_volume_usd >= copy_min_volume:
        reasons.append(f"Market volume ${market_volume_usd:,.0f} is adequate")
    else:
        reasons.append(f"Market volume ${market_volume_usd:,.0f} is low — higher risk")

    # Trade count (experience) component (0-10 pts)
    tc_score = min(trader_profile.total_trades / 50.0, 1.0) * 10
    score += tc_score
    reasons.append(f"Trader has {trader_profile.total_trades} recorded trades")

    # Penalty: selling (closing) positions are less actionable
    if trade.side == "SELL":
        score *= 0.7
        reasons.append("Note: this is a SELL — trader may be closing position")

    # Penalty: very small trade size
    if trade.usd_value < 10:
        score *= 0.8
        reasons.append(f"Small trade size (${trade.usd_value:.2f}) — may be a test")

    score = round(min(score, 100), 1)

    if score >= 70:
        label = "STRONG BUY — high confidence copy"
    elif score >= 50:
        label = "CONSIDER — moderate confidence"
    else:
        label = "SKIP — low confidence"

    return score, label, reasons


def format_trade_alert(
    trade: Trade,
    trader_profile: TraderProfile,
    score: float,
    recommendation: str,
    reasons: list[str],
    market_url: Optional[str] = None,
) -> str:
    """Format a Telegram-ready trade alert message."""
    name = trader_profile.display_name or trader_profile.username or trader_profile.short_address()
    addr_link = f"[{trader_profile.short_address()}](https://polymarket.com/profile/{trader_profile.address})"

    side_emoji = "🟢" if trade.side == "BUY" else "🔴"
    rec_emoji = "🔥" if score >= 70 else ("⚡" if score >= 50 else "⚠️")

    lines = [
        f"{side_emoji} *New Trade Detected*",
        f"",
        f"👤 *Trader:* {name} ({addr_link})",
        f"📊 *Market:* {trade.market_question or trade.market_id}",
        f"",
        f"{'🟢 BUY' if trade.side == 'BUY' else '🔴 SELL'} *{trade.outcome}*",
        f"💰 Amount: *${trade.usd_value:,.2f}* ({trade.size:,.1f} shares @ {trade.price:.3f})",
        f"📈 Implied prob: *{trade.price * 100:.1f}%*",
        f"",
        f"— *Trader Stats* —",
        f"📉 Win Rate: *{trader_profile.win_rate:.0%}* ({trader_profile.winning_trades}/{trader_profile.total_trades} positions)",
        f"💵 ROI: *{trader_profile.roi:+.1f}%* (profit: ${trader_profile.profit:,.2f})",
        f"",
        f"{rec_emoji} *Recommendation: {recommendation}*",
        f"Score: {score}/100",
        f"",
        f"*Reasons:*",
    ]
    for r in reasons:
        lines.append(f"  • {r}")

    if market_url:
        lines.append(f"")
        lines.append(f"🔗 [View Market]({market_url})")

    return "\n".join(lines)


def format_discovery_alert(profile: TraderProfile) -> str:
    """Format a Telegram message for a newly discovered profitable trader."""
    name = profile.display_name or profile.username or profile.short_address()
    addr_link = f"[{profile.short_address()}](https://polymarket.com/profile/{profile.address})"

    lines = [
        f"🔍 *New Profitable Trader Discovered!*",
        f"",
        f"👤 *Trader:* {name} ({addr_link})",
        f"",
        f"📊 *Stats:*",
        f"  • Trades: {profile.total_trades}",
        f"  • Win Rate: *{profile.win_rate:.0%}*",
        f"  • ROI: *{profile.roi:+.1f}%*",
        f"  • Profit: *${profile.profit:,.2f}*",
        f"  • Total Invested: ${profile.total_invested:,.2f}",
        f"",
        f"💡 Consider adding this wallet to your watch list!",
        f"Address: `{profile.address}`",
    ]
    return "\n".join(lines)
