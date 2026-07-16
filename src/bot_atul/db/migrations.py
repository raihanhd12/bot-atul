import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('agent', 'admin')),
    username TEXT,
    display_name TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    position INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tickets (
    number INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL REFERENCES users(telegram_id),
    service_id INTEGER NOT NULL REFERENCES services(id),
    service_name TEXT NOT NULL,
    urgency TEXT NOT NULL CHECK (urgency IN ('Low', 'Normal', 'High', 'Critical')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Open'
        CHECK (status IN ('Open', 'In Progress', 'Fixed', 'Closed')),
    topic_id INTEGER UNIQUE,
    card_message_id INTEGER,
    assignee_id INTEGER REFERENCES users(telegram_id),
    closure_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fixed_at TEXT,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS ticket_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number INTEGER NOT NULL REFERENCES tickets(number),
    direction TEXT NOT NULL CHECK (
        direction IN ('reporter_to_team', 'team_to_reporter', 'internal')
    ),
    source_chat_id INTEGER NOT NULL,
    source_message_id INTEGER NOT NULL,
    destination_chat_id INTEGER,
    destination_message_id INTEGER,
    text TEXT,
    relay_method TEXT NOT NULL DEFAULT 'copy' CHECK (relay_method IN ('copy', 'text')),
    delivery_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_chat_id, source_message_id, direction)
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number INTEGER NOT NULL REFERENCES tickets(number),
    message_id INTEGER REFERENCES ticket_messages(id),
    kind TEXT NOT NULL,
    telegram_file_id TEXT NOT NULL,
    file_name TEXT,
    caption TEXT
);

CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number INTEGER NOT NULL REFERENCES tickets(number),
    agent_id INTEGER NOT NULL REFERENCES users(telegram_id),
    assigned_by INTEGER NOT NULL REFERENCES users(telegram_id),
    assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_workspaces (
    ticket_number INTEGER PRIMARY KEY REFERENCES tickets(number),
    agent_id INTEGER NOT NULL REFERENCES users(telegram_id),
    message_id INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticket_dashboard_cards (
    ticket_number INTEGER PRIMARY KEY REFERENCES tickets(number),
    message_id INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number INTEGER NOT NULL REFERENCES tickets(number),
    previous_status TEXT,
    new_status TEXT NOT NULL,
    actor_id INTEGER NOT NULL REFERENCES users(telegram_id),
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dashboard_posts (
    digest_date TEXT NOT NULL,
    page INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (digest_date, page)
);

CREATE TABLE IF NOT EXISTS processed_updates (
    update_id INTEGER PRIMARY KEY,
    processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER,
    ticket_number INTEGER REFERENCES tickets(number),
    event_type TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS tickets_status_idx ON tickets(status);
CREATE INDEX IF NOT EXISTS tickets_reporter_status_idx ON tickets(reporter_id, status);
CREATE INDEX IF NOT EXISTS messages_ticket_idx ON ticket_messages(ticket_number);
CREATE INDEX IF NOT EXISTS history_ticket_idx ON status_history(ticket_number);
"""

SERVICES = ("General", "Technical", "Billing", "Other")


def migrate(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    connection.executemany(
        "INSERT OR IGNORE INTO services(name, position) VALUES (?, ?)",
        ((name, position) for position, name in enumerate(SERVICES)),
    )
    _migrate_legacy_reporter_roles(connection)
    connection.commit()


def _migrate_legacy_reporter_roles(connection: sqlite3.Connection) -> None:
    """Promote legacy reporter users to agents.

    Existing databases may still carry an older CHECK that mentions
    ``reporter``. Application code rejects new reporter roles, and new
    installs use the tighter schema above.
    """
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    if "users" not in tables:
        return
    connection.execute("UPDATE users SET role = 'agent' WHERE role = 'reporter'")
