from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot_atul.db.repositories import Ticket


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


def dashboard_ticket_actions(ticket: Ticket) -> InlineKeyboardMarkup | None:
    if ticket.assignee_id is not None or ticket.status not in {"Open", "In Progress"}:
        return None
    return action("Assign to Me", f"ticket:assign:{ticket.number}")


def agent_ticket_actions(ticket: Ticket) -> InlineKeyboardMarkup:
    actions: list[tuple[str, str]] = []
    if ticket.status == "Open":
        actions = [
            ("Reply to Reporter", "reply"),
            ("Start Work", "start"),
            ("Close", "close"),
        ]
    elif ticket.status == "In Progress":
        actions = [
            ("Reply to Reporter", "reply"),
            ("Mark Fixed", "fix"),
            ("Close", "close"),
        ]
    elif ticket.status in {"Fixed", "Closed"}:
        actions = [("Reply to Reporter", "reply"), ("Reopen", "reopen")]
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
    if ticket.status == "Open" and ticket.assignee_id is None:
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
