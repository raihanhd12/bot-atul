from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

REPORT = "📝 Report Issue"
MY_TICKETS = "📋 My Tickets"
HELP = "❓ Help"
TEAM_HELP = "👥 Team Help"
EXPORT = "📤 Export Excel"
ADMIN_HELP = "⚙️ Admin Help"


def main_menu(role: str) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=REPORT), KeyboardButton(text=MY_TICKETS)],
        [KeyboardButton(text=HELP)],
    ]
    if role in {"agent", "admin"}:
        rows.append([KeyboardButton(text=TEAM_HELP)])
    if role == "admin":
        rows.append([KeyboardButton(text=EXPORT), KeyboardButton(text=ADMIN_HELP)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Choose an action",
    )


def welcome_text(role: str) -> str:
    return (
        "Welcome to the issue bot.\n"
        f"Your role: {role.title()}.\n"
        "Choose an action below."
    )
