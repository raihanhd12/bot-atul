from bot_atul.db.repositories import Repository, Ticket
from bot_atul.domain.permissions import Action, Role, allowed


class RelayService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def active_for_reporter(self, reporter_id: int) -> list[Ticket]:
        role = self.repository.get_role(reporter_id)
        if not allowed(Role(role) if role else None, Action.SUBMIT):
            raise PermissionError("Reporter access required.")
        return self.repository.active_tickets(reporter_id)

    def reporter_destination(
        self, reporter_id: int, selected_ticket: int | None = None
    ) -> Ticket:
        tickets = self.active_for_reporter(reporter_id)
        if selected_ticket is not None:
            for ticket in tickets:
                if ticket.number == selected_ticket:
                    return ticket
            raise ValueError("Unknown active ticket.")
        if len(tickets) != 1:
            raise ValueError("Choose an active ticket first.")
        return tickets[0]
