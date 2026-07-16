from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery

from bot_atul.db.repositories import Repository, Ticket
from bot_atul.services.dashboard import safe_publish_dashboard
from bot_atul.services.topics import (
    create_agent_workspace,
    create_ticket_card,
    deliver_pending_reporter_messages,
)
from bot_atul.services.workflow import TicketWorkflow
from bot_atul.telegram.formatting import agent_workspace, ticket_card
from bot_atul.telegram.keyboards import (
    agent_ticket_actions,
    dashboard_ticket_actions,
    fix_confirmation,
)


def build_ticket_router(
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    timezone: ZoneInfo,
) -> Router:
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
                current = repository.get_ticket(number)
                if current is None:
                    raise ValueError(f"Unknown ticket: {number}")
                if repository.get_role(query.from_user.id) not in {"agent", "admin"}:
                    raise PermissionError("Agent access required.")
                if current.assignee_id not in {None, query.from_user.id}:
                    raise ValueError("Ticket is already assigned.")
                try:
                    await create_agent_workspace(
                        bot, repository, current, query.from_user.id
                    )
                except TelegramAPIError:
                    await query.answer(
                        "Open this bot in private, press Start, then assign again.",
                        show_alert=True,
                    )
                    return
                ticket = workflow.assign_to_me(number, query.from_user.id)
                await deliver_pending_reporter_messages(bot, repository, ticket)
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

        await _refresh_ticket(
            bot,
            repository,
            team_group_id,
            dashboard_topic_id,
            ticket,
        )
        await safe_publish_dashboard(
            bot,
            repository,
            team_group_id,
            dashboard_topic_id,
            datetime.now(timezone),
        )
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
    bot: Bot,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    ticket: Ticket,
) -> None:
    dashboard_card = repository.get_dashboard_card(ticket.number)
    if dashboard_card is None:
        dashboard_card = await create_ticket_card(
            bot,
            repository,
            team_group_id,
            dashboard_topic_id,
            ticket,
        )
    if dashboard_card is not None:
        await bot.edit_message_text(
            chat_id=team_group_id,
            message_id=dashboard_card,
            text=ticket_card(ticket),
            reply_markup=dashboard_ticket_actions(ticket),
        )
    workspace = repository.get_agent_workspace(ticket.number)
    if workspace is not None:
        await bot.edit_message_text(
            chat_id=workspace.agent_id,
            message_id=workspace.message_id,
            text=agent_workspace(ticket)[:4_096],
            reply_markup=agent_ticket_actions(ticket),
        )
