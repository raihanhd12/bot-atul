from enum import StrEnum


class TicketStatus(StrEnum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    FIXED = "Fixed"
    CLOSED = "Closed"


TRANSITIONS = {
    (TicketStatus.OPEN, "start"): TicketStatus.IN_PROGRESS,
    (TicketStatus.OPEN, "close"): TicketStatus.CLOSED,
    (TicketStatus.IN_PROGRESS, "fix"): TicketStatus.FIXED,
    (TicketStatus.IN_PROGRESS, "close"): TicketStatus.CLOSED,
    (TicketStatus.FIXED, "confirm"): TicketStatus.CLOSED,
    (TicketStatus.FIXED, "close"): TicketStatus.CLOSED,
    (TicketStatus.FIXED, "reject"): TicketStatus.OPEN,
    (TicketStatus.FIXED, "reopen"): TicketStatus.OPEN,
    (TicketStatus.CLOSED, "reopen"): TicketStatus.OPEN,
}


def transition(current: TicketStatus, action: str) -> TicketStatus:
    try:
        return TRANSITIONS[(current, action)]
    except KeyError as error:
        raise ValueError(f"Invalid transition: {current} -> {action}") from error
