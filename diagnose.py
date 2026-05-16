#!/usr/bin/env python3
"""Run this to diagnose bot setup issues: python diagnose.py"""
import asyncio
import aiohttp

TOKEN = "8693918015:AAF8E5rDdqMV62MEOh0nqcElTqVpoClqqt8"
CHAT_ID = "8186255974"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

async def main():
    async with aiohttp.ClientSession() as session:

        # 1. Test Telegram bot token
        print("1. Checking Telegram bot token...")
        async with session.get(f"https://api.telegram.org/bot{TOKEN}/getMe") as r:
            data = await r.json()
            if data.get("ok"):
                print(f"   OK — bot name: @{data['result']['username']}")
            else:
                print(f"   FAIL — {data}")
                return

        # 2. Test sending a message
        print("2. Sending test message to Telegram...")
        async with session.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": "✅ Bot diagnostic: Telegram is working!"}
        ) as r:
            data = await r.json()
            if data.get("ok"):
                print("   OK — message sent! Check your Telegram.")
            else:
                err = data.get("description", "")
                if "chat not found" in err or "blocked" in err:
                    print(f"   FAIL — Chat not found. Open Telegram, find your bot, send /start first.")
                else:
                    print(f"   FAIL — {err}")
                return

        # 3. Test Polymarket API
        print("3. Checking Polymarket API...")
        async with session.get(
            "https://data-api.polymarket.com/trades",
            params={"limit": 1},
            headers=HEADERS
        ) as r:
            if r.status == 200:
                print("   OK — Polymarket API reachable")
            else:
                print(f"   FAIL — status {r.status} (run bot locally, not in cloud)")
                return

        # 4. Resolve @rn1
        print("4. Resolving @rn1 username...")
        for url, params in [
            ("https://polymarket.com/api/profiles", {"username": "rn1"}),
            ("https://gamma-api.polymarket.com/users", {"username": "rn1"}),
        ]:
            async with session.get(url, params=params, headers=HEADERS) as r:
                if r.status == 200:
                    data = await r.json()
                    addr = None
                    if isinstance(data, dict):
                        addr = data.get("proxyWallet") or data.get("address")
                    elif isinstance(data, list) and data:
                        addr = data[0].get("proxyWallet") or data[0].get("address")
                    if addr:
                        print(f"   OK — @rn1 wallet: {addr}")
                        print(f"\n   Add to .env: WATCHED_WALLETS={addr}")
                        break
        else:
            print("   FAIL — Could not resolve @rn1.")
            print("   Go to https://polymarket.com/@rn1 → DevTools → Network → find proxyWallet")

asyncio.run(main())
