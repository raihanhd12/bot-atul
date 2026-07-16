from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot_atul.db.repositories import Repository, Ticket
from bot_atul.domain.permissions import Action, Role, allowed
from bot_atul.services.relay import RelayService
from bot_atul.telegram.keyboards import retry_delivery


def build_relay_router(repository: Repository, team_group_id: int) -> Router:
    router = Router(name="relay")
    service = RelayService(repository)
    pending: dict[int, int] = {}

    @router.message(F.chat.type == "private")
    async def reporter_message(message: Message) -> None:
        if message.from_user is None:
            raise SkipHandler
        role = repository.get_role(message.from_user.id)
        if not allowed(Role(role) if role else None, Action.SUBMIT):
            raise SkipHandler
        bot = message.bot
        if bot is None:
            return
        tickets = service.active_for_reporter(message.from_user.id)
        if not tickets:
            await message.answer(
                "You have no active ticket. Use /new to report an issue."
            )
            return
        if len(tickets) > 1:
            pending[message.from_user.id] = message.message_id
            await message.answer(
                "Which ticket should receive this message?",
                reply_markup=_ticket_choices(tickets),
            )
            return
        failed_id = await _relay_reporter_message(
            bot,
            repository,
            message.from_user.id,
            message.message_id,
            team_group_id,
            tickets[0],
            message.text or message.caption,
        )
        if failed_id is None:
            await message.answer(f"Added to ticket #{tickets[0].number}.")
        else:
            await message.answer(
                "Delivery failed. Your message is saved.",
                reply_markup=retry_delivery(failed_id),
            )

    @router.callback_query(F.data.startswith("relay:ticket:"))
    async def select_ticket(query: CallbackQuery) -> None:
        if query.data is None:
            return
        source_message_id = pending.pop(query.from_user.id, None)
        if source_message_id is None:
            await query.answer("That message has expired.", show_alert=True)
            return
        number = int(query.data.rsplit(":", 1)[1])
        ticket = service.reporter_destination(query.from_user.id, number)
        bot = query.bot
        if bot is None:
            return
        failed_id = await _relay_reporter_message(
            bot,
            repository,
            query.from_user.id,
            source_message_id,
            team_group_id,
            ticket,
            None,
        )
        await query.answer(
            f"Added to ticket #{number}." if failed_id is None else "Delivery failed."
        )
        if isinstance(query.message, Message):
            await query.message.edit_text(
                f"Added to ticket #{number}."
                if failed_id is None
                else "Delivery failed. Your message is saved.",
                reply_markup=retry_delivery(failed_id) if failed_id else None,
            )

    @router.callback_query(F.data.startswith("relay:retry:"))
    async def retry(query: CallbackQuery) -> None:
        if query.data is None or query.bot is None:
            return
        message_id = int(query.data.rsplit(":", 1)[1])
        relay_message = repository.get_relay_message(message_id)
        if relay_message is None:
            await query.answer("Delivery record not found.", show_alert=True)
            return
        ticket = repository.get_ticket(relay_message.ticket_number)
        if ticket is None:
            await query.answer("Ticket not found.", show_alert=True)
            return
        role = repository.get_role(query.from_user.id)
        allowed = (
            relay_message.direction == "reporter_to_team"
            and ticket.reporter_id == query.from_user.id
        ) or (
            relay_message.direction == "team_to_reporter" and role in {"agent", "admin"}
        )
        if not allowed:
            await query.answer("Not allowed.", show_alert=True)
            return
        try:
            if relay_message.direction == "reporter_to_team":
                copied = await query.bot.copy_message(
                    chat_id=team_group_id,
                    from_chat_id=relay_message.source_chat_id,
                    message_id=relay_message.source_message_id,
                    message_thread_id=ticket.topic_id,
                )
                destination_chat_id = team_group_id
                destination_message_id = copied.message_id
            elif relay_message.relay_method == "text":
                sent = await query.bot.send_message(
                    ticket.reporter_id, relay_message.text or ""
                )
                destination_chat_id = ticket.reporter_id
                destination_message_id = sent.message_id
            else:
                copied = await query.bot.copy_message(
                    chat_id=ticket.reporter_id,
                    from_chat_id=relay_message.source_chat_id,
                    message_id=relay_message.source_message_id,
                )
                destination_chat_id = ticket.reporter_id
                destination_message_id = copied.message_id
        except TelegramAPIError:
            await query.answer("Delivery failed again.", show_alert=True)
            return
        repository.mark_message_sent(
            message_id, destination_chat_id, destination_message_id
        )
        await query.answer("Delivered.")
        if isinstance(query.message, Message):
            await query.message.edit_reply_markup(reply_markup=None)

    @router.message(F.chat.id == team_group_id)
    async def team_message(message: Message) -> None:
        if message.from_user is None or message.message_thread_id is None:
            raise SkipHandler
        bot = message.bot
        if bot is None:
            return
        explicit = bool(message.text and message.text.startswith("/reply"))
        reply_id = (
            message.reply_to_message.message_id if message.reply_to_message else None
        )
        try:
            ticket = service.team_destination(
                message.from_user.id,
                topic_id=message.message_thread_id,
                reply_to_message_id=reply_id,
                explicit=explicit,
            )
        except (PermissionError, ValueError):
            raise SkipHandler from None

        text = (message.text or "").removeprefix("/reply").strip() if explicit else None
        if explicit and not text:
            await message.reply("Usage: /reply <message>")
            return
        relay_method = "text" if explicit else "copy"
        try:
            if explicit:
                sent = await bot.send_message(ticket.reporter_id, text or "")
                destination_message_id = sent.message_id
            else:
                copied = await bot.copy_message(
                    chat_id=ticket.reporter_id,
                    from_chat_id=team_group_id,
                    message_id=message.message_id,
                )
                destination_message_id = copied.message_id
        except TelegramAPIError:
            failed_id = repository.record_message(
                ticket_number=ticket.number,
                direction="team_to_reporter",
                source_chat_id=team_group_id,
                source_message_id=message.message_id,
                destination_chat_id=ticket.reporter_id,
                destination_message_id=None,
                text=text or message.text or message.caption,
                relay_method=relay_method,
                delivery_status="failed",
            )
            await message.reply(
                "Delivery failed. Message saved.",
                reply_markup=retry_delivery(failed_id),
            )
            return
        repository.record_message(
            ticket_number=ticket.number,
            direction="team_to_reporter",
            source_chat_id=team_group_id,
            source_message_id=message.message_id,
            destination_chat_id=ticket.reporter_id,
            destination_message_id=destination_message_id,
            text=text or message.text or message.caption,
            relay_method=relay_method,
            delivery_status="sent",
        )
        await message.reply("Sent to reporter.")

    return router


def _ticket_choices(tickets: list[Ticket]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"#{ticket.number} · {ticket.title}",
                    callback_data=f"relay:ticket:{ticket.number}",
                )
            ]
            for ticket in tickets
        ]
    )


async def _relay_reporter_message(
    bot: Bot,
    repository: Repository,
    reporter_id: int,
    source_message_id: int,
    team_group_id: int,
    ticket: Ticket,
    text: str | None,
) -> int | None:
    try:
        delivered = await bot.copy_message(
            chat_id=team_group_id,
            from_chat_id=reporter_id,
            message_id=source_message_id,
            message_thread_id=ticket.topic_id,
        )
    except TelegramAPIError:
        return repository.record_message(
            ticket_number=ticket.number,
            direction="reporter_to_team",
            source_chat_id=reporter_id,
            source_message_id=source_message_id,
            destination_chat_id=team_group_id,
            destination_message_id=None,
            text=text,
            delivery_status="failed",
        )
    repository.record_message(
        ticket_number=ticket.number,
        direction="reporter_to_team",
        source_chat_id=reporter_id,
        source_message_id=source_message_id,
        destination_chat_id=team_group_id,
        destination_message_id=delivered.message_id,
        text=text,
        delivery_status="sent",
    )
    return None
