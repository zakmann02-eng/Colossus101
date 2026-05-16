import logging
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str | int):
        self.bot = Bot(token=token)
        self.chat_id = str(chat_id)
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def send(self, message: str):
        """Queue a message for sending."""
        await self._queue.put(message)

    async def _send_now(self, message: str):
        try:
            # Telegram has a 4096 char limit per message
            for chunk in self._split_message(message):
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=chunk,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(0.3)
        except TelegramError as e:
            logger.error("Telegram send error: %s", e)
            # Retry without markdown if parsing fails
            try:
                plain = message.replace("*", "").replace("`", "").replace("[", "").replace("]", "")
                for chunk in self._split_message(plain):
                    await self.bot.send_message(chat_id=self.chat_id, text=chunk)
            except TelegramError as e2:
                logger.error("Telegram retry also failed: %s", e2)

    def _split_message(self, message: str, limit: int = 4000) -> list[str]:
        if len(message) <= limit:
            return [message]
        chunks = []
        while len(message) > limit:
            split_at = message.rfind("\n", 0, limit)
            if split_at == -1:
                split_at = limit
            chunks.append(message[:split_at])
            message = message[split_at:].lstrip("\n")
        if message:
            chunks.append(message)
        return chunks

    async def run_forever(self):
        """Drain the send queue continuously."""
        logger.info("TelegramNotifier queue processor started.")
        while True:
            message = await self._queue.get()
            await self._send_now(message)
            self._queue.task_done()

    async def send_startup_message(self, watched_wallets: list[tuple[str, str]]):
        lines = [
            "🚀 *Polymarket Wallet Watcher Bot Started*",
            "",
            f"👀 *Watching {len(watched_wallets)} wallet(s):*",
        ]
        for addr, label in watched_wallets:
            lines.append(f"  • [{label}](https://polymarket.com/profile/{addr}) `{addr}`")
        lines += [
            "",
            "🔍 Trader discovery scanner active",
            "📡 Polling for new trades...",
        ]
        await self.send("\n".join(lines))
