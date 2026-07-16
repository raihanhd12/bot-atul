import sqlite3
from types import SimpleNamespace

import pytest

from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.services.topics import (
    create_agent_workspace,
    create_ticket_card,
    deliver_pending_reporter_messages,
    hide_topic_attachments,
    publish_topic_attachments,
)


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []
        self.copies: list[dict[str, object]] = []
        self.attachments: list[dict[str, object]] = []
        self.edits: list[dict[str, object]] = []
        self.deletes: list[dict[str, object]] = []
        self._next_attachment_id = 200

    async def send_message(self, **kwargs: object) -> SimpleNamespace:
        self.messages.append(kwargs)
        return SimpleNamespace(message_id=len(self.messages))

    async def copy_message(self, **kwargs: object) -> SimpleNamespace:
        self.copies.append(kwargs)
        return SimpleNamespace(message_id=100 + len(self.copies))

    async def send_document(self, **kwargs: object) -> SimpleNamespace:
        self.attachments.append(kwargs)
        self._next_attachment_id += 1
        return SimpleNamespace(message_id=self._next_attachment_id)

    async def send_photo(self, **kwargs: object) -> SimpleNamespace:
        self.attachments.append(kwargs)
        self._next_attachment_id += 1
        return SimpleNamespace(message_id=self._next_attachment_id)

    async def delete_message(self, **kwargs: object) -> bool:
        self.deletes.append(kwargs)
        return True

    async def get_chat(self, chat_id: int) -> SimpleNamespace:
        return SimpleNamespace(
            id=chat_id, username=None, full_name=None, first_name=None
        )

    async def edit_message_text(self, **kwargs: object) -> SimpleNamespace:
        self.edits.append(kwargs)
        return SimpleNamespace(message_id=kwargs.get("message_id", 0))


@pytest.fixture
def repository() -> Repository:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "agent")
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
    assert "🔺 Urgency   High" in str(bot.messages[0]["text"])
    assert "View Details" in str(bot.messages[0]["reply_markup"])

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


@pytest.mark.asyncio
async def test_view_details_posts_and_hide_removes_topic_attachments(
    repository: Repository,
) -> None:
    ticket = repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="High",
        title="Crash with logs",
        description="See attachments",
        attachments=(
            ("photo", "photo-1", None, "screen one"),
            ("photo", "photo-2", None, "screen two"),
            ("document", "doc-1", "trace.pdf", None),
        ),
    )
    bot = FakeBot()
    await create_ticket_card(bot, repository, -1001, 24, ticket)

    posted = await publish_topic_attachments(bot, repository, -1001, 24, ticket)
    assert posted == 3
    assert len(bot.attachments) == 3
    assert bot.attachments[0]["photo"] == "photo-1"
    assert bot.attachments[1]["photo"] == "photo-2"
    assert bot.attachments[2]["document"] == "doc-1"
    assert all(item["message_thread_id"] == 24 for item in bot.attachments)
    assert all(item["reply_to_message_id"] == 1 for item in bot.attachments)

    # While open, do not re-post the same files.
    assert await publish_topic_attachments(bot, repository, -1001, 24, ticket) == 0
    assert len(bot.attachments) == 3

    removed = await hide_topic_attachments(bot, repository, -1001, ticket)
    assert removed == 3
    assert len(bot.deletes) == 3
    assert repository.list_topic_attachment_messages(ticket.number) == []

    # View Details again re-posts files after hide.
    posted_again = await publish_topic_attachments(bot, repository, -1001, 24, ticket)
    assert posted_again == 3
    assert len(bot.attachments) == 6
