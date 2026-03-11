from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


@dataclass(slots=True)
class SkillContext:
    campaign_service: Any | None = None
    optimizer: Any | None = None
    simulator_registry: Any | None = None


class SkillMetadata(BaseModel):
    name: str
    description: str
    domain: str = "general"
    source: str = "native"
    trust_level: str = "execution_safe"
    tags: list[str] = Field(default_factory=list)
    required_context: list[str] = Field(default_factory=list)
    required_integrations: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class SkillSpec[InputT: BaseModel, OutputT: BaseModel]:
    def __init__(
        self,
        name: str,
        description: str,
        input_model: type[InputT],
        output_model: type[OutputT],
        executor: Callable[[InputT, SkillContext], OutputT],
        *,
        domain: str = "general",
        source: str = "native",
        trust_level: str = "execution_safe",
        tags: list[str] | None = None,
        required_context: list[str] | None = None,
        required_integrations: list[str] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.input_model = input_model
        self.output_model = output_model
        self.executor = executor
        self.domain = domain
        self.source = source
        self.trust_level = trust_level
        self.tags = tags or []
        self.required_context = required_context or []
        self.required_integrations = required_integrations or []

    def run(self, payload: InputT, context: SkillContext) -> OutputT:
        return self.executor(payload, context)

    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self.name,
            description=self.description,
            domain=self.domain,
            source=self.source,
            trust_level=self.trust_level,
            tags=self.tags,
            required_context=self.required_context,
            required_integrations=self.required_integrations,
            input_schema=self.input_model.model_json_schema(),
            output_schema=self.output_model.model_json_schema(),
        )

    def as_tool(self) -> Callable[..., dict[str, Any]]:
        def _tool(**kwargs: Any) -> dict[str, Any]:
            input_payload = self.input_model.model_validate(kwargs)
            return self.output_model.model_dump(self.run(input_payload, SkillContext()))

        _tool.__name__ = self.name
        _tool.__doc__ = self.description
        return _tool


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillSpec[Any, Any]] = {}

    def register(self, skill: SkillSpec[Any, Any]) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillSpec[Any, Any]:
        return self._skills[name]

    def list(self) -> list[SkillSpec[Any, Any]]:
        return list(self._skills.values())

    def list_metadata(
        self,
        *,
        domain: str | None = None,
        source: str | None = None,
        trust_level: str | None = None,
    ) -> list[SkillMetadata]:
        entries = [skill.metadata() for skill in self._skills.values()]
        if domain is not None:
            entries = [entry for entry in entries if entry.domain == domain]
        if source is not None:
            entries = [entry for entry in entries if entry.source == source]
        if trust_level is not None:
            entries = [entry for entry in entries if entry.trust_level == trust_level]
        return entries
