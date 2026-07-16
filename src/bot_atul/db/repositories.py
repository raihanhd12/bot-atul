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
        ticket = self.get_ticket(cursor.lastrowid)
        assert ticket is not None
        return ticket

    def get_ticket(self, number: int) -> Ticket | None:
        row = self.connection.execute(
            """
            SELECT number, reporter_id, service_name, urgency, title,
                   description, status
            FROM tickets WHERE number = ?
            """,
            (number,),
        ).fetchone()
        return Ticket(**dict(row)) if row else None

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
        if role not in {"reporter", "agent", "admin"}:
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
