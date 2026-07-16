from bot_atul.db.repositories import Ticket

STATUS_ICONS = {
    "Open": "🆕",
    "In Progress": "🔄",
    "Fixed": "🛠️",
    "Closed": "✅",
}

URGENCY_ICONS = {
    "Critical": "🚨",
    "High": "🔺",
    "Normal": "▪️",
    "Low": "▫️",
}


def _label(user_id: int | None, names: dict[int, str] | None) -> str:
    if user_id is None:
        return "Unassigned"
    if names and user_id in names:
        return names[user_id]
    return f"User {user_id}"


def ticket_card(
    ticket: Ticket,
    *,
    names: dict[int, str] | None = None,
    detailed: bool = False,
) -> str:
    status_icon = STATUS_ICONS.get(ticket.status, "📋")
    urgency_icon = URGENCY_ICONS.get(ticket.urgency, "•")
    reporter = _label(ticket.reporter_id, names)
    assignee = _label(ticket.assignee_id, names)

    lines = [
        f"{status_icon} Ticket #{ticket.number} · {ticket.status}",
        "────────────────",
        ticket.title,
        "",
        f"🧩 Service   {ticket.service_name}",
        f"{urgency_icon} Urgency   {ticket.urgency}",
        f"{status_icon} Status    {ticket.status}",
        f"👤 Reported  {reporter}",
        f"🧑‍💻 Owner     {assignee}",
    ]
    if detailed:
        description = ticket.description.strip() or "—"
        if len(description) > 2_800:
            description = description[:2_797] + "..."
        lines.extend(["", "📝 Details", description])
    return "\n".join(lines)


def agent_workspace(
    ticket: Ticket, *, names: dict[int, str] | None = None
) -> str:
    return (
        f"{ticket_card(ticket, names=names, detailed=False)}\n\n"
        f"📝 Description\n{ticket.description}"
    )


def description_chunks(description: str, limit: int = 4_000) -> list[str]:
    return [
        description[index : index + limit]
        for index in range(0, len(description), limit)
    ]
