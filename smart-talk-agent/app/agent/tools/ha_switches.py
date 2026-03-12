"""Switch and input_boolean control tools for Smart Talk."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel, Field

from app.agent.tools.base import SmartTalkTool

_SWITCH_DOMAINS = ["switch", "input_boolean"]


def _joined_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


class GetSwitchStateInput(BaseModel):
    entity_name: str = Field(..., description="Name or description of the switch or boolean to check")


class SwitchInput(BaseModel):
    entity_name: str = Field(..., description="Name or description of the switch or toggle")
    target_all: bool = Field(
        False,
        description="When true, apply the action to ALL matching switches.",
    )


class TurnOnSwitchTool(SmartTalkTool):
    """Turn on a switch or input_boolean."""

    name: str = "turn_on_switch"
    description: str = "Turn on a switch or boolean helper."
    args_schema: Type[BaseModel] = SwitchInput

    async def _arun(self, entity_name: str, target_all: bool = False) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=_SWITCH_DOMAINS)
        if not result.entities:
            return f"Sorry, I couldn't find a switch matching '{entity_name}'."
        if result.is_ambiguous and not target_all:
            return self._ambiguity_clarification(result.candidates_description, "turn on")
        entities = result.entities if target_all else [result.entities[0]]
        names: list[str] = []
        for entity in entities:
            await self.ha_client.call_service(entity.domain, "turn_on", entity.entity_id)
            names.append(entity.friendly_name)
        return f"Turned on {_joined_names(names)}."


class TurnOffSwitchTool(SmartTalkTool):
    """Turn off a switch or input_boolean."""

    name: str = "turn_off_switch"
    description: str = "Turn off a switch or boolean helper."
    args_schema: Type[BaseModel] = SwitchInput

    async def _arun(self, entity_name: str, target_all: bool = False) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=_SWITCH_DOMAINS)
        if not result.entities:
            return f"Sorry, I couldn't find a switch matching '{entity_name}'."
        if result.is_ambiguous and not target_all:
            return self._ambiguity_clarification(result.candidates_description, "turn off")
        entities = result.entities if target_all else [result.entities[0]]
        names: list[str] = []
        for entity in entities:
            await self.ha_client.call_service(entity.domain, "turn_off", entity.entity_id)
            names.append(entity.friendly_name)
        return f"Turned off {_joined_names(names)}."


class ToggleSwitchTool(SmartTalkTool):
    """Toggle a switch or input_boolean between on and off."""

    name: str = "toggle_switch"
    description: str = "Toggle a switch or boolean helper (on→off or off→on)."
    args_schema: Type[BaseModel] = SwitchInput

    async def _arun(self, entity_name: str, target_all: bool = False) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=_SWITCH_DOMAINS)
        if not result.entities:
            return f"Sorry, I couldn't find a switch matching '{entity_name}'."
        if result.is_ambiguous and not target_all:
            return self._ambiguity_clarification(result.candidates_description, "toggle")
        entities = result.entities if target_all else [result.entities[0]]
        names: list[str] = []
        for entity in entities:
            await self.ha_client.call_service(entity.domain, "toggle", entity.entity_id)
            names.append(entity.friendly_name)
        return f"Toggled {_joined_names(names)}."


class GetSwitchStateTool(SmartTalkTool):
    """Fetch the live current state of a switch or input_boolean from Home Assistant."""

    name: str = "get_switch_state"
    description: str = (
        "Get the current state (on/off) of a switch or boolean helper. "
        "Always use this to check live state — never infer from conversation history."
    )
    args_schema: Type[BaseModel] = GetSwitchStateInput

    async def _arun(self, entity_name: str) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=_SWITCH_DOMAINS)
        if not result.entities:
            return f"Sorry, I couldn't find a switch matching '{entity_name}'."
        if result.is_ambiguous:
            return self._ambiguity_clarification(
                result.candidates_description, "check", allow_all=False
            )
        entity = result.entities[0]
        fresh = await self.ha_client.get_state(entity.entity_id)
        return f"{entity.friendly_name} is {fresh.state}."
