import sqlite3
from types import SimpleNamespace

import pytest

from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.services.topics import create_ticket_topic


class FakeBot:
    def __init__(self) -> None:
        self.topics = 0
        self.messages: list[dict[str, object]] = []
        self.attachments: list[dict[str, object]] = []

    async def create_forum_topic(self, **kwargs: object) -> SimpleNamespace:
        self.topics += 1
        return SimpleNamespace(message_thread_id=99)

    async def send_message(self, **kwargs: object) -> SimpleNamespace:
        self.messages.append(kwargs)
        return SimpleNamespace(message_id=len(self.messages))

    async def send_document(self, **kwargs: object) -> SimpleNamespace:
        self.attachments.append(kwargs)
        return SimpleNamespace(message_id=100 + len(self.attachments))

    async def send_photo(self, **kwargs: object) -> SimpleNamespace:
        self.attachments.append(kwargs)
        return SimpleNamespace(message_id=100 + len(self.attachments))


class RetryBot(FakeBot):
    async def send_message(self, **kwargs: object) -> SimpleNamespace:
        if not self.messages:
            self.messages.append(kwargs)
            raise RuntimeError("temporary failure")
        return await super().send_message(**kwargs)


@pytest.mark.asyncio
async def test_topic_creation_is_idempotent() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "reporter")
    ticket = repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="High",
        title="Agent cannot start",
        description="x" * 8_500,
        attachments=(("document", "file-1", "trace.txt", "log"),),
    )
    bot = FakeBot()

    assert await create_ticket_topic(bot, repository, -1001, ticket) == 99
    stored = repository.get_ticket(ticket.number)
    assert stored is not None
    assert stored.topic_id == 99
    assert stored.card_message_id == 1
    assert bot.topics == 1
    assert len(bot.messages) == 4
    assert bot.attachments[0]["document"] == "file-1"

    await create_ticket_topic(bot, repository, -1001, stored)
    assert bot.topics == 1
    assert len(bot.messages) == 4
    assert len(bot.attachments) == 1


@pytest.mark.asyncio
async def test_topic_retry_uses_topic_already_saved_in_repository() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "reporter")
    ticket = repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="High",
        title="Agent cannot start",
        description="Failed once",
    )
    bot = RetryBot()

    with pytest.raises(RuntimeError, match="temporary"):
        await create_ticket_topic(bot, repository, -1001, ticket)
    await create_ticket_topic(bot, repository, -1001, ticket)

    assert bot.topics == 1
