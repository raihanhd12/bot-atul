from bot_atul.db.repositories import Repository, Ticket


class RelayService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def active_for_reporter(self, reporter_id: int) -> list[Ticket]:
        if self.repository.get_role(reporter_id) != "reporter":
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

    def team_destination(
        self,
        actor_id: int,
        *,
        topic_id: int,
        reply_to_message_id: int | None = None,
        explicit: bool = False,
    ) -> Ticket:
        if self.repository.get_role(actor_id) not in {"agent", "admin"}:
            raise PermissionError("Agent access required.")
        if explicit:
            ticket = self.repository.ticket_by_topic(topic_id)
        elif reply_to_message_id is not None:
            ticket = self.repository.ticket_for_team_message(reply_to_message_id)
            if ticket is not None and ticket.topic_id != topic_id:
                ticket = None
        else:
            raise ValueError("Use /reply or a direct reply to a relayed user message.")
        if ticket is None:
            raise ValueError("No matching ticket message found.")
        return ticket
