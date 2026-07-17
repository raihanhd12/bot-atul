from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot_atul.db.repositories import Repository
from bot_atul.services.dashboard import publish_dashboard
from bot_atul.services.exports import export_tickets


def build_dashboard_router(
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    timezone: ZoneInfo,
    data_dir: Path,
) -> Router:
    router = Router(name="dashboard")

    @router.message(Command("export"))
    async def export_command(message: Message) -> None:
        if (
            message.from_user is None
            or repository.get_role(message.from_user.id) != "admin"
        ):
            await message.answer("Not allowed.")
            return
        try:
            start, end = _parse_dates(message.text or "")
        except ValueError:
            await message.answer("Usage: /export [YYYY-MM-DD] [YYYY-MM-DD]")
            return
        bot = message.bot
        if bot is None:
            return
        await _send_export(
            bot,
            message.chat.id,
            repository,
            team_group_id,
            dashboard_topic_id,
            data_dir,
            start,
            end,
        )

    @router.callback_query(F.data.startswith("dashboard:"))
    async def dashboard_callback(query: CallbackQuery) -> None:
        if repository.get_role(query.from_user.id) != "admin":
            await query.answer("Not allowed.", show_alert=True)
            return
        bot = query.bot
        if bot is None or query.data is None:
            return
        if query.data == "dashboard:refresh":
            # Answer first so Telegram stops the loading spinner immediately.
            await query.answer("Refreshing…")
            await publish_dashboard(
                bot,
                repository,
                team_group_id,
                dashboard_topic_id,
                datetime.now(timezone),
            )
        else:
            await query.answer("Excel sent in DM.")
            await _send_export(
                bot,
                query.from_user.id,
                repository,
                team_group_id,
                dashboard_topic_id,
                data_dir,
                None,
                None,
            )

    return router


def _parse_dates(command: str) -> tuple[date | None, date | None]:
    values = command.split()[1:]
    if len(values) > 2:
        raise ValueError
    dates = [date.fromisoformat(value) for value in values]
    if len(dates) == 2 and dates[0] > dates[1]:
        raise ValueError
    return (
        dates[0] if dates else None,
        dates[1] if len(dates) == 2 else dates[0] if dates else None,
    )


async def _send_export(
    bot: Bot,
    chat_id: int,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    data_dir: Path,
    start: date | None,
    end: date | None,
) -> None:
    path = data_dir / f"issues-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    export_tickets(
        repository,
        path,
        team_group_id,
        dashboard_topic_id,
        start,
        end,
    )
    try:
        await bot.send_document(chat_id, FSInputFile(path), caption="Issue export")
    finally:
        path.unlink(missing_ok=True)
