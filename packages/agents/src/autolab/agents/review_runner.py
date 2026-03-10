from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from typing import Any

from autolab.agents.prompts import (
    ANALYSIS_PROMPT,
    CRITIC_PROMPT,
    PLANNER_PROMPT,
    WORKFLOW_PROMPT,
)
from autolab.core.enums import ReviewStatus
from autolab.core.settings import Settings
from pydantic import BaseModel, Field

try:
    from google.adk.agents import LlmAgent
    from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
    from google.adk.runners import Runner
    from google.adk.sessions.in_memory_session_service import InMemorySessionService
    from google.adk.utils.context_utils import Aclosing
    from google.genai import types
except Exception:  # pragma: no cover - runtime dependency check
    LlmAgent = None
    Runner = None
    InMemorySessionService = None
    InMemoryMemoryService = None
    Aclosing = None
    types = None


REVIEW_AGENT_PROMPTS = {
    "analysis_agent": ANALYSIS_PROMPT,
    "critic_agent": CRITIC_PROMPT,
    "planner_agent": PLANNER_PROMPT,
    "workflow_agent": WORKFLOW_PROMPT,
}


class ReviewRuntimeUnavailableError(RuntimeError):
    pass


class ReviewAgentRequest(BaseModel):
    agent_name: str
    objective: str
    context_bundle: dict[str, Any]
    prior_posts: list[dict[str, Any]] = Field(default_factory=list)


class ReviewAgentReply(BaseModel):
    summary: str
    rationale: str
    recommendation: ReviewStatus = ReviewStatus.OPEN
    concerns: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ReviewAgentRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(self, request: ReviewAgentRequest) -> ReviewAgentReply:
        if request.agent_name not in REVIEW_AGENT_PROMPTS:
            msg = f"unsupported review agent: {request.agent_name}"
            raise ValueError(msg)
        self._ensure_runtime()
        return asyncio.run(self._run_async(request))

    def _ensure_runtime(self) -> None:
        if LlmAgent is None or Runner is None or InMemorySessionService is None or types is None:
            msg = "google-adk runtime is not installed"
            raise ReviewRuntimeUnavailableError(msg)
        if self._settings.model_provider.provider == "stub":
            msg = "review runtime requires a configured non-stub model provider"
            raise ReviewRuntimeUnavailableError(msg)
        if not self._settings.model_provider.model_name:
            msg = "review runtime requires AUTOLAB_MODEL__MODEL_NAME"
            raise ReviewRuntimeUnavailableError(msg)
        if not self._settings.model_provider.api_key:
            msg = "review runtime requires AUTOLAB_MODEL__API_KEY"
            raise ReviewRuntimeUnavailableError(msg)
        provider = self._settings.model_provider.provider.lower()
        if provider in {"google", "gemini"}:
            os.environ.setdefault("GOOGLE_API_KEY", self._settings.model_provider.api_key)

    async def _run_async(self, request: ReviewAgentRequest) -> ReviewAgentReply:
        assert LlmAgent is not None
        assert Runner is not None
        assert InMemorySessionService is not None
        assert InMemoryMemoryService is not None
        assert Aclosing is not None
        assert types is not None

        agent = LlmAgent(
            name=request.agent_name,
            description=f"{request.agent_name} review runner",
            model=self._settings.model_provider.model_name,
            instruction=self._instruction_for(request.agent_name),
            output_schema=ReviewAgentReply,
            tools=[],
        )
        runner = Runner(
            app_name=f"autolab-review-{request.agent_name}",
            agent=agent,
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )
        session = await runner.session_service.create_session(
            app_name=f"autolab-review-{request.agent_name}",
            user_id="autolab-review",
            state={},
        )
        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=self._message_for(request))],
        )
        last_content = None
        async with Aclosing(
            runner.run_async(user_id=session.user_id, session_id=session.id, new_message=content)
        ) as events:
            async for event in events:
                if event.content:
                    last_content = event.content
        if last_content is None or last_content.parts is None:
            msg = "review runtime returned no content"
            raise RuntimeError(msg)
        merged_text = "\n".join(part.text for part in last_content.parts if part.text)
        return ReviewAgentReply.model_validate_json(merged_text)

    @staticmethod
    def _instruction_for(agent_name: str) -> str:
        base_prompt = REVIEW_AGENT_PROMPTS[agent_name]
        return "\n".join(
            [
                base_prompt,
                (
                    "You are participating in a structured review thread "
                    "for an autonomous materials lab."
                ),
                "Respond only with JSON that matches the ReviewAgentReply schema.",
                (
                    "Ground every claim in the provided campaign, run, summary, "
                    "decision, artifact, and discussion context."
                ),
                (
                    "Use recommendation values from: open, changes_requested, "
                    "approved, resolved, in_review."
                ),
                (
                    "Prefer 'open' for non-moderator agents unless there is strong "
                    "evidence for approval or changes_requested."
                ),
            ]
        )

    @staticmethod
    def _message_for(request: ReviewAgentRequest) -> str:
        sections: list[str] = [
            f"Review objective:\n{request.objective}",
            "Context bundle:",
            ReviewAgentRequest.model_validate(request).model_dump_json(indent=2),
        ]
        return "\n\n".join(sections)


def default_review_participants(run_attached: bool) -> list[str]:
    participants = ["analysis_agent", "critic_agent"]
    if run_attached:
        participants.append("planner_agent")
    participants.append("workflow_agent")
    return participants


def normalize_moderated_participants(
    participant_keys: Sequence[str] | None, *, run_attached: bool
) -> list[str]:
    default_order = default_review_participants(run_attached)
    if not participant_keys:
        return default_order
    selected = [key for key in default_order if key in set(participant_keys)]
    if "workflow_agent" not in selected:
        selected.append("workflow_agent")
    return selected
