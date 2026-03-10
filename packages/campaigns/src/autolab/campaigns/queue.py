from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from autolab.core.settings import Settings
from pydantic import BaseModel, Field
from redis import Redis


class CampaignEvent(BaseModel):
    campaign_id: UUID
    event_type: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CampaignQueue:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._redis = Redis.from_url(settings.redis.url, decode_responses=True)

    def enqueue(self, event: CampaignEvent) -> str:
        payload = cast(
            dict[str | int | float, str | int | float],
            {key: str(value) for key, value in event.model_dump(mode="json").items()},
        )
        return cast(
            str,
            self._redis.xadd(self._settings.redis.stream_name, payload),  # type: ignore[arg-type]
        )

    def create_group(self) -> None:
        try:
            self._redis.xgroup_create(
                self._settings.redis.stream_name,
                self._settings.redis.group_name,
                id="0",
                mkstream=True,
            )
        except Exception:
            return

    def read(self, consumer_name: str, block_ms: int = 1000) -> list[tuple[str, dict[str, str]]]:
        self.create_group()
        messages = self._redis.xreadgroup(
            self._settings.redis.group_name,
            consumer_name,
            {self._settings.redis.stream_name: ">"},
            count=10,
            block=block_ms,
        )
        if not messages:
            return []
        _, entries = cast(list[tuple[str, list[tuple[str, dict[str, Any]]]]], messages)[0]
        return [
            (message_id, {key: str(value) for key, value in payload.items()})
            for message_id, payload in entries
        ]

    def ack(self, message_id: str) -> None:
        self._redis.xack(
            self._settings.redis.stream_name, self._settings.redis.group_name, message_id
        )
