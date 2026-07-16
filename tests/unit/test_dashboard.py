import sqlite3
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.services.dashboard import (
    build_dashboard,
    dashboard_pages,
    next_dashboard_run,
    publish_dashboard,
)


def test_dashboard_lists_only_actionable_tickets() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "agent")
    repository.upsert_user(20, "agent")
    repository.remember_user(20, "andi", "Andi Agent")
    open_ticket = repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="High",
        title="Agent fails",
        description="Details",
    )
    working = repository.create_ticket(
        reporter_id=10,
        service_name="General",
        urgency="Normal",
        title="Model drift",
        description="Details",
    )
    repository.save_dashboard_card(open_ticket.number, 101)
    repository.save_dashboard_card(working.number, 102)
    repository.assign_ticket(working.number, 20, 20)
    repository.update_status(working.number, "Open", "In Progress", 20)

    text = build_dashboard(
        repository,
        datetime(2026, 7, 20, 9, tzinfo=ZoneInfo("Asia/Jakarta")),
        -1001,
        24,
    )

    assert "Monday Issue Check" in text
    assert "20 July 2026" in text
    assert "🆕 Open (1)" in text
    assert "🔄 In Progress (1)" in text
    assert "#1 Agent fails · 🔺 High" in text
    assert "Andi Agent (@andi)" in text
    assert "https://t.me/c/1/24/101" in text


def test_next_run_skips_weekend() -> None:
    timezone = ZoneInfo("Asia/Jakarta")
    friday = datetime(2026, 7, 17, 10, tzinfo=timezone)

    run_at = next_dashboard_run(friday, timezone)

    assert run_at == datetime(2026, 7, 20, 9, tzinfo=timezone)


def test_dashboard_pages_are_lossless_and_within_telegram_limit() -> None:
    text = ("ticket row\n" * 1_000).rstrip()

    pages = dashboard_pages(text, 200)

    assert "\n".join(pages) == text
    assert all(len(page) <= 200 for page in pages)


@pytest.mark.asyncio
async def test_publish_edits_same_daily_post() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    migrate(connection)
    repository = Repository(connection)

    class FakeBot:
        def __init__(self) -> None:
            self.sent = 0
            self.edited = 0

        async def send_message(self, **_: object) -> SimpleNamespace:
            self.sent += 1
            return SimpleNamespace(message_id=77)

        async def edit_message_text(self, **_: object) -> None:
            self.edited += 1

    bot = FakeBot()
    now = datetime(2026, 7, 20, 9, tzinfo=ZoneInfo("Asia/Jakarta"))

    await publish_dashboard(bot, repository, -1001, 9, now)  # type: ignore[arg-type]
    await publish_dashboard(bot, repository, -1001, 9, now)  # type: ignore[arg-type]

    assert bot.sent == 1
    assert bot.edited == 1


@pytest.mark.asyncio
async def test_publish_creates_cards_for_existing_active_tickets() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "agent")
    ticket = repository.create_ticket(
        reporter_id=10,
        service_name="General",
        urgency="Normal",
        title="Existing ticket",
        description="Details",
    )

    class FakeBot:
        def __init__(self) -> None:
            self.messages: list[dict[str, object]] = []

        async def send_message(self, **kwargs: object) -> SimpleNamespace:
            self.messages.append(kwargs)
            return SimpleNamespace(message_id=len(self.messages))

    bot = FakeBot()
    now = datetime(2026, 7, 20, 9, tzinfo=ZoneInfo("Asia/Jakarta"))

    await publish_dashboard(bot, repository, -1001, 24, now)  # type: ignore[arg-type]

    assert repository.get_dashboard_card(ticket.number) == 1
    assert bot.messages[0]["message_thread_id"] == 24
