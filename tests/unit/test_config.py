from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from bot_atul.config import Config


def valid_env() -> dict[str, str]:
    return {
        "BOT_TOKEN": "123:test-token",
        "TEAM_GROUP_ID": "-100123",
        "DASHBOARD_TOPIC_ID": "42",
        "ADMIN_IDS": "10, 20",
        "TIMEZONE": "Asia/Jakarta",
        "REMINDER_TIME": "09:00",
        "DATA_DIR": "/tmp/bot-atul/data",
        "BACKUP_DIR": "/tmp/bot-atul/backups",
    }


def test_config_parses_required_values() -> None:
    config = Config.from_mapping(valid_env())

    assert config.bot_token == "123:test-token"
    assert config.team_group_id == -100123
    assert config.dashboard_topic_id == 42
    assert config.admin_ids == frozenset({10, 20})
    assert config.timezone == ZoneInfo("Asia/Jakarta")
    assert config.reminder_time == time(9)
    assert config.data_dir == Path("/tmp/bot-atul/data")
    assert config.backup_dir == Path("/tmp/bot-atul/backups")


@pytest.mark.parametrize("missing", valid_env())
def test_config_rejects_missing_values(missing: str) -> None:
    env = valid_env()
    del env[missing]

    with pytest.raises(ValueError, match=missing):
        Config.from_mapping(env)


def test_config_rejects_invalid_timezone() -> None:
    env = valid_env() | {"TIMEZONE": "Mars/Olympus"}

    with pytest.raises(ValueError, match="TIMEZONE"):
        Config.from_mapping(env)


def test_config_rejects_invalid_reminder_time() -> None:
    env = valid_env() | {"REMINDER_TIME": "25:00"}

    with pytest.raises(ValueError, match="REMINDER_TIME"):
        Config.from_mapping(env)


def test_config_repr_hides_token() -> None:
    config = Config.from_mapping(valid_env())

    assert "test-token" not in repr(config)
