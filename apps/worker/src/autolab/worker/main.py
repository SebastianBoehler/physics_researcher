from __future__ import annotations

import time
from uuid import UUID

import ray
from autolab.campaigns import CampaignQueue, CampaignService, ReviewService
from autolab.core.settings import Settings, get_settings
from autolab.simulators import build_default_registry
from autolab.storage import init_db
from autolab.telemetry import get_logger, setup_logging

logger = get_logger(__name__)


@ray.remote
def process_campaign_step(
    settings_payload: dict[str, object], campaign_id: str
) -> dict[str, object]:
    settings = Settings.model_validate(settings_payload)
    init_db(settings)
    service = CampaignService(
        settings=settings, simulator_registry=build_default_registry(settings)
    )
    return service.step_campaign(campaign_id=UUID(campaign_id))


@ray.remote
def process_review_round(
    settings_payload: dict[str, object], review_id: str, review_round_id: str
) -> dict[str, object]:
    settings = Settings.model_validate(settings_payload)
    init_db(settings)
    service = ReviewService(settings=settings)
    round_record = service.execute_round(review_id=UUID(review_id), round_id=UUID(review_round_id))
    return round_record.model_dump(mode="json")


def handle_queue_message(settings: Settings, payload: dict[str, str]) -> dict[str, object] | None:
    event_type = payload.get("event_type")
    if event_type == "step_campaign":
        return ray.get(process_campaign_step.remote(settings.snapshot(), payload["campaign_id"]))
    if event_type == "run_review_round":
        return ray.get(
            process_review_round.remote(
                settings.snapshot(),
                payload["review_id"],
                payload["review_round_id"],
            )
        )
    return None


def main() -> None:
    setup_logging()
    settings = get_settings()
    init_db(settings)
    queue = CampaignQueue(settings)
    queue.create_group()
    try:
        ray.init(address=settings.ray.address, ignore_reinit_error=True, logging_level="ERROR")
    except Exception:
        ray.init(ignore_reinit_error=True, logging_level="ERROR")
    logger.info(
        "worker_started", stream=settings.redis.stream_name, group=settings.redis.group_name
    )
    while True:
        messages = queue.read(consumer_name="worker-1", block_ms=1000)
        for message_id, payload in messages:
            result = handle_queue_message(settings, payload)
            if result is None:
                queue.ack(message_id)
                continue
            logger.info("worker_event_processed", message_id=message_id, result=result)
            queue.ack(message_id)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
