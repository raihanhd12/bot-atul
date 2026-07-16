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
    hide_topic_attachments,
    publish_topic_attachment,
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
        parts = query.data.split(":")
        action = parts[1] if len(parts) > 1 else ""
        actor_id = query.from_user.id

        if action == "file" and len(parts) == 4:
            number = int(parts[2])
            attachment_id = int(parts[3])
            await _open_topic_file(
                query,
                bot,
                repository,
                team_group_id,
                dashboard_topic_id,
                number,
                attachment_id,
            )
            return

        if action in {"detail", "summary", "clearfiles"} and len(parts) >= 3:
            number = int(parts[2])
            await _toggle_topic_detail(
                query,
                bot,
                repository,
                team_group_id,
                dashboard_topic_id,
                number,
                detailed=action != "summary",
                clear_files=action in {"summary", "clearfiles"},
                collapse=action == "summary",
            )
            return

        if len(parts) < 3:
            await query.answer("Unknown action.", show_alert=True)
            return
        number = int(parts[2])

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


async def _open_topic_file(
    query: CallbackQuery,
    bot: Bot,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    number: int,
    attachment_id: int,
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
    # Keep details expanded while browsing files.
    with suppress(TelegramAPIError):
        await render_dashboard_card(
            bot, repository, team_group_id, ticket, detailed=True
        )
    ok = await publish_topic_attachment(
        bot,
        repository,
        team_group_id,
        dashboard_topic_id,
        ticket,
        attachment_id,
        replace_existing=True,
    )
    if ok:
        await query.answer("File preview ready")
    else:
        await query.answer("Could not open that file.", show_alert=True)


async def _toggle_topic_detail(
    query: CallbackQuery,
    bot: Bot,
    repository: Repository,
    team_group_id: int,
    dashboard_topic_id: int,
    number: int,
    *,
    detailed: bool,
    clear_files: bool = False,
    collapse: bool = False,
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

    # Clear preview: only remove temporary file messages; keep the card as-is.
    if clear_files and not collapse:
        removed = await hide_topic_attachments(
            bot, repository, team_group_id, ticket
        )
        await query.answer(
            f"Cleared {removed} preview(s)" if removed else "No preview open"
        )
        return

    show_detailed = detailed and not collapse
    try:
        await render_dashboard_card(
            bot, repository, team_group_id, ticket, detailed=show_detailed
        )
    except TelegramAPIError:
        await query.answer("Could not update the topic card.", show_alert=True)
        return

    if clear_files and collapse:
        removed = await hide_topic_attachments(
            bot, repository, team_group_id, ticket
        )
        await query.answer(
            f"Hidden · cleared {removed} preview(s)" if removed else "Summary"
        )
        return

    # View Details only expands the card + file buttons (no auto bulk dump).
    count = repository.count_attachments(number)
    if count:
        await query.answer(f"Details · tap a file ({count})")
    else:
        await query.answer("Details")


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
