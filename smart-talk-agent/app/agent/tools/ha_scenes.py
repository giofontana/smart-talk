"""Scene activation tool for Smart Talk."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel, Field

from app.agent.tools.base import SmartTalkTool


class ActivateSceneInput(BaseModel):
    entity_name: str = Field(
        ...,
        description="Name or description of the scene to activate (e.g. 'movie night', 'morning routine')",
    )


class ActivateSceneTool(SmartTalkTool):
    """Activate a Home Assistant scene."""

    name: str = "activate_scene"
    description: str = "Activate a Home Assistant scene by name or description."
    args_schema: Type[BaseModel] = ActivateSceneInput

    async def _arun(self, entity_name: str) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=["scene"])
        if not result.entities:
            return f"Sorry, I couldn't find a scene matching '{entity_name}'."
        if result.is_ambiguous:
            return (
                f"I found multiple scenes that could match '{entity_name}': "
                f"{result.candidates_description}. Which one would you like to activate?"
            )
        entity = result.entities[0]
        await self.ha_client.call_service("scene", "turn_on", entity.entity_id)
        return f"Activated scene '{entity.friendly_name}'."
