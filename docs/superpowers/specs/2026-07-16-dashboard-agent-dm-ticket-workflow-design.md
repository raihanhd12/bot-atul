# Dashboard and Agent DM Ticket Workflow

**Date:** 2026-07-16  
**Status:** Approved

## Objective

Keep all team-facing ticket summaries inside the configured dashboard topic
instead of creating one Telegram forum topic per ticket.

The configured `DASHBOARD_TOPIC_ID` is the team's shared overview. Ticket
handling and reporter communication happen in private bot chats.

## User Experience

### Reporter

The reporter continues to use the bot's private chat to:

- submit a ticket;
- add information to an active ticket;
- receive agent replies and status notifications;
- confirm whether a reported fix solved the problem;
- cancel an Open, unassigned ticket.

The reporter never needs access to the private team group.

### Team Dashboard

Each submitted ticket creates one summary card inside
`DASHBOARD_TOPIC_ID`. The bot does not create a new forum topic.

The card contains:

- ticket number;
- service;
- urgency;
- status;
- assignee;
- reporter identity;
- title;
- an **Assign to Me** button while assignment is available.

The card is edited in place after assignment and status changes. The existing
scheduled dashboard digest may remain as a separate message in the same topic.

The shared topic is view-and-action only. Team discussion and reporter
messages are not posted there.

### Assigned Agent

When an agent or admin presses **Assign to Me**:

1. The bot assigns the ticket to that Telegram user.
2. The dashboard card is updated with the assignee.
3. The bot sends or refreshes a private ticket workspace in the assignee's bot
   chat.

The private workspace contains the full ticket details, description,
attachments, current status, and controls appropriate to the current state:

- Start Work
- Reply to Reporter
- Mark Fixed
- Close
- Reopen

An agent must have opened the bot and pressed **Start** before assignment. If
Telegram cannot send the private workspace, assignment is not retained and the
dashboard shows a clear error to the agent.

## Messaging

### Reporter to Agent

When a reporter sends additional information:

- if the reporter has one active ticket, the message is attached to it;
- if the reporter has multiple active tickets, the bot asks which ticket;
- the bot copies the message to the assigned agent's private chat;
- if the ticket is unassigned, the information is stored and becomes visible
  when an agent assigns the ticket.

No reporter message is copied into the dashboard topic.

### Agent to Reporter

The agent starts a reply from the private ticket workspace. The bot records
which ticket is being answered, accepts the next text, photo, or document, and
copies it to the reporter's private chat.

The bot must not infer a ticket from an unrelated private message when the
agent has multiple assigned tickets. A reply action creates an explicit,
short-lived ticket selection state.

Successful delivery is acknowledged. Failed delivery is stored and receives a
retry action; messages are never silently discarded.

## Status Workflow

The existing workflow remains:

`Open -> In Progress -> Fixed -> Closed`

- **Start Work** changes Open to In Progress.
- **Mark Fixed** changes In Progress to Fixed and asks the reporter whether the
  problem is solved.
- **Yes, fixed** changes Fixed to Closed.
- **No, still broken** changes Fixed to Open.
- **Close** changes Open or In Progress directly to Closed.
- **Reopen** changes Fixed or Closed to Open.

Every change updates the database, dashboard card, and assigned agent's private
workspace. The reporter receives the existing status notifications.

## Data Model

Tickets no longer use `topic_id` as their identity or message destination.

The existing `card_message_id` identifies the ticket's dashboard card.
Agent private workspace message IDs require durable storage keyed by ticket and
agent so cards can be edited after restarts.

Existing message records continue to preserve source and destination Telegram
IDs for retry and audit behavior.

The database remains the source of truth. In-memory state is limited to
short-lived interactions such as waiting for an agent's reply content.

## Existing Tickets and Deployment

Existing ticket rows remain valid.

- Tickets that already have individual Telegram topics are not deleted.
- After deployment, new tickets use only the dashboard topic.
- Active existing tickets receive or refresh a dashboard card when next
  updated or when the dashboard is refreshed.
- Historical `topic_id` values may remain stored for audit and export
  compatibility but are not used for new routing.

No automated deletion or closing of existing Telegram topics is included.

## Error Handling

- If the bot cannot access the team group or dashboard topic, submission stays
  retryable and no duplicate ticket card is created.
- If the bot cannot DM an assigning agent, assignment is rejected or rolled
  back with instructions to open the bot and press **Start**.
- If an agent reply or reporter update cannot be delivered, it is stored as a
  failed delivery with a retry action.
- Repeated button presses are idempotent and do not create duplicate cards,
  workspaces, tickets, or assignments.

## Security and Permissions

- Only allowlisted agents and admins can assign tickets or use team controls.
- Only the assigned agent and admins can operate an agent DM workspace.
- Reporter messages are delivered only to the assigned agent.
- Agent replies are delivered only to the reporter associated with the
  selected ticket.
- Dashboard cards contain the existing team-visible reporter details but no
  conversation transcript.

## Acceptance Criteria

1. Submitting 100 tickets creates 100 cards in topic `24` and zero new forum
   topics.
2. Assigning a ticket sends its full private workspace to the assigning agent.
3. Assignment fails clearly if the bot cannot DM the agent.
4. Reporter updates reach only the assigned agent's DM and are retained while
   unassigned.
5. Agent replies from a selected ticket workspace reach the correct reporter.
6. Status changes remain consistent across the database, dashboard card,
   agent workspace, and reporter notifications.
7. Fixed-ticket reporter confirmation still closes or reopens the correct
   ticket.
8. Retries do not create duplicate tickets, dashboard cards, assignments, or
   agent workspaces.
9. Existing tickets remain readable and are not deleted during migration.

## Out of Scope

- A web dashboard.
- Group discussion threads per ticket.
- Automatic deletion of previously created ticket topics.
- Assignment to arbitrary agents by another user.
- Multi-agent collaboration inside one ticket workspace.
