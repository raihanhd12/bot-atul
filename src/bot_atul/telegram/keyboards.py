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


def ticket_actions(ticket: Ticket) -> InlineKeyboardMarkup:
    actions: list[tuple[str, str]] = []
    if ticket.status == "Open":
        actions = [
            ("Assign to Me", "assign"),
            ("Start Work", "start"),
            ("Close", "close"),
        ]
    elif ticket.status == "In Progress":
        actions = [
            ("Assign to Me", "assign"),
            ("Mark Fixed", "fix"),
            ("Close", "close"),
        ]
    elif ticket.status in {"Fixed", "Closed"}:
        actions = [("Reopen", "reopen")]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label, callback_data=f"ticket:{action}:{ticket.number}"
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
    if ticket.status != "Open" or ticket.assignee_id is not None:
        return None
    return action("Cancel Ticket", f"ticket:cancel:{ticket.number}")


def retry_delivery(message_id: int) -> InlineKeyboardMarkup:
    return action("Retry Delivery", f"relay:retry:{message_id}")
