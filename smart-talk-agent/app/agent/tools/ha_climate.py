"""Climate control tools for Smart Talk."""

from __future__ import annotations

from typing import Literal, Type

from pydantic import BaseModel, Field

from app.agent.tools.base import SmartTalkTool

_CLIMATE_DOMAINS = ["climate"]


def _joined_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


# ── Input schemas ─────────────────────────────────────────────────────────────

class SetTemperatureInput(BaseModel):
    entity_name: str = Field(..., description="Name or description of the climate device")
    temperature: float = Field(..., description="Target temperature to set")
    target_all: bool = Field(
        False,
        description="When true, set the same temperature on ALL matching climate devices.",
    )


class SetHvacModeInput(BaseModel):
    entity_name: str = Field(..., description="Name or description of the climate device")
    hvac_mode: Literal["heat", "cool", "auto", "heat_cool", "dry", "fan_only", "off"] = Field(
        ..., description="HVAC operating mode"
    )
    target_all: bool = Field(
        False,
        description="When true, set the same HVAC mode on ALL matching climate devices.",
    )


class GetClimateStateInput(BaseModel):
    entity_name: str = Field(..., description="Name or description of the climate device")


# ── Tools ─────────────────────────────────────────────────────────────────────

class SetTemperatureTool(SmartTalkTool):
    """Set the target temperature on a climate (thermostat/HVAC) entity."""

    name: str = "set_temperature"
    description: str = "Set the target temperature on a thermostat or climate device."
    args_schema: Type[BaseModel] = SetTemperatureInput

    async def _arun(self, entity_name: str, temperature: float, target_all: bool = False) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=_CLIMATE_DOMAINS)
        if not result.entities:
            return f"Sorry, I couldn't find a climate device matching '{entity_name}'."
        if result.is_ambiguous and not target_all:
            return self._ambiguity_clarification(
                result.candidates_description, f"set to {temperature}°"
            )
        entities = result.entities if target_all else [result.entities[0]]
        names: list[str] = []
        for entity in entities:
            await self.ha_client.call_service(
                "climate", "set_temperature", entity.entity_id, temperature=temperature
            )
            names.append(entity.friendly_name)
        return f"Set {_joined_names(names)} target temperature to {temperature}°."


class SetHvacModeTool(SmartTalkTool):
    """Set the HVAC mode on a climate entity."""

    name: str = "set_hvac_mode"
    description: str = (
        "Set the HVAC operating mode on a thermostat or climate device. "
        "Valid modes: heat, cool, auto, heat_cool, dry, fan_only, off."
    )
    args_schema: Type[BaseModel] = SetHvacModeInput

    async def _arun(self, entity_name: str, hvac_mode: str, target_all: bool = False) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=_CLIMATE_DOMAINS)
        if not result.entities:
            return f"Sorry, I couldn't find a climate device matching '{entity_name}'."
        if result.is_ambiguous and not target_all:
            return self._ambiguity_clarification(
                result.candidates_description, f"set to {hvac_mode} mode"
            )
        entities = result.entities if target_all else [result.entities[0]]
        names: list[str] = []
        for entity in entities:
            await self.ha_client.call_service(
                "climate", "set_hvac_mode", entity.entity_id, hvac_mode=hvac_mode
            )
            names.append(entity.friendly_name)
        return f"Set {_joined_names(names)} to {hvac_mode} mode."


class GetClimateStateTool(SmartTalkTool):
    """Get the current and target temperature of a climate entity."""

    name: str = "get_climate_state"
    description: str = (
        "Get the current temperature and target temperature of a thermostat or climate device."
    )
    args_schema: Type[BaseModel] = GetClimateStateInput

    async def _arun(self, entity_name: str) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=_CLIMATE_DOMAINS)
        if not result.entities:
            return f"Sorry, I couldn't find a climate device matching '{entity_name}'."
        if result.is_ambiguous:
            return self._ambiguity_clarification(
                result.candidates_description, "check", allow_all=False
            )
        entity = result.entities[0]
        fresh = await self.ha_client.get_state(entity.entity_id)
        current = fresh.attributes.get("current_temperature", "unknown")
        target = fresh.attributes.get("temperature", "unknown")
        unit = fresh.attributes.get("temperature_unit", "°")
        mode = fresh.state
        return (
            f"{fresh.friendly_name}: current temperature {current}{unit}, "
            f"target {target}{unit}, mode {mode}."
        )
