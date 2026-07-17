# Atul Weekday Ritual

**Date:** 2026-07-17  
**Status:** Implemented (2026-07-17)

## Problem Statement

How might we make Atul’s weekday presence reliable and caring — a fast board refresh for admins, and a private morning touch for every teammate whether they have open work or not?

## Recommended Direction

**Unified weekday ping + living board hygiene.**

At `REMINDER_TIME` (Mon–Fri), Atul contacts **every enabled agent/admin**:

- **Has open / in-progress tickets** → personal work list (existing reminder path, tightened if needed).
- **Has none** → soft check-in with a gentle/sad tone, e.g.  
  “Nothing open on your plate… any issue today? 😔”  
  Buttons: **Yes, report** → start existing new-ticket intake · **All good** → short ack and stop.
- **Team-wide zero tickets** → still send personal quiet-day DMs; team topic posts a short pulse (“all clear + N check-ins sent”) so the group isn’t silent.

**Refresh** is part of the same product quality bar:

1. Answer the callback immediately (“Refreshing…”) so Telegram stops the spinner.
2. Treat Telegram `message is not modified` as success (same pattern as `render_dashboard_card`).
3. Prefer “Already up to date” when digest content is unchanged; only run heavier card ensure when needed.

Wire **Yes, report** into existing intake (`/new` path / session), not a second reporting system.

### Product rules (locked)

| Decision | Choice |
|----------|--------|
| Morning roster | **All** enabled users with role `agent` or `admin` |
| “Yes, I have something” | Jump straight into **new intake** |
| Team has zero tickets | **Still send** personal quiet-day DMs |

## Key Assumptions to Validate

- [ ] Enabled `users` list is the full team people expect as “all”
- [ ] Quiet-day DMs are welcomed after ~1 week (not muted/blocked)
- [ ] “Yes, report” → intake completion rate is non-zero
- [ ] Digest vs reminder ownership rules match after alignment

## MVP Scope

### In

- Roster: all `enabled` users with role agent/admin
- Branch: work reminder vs quiet check-in
- Quiet CTA → existing new intake
- Still DM when team has 0 tickets
- Team pulse line updated (who got work vs quiet pings)
- Refresh: early callback answer + ignore not-modified (+ optional “already up to date”)
- Align “who owns open work” between digest and personal reminders

### Defaults for open product details

- Quiet-day copy: soft tone + one sad emoji
- User with any open ticket they own: **work list only** (no extra quiet line)
- Team topic when everyone is quiet: **one short “all clear” + check-ins sent**

## Not Doing (and Why)

- **Multi-step standup / mood / ETA** — not an issue bot’s job yet; scope creep
- **DMing Telegram IDs not in `users`** — no roster beyond the team directory
- **Opt-out settings UI** — start with copy + “All good”; add mute later if noise appears
- **Parallel card rebuild optimization** — only if refresh still slow after feedback fix
- **Changing dashboard schedule** beyond weekday reminder behavior

## Open Questions

- Exact final quiet-day copy (can tune after first week of use)
- Whether team pulse should list names on quiet days or only counts (default: counts)

## Implementation map

| Area | Touch |
|------|--------|
| `src/bot_atul/services/reminders.py` | Roster = all enabled users; split work vs quiet; team text |
| `src/bot_atul/telegram/keyboards.py` | Quiet check-in buttons |
| `src/bot_atul/telegram/handlers/*` | Callback → start intake session |
| `src/bot_atul/services/dashboard.py` | Not-modified safe edit |
| `src/bot_atul/telegram/handlers/dashboard.py` | Answer callback first |
| Tests | `tests/unit/test_reminders.py`, `tests/unit/test_dashboard.py` |

## Related bugs observed in production

- `TelegramBadRequest: message is not modified` on `publish_dashboard` → `edit_message_text` when refresh content is identical
- Dashboard callback answers only after full publish → long “loading” feel on Refresh
- Digest can show 0 open while team reminder still mentions open work (ownership / timing alignment)

## Decisions log

- 2026-07-17: Idea refined; direction B approved; save to `docs/ideas/atul-weekday-ritual.md`
