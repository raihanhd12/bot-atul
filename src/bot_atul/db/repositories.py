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
