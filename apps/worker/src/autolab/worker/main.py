from __future__ import annotations

import time
from uuid import UUID

import ray
from autolab.campaigns import CampaignQueue, CampaignService
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
            if payload.get("event_type") != "step_campaign":
                queue.ack(message_id)
                continue
            result = ray.get(
                process_campaign_step.remote(settings.snapshot(), payload["campaign_id"])
            )
            logger.info("campaign_step_processed", message_id=message_id, result=result)
            queue.ack(message_id)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
