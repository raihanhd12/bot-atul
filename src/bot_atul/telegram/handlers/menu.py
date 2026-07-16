import sqlite3
from dataclasses import dataclass
from datetime import time
from typing import Literal

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot_atul.db.repositories import Repository, UserRecord
from bot_atul.telegram.handlers.intake import begin_intake
from bot_atul.telegram.keyboards import admin_open_ticket_actions
from bot_atul.telegram.menu import (
    admin_menu,
    back_button,
    main_menu,
    service_actions,
    service_cancel,
    service_disable_confirmation,
    service_menu,
    user_menu,
    welcome_text,
)

HELP_TEXT = (
    "Create an issue with Report Issue. Use My Tickets to view your active "
    "tickets. After submit, the bot auto-assigns the ticket to you and opens "
    "a private workspace. The group dashboard is view-only."
)
TEAM_HELP_TEXT = (
    "Report opens a private workspace for you — no Assign to Me in the group. "
    "Use Start Work, Mark Fixed, and Close from that private chat. "
    "Admins can close any open ticket from Admin Panel → Open Tickets."
)
HINTS = {
    "user_add": "/user_add <telegram_id> <agent|admin>",
    "user_disable": "/user_disable <telegram_id>",
}


@dataclass
class ServiceSession:
    mode: Literal["selected", "add", "rename"]
    service: str | None = None


SERVICE_SESSIONS: dict[int, ServiceSession] = {}


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
            SERVICE_SESSIONS.pop(query.from_user.id, None)
            await _edit(
                query,
                "⚙️ Admin Panel\n\nView the current configuration or choose an action.",
                admin_menu(),
            )
        elif action == "services":
            SERVICE_SESSIONS.pop(query.from_user.id, None)
            await _show_services(query, repository)
        elif action.startswith("service:"):
            await _service_callback(query, repository, action.removeprefix("service:"))
        elif action == "team":
            await _edit(
                query,
                "👥 Team Members\n\n"
                + _format_users(repository.list_users(("admin", "agent"))),
                user_menu(),
            )
        elif action == "open_tickets":
            closable = repository.closable_tickets()
            text = (
                "\n".join(
                    f"#{ticket.number} · {ticket.status} · "
                    f"{ticket.service_name} · {ticket.title}"
                    for ticket in closable
                )
                if closable
                else "No open tickets."
            )
            await _edit(
                query,
                f"📂 Open Tickets\n\n{text}",
                admin_open_ticket_actions(closable),
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

    @router.message((F.chat.type == "private") & F.text)
    async def service_name(message: Message) -> None:
        if message.from_user is None or message.text is None:
            raise SkipHandler
        session = SERVICE_SESSIONS.get(message.from_user.id)
        if session is None or session.mode not in {"add", "rename"}:
            raise SkipHandler
        try:
            response = apply_service_name(
                repository, message.from_user.id, session, message.text
            )
        except (PermissionError, ValueError) as error:
            await message.answer(str(error), reply_markup=service_cancel())
            return
        SERVICE_SESSIONS.pop(message.from_user.id, None)
        services = repository.list_services()
        await message.answer(
            f"{response}\n\n{_services_text(services)}",
            reply_markup=service_menu(services),
        )

    return router


def apply_service_name(
    repository: Repository,
    actor_id: int,
    session: ServiceSession,
    raw_name: str,
) -> str:
    if repository.get_role(actor_id) != "admin":
        raise PermissionError("Not allowed.")
    name = raw_name.strip()
    if not name:
        raise ValueError("Service name cannot be blank.")
    if len(name) > 64:
        raise ValueError("Service name must be 64 characters or fewer.")
    try:
        if session.mode == "add":
            repository.add_service(name)
            details = f"add:{name}"
            response = f"Service {name} added."
        elif session.mode == "rename" and session.service is not None:
            if not repository.rename_service(session.service, name):
                raise ValueError("That service changed. Open Services and try again.")
            details = f"rename:{session.service}->{name}"
            response = f"Service {session.service} renamed to {name}."
        else:
            raise ValueError("Service action expired. Open Services and try again.")
    except sqlite3.IntegrityError as error:
        raise ValueError(f"Service {name} already exists.") from error
    repository.record_audit(actor_id, "admin_service", details)
    return response


async def _service_callback(
    query: CallbackQuery, repository: Repository, action: str
) -> None:
    user_id = query.from_user.id
    services = repository.list_services()
    if action == "add":
        SERVICE_SESSIONS[user_id] = ServiceSession("add")
        await _edit(
            query,
            "Send the new service name.\n\nNames may contain spaces.",
            service_cancel(),
        )
        return
    if action == "cancel":
        SERVICE_SESSIONS.pop(user_id, None)
        await _show_services(query, repository)
        return
    if action.startswith("select:"):
        try:
            selected = services[int(action.removeprefix("select:"))]
        except (ValueError, IndexError):
            await query.answer(
                "Service list changed. Please choose again.", show_alert=True
            )
            await _show_services(query, repository)
            return
        SERVICE_SESSIONS[user_id] = ServiceSession("selected", selected)
        await _show_service(query, repository, selected)
        return

    session = SERVICE_SESSIONS.get(user_id)
    if session is None or session.service is None or session.service not in services:
        SERVICE_SESSIONS.pop(user_id, None)
        await query.answer("Service selection expired.", show_alert=True)
        await _show_services(query, repository)
        return
    name = session.service
    if action == "rename":
        session.mode = "rename"
        await _edit(
            query,
            f"Send the new name for {name}.\n\nNames may contain spaces.",
            service_cancel(),
        )
    elif action in {"move_up", "move_down"}:
        offset = -1 if action == "move_up" else 1
        if repository.move_service_by(name, offset):
            repository.record_audit(user_id, "admin_service", f"{action}:{name}")
        await _show_services(query, repository)
    elif action == "disable":
        await _edit(
            query,
            f"Disable {name}?\n\nIt will no longer appear in new issue reports.",
            service_disable_confirmation(),
        )
    elif action == "disable_cancel":
        await _show_service(query, repository, name)
    elif action == "disable_confirm":
        if not repository.disable_service(name):
            await query.answer("Service selection expired.", show_alert=True)
        else:
            repository.record_audit(user_id, "admin_service", f"disable:{name}")
        SERVICE_SESSIONS.pop(user_id, None)
        await _show_services(query, repository)


async def _show_services(query: CallbackQuery, repository: Repository) -> None:
    services = repository.list_services()
    await _edit(query, _services_text(services), service_menu(services))


async def _show_service(
    query: CallbackQuery, repository: Repository, name: str
) -> None:
    services = repository.list_services()
    if name not in services:
        SERVICE_SESSIONS.pop(query.from_user.id, None)
        await _show_services(query, repository)
        return
    await _edit(
        query,
        f"🧩 Service\n\n{name}\n\nChoose an action.",
        service_actions(services.index(name), len(services)),
    )


def _services_text(services: list[str]) -> str:
    text = "\n".join(f"{index}. {name}" for index, name in enumerate(services, start=1))
    return f"🧩 Active Services\n\n{text or 'No active services.'}"


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
