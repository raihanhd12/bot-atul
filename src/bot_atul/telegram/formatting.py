from bot_atul.db.repositories import Ticket


def ticket_card(ticket: Ticket) -> str:
    return (
        f"📋 Ticket #{ticket.number}\n"
        f"Service: {ticket.service_name}\n"
        f"Urgency: {ticket.urgency}\n"
        f"Status: {ticket.status}\n"
        f"Assignee: {ticket.assignee_id or '—'}\n"
        f"Reporter: {ticket.reporter_id}\n"
        f"Title: {ticket.title}"
    )


def agent_workspace(ticket: Ticket) -> str:
    return f"{ticket_card(ticket)}\n\nDescription:\n{ticket.description}"


def description_chunks(description: str, limit: int = 4_000) -> list[str]:
    return [
        description[index : index + limit]
        for index in range(0, len(description), limit)
    ]
