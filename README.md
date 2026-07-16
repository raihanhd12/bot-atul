# Bot Atul

Self-hosted Telegram issue-management bot for private support teams.

Approved agents and admins report issues through the bot's direct messages. The
bot posts view-only ticket cards in one private Telegram dashboard topic,
auto-assigns each report to the submitter, opens a private DM workspace, tracks
ticket status, publishes a weekday action dashboard, and exports issue data to
Excel.

## Features

- Allowlisted agents and admins using numeric Telegram user IDs
- Guided private-message intake
- Customizable service categories
- Low, Normal, High, and Critical urgency
- Multi-message descriptions without silent truncation
- Photo and document attachments
- One shared team dashboard topic (view-only) with private agent workspaces
- Auto-assignment on report (no group Assign to Me step)
- Safe two-way message relay
- Status controls in the private ticket workspace
- Submitter confirmation when an issue is marked Fixed
- Monday-to-Friday issue dashboard at 09:00 in the configured timezone
- Admin-only `.xlsx` export with date filtering
- Durable failed-message records and retry buttons
- Role-aware interactive menu and automatic slash-command registration
- Configurable weekday reminder for unresolved tickets

## Ticket Workflow

```text
Open -> In Progress -> Fixed -> Closed
  ^                         |
  +--------- Reopen --------+
```

When someone else marks a ticket Fixed, the original submitter receives:

- **Yes, fixed** — closes the ticket
- **No, still broken** — reopens the ticket

Self-owned tickets (normal after auto-assign) skip that confirmation: **Mark
Fixed** closes immediately. Extra private messages on a self-owned ticket are
saved as notes, not echoed back.

An owner may cancel an Open ticket assigned to themselves. Admins may close any
Open, In Progress, or Fixed ticket from **Admin Panel → Open Tickets**.

## Project Structure

```text
src/bot_atul/
  app.py                 Application startup and scheduling
  config.py              Environment configuration
  db/                    SQLite connection, schema, and repository
  domain/                Permissions and ticket status rules
  services/              Ticket, relay, dashboard, and export logic
  telegram/              Telegram formatting, keyboards, and handlers
tests/
  unit/
  integration/
docs/superpowers/
  specs/                 Approved design
  plans/                 Implementation plan
```

The `src/bot_atul/` directory is intentionally retained as the Python package
namespace. It avoids conflicts with generic installed packages named `db`,
`services`, or `telegram`.

## Default Categories

New installations start with generic categories:

- General
- Technical
- Billing
- Other

Admins can add, rename, disable, and reorder categories from Telegram. These
defaults are examples, not a required support taxonomy.

## Requirements

- Telegram bot token from [BotFather](https://t.me/BotFather)
- Private Telegram supergroup with Topics enabled
- Docker and Docker Compose for the recommended deployment
- Git

For local development without Docker:

- Python 3.12
- Poetry 2

## Telegram Setup

1. Create a bot with BotFather and copy its token.
2. Create a private Telegram group.
3. Convert or configure it as a supergroup with Topics enabled.
4. Add the bot as an administrator.
5. Give the bot permission to:
   - manage topics;
   - send and edit messages;
   - send photos and documents.
6. Create a dedicated topic named `Issue Dashboard`.
7. Collect these numeric values:
   - team group ID;
   - dashboard topic ID;
   - initial admin Telegram user ID.

The bot cannot initiate a private conversation with a user who has never
started it. Each agent or admin must open the bot and press **Start** first.

## Environment Configuration

Copy the example file:

```bash
cp .env.example .env
```

Configure:

```dotenv
BOT_TOKEN=123456:replace-with-botfather-token
TEAM_GROUP_ID=-1001234567890
DASHBOARD_TOPIC_ID=1
ADMIN_IDS=123456789
TIMEZONE=Asia/Jakarta
REMINDER_TIME=09:00
DATA_DIR=/app/data
BACKUP_DIR=/app/backups
```

`ADMIN_IDS` accepts comma-separated numeric IDs:

```dotenv
ADMIN_IDS=123456789,987654321
```

Never commit `.env`. It is ignored by Git.

`REMINDER_TIME` accepts one local 24-hour time. The bot sends a reminder
Monday through Friday only when Open or In Progress tickets exist.

## Docker Deployment

Docker Compose is the recommended runtime. PM2 is unnecessary because Compose
already restarts the container with `restart: unless-stopped`.

```bash
git clone <repository-url>
cd bot-atul
cp .env.example .env
nano .env
docker compose up -d --build
```

Check the service:

```bash
docker compose ps
docker compose logs -f bot
```

Restart:

```bash
docker compose restart bot
```

Update after pulling new code:

```bash
git pull
docker compose up -d --build
```

Stop:

```bash
docker compose down
```

SQLite data is mounted at `./data`, and future automated backups will be
mounted at `./backups`. Keep both directories on persistent storage.

## Local Development

```bash
poetry install
cp .env.example .env
set -a
source .env
set +a
poetry run python -m bot_atul.app
```

The bot uses Telegram long polling, so no inbound public HTTP port is required.

## Admin Commands

Only allowlisted admins can use these commands:

```text
/user_add <telegram_id> <agent|admin>
/user_disable <telegram_id>
/service_add <name>
/service_rename <old> <new>
/service_disable <name>
/service_move <name> <position>
/export
/export YYYY-MM-DD
/export YYYY-MM-DD YYYY-MM-DD
```

Examples:

```text
/user_add 123456789 agent
/user_add 987654321 admin
/service_move Technical 1
/export 2026-07-01 2026-07-31
```

Service changes affect new intake choices. Existing tickets retain the service
label recorded when they were submitted.

## Interactive Dashboard

Send `/start` in the bot's private chat to open a role-aware dashboard. The bot
edits that message as the user navigates, so most actions are button-driven.

All approved users see:

- Report Issue
- My Tickets
- Help

Agents and admins also see Team Help. Admins additionally see Export Excel and
the Admin Panel.

The Admin Panel shows:

- the active service list in its current order;
- current admins and agents;
- the configured weekday reminder time;
- shortcuts for service and user management commands.

Telegram IDs and new category names still require typing because they are input
values, but the available actions and current configuration are discoverable
from the buttons.

Roles are hierarchical:

- **Agent** — submits and handles issues
- **Admin** — submits, handles, manages users/categories, and exports

The bot registers its slash-command list automatically during startup, so
manual BotFather command-menu configuration is optional.

## Report Flow

1. The admin allowlists the agent's numeric Telegram ID.
2. The agent opens the bot and presses **Start**.
3. The agent sends `/new` or taps **Report Issue**.
4. The bot asks for:
   - title;
   - service;
   - urgency;
   - description;
   - optional attachments;
   - final confirmation.
5. The bot posts a view-only card in the dashboard topic, auto-assigns the
   ticket to the submitter, and opens a private workspace.
6. Further private messages are routed to the active ticket.
7. If the agent has several active tickets, the bot asks which ticket should
   receive the message.

## Team Flow

Each ticket appears as a polished view-only card in the shared dashboard topic:

- status and urgency icons (for example ✅ Closed, 🚨 Critical);
- display names and `@username` instead of raw Telegram IDs;
- **View Details / Hide Details** so the whole team can expand the description
  in the topic.

No assign or close buttons appear in the group.

After reporting, the submitter receives a private ticket workspace and can:

- start work, mark it Fixed, close, or reopen it from that workspace;
- use **Reply to Reporter** to send a private response.

Ticket conversation is never posted in the dashboard topic.

## Daily Dashboard

The Issue Dashboard topic is updated:

- automatically at 09:00 in `TIMEZONE`, Monday through Friday;
- after a new ticket is submitted;
- after assignment or status changes;
- when an admin selects **Refresh List**.

It lists all Open and In Progress tickets grouped by status, including urgency,
age, assignee, and a direct ticket-card link. Long dashboards are split across
ordered messages rather than truncated.

## Excel Export

Admins can use `/export` or the dashboard's **Export Excel** button.

The workbook contains:

1. **Issues** — filterable ticket details and clickable ticket-card links
2. **Summary** — counts by status, service, and creation date
3. **Status History** — transition audit trail
4. **Description Parts** — ordered chunks for descriptions exceeding Excel's
   32,767-character per-cell limit

Descriptions are never silently truncated. Concatenating Description Parts in
part-number order reproduces the complete stored description.

## Verification

Run all automated tests:

```bash
poetry run pytest -q
```

Run all quality checks:

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy
```

Build the container:

```bash
docker compose build
```

## Current Readiness

The core bot workflow is implemented and covered by automated tests. Before
using it for real production issues, complete these remaining steps:

- automated daily SQLite backups and tested restoration;
- operational and recovery documentation;
- successful Docker image build verification;
- end-to-end testing with a separate staging bot and forum group;
- production acceptance test with real Telegram permissions.

The current version is suitable for staging, not yet recommended for production
data.

## Security and Privacy

- Keep `.env`, bot tokens, database files, exports, and backups out of Git.
- Use numeric Telegram IDs for authorization; usernames can change.
- Keep the support group private and grant bot permissions only as required.
- Treat exported workbooks as sensitive because they contain issue descriptions
  and user identifiers.
- Store `data/` and `backups/` on access-controlled persistent storage.
- Rotate the BotFather token immediately if it is exposed.
- Review the repository history before making a previously private repository
  public; deleting a secret from the latest commit does not remove it from old
  commits.

## Troubleshooting

### Ticket card does not appear

Confirm `TEAM_GROUP_ID` and `DASHBOARD_TOPIC_ID` identify the private forum and
dashboard topic. The bot must be an administrator that can send messages.

### User cannot submit an issue

Confirm the user pressed **Start** in the bot's DM and their numeric ID was
added with `/user_add <id> reporter`.

### Agent reply is not sent

Open the bot in private and press **Start** before assigning a ticket. Use
**Reply to Reporter** in the private ticket workspace, then send the message.

### Docker cannot connect

Start the Docker service or Docker Desktop, then run:

```bash
docker compose build
```

### Data disappears after replacing a container

Confirm `./data:/app/data` remains configured in `compose.yaml` and that
`DATA_DIR=/app/data`.

## Design Documents

- [Approved design](docs/superpowers/specs/2026-07-16-telegram-issue-bot-design.md)
- [Implementation plan](docs/superpowers/plans/2026-07-16-telegram-issue-bot-implementation.md)
