from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot_atul.db.repositories import Repository, Ticket
from bot_atul.services.relay import RelayService


def build_relay_router(repository: Repository, team_group_id: int) -> Router:
    router = Router(name="relay")
    service = RelayService(repository)
    pending: dict[int, int] = {}

    @router.message(F.chat.type == "private")
    async def reporter_message(message: Message) -> None:
        if (
            message.from_user is None
            or repository.get_role(message.from_user.id) != "reporter"
        ):
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
        await _relay_reporter_message(
            bot,
            repository,
            message.from_user.id,
            message.message_id,
            team_group_id,
            tickets[0],
            message.text or message.caption,
        )
        await message.answer(f"Added to ticket #{tickets[0].number}.")

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
        await _relay_reporter_message(
            bot,
            repository,
            query.from_user.id,
            source_message_id,
            team_group_id,
            ticket,
            None,
        )
        await query.answer(f"Added to ticket #{number}.")
        if isinstance(query.message, Message):
            await query.message.edit_text(f"Added to ticket #{number}.")

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

        if explicit:
            text = (message.text or "").removeprefix("/reply").strip()
            if not text:
                await message.reply("Usage: /reply <message>")
                return
            delivered = await bot.send_message(ticket.reporter_id, text)
            destination_message_id = delivered.message_id
        else:
            copied = await bot.copy_message(
                chat_id=ticket.reporter_id,
                from_chat_id=team_group_id,
                message_id=message.message_id,
            )
            destination_message_id = copied.message_id
        repository.record_message(
            ticket_number=ticket.number,
            direction="team_to_reporter",
            source_chat_id=team_group_id,
            source_message_id=message.message_id,
            destination_chat_id=ticket.reporter_id,
            destination_message_id=destination_message_id,
            text=message.text or message.caption,
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
) -> None:
    delivered = await bot.copy_message(
        chat_id=team_group_id,
        from_chat_id=reporter_id,
        message_id=source_message_id,
        message_thread_id=ticket.topic_id,
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
