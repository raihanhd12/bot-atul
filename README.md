# Bot Atul

Self-hosted Telegram issue-management bot for private support teams.

Approved users report issues through the bot's direct messages. The bot creates
one topic per issue in a private Telegram forum group, relays conversation
between the reporter and team, tracks ticket status, publishes a weekday action
dashboard, and exports issue data to Excel.

## Features

- Allowlisted reporters, agents, and admins using numeric Telegram user IDs
- Guided private-message intake
- Customizable service categories
- Low, Normal, High, and Critical urgency
- Multi-message descriptions without silent truncation
- Photo and document attachments
- One private forum topic per ticket
- Safe two-way message relay
- Assignment and status controls
- Reporter confirmation when an issue is marked Fixed
- Monday-to-Friday issue dashboard at 09:00 in the configured timezone
- Admin-only `.xlsx` export with date filtering
- Durable failed-message records and retry buttons

## Ticket Workflow

```text
Open -> In Progress -> Fixed -> Closed
  ^                         |
  +--------- Reopen --------+
```

When an agent marks a ticket Fixed, the reporter receives:

- **Yes, fixed** — closes the ticket
- **No, still broken** — reopens the ticket

A reporter may cancel only an Open, unassigned ticket.

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
started it. Each reporter must open the bot and press **Start** first.

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
DATA_DIR=/app/data
BACKUP_DIR=/app/backups
```

`ADMIN_IDS` accepts comma-separated numeric IDs:

```dotenv
ADMIN_IDS=123456789,987654321
```

Never commit `.env`. It is ignored by Git.

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
/user_add <telegram_id> <reporter|agent|admin>
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
/user_add 123456789 reporter
/user_add 987654321 agent
/service_move Technical 1
/export 2026-07-01 2026-07-31
```

Service changes affect new intake choices. Existing tickets retain the service
label recorded when they were submitted.

## Reporter Flow

1. The admin allowlists the reporter's numeric Telegram ID.
2. The reporter opens the bot and presses **Start**.
3. The reporter sends `/new`.
4. The bot asks for:
   - title;
   - service;
   - urgency;
   - description;
   - optional attachments;
   - final confirmation.
5. The bot creates the ticket topic and sends the ticket number.
6. Further private messages are routed to the active ticket.
7. If the reporter has several active tickets, the bot asks which ticket should
   receive the message.

## Team Flow

Each ticket topic contains the ticket card and status controls.

Team members can:

- assign the ticket to themselves;
- start work;
- mark it Fixed;
- close or reopen it;
- reply directly to a relayed reporter message;
- send `/reply <message>` for a deliberate private response.

Ordinary topic discussion is internal and is not sent to the reporter.

## Daily Dashboard

The Issue Dashboard topic is updated:

- automatically at 09:00 in `TIMEZONE`, Monday through Friday;
- after a new ticket is submitted;
- after assignment or status changes;
- when an admin selects **Refresh List**.

It lists all Open and In Progress tickets grouped by status, including urgency,
age, assignee, and a direct topic link. Long dashboards are split across
ordered messages rather than truncated.

## Excel Export

Admins can use `/export` or the dashboard's **Export Excel** button.

The workbook contains:

1. **Issues** — filterable ticket details and clickable topic links
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

### Bot does not create topics

Confirm the group has Topics enabled and the bot is an administrator with
permission to manage topics.

### User cannot submit an issue

Confirm the user pressed **Start** in the bot's DM and their numeric ID was
added with `/user_add <id> reporter`.

### Agent reply is not sent

The agent must directly reply to a reporter message relayed by the bot or use
`/reply <message>`. Normal topic messages remain internal.

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
