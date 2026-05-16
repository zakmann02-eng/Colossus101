# Polymarket Wallet Watcher Bot

A local bot that watches Polymarket wallets, sends Telegram alerts for new trades, and surfaces profitable new traders from the global feed — with copy-trade recommendations.

## Features

- **Wallet Watching** — monitors any number of Polymarket wallets for new trades in real time
- **Telegram Alerts** — sends formatted alerts with trade details (market, outcome, price, USD value)
- **Copy-Trade Scoring** — rates each trade 0–100 with a STRONG BUY / CONSIDER / SKIP recommendation based on the trader's win rate, ROI, and market volume
- **Trader Discovery** — scans the global Polymarket trade feed and alerts you when a new trader with strong metrics appears (configurable win rate + ROI thresholds)
- **Username Lookup** — resolve `@username` handles to wallet addresses automatically

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token (from @BotFather) |
| `TELEGRAM_CHAT_ID` | Your Telegram chat/user ID (send `/start` to @userinfobot to get it) |
| `WATCHED_USERNAMES` | Comma-separated Polymarket usernames, e.g. `rn1` |
| `WATCHED_WALLETS` | Comma-separated wallet addresses (optional if using usernames) |
| `POLL_INTERVAL` | How often (seconds) to check for new trades (default: 30) |

### 3. Look up a wallet address (optional)

```bash
python main.py --lookup rn1
```

This prints the wallet address for `@rn1` so you can add it to `.env`.

### 4. Run the bot

```bash
python main.py
```

Leave it running. The bot will:
- Immediately send a startup message to your Telegram with the watched wallets
- Poll every `POLL_INTERVAL` seconds for new trades from each wallet
- Scan the global feed every 5 minutes for new profitable traders

## Telegram Alert Examples

**Trade alert:**
```
🟢 New Trade Detected

👤 Trader: @rn1 (0x1234...5678)
📊 Market: Will X happen before Y?

🟢 BUY Yes
💰 Amount: $250.00 (500.0 shares @ 0.500)
📈 Implied prob: 50.0%

— Trader Stats —
📉 Win Rate: 67% (12/18 positions)
💵 ROI: +42.3% (profit: $1,234.56)

🔥 Recommendation: STRONG BUY — high confidence copy
Score: 74.5/100
```

**Discovery alert:**
```
🔍 New Profitable Trader Discovered!

👤 Trader: 0xabcd...ef01
📊 Stats:
  • Trades: 25
  • Win Rate: 72%
  • ROI: +89.4%
  • Profit: $4,200.00
```

## Configuration Reference

All settings are in `.env`:

| Variable | Default | Description |
|---|---|---|
| `POLL_INTERVAL` | 30 | Wallet polling interval (seconds) |
| `DISCOVERY_MIN_TRADES` | 10 | Min trades for discovery |
| `DISCOVERY_MIN_WIN_RATE` | 0.60 | Min win rate for discovery (0–1) |
| `DISCOVERY_MIN_ROI` | 15.0 | Min ROI % for discovery |
| `DISCOVERY_FEED_LIMIT` | 500 | How many recent trades to scan |
| `COPY_TRADE_MIN_WIN_RATE` | 0.55 | Min trader win rate to recommend copying |
| `COPY_TRADE_MIN_VOLUME` | 10000 | Min market volume ($) to recommend |

## Adding More Wallets

Add addresses or usernames to `.env`:

```
WATCHED_USERNAMES=rn1,another_user
WATCHED_WALLETS=0xABCD...,0xEFGH...
```

Restart the bot to pick up the new wallets.

## Logs

The bot logs to both stdout and `bot.log` in the project directory.
