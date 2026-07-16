import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot_atul.config import Config
from bot_atul.db.connection import connect
from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.telegram.handlers.admin import build_admin_router
from bot_atul.telegram.handlers.intake import build_intake_router
from bot_atul.telegram.handlers.relay import build_relay_router


async def run() -> None:
    config = Config.from_env()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.backup_dir.mkdir(parents=True, exist_ok=True)

    connection = connect(config.data_dir / "bot.db")
    migrate(connection)
    repository = Repository(connection)
    for admin_id in config.admin_ids:
        repository.upsert_user(admin_id, "admin")

    bot = Bot(config.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(build_admin_router(repository))
    dispatcher.include_router(build_intake_router(repository, config.team_group_id))
    dispatcher.include_router(build_relay_router(repository, config.team_group_id))
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        connection.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
