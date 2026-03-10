from __future__ import annotations

import importlib
from typing import Any

from autolab.core.settings import get_settings

worker_main = importlib.import_module("autolab.worker.main")


class _RemoteStub:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.calls: list[tuple[Any, ...]] = []

    def remote(self, *args: Any) -> dict[str, object]:
        self.calls.append(args)
        return self.result


def test_handle_queue_message_dispatches_review_round(monkeypatch) -> None:
    settings = get_settings()
    remote_stub = _RemoteStub({"status": "completed"})
    monkeypatch.setattr(worker_main, "process_review_round", remote_stub)
    monkeypatch.setattr(worker_main.ray, "get", lambda payload: payload)

    result = worker_main.handle_queue_message(
        settings,
        {
            "event_type": "run_review_round",
            "review_id": "11111111-1111-1111-1111-111111111111",
            "review_round_id": "22222222-2222-2222-2222-222222222222",
        },
    )

    assert result == {"status": "completed"}
    assert remote_stub.calls
