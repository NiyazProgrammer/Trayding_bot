
import asyncio
from utils.logging_setup import setup_logger
logger = setup_logger()
from View.UI.telegram_bot import TelegramTradingBot
from config import TelegramConfig

def main():
    if not TelegramConfig.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    logger.info("🤖 WAVEX Telegram Bot starting...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot = TelegramTradingBot(
        token=TelegramConfig.BOT_TOKEN,
        loop=loop,
    )

    bot.run()


if __name__ == "__main__":
    main()