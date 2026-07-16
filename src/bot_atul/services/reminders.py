import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot_atul.db.repositories import Repository
from bot_atul.telegram.formatting import STATUS_ICONS, URGENCY_ICONS
from bot_atul.telegram.keyboards import dashboard_actions, reminder_actions

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenTicketLine:
    number: int
    title: str
    urgency: str
    status: str
    age_days: int


@dataclass(frozen=True)
class PersonReminder:
    user_id: int
    greeting_name: str
    tickets: tuple[OpenTicketLine, ...]


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


def _greeting_name(repository: Repository, user_id: int) -> str:
    user = repository.get_user(user_id)
    if user is None:
        return "there"
    if user.display_name:
        # "Raihan HD" / "Raihan (@x)" → first word feels natural in a DM.
        return user.display_name.split()[0].split("(")[0].strip() or "there"
    if user.username:
        return user.username
    return "there"


def list_person_reminders(repository: Repository) -> list[PersonReminder]:
    rows = repository.connection.execute(
        """
        SELECT COALESCE(assignee_id, reporter_id) AS owner_id,
               number, title, urgency, status,
               CAST(julianday('now') - julianday(created_at) AS INTEGER) AS age_days
        FROM tickets
        WHERE status IN ('Open', 'In Progress')
        ORDER BY owner_id, number
        """
    ).fetchall()
    grouped: dict[int, list[OpenTicketLine]] = defaultdict(list)
    for row in rows:
        owner_id = int(row["owner_id"])
        grouped[owner_id].append(
            OpenTicketLine(
                number=int(row["number"]),
                title=str(row["title"]),
                urgency=str(row["urgency"]),
                status=str(row["status"]),
                age_days=int(row["age_days"] or 0),
            )
        )
    reminders: list[PersonReminder] = []
    for user_id, tickets in grouped.items():
        reminders.append(
            PersonReminder(
                user_id=user_id,
                greeting_name=_greeting_name(repository, user_id),
                tickets=tuple(tickets),
            )
        )
    return reminders


def build_personal_reminder(person: PersonReminder) -> str:
    open_count = sum(1 for ticket in person.tickets if ticket.status == "Open")
    progress_count = len(person.tickets) - open_count
    lines = [
        f"Hi {person.greeting_name} 👋",
        "",
        "Friendly reminder — you still have open issues waiting on you:",
        "",
    ]
    for ticket in person.tickets:
        status_icon = STATUS_ICONS.get(ticket.status, "•")
        urgency_icon = URGENCY_ICONS.get(ticket.urgency, "•")
        age = "today" if ticket.age_days <= 0 else f"{ticket.age_days}d"
        lines.append(
            f"{status_icon} #{ticket.number} · {ticket.title}\n"
            f"   {urgency_icon} {ticket.urgency} · {ticket.status} · {age}"
        )
    lines.extend(
        [
            "",
            f"Total: {len(person.tickets)} "
            f"({open_count} open · {progress_count} in progress)",
            "",
            "Please check and update them when you can 🙏",
        ]
    )
    return "\n".join(lines)


def build_team_reminder(repository: Repository) -> str | None:
    people = list_person_reminders(repository)
    if not people:
        return None
    total = sum(len(person.tickets) for person in people)
    open_count = sum(
        1
        for person in people
        for ticket in person.tickets
        if ticket.status == "Open"
    )
    progress_count = total - open_count
    oldest = max(
        (ticket.age_days for person in people for ticket in person.tickets),
        default=0,
    )
    lines = [
        "⏰ Team issue reminder",
        "────────────────",
        f"{total} still open · {open_count} Open · {progress_count} In Progress",
        f"Oldest: {oldest} day(s)",
        "",
        "People with open issues:",
    ]
    for person in people:
        label = repository.user_label(person.user_id)
        lines.append(f"• {label} — {len(person.tickets)} ticket(s)")
    lines.extend(
        [
            "",
            "Personal reminders were also sent in private chat.",
        ]
    )
    return "\n".join(lines)


def build_reminder(repository: Repository) -> str | None:
    """Backward-compatible team summary used by tests and callers."""
    return build_team_reminder(repository)


async def send_reminder(
    bot: Bot,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
) -> bool:
    people = list_person_reminders(repository)
    if not people:
        return False

    for person in people:
        text = build_personal_reminder(person)
        try:
            await bot.send_message(
                chat_id=person.user_id,
                text=text,
                reply_markup=reminder_actions(),
            )
        except TelegramAPIError:
            LOGGER.exception(
                "Personal reminder failed for user %s", person.user_id
            )

    team_text = build_team_reminder(repository)
    if team_text is not None:
        try:
            await bot.send_message(
                chat_id=team_group_id,
                message_thread_id=dashboard_topic_id,
                text=team_text,
                reply_markup=dashboard_actions(),
            )
        except TelegramAPIError:
            LOGGER.exception("Team reminder delivery failed")
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
