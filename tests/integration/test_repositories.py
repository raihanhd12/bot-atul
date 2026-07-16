from pathlib import Path

import pytest

from bot_atul.db.connection import connect
from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository


@pytest.fixture
def repository(tmp_path: Path) -> Repository:
    connection = connect(tmp_path / "bot.db")
    migrate(connection)
    connection.execute("INSERT INTO users(telegram_id, role) VALUES (10, 'reporter')")
    connection.commit()
    return Repository(connection)


def test_ticket_round_trip_preserves_long_description(repository: Repository) -> None:
    description = "Masalah panjang 🚀\n" * 10_000

    ticket = repository.create_ticket(
        reporter_id=10,
        service_name="AI-Agents",
        urgency="High",
        title="Agent cannot start",
        description=description,
        attachments=(("document", "file-1", "trace.txt", "log"),),
    )

    stored = repository.get_ticket(ticket.number)
    assert stored is not None
    assert stored.description == description
    assert stored.service_name == "AI-Agents"
    assert stored.status == "Open"
    attachment = repository.connection.execute(
        "SELECT telegram_file_id, file_name FROM attachments WHERE ticket_number = ?",
        (ticket.number,),
    ).fetchone()
    assert tuple(attachment) == ("file-1", "trace.txt")


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
