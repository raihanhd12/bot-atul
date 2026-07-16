from bot_atul.db.repositories import AttachmentRecord, Ticket

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


def attachment_label(attachment: AttachmentRecord, index: int) -> str:
    if attachment.kind == "photo":
        return attachment.caption or f"Photo {index}"
    return attachment.file_name or attachment.caption or f"File {index}"


def attachment_icon(kind: str) -> str:
    if kind == "photo":
        return "🖼️"
    return "📄"


def format_attachment_lines(attachments: list[AttachmentRecord]) -> list[str]:
    if not attachments:
        return []
    lines = [f"📎 Attachments  {len(attachments)}"]
    for index, attachment in enumerate(attachments, start=1):
        icon = attachment_icon(attachment.kind)
        lines.append(f"  {icon} {attachment_label(attachment, index)}")
    return lines


def ticket_card(
    ticket: Ticket,
    *,
    names: dict[int, str] | None = None,
    detailed: bool = False,
    attachments: list[AttachmentRecord] | None = None,
) -> str:
    status_icon = STATUS_ICONS.get(ticket.status, "📋")
    urgency_icon = URGENCY_ICONS.get(ticket.urgency, "•")
    # Product language: one person ("By"). assignee_id stays internal plumbing.
    by_id = ticket.assignee_id or ticket.reporter_id
    by = _label(by_id, names)
    files = attachments or []

    lines = [
        f"{status_icon} Ticket #{ticket.number} · {ticket.status}",
        "────────────────",
        ticket.title,
        "",
        f"🧩 Service   {ticket.service_name}",
        f"{urgency_icon} Urgency   {ticket.urgency}",
        f"{status_icon} Status    {ticket.status}",
        f"👤 By        {by}",
    ]
    if files and not detailed:
        lines.append(f"📎 Files     {len(files)} attachment(s)")
    if detailed:
        description = ticket.description.strip() or "—"
        if len(description) > 2_500:
            description = description[:2_497] + "..."
        lines.extend(["", "📝 Details", description])
        if files:
            lines.extend(["", *format_attachment_lines(files)])
            lines.append("")
            lines.append("Files are posted below this card in the topic.")
        else:
            lines.extend(["", "📎 Attachments  none"])
    return "\n".join(lines)


def agent_workspace(
    ticket: Ticket,
    *,
    names: dict[int, str] | None = None,
    attachments: list[AttachmentRecord] | None = None,
) -> str:
    files = attachments or []
    body = (
        f"{ticket_card(ticket, names=names, detailed=False, attachments=files)}\n\n"
        f"📝 Description\n{ticket.description}"
    )
    if files:
        body += "\n\n" + "\n".join(format_attachment_lines(files))
    return body


def description_chunks(description: str, limit: int = 4_000) -> list[str]:
    return [
        description[index : index + limit]
        for index in range(0, len(description), limit)
    ]
