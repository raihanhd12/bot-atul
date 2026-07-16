import pytest

from bot_atul.domain.statuses import TicketStatus, transition


@pytest.mark.parametrize(
    ("current", "action", "expected"),
    [
        (TicketStatus.OPEN, "start", TicketStatus.IN_PROGRESS),
        (TicketStatus.IN_PROGRESS, "fix", TicketStatus.FIXED),
        (TicketStatus.FIXED, "confirm", TicketStatus.CLOSED),
        (TicketStatus.FIXED, "close", TicketStatus.CLOSED),
        (TicketStatus.FIXED, "reject", TicketStatus.OPEN),
        (TicketStatus.CLOSED, "reopen", TicketStatus.OPEN),
        (TicketStatus.FIXED, "reopen", TicketStatus.OPEN),
        (TicketStatus.OPEN, "close", TicketStatus.CLOSED),
    ],
)
def test_valid_transition(
    current: TicketStatus, action: str, expected: TicketStatus
) -> None:
    assert transition(current, action) is expected


@pytest.mark.parametrize(
    ("current", "action"),
    [
        (TicketStatus.OPEN, "fix"),
        (TicketStatus.OPEN, "confirm"),
        (TicketStatus.IN_PROGRESS, "reopen"),
        (TicketStatus.CLOSED, "start"),
    ],
)
def test_invalid_transition(current: TicketStatus, action: str) -> None:
    with pytest.raises(ValueError, match="Invalid transition"):
        transition(current, action)
