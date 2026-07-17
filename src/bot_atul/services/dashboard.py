import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot_atul.db.repositories import Repository
from bot_atul.services.topics import create_ticket_card
from bot_atul.telegram.keyboards import dashboard_actions

LOGGER = logging.getLogger(__name__)


def topic_link(group_id: int, topic_id: int, message_id: int | None = None) -> str:
    internal_id = str(abs(group_id)).removeprefix("100")
    suffix = f"/{message_id}" if message_id is not None else ""
    return f"https://t.me/c/{internal_id}/{topic_id}{suffix}"


def build_dashboard(
    repository: Repository,
    now: datetime,
    team_group_id: int,
    dashboard_topic_id: int,
) -> str:
    rows = repository.connection.execute(
        """
        SELECT t.number, t.title, t.urgency, t.status, t.assignee_id,
               c.message_id AS dashboard_card_id,
               CAST(julianday(?) - julianday(created_at) AS INTEGER) AS age_days
        FROM tickets t
        LEFT JOIN ticket_dashboard_cards c ON c.ticket_number = t.number
        WHERE t.status IN ('Open', 'In Progress')
        ORDER BY CASE urgency
            WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
            WHEN 'Normal' THEN 3 ELSE 4 END, number
        """,
        (now.isoformat(),),
    ).fetchall()
    yesterday = (now.date() - timedelta(days=1)).isoformat()
    fixed_count = repository.connection.execute(
        "SELECT COUNT(*) FROM tickets WHERE date(fixed_at) = ?", (yesterday,)
    ).fetchone()[0]
    groups: dict[str, list[str]] = {"Open": [], "In Progress": []}
    for row in rows:
        link = (
            topic_link(
                team_group_id,
                dashboard_topic_id,
                int(row["dashboard_card_id"]),
            )
            if row["dashboard_card_id"] is not None
            else ""
        )
        owner = (
            f" · {repository.user_label(int(row['assignee_id']))}"
            if row["assignee_id"] is not None
            else ""
        )
        age = f" · {row['age_days']}d" if row["age_days"] else " · Today"
        urgency_icon = {
            "Critical": "🚨",
            "High": "🔺",
            "Normal": "▪️",
            "Low": "▫️",
        }.get(str(row["urgency"]), "•")
        status_icon = "🆕" if row["status"] == "Open" else "🔄"
        groups[str(row["status"])].append(
            f"{status_icon} #{row['number']} {row['title']} · "
            f"{urgency_icon} {row['urgency']}{owner}{age}\n{link}"
        )

    lines = [
        f"📋 {now.strftime('%A')} Issue Check",
        f"{now.day} {now.strftime('%B %Y')} · {len(rows)} need attention",
        "",
        f"🆕 Open ({len(groups['Open'])})",
        *(groups["Open"] or ["• None"]),
        "",
        f"🔄 In Progress ({len(groups['In Progress'])})",
        *(groups["In Progress"] or ["• None"]),
        "",
        f"✅ Fixed yesterday: {fixed_count}",
    ]
    return "\n".join(lines)


def next_dashboard_run(now: datetime, timezone: ZoneInfo) -> datetime:
    local = now.astimezone(timezone)
    candidate = datetime.combine(local.date(), time(9), timezone)
    if local >= candidate:
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


async def publish_dashboard(
    bot: Bot,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    now: datetime,
) -> int:
    for ticket in repository.actionable_tickets():
        await create_ticket_card(
            bot,
            repository,
            team_group_id,
            dashboard_topic_id,
            ticket,
        )
    digest_date = now.date().isoformat()
    pages = dashboard_pages(
        build_dashboard(repository, now, team_group_id, dashboard_topic_id)
    )
    rows = repository.connection.execute(
        "SELECT page, message_id FROM dashboard_posts WHERE digest_date = ?",
        (digest_date,),
    ).fetchall()
    existing = {int(row["page"]): int(row["message_id"]) for row in rows}
    message_ids: list[int] = []
    for page, text in enumerate(pages, start=1):
        markup = dashboard_actions() if page == 1 else None
        if page in existing:
            message_id = existing[page]
            try:
                await bot.edit_message_text(
                    chat_id=team_group_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=markup,
                )
            except TelegramAPIError as error:
                # Telegram rejects identical content; treat as already up to date.
                if "message is not modified" not in str(error).lower():
                    raise
        else:
            message = await bot.send_message(
                chat_id=team_group_id,
                message_thread_id=dashboard_topic_id,
                text=text,
                reply_markup=markup,
            )
            message_id = message.message_id
            with repository.connection:
                repository.connection.execute(
                    """
                    INSERT INTO dashboard_posts(digest_date, page, message_id)
                    VALUES (?, ?, ?)
                    """,
                    (digest_date, page, message_id),
                )
        message_ids.append(message_id)
    for page, message_id in existing.items():
        if page > len(pages):
            await bot.delete_message(team_group_id, message_id)
            with repository.connection:
                repository.connection.execute(
                    "DELETE FROM dashboard_posts WHERE digest_date = ? AND page = ?",
                    (digest_date, page),
                )
    return message_ids[0]


def dashboard_pages(text: str, limit: int = 4_000) -> list[str]:
    pages: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if current and len(current) + len(line) > limit:
            pages.append(current.rstrip())
            current = ""
        while len(line) > limit:
            pages.append(line[:limit])
            line = line[limit:]
        current += line
    if current:
        pages.append(current.rstrip())
    return pages or [text]


async def safe_publish_dashboard(
    bot: Bot,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    now: datetime,
) -> None:
    try:
        await publish_dashboard(bot, repository, team_group_id, dashboard_topic_id, now)
    except TelegramAPIError:
        LOGGER.exception("Dashboard update failed")
