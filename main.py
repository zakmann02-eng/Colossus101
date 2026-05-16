#!/usr/bin/env python3
"""
Polymarket Wallet Watcher Bot
------------------------------
Tracks specified wallets and the global Polymarket trade feed,
sending Telegram alerts with copy-trade recommendations.

Usage:
  python main.py                    # Run the bot
  python main.py --lookup rn1       # Look up a username's wallet address
"""

import asyncio
import argparse
import logging
import sys

import aiohttp

from config import Config
from polymarket.client import PolymarketClient
from watchers.wallet_watcher import WalletWatcher
from watchers.discovery import TraderDiscovery
from telegram_bot.notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log"),
    ],
)
logger = logging.getLogger(__name__)


async def lookup_username(username: str):
    """CLI helper to resolve a Polymarket username to a wallet address."""
    async with aiohttp.ClientSession() as session:
        client = PolymarketClient(session)
        print(f"Looking up @{username}...")
        addr = await client.resolve_username(username)
        if addr:
            print(f"  Wallet address: {addr}")
            print(f"  Profile URL: https://polymarket.com/profile/{addr}")
            print(f"\nAdd to .env:")
            print(f"  WATCHED_WALLETS={addr}")
        else:
            print(f"  Could not resolve @{username}. Try adding the wallet address manually.")


async def run_bot(config: Config):
    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:
        client = PolymarketClient(session)
        notifier = TelegramNotifier(config.telegram_token, config.telegram_chat_id)

        # Resolve usernames -> wallet addresses
        for username in config.watched_usernames:
            logger.info("Resolving username @%s...", username)
            addr = await client.resolve_username(username)
            if addr and addr not in config.watched_wallets:
                config.watched_wallets.append(addr)
                logger.info("Resolved @%s -> %s", username, addr)
            elif not addr:
                logger.warning("Could not resolve @%s — skipping", username)

        if not config.watched_wallets:
            logger.error(
                "No wallets to watch. Set WATCHED_WALLETS or WATCHED_USERNAMES in your .env file."
            )
            return

        # Set up wallet watcher
        watcher = WalletWatcher(
            client,
            poll_interval=config.poll_interval,
            copy_min_win_rate=config.copy_min_win_rate,
            copy_min_volume=config.copy_min_volume,
        )
        watcher.set_alert_callback(notifier.send)

        for addr in config.watched_wallets:
            label = next(
                (u for u in config.watched_usernames
                 if hasattr(addr, '__contains__')),
                addr[:8]
            )
            await watcher.add_wallet(addr, label)

        # Set up trader discovery
        discovery = TraderDiscovery(
            client,
            poll_interval=config.discovery_poll_interval if hasattr(config, "discovery_poll_interval") else 300,
            feed_limit=config.discovery_feed_limit,
            min_trades=config.discovery_min_trades,
            min_win_rate=config.discovery_min_win_rate,
            min_roi=config.discovery_min_roi,
            ignored_addresses=set(config.watched_wallets),
        )
        discovery.set_alert_callback(notifier.send)

        # Build startup message with labels
        wallet_labels = []
        for addr in config.watched_wallets:
            label = next(
                (u for u in config.watched_usernames),
                addr[:8]
            )
            wallet_labels.append((addr, f"@{label}" if label in config.watched_usernames else label))

        await notifier.send_startup_message(wallet_labels)

        logger.info("Bot initialized. Starting tasks...")

        # Run all tasks concurrently
        await asyncio.gather(
            notifier.run_forever(),
            watcher.run_forever(),
            discovery.run_forever(),
        )


async def main():
    parser = argparse.ArgumentParser(description="Polymarket Wallet Watcher Bot")
    parser.add_argument("--lookup", metavar="USERNAME",
                        help="Look up a Polymarket username's wallet address")
    args = parser.parse_args()

    if args.lookup:
        await lookup_username(args.lookup)
        return

    try:
        config = Config.load()
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        print(f"\nError: {e}")
        print("Copy .env.example to .env and fill in your credentials.\n")
        sys.exit(1)

    logger.info("Starting Polymarket Wallet Watcher Bot...")
    await run_bot(config)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
