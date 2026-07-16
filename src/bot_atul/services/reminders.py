import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot_atul.db.repositories import Repository
from bot_atul.telegram.keyboards import dashboard_actions

LOGGER = logging.getLogger(__name__)


def next_reminder_run(
    now: datetime, timezone: ZoneInfo, reminder_time: time
) -> datetime:
    local = now.astimezone(timezone)
    candidate = datetime.combine(local.date(), reminder_time, timezone)
    if local >= candidate:
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def build_reminder(repository: Repository) -> str | None:
    rows = repository.connection.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM tickets WHERE status IN ('Open', 'In Progress')
        GROUP BY status
        """
    ).fetchall()
    counts = {str(row["status"]): int(row["count"]) for row in rows}
    total = sum(counts.values())
    if total == 0:
        return None
    oldest = repository.connection.execute(
        """
        SELECT CAST(julianday('now') - julianday(MIN(created_at)) AS INTEGER)
        FROM tickets WHERE status IN ('Open', 'In Progress')
        """
    ).fetchone()[0]
    return (
        "⏰ Unresolved issue reminder\n"
        f"{counts.get('Open', 0)} Open · "
        f"{counts.get('In Progress', 0)} In Progress\n"
        f"Oldest unresolved issue: {int(oldest or 0)} day(s)\n"
        "Open the current dashboard for details."
    )


async def send_reminder(
    bot: Bot,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
) -> bool:
    text = build_reminder(repository)
    if text is None:
        return False
    await bot.send_message(
        chat_id=team_group_id,
        message_thread_id=dashboard_topic_id,
        text=text,
        reply_markup=dashboard_actions(),
    )
    return True


async def safe_send_reminder(
    bot: Bot,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
) -> None:
    try:
        await send_reminder(bot, repository, team_group_id, dashboard_topic_id)
    except TelegramAPIError:
        LOGGER.exception("Reminder delivery failed")
