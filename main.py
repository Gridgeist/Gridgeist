import asyncio
import os

from src.client import BotClient


async def main():
    # 1. Instantiate the Client
    bot = BotClient()

    # 2. Start the Bot
    try:
        await bot.initialize()
        await bot.start(os.getenv("DISCORD_TOKEN"))
    except asyncio.CancelledError:
        pass
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        print("\n👋 Gridgeist has been powered down. See you next time!")
