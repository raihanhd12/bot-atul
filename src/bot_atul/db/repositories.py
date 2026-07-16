from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Ticket:
    number: int
    reporter_id: int
    service_name: str
    urgency: str
    title: str
    description: str
    status: str
    topic_id: int | None
    card_message_id: int | None
    assignee_id: int | None


@dataclass(frozen=True)
class RelayMessage:
    id: int
    ticket_number: int
    direction: str
    source_chat_id: int
    source_message_id: int
    destination_chat_id: int | None
    destination_message_id: int | None
    text: str | None
    relay_method: str
    delivery_status: str


@dataclass(frozen=True)
class UserRecord:
    telegram_id: int
    role: str
    username: str | None
    display_name: str | None


@dataclass(frozen=True)
class AgentWorkspace:
    ticket_number: int
    agent_id: int
    message_id: int


@dataclass(frozen=True)
class AttachmentRecord:
    id: int
    kind: str
    file_id: str
    file_name: str | None
    caption: str | None


class Repository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_ticket(
        self,
        *,
        reporter_id: int,
        service_name: str,
        urgency: str,
        title: str,
        description: str,
        attachments: tuple[tuple[str, str, str | None, str | None], ...] = (),
    ) -> Ticket:
        service = self.connection.execute(
            "SELECT id, name FROM services WHERE name = ? AND enabled = 1",
            (service_name,),
        ).fetchone()
        if service is None:
            raise ValueError(f"Unknown or disabled service: {service_name}")

        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO tickets(
                    reporter_id, service_id, service_name, urgency, title, description
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    reporter_id,
                    service["id"],
                    service["name"],
                    urgency,
                    title,
                    description,
                ),
            )
            assert cursor.lastrowid is not None
            self.connection.executemany(
                """
                INSERT INTO attachments(
                    ticket_number, kind, telegram_file_id, file_name, caption
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (cursor.lastrowid, kind, file_id, file_name, caption)
                    for kind, file_id, file_name, caption in attachments
                ),
            )
        ticket = self.get_ticket(cursor.lastrowid)
        assert ticket is not None
        return ticket

    def get_ticket(self, number: int) -> Ticket | None:
        row = self.connection.execute(
            """
            SELECT number, reporter_id, service_name, urgency, title,
                   description, status, topic_id, card_message_id, assignee_id
            FROM tickets WHERE number = ?
            """,
            (number,),
        ).fetchone()
        return Ticket(**dict(row)) if row else None

    def attach_topic(self, number: int, topic_id: int) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE tickets SET topic_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE number = ? AND topic_id IS NULL
                """,
                (topic_id, number),
            )

    def attach_card(self, number: int, card_message_id: int) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE tickets SET card_message_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE number = ?
                """,
                (card_message_id, number),
            )

    def save_dashboard_card(self, number: int, message_id: int) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO ticket_dashboard_cards(ticket_number, message_id)
                VALUES (?, ?)
                ON CONFLICT(ticket_number) DO UPDATE SET
                    message_id = excluded.message_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (number, message_id),
            )

    def get_dashboard_card(self, number: int) -> int | None:
        row = self.connection.execute(
            "SELECT message_id FROM ticket_dashboard_cards WHERE ticket_number = ?",
            (number,),
        ).fetchone()
        return int(row[0]) if row else None

    def save_agent_workspace(
        self, number: int, agent_id: int, message_id: int
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO agent_workspaces(ticket_number, agent_id, message_id)
                VALUES (?, ?, ?)
                ON CONFLICT(ticket_number) DO UPDATE SET
                    agent_id = excluded.agent_id,
                    message_id = excluded.message_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (number, agent_id, message_id),
            )

    def get_agent_workspace(self, number: int) -> AgentWorkspace | None:
        row = self.connection.execute(
            """
            SELECT ticket_number, agent_id, message_id
            FROM agent_workspaces WHERE ticket_number = ?
            """,
            (number,),
        ).fetchone()
        return AgentWorkspace(**dict(row)) if row else None

    def list_attachments(self, number: int) -> list[AttachmentRecord]:
        rows = self.connection.execute(
            """
            SELECT id, kind, telegram_file_id, file_name, caption
            FROM attachments WHERE ticket_number = ? ORDER BY id
            """,
            (number,),
        ).fetchall()
        return [
            AttachmentRecord(
                id=int(row[0]),
                kind=str(row[1]),
                file_id=str(row[2]),
                file_name=row[3],
                caption=row[4],
            )
            for row in rows
        ]

    def count_attachments(self, number: int) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM attachments WHERE ticket_number = ?",
            (number,),
        ).fetchone()
        return int(row[0])

    def is_topic_attachment_posted(self, attachment_id: int) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM ticket_topic_attachments WHERE attachment_id = ?",
            (attachment_id,),
        ).fetchone()
        return row is not None

    def save_topic_attachment(
        self, ticket_number: int, attachment_id: int, message_id: int
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO ticket_topic_attachments(
                    attachment_id, ticket_number, message_id
                ) VALUES (?, ?, ?)
                ON CONFLICT(attachment_id) DO UPDATE SET
                    message_id = excluded.message_id,
                    posted_at = CURRENT_TIMESTAMP
                """,
                (attachment_id, ticket_number, message_id),
            )

    def count_tickets(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) FROM tickets").fetchone()
        return int(row[0])

    def claim_update(self, update_id: int) -> bool:
        try:
            with self.connection:
                self.connection.execute(
                    "INSERT INTO processed_updates(update_id) VALUES (?)", (update_id,)
                )
        except sqlite3.IntegrityError:
            return False
        return True

    def upsert_user(self, telegram_id: int, role: str) -> None:
        if role not in {"agent", "admin"}:
            raise ValueError(f"Invalid role: {role}")
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO users(telegram_id, role, enabled) VALUES (?, ?, 1)
                ON CONFLICT(telegram_id) DO UPDATE SET role = excluded.role, enabled = 1
                """,
                (telegram_id, role),
            )

    def disable_user(self, telegram_id: int) -> bool:
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE users SET enabled = 0 WHERE telegram_id = ?", (telegram_id,)
            )
        return cursor.rowcount == 1

    def get_role(self, telegram_id: int) -> str | None:
        row = self.connection.execute(
            "SELECT role FROM users WHERE telegram_id = ? AND enabled = 1",
            (telegram_id,),
        ).fetchone()
        return str(row[0]) if row else None

    def get_user(self, telegram_id: int) -> UserRecord | None:
        row = self.connection.execute(
            """
            SELECT telegram_id, role, username, display_name
            FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        ).fetchone()
        return UserRecord(**dict(row)) if row else None

    def user_label(self, telegram_id: int | None) -> str:
        if telegram_id is None:
            return "Unassigned"
        user = self.get_user(telegram_id)
        if user is None:
            return f"User {telegram_id}"
        if user.display_name and user.username:
            return f"{user.display_name} (@{user.username})"
        if user.display_name:
            return user.display_name
        if user.username:
            return f"@{user.username}"
        return f"User {telegram_id}"

    def user_labels(self, *telegram_ids: int | None) -> dict[int, str]:
        labels: dict[int, str] = {}
        for telegram_id in telegram_ids:
            if telegram_id is not None and telegram_id not in labels:
                labels[telegram_id] = self.user_label(telegram_id)
        return labels

    def remember_user(
        self, telegram_id: int, username: str | None, display_name: str
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE users SET username = ?, display_name = ?
                WHERE telegram_id = ?
                """,
                (username, display_name, telegram_id),
            )

    def list_users(self, roles: tuple[str, ...]) -> list[UserRecord]:
        placeholders = ",".join("?" for _ in roles)
        rows = self.connection.execute(
            f"""
            SELECT telegram_id, role, username, display_name
            FROM users
            WHERE enabled = 1 AND role IN ({placeholders})
            ORDER BY CASE role WHEN 'admin' THEN 1 WHEN 'agent' THEN 2 ELSE 3 END,
                     COALESCE(display_name, username, telegram_id)
            """,
            roles,
        ).fetchall()
        return [UserRecord(**dict(row)) for row in rows]

    def list_services(self) -> list[str]:
        rows = self.connection.execute(
            "SELECT name FROM services WHERE enabled = 1 ORDER BY position, id"
        ).fetchall()
        return [str(row[0]) for row in rows]

    def add_service(self, name: str) -> None:
        position = self.connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM services"
        ).fetchone()[0]
        with self.connection:
            self.connection.execute(
                "INSERT INTO services(name, position) VALUES (?, ?)", (name, position)
            )

    def rename_service(self, old_name: str, new_name: str) -> bool:
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE services SET name = ? WHERE name = ? AND enabled = 1",
                (new_name, old_name),
            )
        return cursor.rowcount == 1

    def disable_service(self, name: str) -> bool:
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE services SET enabled = 0 WHERE name = ? AND enabled = 1",
                (name,),
            )
        return cursor.rowcount == 1

    def move_service(self, name: str, position: int) -> bool:
        if position < 1:
            raise ValueError("Position must be at least 1")
        row = self.connection.execute(
            "SELECT id FROM services WHERE name = ? AND enabled = 1", (name,)
        ).fetchone()
        if row is None:
            return False
        with self.connection:
            self.connection.execute(
                "UPDATE services SET position = position + 1 WHERE position >= ?",
                (position - 1,),
            )
            self.connection.execute(
                "UPDATE services SET position = ? WHERE id = ?", (position - 1, row[0])
            )
        return True

    def move_service_by(self, name: str, offset: int) -> bool:
        services = self.list_services()
        if name not in services:
            return False
        current = services.index(name)
        target = current + offset
        if target < 0 or target >= len(services):
            return False
        services[current], services[target] = services[target], services[current]
        with self.connection:
            self.connection.executemany(
                "UPDATE services SET position = ? WHERE name = ? AND enabled = 1",
                ((position, service) for position, service in enumerate(services)),
            )
        return True

    def record_audit(self, actor_id: int, event_type: str, details: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO audit_events(actor_id, event_type, details)
                VALUES (?, ?, ?)
                """,
                (actor_id, event_type, details),
            )

    def count_audit_events(self, event_type: str) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM audit_events WHERE event_type = ?", (event_type,)
        ).fetchone()
        return int(row[0])

    def assign_ticket(self, number: int, agent_id: int, assigned_by: int) -> Ticket:
        ticket = self.get_ticket(number)
        if ticket is None:
            raise ValueError(f"Unknown ticket: {number}")
        if ticket.status not in {"Open", "In Progress"}:
            raise ValueError("Only an active ticket can be assigned.")
        if ticket.assignee_id is not None:
            if ticket.assignee_id == agent_id:
                return ticket
            raise ValueError("Ticket is already assigned.")
        with self.connection:
            self.connection.execute(
                """
                UPDATE tickets SET assignee_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE number = ?
                """,
                (agent_id, number),
            )
            self.connection.execute(
                """
                INSERT INTO assignments(ticket_number, agent_id, assigned_by)
                VALUES (?, ?, ?)
                """,
                (number, agent_id, assigned_by),
            )
        assigned = self.get_ticket(number)
        assert assigned is not None
        return assigned

    def update_status(
        self,
        number: int,
        expected_status: str,
        new_status: str,
        actor_id: int,
        reason: str | None = None,
    ) -> Ticket:
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP,
                    fixed_at = CASE WHEN ? = 'Fixed'
                        THEN CURRENT_TIMESTAMP ELSE fixed_at END,
                    closed_at = CASE WHEN ? = 'Closed'
                        THEN CURRENT_TIMESTAMP ELSE closed_at END
                WHERE number = ? AND status = ?
                """,
                (new_status, new_status, new_status, number, expected_status),
            )
            if cursor.rowcount != 1:
                raise ValueError("Ticket status changed; refresh and retry.")
            self.connection.execute(
                """
                INSERT INTO status_history(
                    ticket_number, previous_status, new_status, actor_id, reason
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (number, expected_status, new_status, actor_id, reason),
            )
        ticket = self.get_ticket(number)
        assert ticket is not None
        return ticket

    def count_status_history(self, number: int) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM status_history WHERE ticket_number = ?", (number,)
        ).fetchone()
        return int(row[0])

    def active_tickets(self, reporter_id: int) -> list[Ticket]:
        rows = self.connection.execute(
            """
            SELECT number, reporter_id, service_name, urgency, title, description,
                   status, topic_id, card_message_id, assignee_id
            FROM tickets
            WHERE reporter_id = ? AND status != 'Closed'
            ORDER BY number
            """,
            (reporter_id,),
        ).fetchall()
        return [Ticket(**dict(row)) for row in rows]

    def actionable_tickets(self) -> list[Ticket]:
        rows = self.connection.execute(
            """
            SELECT number, reporter_id, service_name, urgency, title, description,
                   status, topic_id, card_message_id, assignee_id
            FROM tickets
            WHERE status IN ('Open', 'In Progress')
            ORDER BY number
            """
        ).fetchall()
        return [Ticket(**dict(row)) for row in rows]

    def closable_tickets(self) -> list[Ticket]:
        """Open, In Progress, and Fixed tickets an admin can close."""
        rows = self.connection.execute(
            """
            SELECT number, reporter_id, service_name, urgency, title, description,
                   status, topic_id, card_message_id, assignee_id
            FROM tickets
            WHERE status IN ('Open', 'In Progress', 'Fixed')
            ORDER BY number
            """
        ).fetchall()
        return [Ticket(**dict(row)) for row in rows]

    def record_message(
        self,
        *,
        ticket_number: int,
        direction: str,
        source_chat_id: int,
        source_message_id: int,
        destination_chat_id: int | None,
        destination_message_id: int | None,
        text: str | None,
        delivery_status: str,
        relay_method: str = "copy",
    ) -> int:
        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO ticket_messages(
                    ticket_number, direction, source_chat_id, source_message_id,
                    destination_chat_id, destination_message_id, text,
                    relay_method, delivery_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket_number,
                    direction,
                    source_chat_id,
                    source_message_id,
                    destination_chat_id,
                    destination_message_id,
                    text,
                    relay_method,
                    delivery_status,
                ),
            )
        row = self.connection.execute(
            """
            SELECT id FROM ticket_messages
            WHERE source_chat_id = ? AND source_message_id = ? AND direction = ?
            """,
            (source_chat_id, source_message_id, direction),
        ).fetchone()
        return int(row[0])

    def get_relay_message(self, message_id: int) -> RelayMessage | None:
        row = self.connection.execute(
            """
            SELECT id, ticket_number, direction, source_chat_id, source_message_id,
                   destination_chat_id, destination_message_id, text,
                   relay_method, delivery_status
            FROM ticket_messages WHERE id = ?
            """,
            (message_id,),
        ).fetchone()
        return RelayMessage(**dict(row)) if row else None

    def mark_message_sent(
        self, message_id: int, destination_chat_id: int, destination_message_id: int
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE ticket_messages
                SET destination_chat_id = ?, destination_message_id = ?,
                    delivery_status = 'sent'
                WHERE id = ?
                """,
                (destination_chat_id, destination_message_id, message_id),
            )

    def pending_reporter_messages(self, number: int) -> list[RelayMessage]:
        rows = self.connection.execute(
            """
            SELECT id, ticket_number, direction, source_chat_id, source_message_id,
                   destination_chat_id, destination_message_id, text,
                   relay_method, delivery_status
            FROM ticket_messages
            WHERE ticket_number = ? AND direction = 'reporter_to_team'
              AND delivery_status IN ('pending', 'failed')
            ORDER BY id
            """,
            (number,),
        ).fetchall()
        return [RelayMessage(**dict(row)) for row in rows]
