from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class Config:
    bot_token: str = field(repr=False)
    team_group_id: int
    dashboard_topic_id: int
    admin_ids: frozenset[int]
    timezone: ZoneInfo
    data_dir: Path
    backup_dir: Path

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Config:
        required = (
            "BOT_TOKEN",
            "TEAM_GROUP_ID",
            "DASHBOARD_TOPIC_ID",
            "ADMIN_IDS",
            "TIMEZONE",
            "DATA_DIR",
            "BACKUP_DIR",
        )
        missing = [name for name in required if not values.get(name, "").strip()]
        if missing:
            raise ValueError(f"Missing configuration: {', '.join(missing)}")

        try:
            timezone = ZoneInfo(values["TIMEZONE"])
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"Invalid TIMEZONE: {values['TIMEZONE']}") from error

        try:
            return cls(
                bot_token=values["BOT_TOKEN"],
                team_group_id=int(values["TEAM_GROUP_ID"]),
                dashboard_topic_id=int(values["DASHBOARD_TOPIC_ID"]),
                admin_ids=frozenset(
                    int(value.strip()) for value in values["ADMIN_IDS"].split(",")
                ),
                timezone=timezone,
                data_dir=Path(values["DATA_DIR"]),
                backup_dir=Path(values["BACKUP_DIR"]),
            )
        except ValueError as error:
            raise ValueError(f"Invalid numeric configuration: {error}") from error

    @classmethod
    def from_env(cls) -> Config:
        return cls.from_mapping(os.environ)
