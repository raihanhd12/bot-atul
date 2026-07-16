import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot_atul.config import Config


async def run() -> None:
    config = Config.from_env()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.backup_dir.mkdir(parents=True, exist_ok=True)

    bot = Bot(config.bot_token)
    try:
        await Dispatcher().start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
