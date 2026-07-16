from contextlib import suppress
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
    publish_topic_attachments,
    render_dashboard_card,
    ticket_names,
)
from bot_atul.services.workflow import TicketWorkflow
from bot_atul.telegram.formatting import agent_workspace
from bot_atul.telegram.keyboards import agent_ticket_actions, fix_confirmation


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
        actor_id = query.from_user.id

        if action in {"detail", "summary", "files"}:
            await _toggle_topic_detail(
                query,
                bot,
                repository,
                team_group_id,
                dashboard_topic_id,
                number,
                detailed=action != "summary",
                publish_files=action in {"detail", "files"},
            )
            return

        try:
            if action == "assign":
                # Legacy unassigned tickets only; normal reports auto-assign.
                current = repository.get_ticket(number)
                if current is None:
                    raise ValueError(f"Unknown ticket: {number}")
                if repository.get_role(actor_id) not in {"agent", "admin"}:
                    raise PermissionError("Agent access required.")
                if current.assignee_id not in {None, actor_id}:
                    raise ValueError("Ticket is already assigned.")
                try:
                    await create_agent_workspace(bot, repository, current, actor_id)
                except TelegramAPIError:
                    await query.answer(
                        "Open this bot in private, press Start, then try again.",
                        show_alert=True,
                    )
                    return
                ticket = workflow.assign_to_me(number, actor_id)
                await deliver_pending_reporter_messages(bot, repository, ticket)
            elif action == "cancel":
                ticket = workflow.cancel(number, actor_id)
            elif action in {"confirm", "reject"}:
                ticket = workflow.confirm_fix(
                    number, actor_id, fixed=action == "confirm"
                )
            elif action == "fix":
                ticket = workflow.mark_fixed(number, actor_id)
            else:
                ticket = workflow.change_status(number, actor_id, action)
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
        # Never DM the actor about their own action (self-owned tickets).
        if ticket.reporter_id != actor_id:
            if action == "fix" and ticket.status == "Fixed":
                await bot.send_message(
                    ticket.reporter_id,
                    f"Ticket #{number} was marked Fixed. Is the problem solved?",
                    reply_markup=fix_confirmation(number),
                )
            elif action not in {"assign", "confirm", "reject", "fix"}:
                await bot.send_message(
                    ticket.reporter_id,
                    f"Ticket #{number} is now {ticket.status}.",
                )
            elif action == "fix" and ticket.status == "Closed":
                await bot.send_message(
                    ticket.reporter_id,
                    f"Ticket #{number} is now Closed.",
                )
        await query.answer(f"Ticket #{number}: {ticket.status}")

    return router


async def _toggle_topic_detail(
    query: CallbackQuery,
    bot: Bot,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    number: int,
    *,
    detailed: bool,
    publish_files: bool = False,
) -> None:
    if repository.get_role(query.from_user.id) not in {"agent", "admin"}:
        await query.answer("Team access required.", show_alert=True)
        return
    ticket = repository.get_ticket(number)
    if ticket is None:
        await query.answer("Ticket not found.", show_alert=True)
        return
    if repository.get_dashboard_card(number) is None:
        await create_ticket_card(
            bot, repository, team_group_id, dashboard_topic_id, ticket
        )
    try:
        await render_dashboard_card(
            bot, repository, team_group_id, ticket, detailed=detailed
        )
    except TelegramAPIError:
        await query.answer("Could not update the topic card.", show_alert=True)
        return
    posted = 0
    if publish_files:
        posted = await publish_topic_attachments(
            bot, repository, team_group_id, dashboard_topic_id, ticket
        )
    if publish_files and repository.count_attachments(number):
        if posted:
            await query.answer(f"Posted {posted} file(s) in the topic")
        else:
            await query.answer("Attachments already in the topic")
    else:
        await query.answer("Details" if detailed else "Summary")


async def _refresh_ticket(
    bot: Bot,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    ticket: Ticket,
) -> None:
    dashboard_card = repository.get_dashboard_card(ticket.number)
    if dashboard_card is None:
        await create_ticket_card(
            bot,
            repository,
            team_group_id,
            dashboard_topic_id,
            ticket,
        )
    else:
        with suppress(TelegramAPIError):
            await render_dashboard_card(
                bot, repository, team_group_id, ticket, detailed=False
            )
    workspace = repository.get_agent_workspace(ticket.number)
    if workspace is not None:
        names = await ticket_names(bot, repository, ticket)
        attachments = repository.list_attachments(ticket.number)
        with suppress(TelegramAPIError):
            await bot.edit_message_text(
                chat_id=workspace.agent_id,
                message_id=workspace.message_id,
                text=agent_workspace(
                    ticket, names=names, attachments=attachments
                )[:4_096],
                reply_markup=agent_ticket_actions(ticket),
            )
