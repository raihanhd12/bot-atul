from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot_atul.db.repositories import Repository
from bot_atul.domain.permissions import Action, Role, allowed
from bot_atul.services.dashboard import safe_publish_dashboard
from bot_atul.services.tickets import IntakeSession, IntakeStep
from bot_atul.services.topics import create_ticket_topic
from bot_atul.telegram.keyboards import (
    action,
    choices,
    reporter_ticket_actions,
    review_actions,
)
from bot_atul.telegram.menu import REPORT

URGENCIES = ("Low", "Normal", "High", "Critical")


def build_intake_router(
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    timezone: ZoneInfo,
) -> Router:
    router = Router(name="intake")
    sessions: dict[int, IntakeSession] = {}

    @router.message((Command("new") | (F.text == REPORT)) & (F.chat.type == "private"))
    async def start(message: Message) -> None:
        if message.from_user is None:
            return
        role = repository.get_role(message.from_user.id)
        if not allowed(Role(role) if role else None, Action.SUBMIT):
            await message.answer("You are not approved to submit issues.")
            return
        sessions[message.from_user.id] = IntakeSession(
            message.from_user.id, tuple(repository.list_services())
        )
        await message.answer("What is the short issue title?")

    @router.message(F.chat.type == "private")
    async def receive(message: Message) -> None:
        if message.from_user is None:
            return
        session = sessions.get(message.from_user.id)
        if session is None:
            raise SkipHandler
        if session.step in {IntakeStep.TITLE, IntakeStep.DESCRIPTION} and message.text:
            try:
                session.answer(message.text)
            except ValueError as error:
                await message.answer(str(error))
                return
            if session.step is IntakeStep.SERVICE:
                await message.answer(
                    "Which service?",
                    reply_markup=choices("intake:service", session.services),
                )
            else:
                await message.answer(
                    "Description part added. Send more or finish.",
                    reply_markup=action(
                        "Description Complete", "intake:description_done"
                    ),
                )
            return
        if session.step is IntakeStep.ATTACHMENTS:
            if message.document:
                session.add_attachment(
                    "document",
                    message.document.file_id,
                    message.document.file_name,
                    message.caption,
                )
            elif message.photo:
                session.add_attachment(
                    "photo", message.photo[-1].file_id, None, message.caption
                )
            else:
                await message.answer(
                    "Send a photo/document or select Attachments Complete."
                )
                return
            await message.answer(
                "Attachment added.",
                reply_markup=action("Attachments Complete", "intake:attachments_done"),
            )

    @router.callback_query(F.data.startswith("intake:"))
    async def callback(query: CallbackQuery) -> None:
        if query.from_user is None or query.data is None:
            return
        session = sessions.get(query.from_user.id)
        if session is None:
            await query.answer("Start again with /new.", show_alert=True)
            return
        data = query.data
        try:
            if data.startswith("intake:service:"):
                session.answer(data.removeprefix("intake:service:"))
                await _edit(
                    query, "How urgent is it?", choices("intake:urgency", URGENCIES)
                )
            elif data.startswith("intake:urgency:"):
                session.answer(data.removeprefix("intake:urgency:"))
                await _edit(
                    query, "Describe the problem. You may send several messages."
                )
            elif data == "intake:description_done":
                session.complete_description()
                await _edit(
                    query,
                    "Send optional photos/documents, or finish this step.",
                    action("Attachments Complete", "intake:attachments_done"),
                )
            elif data == "intake:attachments_done":
                session.finish_attachments()
                await _edit(query, session.summary(), review_actions())
            elif data == "intake:confirm":
                bot = query.bot
                if bot is None:
                    return
                ticket = session.confirm(repository)
                await create_ticket_topic(bot, repository, team_group_id, ticket)
                await safe_publish_dashboard(
                    bot,
                    repository,
                    team_group_id,
                    dashboard_topic_id,
                    datetime.now(timezone),
                )
                sessions.pop(query.from_user.id, None)
                await _edit(
                    query,
                    f"Ticket #{ticket.number} submitted successfully.",
                    reporter_ticket_actions(ticket),
                )
            elif data == "intake:cancel":
                session.cancel()
                sessions.pop(query.from_user.id, None)
                await _edit(query, "Issue report cancelled.")
            await query.answer()
        except ValueError as error:
            await query.answer(str(error), show_alert=True)

    return router


async def _edit(
    query: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=reply_markup)
