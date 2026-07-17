import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError

from bot_atul.config import Config
from bot_atul.db.connection import connect
from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.services.dashboard import next_dashboard_run, safe_publish_dashboard
from bot_atul.services.reminders import next_reminder_run, safe_send_reminder
from bot_atul.telegram.commands import register_commands
from bot_atul.telegram.handlers.admin import build_admin_router
from bot_atul.telegram.handlers.dashboard import build_dashboard_router
from bot_atul.telegram.handlers.intake import build_intake_router
from bot_atul.telegram.handlers.menu import build_menu_router
from bot_atul.telegram.handlers.relay import build_relay_router
from bot_atul.telegram.handlers.tickets import build_ticket_router

LOGGER = logging.getLogger(__name__)


async def dashboard_loop(bot: Bot, repository: Repository, config: Config) -> None:
    while True:
        now = datetime.now(config.timezone)
        run_at = next_dashboard_run(now, config.timezone)
        await asyncio.sleep((run_at - now).total_seconds())
        await safe_publish_dashboard(
            bot,
            repository,
            config.team_group_id,
            config.dashboard_topic_id,
            run_at,
        )


async def reminder_loop(bot: Bot, repository: Repository, config: Config) -> None:
    while True:
        now = datetime.now(config.timezone)
        run_at = next_reminder_run(now, config.timezone, config.reminder_time)
        await asyncio.sleep((run_at - now).total_seconds())
        await safe_send_reminder(
            bot,
            repository,
            config.team_group_id,
            config.dashboard_topic_id,
        )


async def close_issues_topic(bot: Bot, team_group_id: int, topic_id: int) -> None:
    """Keep the issues topic view-only for members.

    Closed forum topics allow only admins (and the bot) to post. Members can
    still read cards and press buttons, but cannot send free-form messages.
    """
    try:
        await bot.close_forum_topic(
            chat_id=team_group_id,
            message_thread_id=topic_id,
        )
        LOGGER.info("Issues topic %s closed for member posts", topic_id)
    except TelegramAPIError as error:
        # Already closed from a previous boot — not an error.
        if "topic_not_modified" in str(error).lower():
            LOGGER.info("Issues topic %s already closed", topic_id)
            return
        LOGGER.exception(
            "Could not close issues topic %s. Give the bot Manage Topics and "
            "close the topic manually in Telegram if needed.",
            topic_id,
        )


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
    dispatcher.include_router(build_menu_router(repository, config.reminder_time))
    dispatcher.include_router(build_admin_router(repository))
    dispatcher.include_router(
        build_intake_router(
            repository,
            config.team_group_id,
            config.dashboard_topic_id,
            config.timezone,
        )
    )
    dispatcher.include_router(build_relay_router(repository, config.team_group_id))
    dispatcher.include_router(
        build_ticket_router(
            repository,
            config.team_group_id,
            config.dashboard_topic_id,
            config.timezone,
        )
    )
    dispatcher.include_router(
        build_dashboard_router(
            repository,
            config.team_group_id,
            config.dashboard_topic_id,
            config.timezone,
            config.data_dir,
        )
    )
    dashboard_task = asyncio.create_task(dashboard_loop(bot, repository, config))
    reminder_task = asyncio.create_task(reminder_loop(bot, repository, config))
    try:
        await register_commands(bot, config.admin_ids)
        await close_issues_topic(
            bot, config.team_group_id, config.dashboard_topic_id
        )
        await dispatcher.start_polling(bot)
    finally:
        dashboard_task.cancel()
        reminder_task.cancel()
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
