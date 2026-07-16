from pathlib import Path

import pytest

from bot_atul.db.connection import connect
from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    connection = connect(tmp_path / "bot.db")
    migrate(connection)
    connection.execute("INSERT INTO users(telegram_id, role) VALUES (10, 'agent')")
    connection.commit()
    return Repository(connection)


def test_ticket_round_trip_preserves_long_description(repository: Repository) -> None:
    description = "Masalah panjang 🚀\n" * 10_000

    ticket = repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="High",
        title="Agent cannot start",
        description=description,
        attachments=(("document", "file-1", "trace.txt", "log"),),
    )

    stored = repository.get_ticket(ticket.number)
    assert stored is not None
    assert stored.description == description
    assert stored.service_name == "Technical"
    assert stored.status == "Open"
    attachments = repository.list_attachments(ticket.number)
    assert len(attachments) == 1
    assert attachments[0].file_id == "file-1"
    assert attachments[0].file_name == "trace.txt"
    assert attachments[0].kind == "document"


def test_ticket_stores_multiple_attachments(repository: Repository) -> None:
    ticket = repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="High",
        title="Many files",
        description="Details",
        attachments=(
            ("photo", "photo-a", None, "one"),
            ("document", "doc-b", "notes.pdf", None),
            ("photo", "photo-c", None, None),
        ),
    )

    attachments = repository.list_attachments(ticket.number)
    assert [item.kind for item in attachments] == ["photo", "document", "photo"]
    assert repository.count_attachments(ticket.number) == 3
    repository.save_topic_attachment(ticket.number, attachments[0].id, 501)
    assert repository.is_topic_attachment_posted(attachments[0].id) is True
    assert repository.is_topic_attachment_posted(attachments[1].id) is False


def test_processed_update_is_claimed_once(repository: Repository) -> None:
    assert repository.claim_update(123) is True
    assert repository.claim_update(123) is False


def test_ticket_write_rolls_back_on_invalid_service(repository: Repository) -> None:
    with pytest.raises(ValueError, match="service"):
        repository.create_ticket(
            reporter_id=10,
            service_name="Unknown",
            urgency="Normal",
            title="No service",
            description="Details",
        )

    assert repository.count_tickets() == 0
