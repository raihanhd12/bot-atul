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
    pending_agent_replies: dict[int, int] = {}

    @router.callback_query(F.data.startswith("relay:reply:"))
    async def begin_agent_reply(query: CallbackQuery) -> None:
        if query.data is None:
            return
        number = int(query.data.rsplit(":", 1)[1])
        ticket = repository.get_ticket(number)
        role = repository.get_role(query.from_user.id)
        if ticket is None:
            await query.answer("Ticket not found.", show_alert=True)
            return
        if role != "admin" and ticket.assignee_id != query.from_user.id:
            await query.answer(
                "Only the assigned agent can reply.", show_alert=True
            )
            return
        if ticket.reporter_id == query.from_user.id:
            await query.answer(
                "This ticket is yours — no separate reporter to message.",
                show_alert=True,
            )
            return
        pending_agent_replies[query.from_user.id] = number
        await query.answer()
        if isinstance(query.message, Message):
            await query.message.answer(
                f"Replying to ticket #{number}. Send the next message, photo, "
                "or document."
            )

    @router.message(F.chat.type == "private")
    async def agent_reply(message: Message) -> None:
        if message.from_user is None:
            raise SkipHandler
        number = pending_agent_replies.get(message.from_user.id)
        if number is None:
            raise SkipHandler
        ticket = repository.get_ticket(number)
        role = repository.get_role(message.from_user.id)
        if ticket is None or (
            role != "admin" and ticket.assignee_id != message.from_user.id
        ):
            pending_agent_replies.pop(message.from_user.id, None)
            await message.answer("That ticket reply is no longer available.")
            return
        if ticket.reporter_id == message.from_user.id:
            pending_agent_replies.pop(message.from_user.id, None)
            await message.answer(
                "This ticket is yours — no separate reporter to message."
            )
            return
        bot = message.bot
        if bot is None:
            return
        try:
            await bot.send_message(
                chat_id=ticket.reporter_id,
                text=f"Reply for ticket #{ticket.number}:",
            )
            copied = await bot.copy_message(
                chat_id=ticket.reporter_id,
                from_chat_id=message.from_user.id,
                message_id=message.message_id,
            )
        except TelegramAPIError:
            pending_agent_replies.pop(message.from_user.id, None)
            failed_id = repository.record_message(
                ticket_number=ticket.number,
                direction="team_to_reporter",
                source_chat_id=message.from_user.id,
                source_message_id=message.message_id,
                destination_chat_id=ticket.reporter_id,
                destination_message_id=None,
                text=message.text or message.caption,
                delivery_status="failed",
            )
            await message.answer(
                "Delivery failed. Message saved.",
                reply_markup=retry_delivery(failed_id),
            )
            return
        pending_agent_replies.pop(message.from_user.id, None)
        repository.record_message(
            ticket_number=ticket.number,
            direction="team_to_reporter",
            source_chat_id=message.from_user.id,
            source_message_id=message.message_id,
            destination_chat_id=ticket.reporter_id,
            destination_message_id=int(copied.message_id),
            text=message.text or message.caption,
            delivery_status="sent",
        )
        await message.answer(f"Sent to reporter for ticket #{number}.")

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
            tickets[0],
            message.text or message.caption,
        )
        if tickets[0].assignee_id is None:
            await message.answer(
                f"Added to ticket #{tickets[0].number}. The assigned agent will "
                "receive it."
            )
        elif tickets[0].assignee_id == message.from_user.id:
            await message.answer(
                f"Saved on ticket #{tickets[0].number}."
            )
        elif failed_id is None:
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
            ticket,
            None,
        )
        pending_delivery = ticket.assignee_id is None
        await query.answer(
            f"Added to ticket #{number}."
            if failed_id is None or pending_delivery
            else "Delivery failed."
        )
        if isinstance(query.message, Message):
            await query.message.edit_text(
                f"Added to ticket #{number}."
                if failed_id is None or pending_delivery
                else "Delivery failed. Your message is saved.",
                reply_markup=(
                    retry_delivery(failed_id)
                    if failed_id is not None and not pending_delivery
                    else None
                ),
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
            relay_message.direction == "team_to_reporter"
            and (
                role == "admin"
                or (
                    role == "agent"
                    and ticket.assignee_id == query.from_user.id
                )
            )
        )
        if not allowed:
            await query.answer("Not allowed.", show_alert=True)
            return
        try:
            if relay_message.direction == "reporter_to_team":
                if ticket.assignee_id is None:
                    await query.answer(
                        "Ticket is not assigned yet.", show_alert=True
                    )
                    return
                await query.bot.send_message(
                    chat_id=ticket.assignee_id,
                    text=f"Update for ticket #{ticket.number}:",
                )
                copied = await query.bot.copy_message(
                    chat_id=ticket.assignee_id,
                    from_chat_id=relay_message.source_chat_id,
                    message_id=relay_message.source_message_id,
                )
                destination_chat_id = ticket.assignee_id
                destination_message_id = copied.message_id
            elif relay_message.relay_method == "text":
                sent = await query.bot.send_message(
                    ticket.reporter_id,
                    f"Reply for ticket #{ticket.number}:\n"
                    f"{relay_message.text or ''}",
                )
                destination_chat_id = ticket.reporter_id
                destination_message_id = sent.message_id
            else:
                await query.bot.send_message(
                    chat_id=ticket.reporter_id,
                    text=f"Reply for ticket #{ticket.number}:",
                )
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
    ticket: Ticket,
    text: str | None,
) -> int | None:
    if ticket.assignee_id is None:
        return repository.record_message(
            ticket_number=ticket.number,
            direction="reporter_to_team",
            source_chat_id=reporter_id,
            source_message_id=source_message_id,
            destination_chat_id=None,
            destination_message_id=None,
            text=text,
            delivery_status="pending",
        )
    # Self-owned tickets: store a note, do not echo the message back to the owner.
    if ticket.assignee_id == reporter_id:
        repository.record_message(
            ticket_number=ticket.number,
            direction="internal",
            source_chat_id=reporter_id,
            source_message_id=source_message_id,
            destination_chat_id=reporter_id,
            destination_message_id=source_message_id,
            text=text,
            delivery_status="sent",
        )
        return None
    try:
        await bot.send_message(
            chat_id=ticket.assignee_id,
            text=f"Update for ticket #{ticket.number}:",
        )
        delivered = await bot.copy_message(
            chat_id=ticket.assignee_id,
            from_chat_id=reporter_id,
            message_id=source_message_id,
        )
    except TelegramAPIError:
        return repository.record_message(
            ticket_number=ticket.number,
            direction="reporter_to_team",
            source_chat_id=reporter_id,
            source_message_id=source_message_id,
            destination_chat_id=ticket.assignee_id,
            destination_message_id=None,
            text=text,
            delivery_status="failed",
        )
    repository.record_message(
        ticket_number=ticket.number,
        direction="reporter_to_team",
        source_chat_id=reporter_id,
        source_message_id=source_message_id,
        destination_chat_id=ticket.assignee_id,
        destination_message_id=delivered.message_id,
        text=text,
        delivery_status="sent",
    )
    return None
