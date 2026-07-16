import sqlite3
from datetime import datetime, time
from zoneinfo import ZoneInfo

from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.services.reminders import build_reminder, next_reminder_run


def test_next_reminder_skips_weekend() -> None:
    timezone = ZoneInfo("Asia/Jakarta")
    friday = datetime(2026, 7, 17, 10, tzinfo=timezone)

    assert next_reminder_run(friday, timezone, time(9)) == datetime(
        2026, 7, 20, 9, tzinfo=timezone
    )


def test_reminder_is_empty_without_unresolved_tickets() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    migrate(connection)

    assert build_reminder(Repository(connection)) is None


def test_reminder_summarizes_unresolved_tickets() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "agent")
    repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="High",
        title="Login fails",
        description="Details",
    )

    reminder = build_reminder(repository)

    assert reminder is not None
    assert "1 Open" in reminder
    assert "0 In Progress" in reminder
