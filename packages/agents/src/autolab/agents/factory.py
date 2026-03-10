from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from autolab.agents.prompts import (
    ANALYSIS_PROMPT,
    CRITIC_PROMPT,
    EXECUTION_PROMPT,
    PLANNER_PROMPT,
    WORKFLOW_PROMPT,
)
from autolab.core.settings import Settings
from autolab.skills import SkillRegistry, get_builtin_skills

ADK_LLM_AGENT: Any | None = None
try:
    from google.adk.agents import LlmAgent as ImportedLlmAgent
except Exception:  # pragma: no cover - fallback for environments without ADK
    pass
else:
    ADK_LLM_AGENT = ImportedLlmAgent


@dataclass(slots=True)
class AgentSuite:
    planner_agent: Any
    execution_agent: Any
    analysis_agent: Any
    critic_agent: Any
    workflow_agent: Any


def _build_agent(name: str, instruction: str, tools: list[Any], settings: Settings) -> Any:
    if ADK_LLM_AGENT is None:
        return {
            "name": name,
            "instruction": instruction,
            "model": settings.model_provider.model_name,
            "tools": tools,
        }
    return ADK_LLM_AGENT(
        name=name,
        model=settings.model_provider.model_name,
        instruction=instruction,
        tools=tools,
    )


def build_agent_suite(settings: Settings, registry: SkillRegistry | None = None) -> AgentSuite:
    skill_registry = registry or get_builtin_skills()
    tools = [skill.as_tool() for skill in skill_registry.list()]
    return AgentSuite(
        planner_agent=_build_agent("planner_agent", PLANNER_PROMPT, tools, settings),
        execution_agent=_build_agent("execution_agent", EXECUTION_PROMPT, tools, settings),
        analysis_agent=_build_agent("analysis_agent", ANALYSIS_PROMPT, tools, settings),
        critic_agent=_build_agent("critic_agent", CRITIC_PROMPT, tools, settings),
        workflow_agent=_build_agent("workflow_agent", WORKFLOW_PROMPT, tools, settings),
    )
