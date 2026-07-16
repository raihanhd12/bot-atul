import sqlite3
from types import SimpleNamespace

import pytest

from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.services.topics import (
    create_agent_workspace,
    create_ticket_card,
    deliver_pending_reporter_messages,
)


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.copies: list[dict[str, object]] = []
        self.attachments: list[dict[str, object]] = []

    async def send_message(self, **kwargs: object) -> SimpleNamespace:
        self.messages.append(kwargs)
        return SimpleNamespace(message_id=len(self.messages))

    async def copy_message(self, **kwargs: object) -> SimpleNamespace:
        self.copies.append(kwargs)
        return SimpleNamespace(message_id=100 + len(self.copies))

    async def send_document(self, **kwargs: object) -> SimpleNamespace:
        self.attachments.append(kwargs)
        return SimpleNamespace(message_id=200 + len(self.attachments))

    async def send_photo(self, **kwargs: object) -> SimpleNamespace:
        self.attachments.append(kwargs)
        return SimpleNamespace(message_id=200 + len(self.attachments))


@pytest.fixture
def repository() -> Repository:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "reporter")
    repository.upsert_user(20, "agent")
    return repository


@pytest.mark.asyncio
async def test_ticket_card_stays_in_dashboard_topic(
    repository: Repository,
) -> None:
    ticket = repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="High",
        title="Agent cannot start",
        description="Failure",
    )
    bot = FakeBot()

    assert await create_ticket_card(bot, repository, -1001, 24, ticket) == 1
    stored = repository.get_ticket(ticket.number)
    assert stored is not None
    assert stored.topic_id is None
    assert stored.card_message_id == 1
    assert repository.get_dashboard_card(ticket.number) == 1
    assert bot.messages[0]["message_thread_id"] == 24

    await create_ticket_card(bot, repository, -1001, 24, stored)
    assert len(bot.messages) == 1


@pytest.mark.asyncio
async def test_assignment_workspace_and_pending_message_are_private(
    repository: Repository,
) -> None:
    ticket = repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="High",
        title="Agent cannot start",
        description="Failure",
        attachments=(("document", "file-1", "trace.txt", "log"),),
    )
    pending_id = repository.record_message(
        ticket_number=ticket.number,
        direction="reporter_to_team",
        source_chat_id=10,
        source_message_id=7,
        destination_chat_id=None,
        destination_message_id=None,
        text="More information",
        delivery_status="pending",
    )
    bot = FakeBot()

    await create_agent_workspace(bot, repository, ticket, 20)
    assigned = repository.assign_ticket(ticket.number, 20, 20)
    await deliver_pending_reporter_messages(bot, repository, assigned)

    workspace = repository.get_agent_workspace(ticket.number)
    assert workspace is not None
    assert workspace.agent_id == 20
    assert bot.messages[0]["chat_id"] == 20
    assert bot.attachments[0]["chat_id"] == 20
    assert bot.copies[0]["chat_id"] == 20
    assert repository.get_relay_message(pending_id).delivery_status == "sent"  # type: ignore[union-attr]
