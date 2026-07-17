from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot_atul.db.repositories import AttachmentRecord, Ticket
from bot_atul.telegram.formatting import attachment_icon, attachment_label


def choices(prefix: str, values: tuple[str, ...]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=value, callback_data=f"{prefix}:{value}")]
            for value in values
        ]
    )


def action(text: str, data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=data)]]
    )


def review_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Submit", callback_data="intake:confirm")],
            [InlineKeyboardButton(text="Cancel", callback_data="intake:cancel")],
        ]
    )


def _file_button_label(attachment: AttachmentRecord, index: int) -> str:
    icon = attachment_icon(attachment.kind)
    name = attachment_label(attachment, index)
    label = f"{icon} {index}. {name}"
    return label if len(label) <= 64 else label[:61] + "..."


def dashboard_ticket_actions(
    ticket: Ticket,
    *,
    detailed: bool = False,
    attachments: list[AttachmentRecord] | None = None,
) -> InlineKeyboardMarkup:
    """Topic cards are view-only: expand details and open one file at a time."""
    files = attachments or []
    rows: list[list[InlineKeyboardButton]] = []
    if detailed:
        rows.append(
            [
                InlineKeyboardButton(
                    text="▲ Hide Details",
                    callback_data=f"ticket:summary:{ticket.number}",
                )
            ]
        )
        # One button per file — tap to preview under the card (temporary).
        for index, attachment in enumerate(files[:10], start=1):
            rows.append(
                [
                    InlineKeyboardButton(
                        text=_file_button_label(attachment, index),
                        callback_data=(
                            f"ticket:file:{ticket.number}:{attachment.id}"
                        ),
                    )
                ]
            )
        if len(files) > 10:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"… +{len(files) - 10} more in private workspace",
                        callback_data=f"ticket:detail:{ticket.number}",
                    )
                ]
            )
        if files:
            rows.append(
                [
                    InlineKeyboardButton(
                        text="🧹 Clear preview",
                        callback_data=f"ticket:clearfiles:{ticket.number}",
                    )
                ]
            )
    else:
        label = "📄 View Details"
        if files:
            label = f"📄 View Details · {len(files)} file(s)"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"ticket:detail:{ticket.number}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def agent_ticket_actions(ticket: Ticket) -> InlineKeyboardMarkup:
    # Self-owned tickets (auto-assigned on report) have no separate reporter.
    self_owned = (
        ticket.assignee_id is not None and ticket.reporter_id == ticket.assignee_id
    )
    actions: list[tuple[str, str]] = []
    if ticket.status == "Open":
        actions = [
            *([] if self_owned else [("Reply to Reporter", "reply")]),
            ("Start Work", "start"),
            ("Close", "close"),
        ]
    elif ticket.status == "In Progress":
        actions = [
            *([] if self_owned else [("Reply to Reporter", "reply")]),
            ("Mark Fixed", "fix"),
            ("Close", "close"),
        ]
    elif ticket.status == "Fixed":
        actions = [
            *([] if self_owned else [("Reply to Reporter", "reply")]),
            ("Close", "close"),
            ("Reopen", "reopen"),
        ]
    elif ticket.status == "Closed":
        actions = [
            *([] if self_owned else [("Reply to Reporter", "reply")]),
            ("Reopen", "reopen"),
        ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=(
                        f"relay:reply:{ticket.number}"
                        if action == "reply"
                        else f"ticket:{action}:{ticket.number}"
                    ),
                )
            ]
            for label, action in actions
        ]
    )


def admin_open_ticket_actions(tickets: list[Ticket]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for ticket in tickets:
        label = f"#{ticket.number} · {ticket.status} · {ticket.title}"
        if len(label) > 60:
            label = label[:57] + "..."
        if ticket.status in {"Open", "In Progress", "Fixed"}:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"Close {label}",
                        callback_data=f"ticket:close:{ticket.number}",
                    )
                ]
            )
    rows.append(
        [InlineKeyboardButton(text="← Admin Panel", callback_data="admin:home")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def fix_confirmation(ticket_number: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Yes, fixed", callback_data=f"ticket:confirm:{ticket_number}"
                ),
                InlineKeyboardButton(
                    text="No, still broken",
                    callback_data=f"ticket:reject:{ticket_number}",
                ),
            ]
        ]
    )


def reporter_ticket_actions(ticket: Ticket) -> InlineKeyboardMarkup | None:
    rows = []
    if ticket.status == "Open" and ticket.assignee_id in {None, ticket.reporter_id}:
        rows.append(
            [
                InlineKeyboardButton(
                    text="Cancel Ticket",
                    callback_data=f"ticket:cancel:{ticket.number}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="← Dashboard", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def retry_delivery(message_id: int) -> InlineKeyboardMarkup:
    return action("Retry Delivery", f"relay:retry:{message_id}")


def dashboard_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Refresh List", callback_data="dashboard:refresh"
                ),
                InlineKeyboardButton(
                    text="Export Excel", callback_data="dashboard:export"
                ),
            ]
        ]
    )


def reminder_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 My Tickets", callback_data="menu:tickets"
                ),
                InlineKeyboardButton(
                    text="📝 Report Issue", callback_data="menu:report"
                ),
            ],
            [InlineKeyboardButton(text="🏠 Menu", callback_data="menu:home")],
        ]
    )


def quiet_checkin_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Yes, report", callback_data="checkin:report"
                ),
                InlineKeyboardButton(
                    text="All good", callback_data="checkin:ok"
                ),
            ]
        ]
    )
