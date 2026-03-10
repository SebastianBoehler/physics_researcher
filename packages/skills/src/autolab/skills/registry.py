from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(slots=True)
class SkillContext:
    campaign_service: Any | None = None
    optimizer: Any | None = None
    simulator_registry: Any | None = None


class SkillSpec[InputT: BaseModel, OutputT: BaseModel]:
    def __init__(
        self,
        name: str,
        description: str,
        input_model: type[InputT],
        output_model: type[OutputT],
        executor: Callable[[InputT, SkillContext], OutputT],
    ) -> None:
        self.name = name
        self.description = description
        self.input_model = input_model
        self.output_model = output_model
        self.executor = executor

    def run(self, payload: InputT, context: SkillContext) -> OutputT:
        return self.executor(payload, context)

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
