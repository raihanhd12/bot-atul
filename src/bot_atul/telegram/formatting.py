from bot_atul.db.repositories import Ticket


def topic_title(ticket: Ticket) -> str:
    prefix = f"#{ticket.number} · {ticket.service_name} · "
    suffix = f" · {ticket.status}"
    available = 128 - len(prefix) - len(suffix)
    title = ticket.title
    if len(title) > available:
        title = title[: max(available - 1, 0)] + "…"
    return prefix + title + suffix


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


def description_chunks(description: str, limit: int = 4_000) -> list[str]:
    return [
        description[index : index + limit]
        for index in range(0, len(description), limit)
    ]
