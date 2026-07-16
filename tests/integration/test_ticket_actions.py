import sqlite3

import pytest

from bot_atul.db.migrations import migrate
from bot_atul.db.repositories import Repository
from bot_atul.services.workflow import TicketWorkflow


@pytest.fixture
def workflow() -> tuple[Repository, TicketWorkflow, int]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    repository = Repository(connection)
    repository.upsert_user(10, "reporter")
    repository.upsert_user(20, "agent")
    repository.upsert_user(30, "admin")
    ticket = repository.create_ticket(
        reporter_id=10,
        service_name="Technical",
        urgency="Normal",
        title="Tool call fails",
        description="Details",
    )
    return repository, TicketWorkflow(repository), ticket.number


def test_agent_assigns_and_resolves_ticket(
    workflow: tuple[Repository, TicketWorkflow, int],
) -> None:
    repository, service, number = workflow

    service.assign_to_me(number, 20)
    assert repository.get_ticket(number).assignee_id == 20  # type: ignore[union-attr]
    assert service.change_status(number, 20, "start").status == "In Progress"
    assert service.change_status(number, 20, "fix").status == "Fixed"
    assert service.confirm_fix(number, 10, fixed=True).status == "Closed"
    assert repository.count_status_history(number) == 3


def test_reporter_can_reject_fix(
    workflow: tuple[Repository, TicketWorkflow, int],
) -> None:
    _, service, number = workflow
    service.assign_to_me(number, 20)
    service.change_status(number, 20, "start")
    service.change_status(number, 20, "fix")

    assert service.confirm_fix(number, 10, fixed=False).status == "Open"


def test_permissions_and_invalid_transitions_are_rejected(
    workflow: tuple[Repository, TicketWorkflow, int],
) -> None:
    _, service, number = workflow

    with pytest.raises(PermissionError):
        service.change_status(number, 10, "start")
    service.assign_to_me(number, 20)
    with pytest.raises(ValueError, match="Invalid transition"):
        service.change_status(number, 20, "fix")
    with pytest.raises(PermissionError):
        service.confirm_fix(number, 99, fixed=True)


def test_unassigned_agent_cannot_update_ticket(
    workflow: tuple[Repository, TicketWorkflow, int],
) -> None:
    repository, service, number = workflow
    repository.upsert_user(21, "agent")
    service.assign_to_me(number, 20)

    with pytest.raises(PermissionError, match="assigned"):
        service.change_status(number, 21, "start")


def test_reporter_cancels_only_open_unassigned_ticket(
    workflow: tuple[Repository, TicketWorkflow, int],
) -> None:
    _, service, number = workflow

    cancelled = service.cancel(number, 10)
    assert cancelled.status == "Closed"


def test_assigned_ticket_cannot_be_cancelled(
    workflow: tuple[Repository, TicketWorkflow, int],
) -> None:
    _, service, number = workflow
    service.assign_to_me(number, 20)

    with pytest.raises(ValueError, match="unassigned"):
        service.cancel(number, 10)


def test_closed_ticket_cannot_be_assigned(
    workflow: tuple[Repository, TicketWorkflow, int],
) -> None:
    _, service, number = workflow
    service.cancel(number, 10)

    with pytest.raises(ValueError, match="active"):
        service.assign_to_me(number, 20)
