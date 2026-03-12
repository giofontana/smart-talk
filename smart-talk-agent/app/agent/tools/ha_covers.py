"""Cover control tools for Smart Talk (blinds, garage doors, etc.)."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel, Field

from app.agent.tools.base import SmartTalkTool

_COVER_DOMAINS = ["cover"]


class GetCoverStateInput(BaseModel):
    entity_name: str = Field(..., description="Name or description of the cover to check")


class CoverInput(BaseModel):
    entity_name: str = Field(..., description="Name or description of the cover (e.g. 'bedroom blinds')")
    target_all: bool = Field(
        False,
        description="When true, apply the action to ALL matching covers. "
                    "Use this after the user confirms they want all similar devices affected.",
    )


class SetCoverPositionInput(BaseModel):
    entity_name: str = Field(..., description="Name or description of the cover")
    position: int = Field(..., ge=0, le=100, description="Target position percentage (0=closed, 100=fully open)")
    target_all: bool = Field(
        False,
        description="When true, set position on ALL matching covers.",
    )


def _joined_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


class OpenCoverTool(SmartTalkTool):
    """Open a cover such as blinds, shutters, or a garage door."""

    name: str = "open_cover"
    description: str = "Open a cover (blinds, shutters, garage door, etc.)."
    args_schema: Type[BaseModel] = CoverInput

    async def _arun(self, entity_name: str, target_all: bool = False) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=_COVER_DOMAINS)
        if not result.entities:
            return f"Sorry, I couldn't find a cover matching '{entity_name}'."
        if result.is_ambiguous and not target_all:
            return self._ambiguity_clarification(result.candidates_description, "open")
        entities = result.entities if target_all else [result.entities[0]]
        names: list[str] = []
        for entity in entities:
            await self.ha_client.call_service("cover", "open_cover", entity.entity_id)
            names.append(entity.friendly_name)
        return f"Opened {_joined_names(names)}."


class CloseCoverTool(SmartTalkTool):
    """Close a cover such as blinds, shutters, or a garage door."""

    name: str = "close_cover"
    description: str = "Close a cover (blinds, shutters, garage door, etc.)."
    args_schema: Type[BaseModel] = CoverInput

    async def _arun(self, entity_name: str, target_all: bool = False) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=_COVER_DOMAINS)
        if not result.entities:
            return f"Sorry, I couldn't find a cover matching '{entity_name}'."
        if result.is_ambiguous and not target_all:
            return self._ambiguity_clarification(result.candidates_description, "close")
        entities = result.entities if target_all else [result.entities[0]]
        names: list[str] = []
        for entity in entities:
            await self.ha_client.call_service("cover", "close_cover", entity.entity_id)
            names.append(entity.friendly_name)
        return f"Closed {_joined_names(names)}."


class SetCoverPositionTool(SmartTalkTool):
    """Set a cover to a specific position (0=fully closed, 100=fully open)."""

    name: str = "set_cover_position"
    description: str = "Set a cover to a specific position (0=fully closed, 100=fully open)."
    args_schema: Type[BaseModel] = SetCoverPositionInput

    async def _arun(self, entity_name: str, position: int, target_all: bool = False) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=_COVER_DOMAINS)
        if not result.entities:
            return f"Sorry, I couldn't find a cover matching '{entity_name}'."
        if result.is_ambiguous and not target_all:
            return self._ambiguity_clarification(
                result.candidates_description, f"set to {position}%"
            )
        entities = result.entities if target_all else [result.entities[0]]
        names: list[str] = []
        for entity in entities:
            await self.ha_client.call_service(
                "cover", "set_cover_position", entity.entity_id, position=position
            )
            names.append(entity.friendly_name)
        return f"Set {_joined_names(names)} to {position}% open."


class GetCoverStateTool(SmartTalkTool):
    """Fetch the live current state of a cover directly from Home Assistant."""

    name: str = "get_cover_state"
    description: str = (
        "Get the current state (open/closed/opening/closing, position) of a cover "
        "such as blinds, shutters, or a garage door. "
        "Always use this to check live state — never infer from conversation history."
    )
    args_schema: Type[BaseModel] = GetCoverStateInput

    async def _arun(self, entity_name: str) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=_COVER_DOMAINS)
        if not result.entities:
            return f"Sorry, I couldn't find a cover matching '{entity_name}'."
        if result.is_ambiguous:
            return self._ambiguity_clarification(
                result.candidates_description, "check", allow_all=False
            )
        entity = result.entities[0]
        fresh = await self.ha_client.get_state(entity.entity_id)
        state = fresh.state
        parts: list[str] = [f"{entity.friendly_name} is {state}"]
        position = fresh.attributes.get("current_position")
        if position is not None:
            parts.append(f"position {position}%")
        return ", ".join(parts) + "."
