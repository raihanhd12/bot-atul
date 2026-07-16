# Interactive Service Management Design

Date: 2026-07-16
Status: Approved design

## Purpose

Replace the admin Services screen's command hints with a guided Telegram
interface. Admins should be able to add, rename, disable, and reorder services
without remembering or typing `/service_*` commands.

Existing service commands remain supported for compatibility.

## Scope

This change covers service management reached through:

`/start -> Admin Panel -> Services`

It does not redesign team-member management, ticket intake, or the rest of the
admin panel.

## Interaction Model

The Services screen uses a service-first flow:

- Each active service is an inline button.
- **Add Service** appears after the service list.
- **Back** returns to the Admin Panel.
- Selecting a service opens an action screen for that service.

The service action screen shows:

- **Rename**
- **Move Up**
- **Move Down**
- **Disable**
- **Back to Services**

Move buttons are omitted when the selected service is already at the relevant
boundary. Successful operations return the admin to a refreshed Services
screen.

## Add Flow

1. The admin selects **Add Service**.
2. The bot asks for the new service name and shows **Cancel**.
3. The next private text message from that admin is treated as the name.
4. The bot validates and creates the service.
5. The bot confirms success and displays the refreshed service list.

## Rename Flow

1. The admin selects a service and then **Rename**.
2. The bot asks for the new name and shows **Cancel**.
3. The next private text message from that admin is treated as the new name.
4. The bot validates and applies the rename.
5. The bot confirms the old and new names and displays the refreshed service
   list.

Interactive Add and Rename accept names containing spaces. Leading and trailing
whitespace is removed. A valid name must contain at least one non-whitespace
character and be no longer than 64 characters. An exact duplicate active or
disabled service name is rejected because service names are unique in storage.

The existing typed commands keep their current syntax and behavior.

## Reorder Flow

The action screen uses **Move Up** and **Move Down** rather than asking for a
numeric position.

Each action swaps the selected service with its adjacent active service. The
updated ordering is immediately shown. Reordering does not rename, disable, or
otherwise modify either service.

## Disable Flow

1. The admin selects a service and then **Disable**.
2. The bot shows a confirmation screen naming the service.
3. **Yes, Disable** applies the change.
4. **Cancel** returns to that service's action screen.
5. After confirmation, the bot displays the refreshed active-service list.

Disabling removes the service from future issue-submission choices. Existing
tickets retain their stored service label.

## Session State

The bot keeps a small in-memory admin session keyed by Telegram user ID. A
session records:

- whether the bot is waiting for an Add or Rename name;
- the selected service name when required.

Only private messages participate in these text-entry flows. Starting another
service action replaces that admin's previous service-management session.
Selecting **Cancel** removes the session.

Sessions are intentionally not persisted. If the bot restarts during Add or
Rename, no database change has occurred; the admin can reopen Services and
start again.

This follows the existing in-memory guided-intake pattern and avoids adding a
new state-management dependency.

## Authorization and Stale State

Every callback and submitted text message re-checks that the actor is currently
an admin.

Service callbacks identify the selected item by its displayed list position,
not by embedding the service name in Telegram callback data. On selection, the
current name is stored in the admin session. This keeps callback payloads short
and supports names containing spaces.

Before applying Rename, Move, or Disable, the bot verifies that the selected
service is still active. If another admin has already changed it, the bot
reports that the selection is stale, clears the session, and shows the
refreshed service list.

## Errors and Feedback

The bot provides a clear, recoverable message for:

- blank or overlong names;
- duplicate names;
- stale or missing service selections;
- moving beyond the first or last position;
- missing or expired in-memory sessions;
- unauthorized access;
- database integrity failures.

Validation errors during Add or Rename leave the session active so the admin
can submit a corrected name or cancel. No partial database change is retained.

## Auditing

Successful interactive Add, Rename, Move, and Disable operations create audit
events with the admin ID, action, and affected service details. Typed commands
continue using their existing audit behavior.

## Code Boundaries

The change should remain focused:

- `telegram/menu.py` builds the service list, service action, confirmation, and
  cancel keyboards.
- `telegram/handlers/menu.py` handles service callbacks and private text-entry
  sessions.
- `db/repositories.py` performs adjacent reorder operations and existing
  service mutations.
- Tests cover keyboard structure, handler behavior, repository ordering, and
  authorization.

No new dependency or database migration is required.

## Verification

Automated tests must prove:

- admins see active services as buttons;
- non-admins cannot use service callbacks or submit service names;
- Add accepts a multi-word name and records an audit event;
- Rename accepts a multi-word name and records old and new names;
- blank, overlong, and duplicate names are rejected without losing the active
  text-entry session;
- Cancel clears pending Add or Rename state;
- Move Up and Move Down swap adjacent active services;
- boundary move buttons are omitted and invalid boundary moves are harmless;
- Disable requires explicit confirmation;
- cancelling Disable leaves the service active;
- confirming Disable removes it from future active-service lists;
- stale selections are rejected and refreshed safely;
- existing `/service_*` command tests continue to pass.

The full test suite and static checks configured by the project must pass.

## Acceptance Criteria

The feature is complete when an admin can manage the full service lifecycle
from `/start` using Telegram buttons and guided text input, without typing a
service-management command, while permissions, auditing, historical ticket
labels, and existing command compatibility remain intact.
