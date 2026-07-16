from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from bot_atul.db.repositories import Repository, Ticket
from bot_atul.services.workflow import TicketWorkflow
from bot_atul.telegram.formatting import ticket_card, topic_title
from bot_atul.telegram.keyboards import fix_confirmation, ticket_actions


def build_ticket_router(repository: Repository, team_group_id: int) -> Router:
    router = Router(name="tickets")
    workflow = TicketWorkflow(repository)

    @router.callback_query(F.data.startswith("ticket:"))
    async def ticket_action(query: CallbackQuery) -> None:
        if query.data is None:
            return
        bot = query.bot
        if bot is None:
            return
        _, action, number_text = query.data.split(":", 2)
        number = int(number_text)
        try:
            if action == "assign":
                ticket = workflow.assign_to_me(number, query.from_user.id)
            elif action == "cancel":
                ticket = workflow.cancel(number, query.from_user.id)
            elif action in {"confirm", "reject"}:
                ticket = workflow.confirm_fix(
                    number, query.from_user.id, fixed=action == "confirm"
                )
            else:
                ticket = workflow.change_status(number, query.from_user.id, action)
        except (PermissionError, ValueError) as error:
            await query.answer(str(error), show_alert=True)
            return

        await _refresh_ticket(bot, repository, team_group_id, ticket)
        if action == "fix":
            await bot.send_message(
                ticket.reporter_id,
                f"Ticket #{number} was marked Fixed. Is the problem solved?",
                reply_markup=fix_confirmation(number),
            )
        elif action not in {"assign", "confirm", "reject"}:
            await bot.send_message(
                ticket.reporter_id, f"Ticket #{number} is now {ticket.status}."
            )
        await query.answer(f"Ticket #{number}: {ticket.status}")

    return router


async def _refresh_ticket(
    bot: Bot, repository: Repository, team_group_id: int, ticket: Ticket
) -> None:
    if ticket.topic_id is None or ticket.card_message_id is None:
        return
    await bot.edit_forum_topic(
        chat_id=team_group_id,
        message_thread_id=ticket.topic_id,
        name=topic_title(ticket),
    )
    await bot.edit_message_text(
        chat_id=team_group_id,
        message_id=ticket.card_message_id,
        text=ticket_card(ticket),
        reply_markup=ticket_actions(ticket),
    )
