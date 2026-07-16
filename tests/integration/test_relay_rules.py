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
        service_name="AI-Agents",
        urgency="Normal",
        title="First",
        description="One",
    )
    second = repository.create_ticket(
        reporter_id=10,
        service_name="AI-ML",
        urgency="Normal",
        title="Second",
        description="Two",
    )
    repository.attach_topic(first.number, 101)
    repository.attach_topic(second.number, 102)
    return repository, RelayService(repository), first.number, second.number


def test_reporter_must_choose_when_multiple_tickets(
    relay: tuple[Repository, RelayService, int, int],
) -> None:
    _, service, first, second = relay

    assert [ticket.number for ticket in service.active_for_reporter(10)] == [
        first,
        second,
    ]
    assert service.reporter_destination(10, second).topic_id == 102
    with pytest.raises(ValueError, match="Choose"):
        service.reporter_destination(10)


def test_direct_reply_routes_to_original_reporter(
    relay: tuple[Repository, RelayService, int, int],
) -> None:
    repository, service, first, _ = relay
    repository.record_message(
        ticket_number=first,
        direction="reporter_to_team",
        source_chat_id=10,
        source_message_id=5,
        destination_chat_id=-1001,
        destination_message_id=50,
        text="More details",
        delivery_status="sent",
    )

    destination = service.team_destination(20, topic_id=101, reply_to_message_id=50)
    assert destination.reporter_id == 10
    assert destination.number == first


def test_internal_message_and_unknown_actor_are_rejected(
    relay: tuple[Repository, RelayService, int, int],
) -> None:
    _, service, _, _ = relay

    with pytest.raises(ValueError, match="direct reply"):
        service.team_destination(20, topic_id=101)
    with pytest.raises(PermissionError):
        service.team_destination(99, topic_id=101, explicit=True)


def test_explicit_reply_uses_topic_ticket(
    relay: tuple[Repository, RelayService, int, int],
) -> None:
    _, service, first, _ = relay

    assert service.team_destination(20, topic_id=101, explicit=True).number == first
