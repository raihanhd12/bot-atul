from datetime import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot_atul.db.repositories import Repository, UserRecord
from bot_atul.telegram.handlers.intake import begin_intake
from bot_atul.telegram.menu import (
    admin_menu,
    back_button,
    main_menu,
    service_menu,
    user_menu,
    welcome_text,
)

HELP_TEXT = (
    "Create an issue with Report Issue. Use My Tickets to view your active "
    "reports. The bot will notify you about replies and status changes."
)
TEAM_HELP_TEXT = (
    "In a ticket topic, reply directly to a relayed reporter message or use "
    "/reply <message>. Use the ticket buttons to assign and update status."
)
HINTS = {
    "user_add": "/user_add <telegram_id> <reporter|agent|admin>",
    "user_disable": "/user_disable <telegram_id>",
    "service_add": "/service_add <name>",
    "service_rename": "/service_rename <old> <new>",
    "service_disable": "/service_disable <name>",
    "service_move": "/service_move <name> <position>",
}


def build_menu_router(repository: Repository, reminder_time: time) -> Router:
    router = Router(name="menu")

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        if message.from_user is None:
            return
        role = repository.get_role(message.from_user.id)
        if role is None:
            await message.answer(
                "You are not approved yet. Ask an admin to add your Telegram user ID."
            )
            return
        repository.remember_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
        await message.answer(welcome_text(role), reply_markup=main_menu(role))

    @router.callback_query(F.data.startswith("menu:"))
    async def menu_callback(query: CallbackQuery) -> None:
        if query.data is None:
            return
        role = repository.get_role(query.from_user.id)
        if role is None:
            await query.answer("You are not approved.", show_alert=True)
            return
        action = query.data.removeprefix("menu:")
        if action == "home":
            await _edit(query, welcome_text(role), main_menu(role))
        elif action == "report":
            try:
                begin_intake(repository, query.from_user.id)
            except PermissionError as error:
                await query.answer(str(error), show_alert=True)
                return
            await _edit(query, "What is the short issue title?")
        elif action == "tickets":
            tickets = repository.active_tickets(query.from_user.id)
            text = (
                "\n".join(
                    f"#{ticket.number} · {ticket.status} · "
                    f"{ticket.service_name} · {ticket.title}"
                    for ticket in tickets
                )
                if tickets
                else "You have no active tickets."
            )
            await _edit(query, f"📋 My Active Tickets\n\n{text}", back_button())
        elif action == "help":
            await _edit(query, f"❓ Help\n\n{HELP_TEXT}", back_button())
        elif action == "team_help" and role in {"agent", "admin"}:
            await _edit(query, f"👥 Team Help\n\n{TEAM_HELP_TEXT}", back_button())
        await query.answer()

    @router.callback_query(F.data.startswith("admin:"))
    async def admin_callback(query: CallbackQuery) -> None:
        if query.data is None:
            return
        if repository.get_role(query.from_user.id) != "admin":
            await query.answer("Not allowed.", show_alert=True)
            return
        action = query.data.removeprefix("admin:")
        if action == "home":
            await _edit(
                query,
                "⚙️ Admin Panel\n\nView the current configuration or choose an action.",
                admin_menu(),
            )
        elif action == "services":
            services = repository.list_services()
            text = "\n".join(
                f"{index}. {name}" for index, name in enumerate(services, start=1)
            )
            await _edit(
                query,
                f"🧩 Active Services\n\n{text or 'No active services.'}",
                service_menu(),
            )
        elif action == "team":
            await _edit(
                query,
                "👥 Team Members\n\n"
                + _format_users(repository.list_users(("admin", "agent"))),
                user_menu(),
            )
        elif action == "reporters":
            await _edit(
                query,
                "👤 Reporters\n\n"
                + _format_users(repository.list_users(("reporter",))),
                user_menu(),
            )
        elif action == "reminder":
            await _edit(
                query,
                "⏰ Reminder Schedule\n\n"
                f"Monday–Friday at {reminder_time.strftime('%H:%M')}.\n"
                "The bot sends a reminder only when unresolved tickets exist.\n\n"
                "Change REMINDER_TIME in .env and restart the bot to update it.",
                back_button("admin:home"),
            )
        elif action.startswith("hint:"):
            command = action.removeprefix("hint:")
            await query.answer(
                f"Send this command:\n{HINTS.get(command, command)}",
                show_alert=True,
            )
            return
        await query.answer()

    return router


def _format_users(users: list[UserRecord]) -> str:
    if not users:
        return "No users found."
    lines = []
    for user in users:
        name = user.display_name or (
            f"@{user.username}" if user.username else "Not started yet"
        )
        username = f" · @{user.username}" if user.username else ""
        lines.append(
            f"• {name}{username}\n  ID: {user.telegram_id} · {user.role.title()}"
        )
    return "\n".join(lines)


async def _edit(
    query: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=reply_markup)
