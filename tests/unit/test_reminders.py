import sqlite3
from datetime import datetime, time
from zoneinfo import ZoneInfo

from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.services.reminders import (
    build_personal_reminder,
    build_reminder,
    list_person_reminders,
    next_reminder_run,
)


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
    assert list_person_reminders(Repository(connection)) == []


def test_reminder_summarizes_unresolved_tickets() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "agent")
    repository.remember_user(10, "raihanhd", "Raihan HD")
    repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="High",
        title="Login fails",
        description="Details",
    )
    repository.assign_ticket(1, 10, 10)

    reminder = build_reminder(repository)

    assert reminder is not None
    assert "1 still open" in reminder
    assert "1 Open" in reminder
    assert "Raihan HD (@raihanhd)" in reminder
    assert "Personal reminders were also sent" in reminder


def test_personal_reminder_uses_friendly_name_and_ticket_list() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "agent")
    repository.remember_user(10, "raihanhd", "Raihan HD")
    repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="Critical",
        title="Login fails",
        description="Details",
    )
    repository.assign_ticket(1, 10, 10)
    repository.create_ticket(
        reporter_id=10,
        service_name="General",
        urgency="Normal",
        title="Docs typo",
        description="Details",
    )
    repository.assign_ticket(2, 10, 10)
    repository.update_status(2, "Open", "In Progress", 10)

    people = list_person_reminders(repository)
    assert len(people) == 1
    person = people[0]
    assert person.greeting_name == "Raihan"
    text = build_personal_reminder(person)

    assert text.startswith("Hi Raihan")
    assert "you still have open issues" in text
    assert "#1 · Login fails" in text
    assert "#2 · Docs typo" in text
    assert "2 (" in text
