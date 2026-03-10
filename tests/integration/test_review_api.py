from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from autolab.agents import ReviewAgentReply
from autolab.api.dependencies import get_review_service
from autolab.api.main import app
from autolab.campaigns import ReviewService
from autolab.core.enums import ReviewStatus
from autolab.core.settings import get_settings
from autolab.storage import ArtifactRepository
from autolab.storage.db import session_scope
from fastapi.testclient import TestClient


class StubReviewRunner:
    def __init__(self) -> None:
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        recommendation = "open"
        if request.agent_name == "workflow_agent":
            recommendation = "approved"
        return ReviewAgentReply(
            summary=f"{request.agent_name} summary",
            rationale=f"{request.agent_name} rationale",
            recommendation=recommendation,
            concerns=["none"],
            next_steps=["ship it"],
        )


def test_review_api_flow() -> None:
    settings = get_settings()
    app.dependency_overrides[get_review_service] = lambda: ReviewService(
        settings, review_runner=StubReviewRunner()
    )
    try:
        client = TestClient(app)
        headers = {"Authorization": "Bearer dev-token"}
        payload = json.loads(
            Path("examples/campaigns/demo_campaign.json").read_text(encoding="utf-8")
        )

        campaign = client.post("/campaigns", json=payload, headers=headers).json()
        client.post(f"/campaigns/{campaign['id']}/start", headers=headers)
        step_response = client.post(
            f"/campaigns/{campaign['id']}/step",
            json={"execute_inline": True},
            headers=headers,
        )
        assert step_response.status_code == 200
        run_id = step_response.json()["run_ids"][0]

        with session_scope(settings) as session:
            artifacts = ArtifactRepository(session).list_for_campaign(
                campaign_id=UUID(campaign["id"])
            )
        artifact_id = str(artifacts[0].id)

        create_review = client.post(
            f"/campaigns/{campaign['id']}/reviews",
            json={
                "title": "Run acceptance",
                "objective": "Decide whether the run is acceptable.",
                "created_by": "alice",
                "run_id": run_id,
                "artifact_ids": [artifact_id],
                "participants": [],
            },
            headers=headers,
        )
        assert create_review.status_code == 201
        review_id = create_review.json()["review"]["id"]

        comment = client.post(
            f"/reviews/{review_id}/posts",
            json={
                "author_key": "alice",
                "author_type": "human",
                "body": "Please review this run.",
            },
            headers=headers,
        )
        assert comment.status_code == 200

        round_response = client.post(
            f"/reviews/{review_id}/rounds",
            json={"mode": "moderated_panel", "participant_keys": [], "execute_inline": True},
            headers=headers,
        )
        assert round_response.status_code == 200
        assert round_response.json()["round"]["recommendation"] == "approved"

        detail = client.get(f"/reviews/{review_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["review"]["status"] == "approved"

        posts = client.get(f"/reviews/{review_id}/posts", headers=headers)
        assert posts.status_code == 200
        assert len(posts.json()["posts"]) >= 5

        filtered = client.get(
            f"/campaigns/{campaign['id']}/reviews",
            params={"run_id": run_id},
            headers=headers,
        )
        assert filtered.status_code == 200
        assert len(filtered.json()["reviews"]) == 1

        resolve = client.post(
            f"/reviews/{review_id}/resolve",
            json={
                "status": ReviewStatus.CHANGES_REQUESTED.value,
                "resolution_summary": "Need one more validation pass.",
                "resolved_by": "alice",
            },
            headers=headers,
        )
        assert resolve.status_code == 200
        assert resolve.json()["review"]["status"] == ReviewStatus.CHANGES_REQUESTED.value
    finally:
        app.dependency_overrides.clear()
