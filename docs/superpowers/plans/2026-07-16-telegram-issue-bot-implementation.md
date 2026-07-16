# Telegram Issue Bot Implementation Plan

Date: 2026-07-16
Design: `docs/superpowers/specs/2026-07-16-telegram-issue-bot-design.md`

## Delivery Strategy

Build the bot in small vertical slices. Each task begins with a failing test,
adds only enough code to pass it, and ends with the relevant test suite and
format/static checks. Telegram network calls are isolated behind a gateway so
most behavior is deterministic and testable without a live bot.

The intended Python package layout is:

```text
src/bot_atul/
  app.py
  config.py
  domain/
    models.py
    permissions.py
    statuses.py
  db/
    connection.py
    migrations.py
    repositories.py
  telegram/
    gateway.py
    handlers/
      intake.py
      reporter.py
      team.py
      admin.py
    keyboards.py
    formatting.py
  services/
    tickets.py
    relay.py
    dashboard.py
    exports.py
    backups.py
tests/
  unit/
  integration/
```

Keep modules focused; introduce no repository abstraction beyond the small
interfaces required to substitute SQLite and Telegram in tests.

## Task 1: Project Foundation

**Create:** `pyproject.toml`, `src/bot_atul/__init__.py`,
`src/bot_atul/app.py`, `src/bot_atul/config.py`, `tests/unit/test_config.py`,
`.env.example`, `Dockerfile`, `compose.yaml`

1. Add a failing configuration test covering required bot token, group ID,
   dashboard topic ID, initial admin IDs, timezone, and data/backup paths.
2. Configure Python, aiogram, SQLite access, scheduling, Excel generation,
   pytest, formatting, linting, and type checking with the minimum necessary
   dependencies.
3. Implement typed environment loading with useful startup errors and secret
   redaction.
4. Add the smallest bot entry point and Docker health/restart configuration.
5. Verify unit tests, lint, formatting, typing, and container build.

## Task 2: Database Schema and Migrations

**Create:** `src/bot_atul/db/connection.py`,
`src/bot_atul/db/migrations.py`, `src/bot_atul/db/repositories.py`,
`src/bot_atul/domain/models.py`, `tests/unit/test_migrations.py`,
`tests/integration/test_repositories.py`

1. Test creation and upgrade of an empty temporary database.
2. Create tables for users/roles, services, tickets, ticket messages,
   attachments, assignments, status history, dashboard posts, processed
   updates, and audit/delivery events.
3. Add foreign keys, uniqueness constraints for Telegram update/message IDs,
   indexes for active-ticket and dashboard queries, and transactional helpers.
4. Seed the four approved services idempotently.
5. Test ticket persistence, full long descriptions, service history, message
   links, assignments, and rollback on failure.

## Task 3: Authorization and Admin Configuration

**Create:** `src/bot_atul/domain/permissions.py`,
`src/bot_atul/telegram/handlers/admin.py`,
`tests/unit/test_permissions.py`, `tests/integration/test_admin_handlers.py`

1. Write role-matrix tests for reporter, agent, admin, and unknown users.
2. Implement numeric-ID authorization at the handler and service boundaries.
3. Add admin commands for listing/adding/disabling reporters and agents.
4. Add service list/add/rename/disable/reorder commands while preserving the
   service label stored on historical tickets.
5. Audit all administrative changes without storing secret values.

## Task 4: Guided Reporter Intake

**Create:** `src/bot_atul/telegram/handlers/intake.py`,
`src/bot_atul/telegram/keyboards.py`, `src/bot_atul/services/tickets.py`,
`tests/unit/test_intake.py`, `tests/integration/test_ticket_creation.py`

1. Test the complete state sequence: title, service, urgency, multi-message
   description, Description Complete, attachments, review, and confirmation.
2. Test validation, back/cancel behavior, unknown users, disabled services,
   duplicate confirmation updates, and interrupted sessions.
3. Store descriptions losslessly and retain Telegram file IDs for supported
   photos/documents.
4. Allocate a sequential ticket number and create exactly one database ticket
   on confirmation.
5. Return a reporter receipt with ticket number and supported actions.

## Task 5: Forum Topic Creation and Ticket Card

**Create:** `src/bot_atul/telegram/gateway.py`,
`src/bot_atul/telegram/formatting.py`,
`tests/unit/test_formatting.py`, `tests/integration/test_topic_creation.py`

1. Define and fake the narrow Telegram gateway used by application services.
2. Test topic-title formatting and safe length handling.
3. Test a compact ticket card containing all approved fields and controls.
4. Split long descriptions into numbered Telegram messages without losing or
   reordering content.
5. Create one topic per confirmed ticket, persist its ID/message links, and
   make retries idempotent.
6. Record actionable creation failures for an admin retry rather than creating
   a second ticket.

## Task 6: Two-way Message Relay

**Create:** `src/bot_atul/services/relay.py`,
`src/bot_atul/telegram/handlers/reporter.py`,
`src/bot_atul/telegram/handlers/team.py`,
`tests/unit/test_relay_rules.py`, `tests/integration/test_message_relay.py`

1. Test reporter routing with zero, one, and multiple active tickets.
2. Relay supported reporter text, captions, photos, and documents to the
   correct topic and persist source/destination links.
3. Test that only a direct reply to a relayed reporter message or `/reply`
   becomes outbound; ordinary topic discussion remains internal.
4. Test authorization, duplicate update suppression, reply context, and
   closed-ticket behavior.
5. Add delivery confirmation, failure records, and idempotent Retry actions.

## Task 7: Assignment and Status Workflow

**Create:** `src/bot_atul/domain/statuses.py`,
`tests/unit/test_statuses.py`, `tests/integration/test_ticket_actions.py`

1. Define and test the allowed Open, In Progress, Fixed, Closed, and Reopen
   transitions, including Open/unassigned reporter cancellation.
2. Implement Assign to Me, Start Work, Mark Fixed, Close, and Reopen callbacks.
3. Update ticket state, status history, audit event, topic title, and ticket
   card in one logical operation with recoverable Telegram-side failures.
4. Notify the reporter on every valid transition.
5. Implement Yes, fixed -> Closed and No, still broken -> Open with duplicate
   callback protection.

## Task 8: Daily Action Dashboard

**Create:** `src/bot_atul/services/dashboard.py`,
`tests/unit/test_dashboard.py`, `tests/integration/test_dashboard_schedule.py`

1. Test Asia/Jakarta scheduling at 09:00 Monday through Friday and explicitly
   confirm that Version 1 does not skip public holidays.
2. Query and group all Open and In Progress tickets with urgency, age,
   assignee, and topic link; count tickets fixed on the previous calendar day.
3. Format the scan-friendly action layout approved in the visual mockup.
4. Create or edit exactly one digest per date and persist its Telegram message
   ID so retries and restarts do not duplicate it.
5. Implement admin-only Refresh List and Export Excel controls.

## Task 9: Lossless Excel Export

**Create:** `src/bot_atul/services/exports.py`,
`tests/unit/test_exports.py`, `tests/integration/test_export_handler.py`

1. Test all-time and inclusive creation-date ranges in Asia/Jakarta time.
2. Generate Issues, Summary, Status History, and Description Parts worksheets
   from a consistent SQLite snapshot.
3. Add headers, filters, frozen rows, readable widths, date formats, status
   styling, and clickable topic links without sacrificing data fidelity.
4. Keep descriptions up to Excel's 32,767-character cell limit in Issues; for
   longer values, emit ordered safe-size parts and a clear reference.
5. Prove by reconstruction tests that exported description parts match the
   stored Unicode text character for character.
6. Restrict the command and dashboard action to admins and remove temporary
   workbook files after Telegram delivery.

## Task 10: Backups and Recovery

**Create:** `src/bot_atul/services/backups.py`,
`tests/integration/test_backups.py`, `scripts/restore-backup.sh`

1. Use SQLite's online backup API for a consistent daily snapshot.
2. Name backups by timestamp, retain the newest 30 daily files, and log
   success/failure without sensitive data.
3. Test restoration into a fresh data directory, integrity checking, and
   preservation of active tickets and message links.
4. Make the restore script refuse to overwrite a running production database.

## Task 11: Runtime Wiring and Operational Documentation

**Modify:** `src/bot_atul/app.py`, `compose.yaml`, `.env.example`

**Create:** `README.md`, `docs/operations.md`,
`tests/integration/test_app_startup.py`

1. Wire database initialization, handlers, scheduler, long polling, graceful
   shutdown, and privacy-safe logging.
2. Verify startup failure is explicit for missing permissions/configuration.
3. Document BotFather creation, forum permissions, dashboard topic, numeric ID
   discovery, allowlists, services, Docker startup after reboot, disabling host
   sleep, backups, restore, upgrade, rollback, and later VPS migration.
4. Run the full automated suite and build the production container from a
   clean checkout.

## Task 12: Staging Acceptance and Production Readiness

No application behavior is added in this task.

1. Create a separate staging bot and private forum group.
2. Run the acceptance checklist with one reporter, agent, and admin account.
3. Verify real topic creation, long descriptions, attachments, relay safety,
   all statuses, fix confirmation, daily refresh, topic links, and lossless
   workbook export.
4. Restart the container mid-ticket and verify routing resumes correctly.
5. Restore a backup in staging and repeat an active-ticket reply.
6. Record staging evidence and any operational deviations in
   `docs/staging-checklist.md`.
7. Launch production only after every design acceptance criterion passes.

## Global Verification Commands

Exact tool commands will be finalized with `pyproject.toml`. The project must
provide single commands for these gates:

```text
format check
lint
type check
unit tests
integration tests
full verification
container build
```

No task is complete while its focused tests fail. No production launch is
complete until the full verification suite, staging acceptance, restart test,
and backup restoration all pass.
