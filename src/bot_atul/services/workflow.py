from bot_atul.db.repositories import Repository, Ticket
from bot_atul.domain.statuses import TicketStatus, transition


class TicketWorkflow:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def assign_to_me(self, number: int, actor_id: int) -> Ticket:
        self._require_agent(actor_id)
        return self.repository.assign_ticket(number, actor_id, actor_id)

    def change_status(self, number: int, actor_id: int, action: str) -> Ticket:
        self._require_agent(actor_id)
        ticket = self._ticket(number)
        if (
            self.repository.get_role(actor_id) != "admin"
            and ticket.assignee_id != actor_id
        ):
            raise PermissionError("Only the assigned agent can update this ticket.")
        new_status = transition(TicketStatus(ticket.status), action)
        return self.repository.update_status(
            number, ticket.status, new_status, actor_id
        )

    def confirm_fix(self, number: int, reporter_id: int, *, fixed: bool) -> Ticket:
        ticket = self._ticket(number)
        if ticket.reporter_id != reporter_id:
            raise PermissionError("Only the ticket reporter can confirm the fix.")
        action = "confirm" if fixed else "reject"
        new_status = transition(TicketStatus(ticket.status), action)
        reason = "Reporter confirmed" if fixed else "Reporter says still broken"
        return self.repository.update_status(
            number, ticket.status, new_status, reporter_id, reason
        )

    def cancel(self, number: int, actor_id: int) -> Ticket:
        ticket = self._ticket(number)
        role = self.repository.get_role(actor_id)
        is_owner = ticket.reporter_id == actor_id
        is_admin = role == "admin"
        if not is_owner and not is_admin:
            raise PermissionError("Only the ticket owner or an admin can cancel it.")
        if ticket.status != TicketStatus.OPEN:
            raise ValueError("Only an Open ticket can be cancelled.")
        if (
            not is_admin
            and ticket.assignee_id is not None
            and ticket.assignee_id != actor_id
        ):
            raise ValueError("Only the assigned owner can cancel this ticket.")
        return self.repository.update_status(
            number,
            ticket.status,
            TicketStatus.CLOSED,
            actor_id,
            "Ticket cancelled",
        )

    def _require_agent(self, actor_id: int) -> None:
        if self.repository.get_role(actor_id) not in {"agent", "admin"}:
            raise PermissionError("Agent access required.")

    def _ticket(self, number: int) -> Ticket:
        ticket = self.repository.get_ticket(number)
        if ticket is None:
            raise ValueError(f"Unknown ticket: {number}")
        return ticket
