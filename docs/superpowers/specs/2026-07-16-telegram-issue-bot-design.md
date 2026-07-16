# Telegram Issue Bot Design

Date: 2026-07-16
Status: Approved design

## Purpose

Build a private Telegram issue-management bot for a small team. Approved users
describe issues in the bot's direct messages. Each issue becomes a dedicated
topic in a private Telegram forum group, where approved agents can discuss,
reply to the reporter, assign work, and update status. The bot publishes a
daily unresolved-issue digest and lets admins export ticket data to Excel.

## Goals

- Keep all reporter interaction in the bot's private chat.
- Give every issue an isolated, linkable team topic.
- Let agents reply to reporters without exposing private team discussion.
- Make unresolved work easy to scan each workday.
- Maintain an auditable ticket history and accurate Excel export.
- Run reliably on an always-on office computer with minimal maintenance.

## Non-goals for Version 1

- Public access or anonymous issue submission
- A web dashboard
- AI classification or summarization
- SLA automation
- CRM or help-desk integrations
- Multiple Telegram support groups

## Users and Permissions

Access is controlled with immutable numeric Telegram user IDs. Usernames and
display names are labels only.

- **Reporter:** An allowlisted user who can create tickets, add information,
  receive replies and status notifications, cancel an Open and unassigned
  ticket, and confirm or reject a proposed fix.
- **Agent:** An allowlisted team member who can view group topics, assign
  tickets, reply to reporters, and change ticket status.
- **Admin:** An agent who can also manage allowlists and services, change
  configuration, refresh the dashboard, and export Excel workbooks.

Every command, callback, and relayed message must re-check the actor's role.

## Technical Architecture

The service uses Python, aiogram, SQLite, and Docker. Telegram long polling
avoids exposing an inbound port on the office network. A single bot process is
appropriate for the expected load of at most 50 users and roughly 20 new
issues per day.

SQLite stores application state in a mounted Docker volume. Docker restarts
the service after a crash or host reboot. The office computer must remain
powered on, connected, and configured not to sleep. The container remains
portable to a VPS if hosting requirements change.

Environment configuration contains the bot token, forum group ID, dashboard
topic ID, Asia/Jakarta timezone, initial admin IDs, database path, and backup
path. Secrets are never committed.

## Reporter Intake

An approved reporter selects **Report an Issue** or sends `/new`. The bot asks
one guided question at a time:

1. Short title
2. Service
3. Urgency
4. Detailed description
5. Optional photos or documents
6. Review and confirmation

The description step accepts multiple consecutive text messages. The reporter
selects **Description Complete** when finished. The bot stores the combined
UTF-8 text without shortening it. Telegram messages have a platform length
limit, so a long description is displayed in the team topic as numbered,
ordered messages rather than being truncated.

Services initially available are:

- AI-ML
- AI-Agents
- AI-Intelligence
- AI-Media

Exactly one service is required per ticket. Admins may add, rename, disable,
or reorder services. Historical tickets retain the service label recorded at
submission time.

Urgency choices are Low, Normal, High, and Critical. Normal is the default.
After confirmation, the bot assigns a sequential ticket number and sends the
reporter a receipt with the current status and **Add Information** and
**Cancel Ticket** actions. Cancellation is available only while the ticket is
Open and unassigned. It changes the ticket to Closed with the audited closure
reason `Reporter cancelled`.

If a reporter has one active ticket, subsequent free-form DM messages and
attachments are routed to it. If the reporter has multiple active tickets,
the bot asks which ticket should receive the new information.

## Team Topic Workflow

Each confirmed ticket creates one topic in the private forum group. The topic
title follows this form:

`#1042 · AI-Agents · Login problem · Open`

The bot's first topic message is a ticket card containing the reporter,
service, urgency, description, attachments, creation time, current age,
assignee, status, and last update. It exposes these controls as appropriate to
the current state and actor:

- Assign to Me
- Start Work
- Mark Fixed
- Close
- Reopen

The workflow is:

`Open -> In Progress -> Fixed -> Closed`

A Closed or Fixed ticket can become Open through Reopen. Invalid transitions
are rejected without changing stored state. Every valid transition updates the
ticket card and topic title, records actor and timestamp, and notifies the
reporter.

When an agent selects **Mark Fixed**, the reporter receives **Yes, fixed** and
**No, still broken**. Confirmation changes Fixed to Closed; rejection changes
Fixed to Open and informs the topic.

## Safe Two-way Messaging

User messages are copied into the ticket topic with a stable link between the
source and relayed Telegram message IDs. Text, captions, photos, and documents
are supported. Telegram file IDs are stored rather than downloading file
contents.

An agent message is delivered to the reporter only when it directly replies
to a bot-relayed reporter message or uses `/reply`. Ordinary messages in the
topic remain internal. The bot confirms successful delivery. A failed delivery
is recorded and shown in the topic with a **Retry** action; it is never silently
dropped.

## Daily Issue Dashboard

A dedicated **Issue Dashboard** topic receives one action-focused digest each
Monday through Friday at 09:00 Asia/Jakarta. Version 1 does not apply a public
holiday calendar. The digest shows:

- Weekday and full date
- Number of issues needing attention
- All Open tickets grouped together
- All In Progress tickets grouped together
- Ticket number, title, urgency, age, and assignee
- A direct link to each ticket topic
- Count of tickets fixed during the previous calendar day
- **Refresh List** and **Export Excel** admin actions

The bot edits the current day's digest instead of posting duplicates. Manual
refresh recalculates the same message. Fixed and Closed tickets are excluded
from the detailed action list.

## Excel Export

Admins may run `/export` or use **Export Excel**. The bot supports all-time
export and an optional inclusive date range based on ticket creation date in
Asia/Jakarta time. It returns an `.xlsx` workbook with four worksheets:

1. **Issues** — one filterable row per ticket with ticket number, created and
   updated timestamps, status, urgency, service, title, description, reporter,
   assignee, age, resolved/closed timestamps, and clickable topic link. The
   Description cell contains the complete text when it fits Excel's 32,767
   character cell limit. For longer text, it identifies the ordered rows in
   **Description Parts**; it never presents a shortened value as complete.
2. **Summary** — totals grouped by status, service, and creation date.
3. **Status History** — ticket number, previous status, new status, actor, and
   transition timestamp.
4. **Description Parts** — ticket number, part number, and text chunks within
   Excel's per-cell limit. Concatenating parts in numeric order reproduces the
   entire stored description without lost characters.

The export is generated from a consistent database snapshot. Description text
is never silently truncated. Message bodies and attachments are not included
in Version 1 beyond the ticket's submitted description, minimizing unnecessary
personal-data exposure.

## Data Model

The database contains focused tables for:

- users and roles
- services
- tickets
- ticket messages and Telegram message links
- attachment metadata
- assignments
- status history
- daily dashboard posts
- processed Telegram updates
- audit and delivery events

Ticket changes use transactions. Telegram update IDs and relay identifiers are
unique so retried updates cannot create duplicate tickets or messages.

## Reliability, Privacy, and Recovery

- Expected delivery and API failures produce actionable topic notices.
- Unexpected exceptions are logged with operational context but without bot
  tokens or private message bodies.
- Health logs cover startup, Telegram connectivity, dashboard execution,
  backup completion, and failures.
- A timestamped SQLite backup runs daily and retains the latest 30 days.
- Backup creation uses SQLite's safe backup mechanism rather than copying an
  actively written database file.
- Restore instructions verify the database before the bot resumes polling.
- Admin and agent actions are retained in the audit history.

## Verification

Automated tests cover:

- Guided intake, validation, confirmation, and cancellation
- Reporter, agent, and admin authorization
- Topic and ticket creation without duplicates
- Single- and multi-ticket DM routing
- Text and attachment relay in both directions
- Protection of internal team messages
- Assignment and all valid and invalid status transitions
- Fixed confirmation and reopening
- Daily digest grouping, counts, links, and idempotent refresh
- Excel worksheets, filters, timezone dates, links, totals, and lossless
  reconstruction of descriptions longer than one Excel cell
- Delivery failure and retry behavior
- Backup creation and restoration

Integration tests use simulated Telegram updates. Before production launch, a
separate staging bot and forum group verify actual topic creation, buttons,
replies, attachments, dashboard links, and workbook delivery without sending
test content to the production team.

## Operational Setup

Documentation must cover BotFather setup, required bot permissions, forum and
dashboard topic configuration, role allowlists, service management, Docker
startup on host reboot, preventing host sleep, backup location, upgrade, and
rollback.

The bot requires permissions to create and manage forum topics, send and edit
messages, and send documents in the private team group.

## Acceptance Criteria

The design is successfully implemented when:

1. An approved reporter completes guided intake and receives a ticket number.
2. The bot creates exactly one correctly titled topic with a complete ticket
   card and attachments.
3. An approved agent can assign, discuss, reply, and update the ticket while
   internal discussion remains private.
4. The reporter receives replies and status changes and can confirm or reject
   a proposed fix.
5. The 09:00 Monday-through-Friday digest accurately lists all Open and In
   Progress tickets with working topic links and no duplicate daily post.
6. An admin exports an accurate four-sheet workbook for all time or a chosen
   date range, with every submitted description preserved in full.
7. Restarting the container preserves all state, and a tested backup restores
   open tickets and message routing data.
