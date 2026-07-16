import sqlite3

import pytest

from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.services.relay import RelayService


@pytest.fixture
def relay() -> tuple[Repository, RelayService, int, int]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "reporter")
    repository.upsert_user(20, "agent")
    first = repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="Normal",
        title="First",
        description="One",
    )
    second = repository.create_ticket(
        reporter_id=10,
        service_name="General",
        urgency="Normal",
        title="Second",
        description="Two",
    )
    return repository, RelayService(repository), first.number, second.number


def test_reporter_must_choose_when_multiple_tickets(
    relay: tuple[Repository, RelayService, int, int],
) -> None:
    _, service, first, second = relay

    assert [ticket.number for ticket in service.active_for_reporter(10)] == [
        first,
        second,
    ]
    assert service.reporter_destination(10, second).number == second
    with pytest.raises(ValueError, match="Choose"):
        service.reporter_destination(10)


def test_failed_delivery_record_can_be_completed(
    relay: tuple[Repository, RelayService, int, int],
) -> None:
    repository, _, first, _ = relay
    message_id = repository.record_message(
        ticket_number=first,
        direction="team_to_reporter",
        source_chat_id=-1001,
        source_message_id=80,
        destination_chat_id=10,
        destination_message_id=None,
        text="Please retry",
        relay_method="text",
        delivery_status="failed",
    )

    assert repository.get_relay_message(message_id).delivery_status == "failed"  # type: ignore[union-attr]
    repository.mark_message_sent(message_id, 10, 81)
    assert repository.get_relay_message(message_id).delivery_status == "sent"  # type: ignore[union-attr]
