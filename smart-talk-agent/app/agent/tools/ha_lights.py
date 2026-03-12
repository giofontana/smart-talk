"""Light control tools for Smart Talk."""

from __future__ import annotations

from typing import Optional, Type

from pydantic import BaseModel, Field

from app.agent.tools.base import SmartTalkTool


def _joined_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


# ── Input schemas ─────────────────────────────────────────────────────────────

class GetLightStateInput(BaseModel):
    entity_name: str = Field(..., description="Name or description of the light to check")


class TurnOnLightInput(BaseModel):
    entity_name: str = Field(..., description="Name or description of the light (e.g. 'kitchen ceiling light')")
    brightness: Optional[int] = Field(None, ge=0, le=100, description="Brightness percentage (0–100)")
    color_temp: Optional[int] = Field(None, description="Colour temperature in Kelvin (e.g. 2700 for warm white)")
    rgb_color: Optional[list[int]] = Field(None, description="RGB colour as [R, G, B] integers (0–255 each)")
    target_all: bool = Field(
        False,
        description="When true, turn on ALL matching lights. "
                    "Use after the user confirms they want all similar lights affected.",
    )


class TurnOffLightInput(BaseModel):
    entity_name: str = Field(..., description="Name or description of the light to turn off")
    target_all: bool = Field(
        False,
        description="When true, turn off ALL matching lights.",
    )


# ── Tools ─────────────────────────────────────────────────────────────────────

class TurnOnLightTool(SmartTalkTool):
    """Turn on a light or lighting group, with optional brightness and colour settings."""

    name: str = "turn_on_light"
    description: str = (
        "Turn on a light or lighting group. "
        "Optionally adjust brightness (0-100%) and colour temperature or RGB colour."
    )
    args_schema: Type[BaseModel] = TurnOnLightInput

    async def _arun(  # type: ignore[override]
        self,
        entity_name: str,
        brightness: int | None = None,
        color_temp: int | None = None,
        rgb_color: list[int] | None = None,
        target_all: bool = False,
    ) -> str:
        result = await self._resolve_entities(entity_name, domain_filter=["light"])
        if not result.entities:
            return f"Sorry, I couldn't find a light matching '{entity_name}'."
        if result.is_ambiguous and not target_all:
            return self._ambiguity_clarification(result.candidates_description, "turn on")

        service_data: dict = {}
        if brightness is not None:
            service_data["brightness_pct"] = brightness
        if color_temp is not None:
            service_data["color_temp_kelvin"] = color_temp
        if rgb_color is not None:
            service_data["rgb_color"] = rgb_color

        entities = result.entities if target_all else [result.entities[0]]
        names: list[str] = []
        for entity in entities:
            await self.ha_client.call_service("light", "turn_on", entity.entity_id, **service_data)
            names.append(entity.friendly_name)

        details_parts: list[str] = []
        if brightness is not None:
            details_parts.append(f"brightness {brightness}%")
        if color_temp is not None:
            details_parts.append(f"colour temperature {color_temp}K")
        details = f" ({', '.join(details_parts)})" if details_parts else ""
        return f"Turned on {_joined_names(names)}{details}."


class TurnOffLightTool(SmartTalkTool):
    """Turn off a light or lighting group."""

    name: str = "turn_off_light"
    description: str = "Turn off a light or lighting group."
    args_schema: Type[BaseModel] = TurnOffLightInput

    async def _arun(self, entity_name: str, target_all: bool = False) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=["light"])
        if not result.entities:
            return f"Sorry, I couldn't find a light matching '{entity_name}'."
        if result.is_ambiguous and not target_all:
            return self._ambiguity_clarification(result.candidates_description, "turn off")
        entities = result.entities if target_all else [result.entities[0]]
        names: list[str] = []
        for entity in entities:
            await self.ha_client.call_service("light", "turn_off", entity.entity_id)
            names.append(entity.friendly_name)
        return f"Turned off {_joined_names(names)}."


class GetLightStateTool(SmartTalkTool):
    """Fetch the live current state of a light directly from Home Assistant."""

    name: str = "get_light_state"
    description: str = (
        "Get the current state (on/off, brightness, colour) of a light. "
        "Always use this to check live state — never infer from conversation history."
    )
    args_schema: Type[BaseModel] = GetLightStateInput

    async def _arun(self, entity_name: str) -> str:  # type: ignore[override]
        result = await self._resolve_entities(entity_name, domain_filter=["light"])
        if not result.entities:
            return f"Sorry, I couldn't find a light matching '{entity_name}'."
        if result.is_ambiguous:
            return self._ambiguity_clarification(
                result.candidates_description, "check", allow_all=False
            )
        entity = result.entities[0]
        fresh = await self.ha_client.get_state(entity.entity_id)
        state = fresh.state
        parts: list[str] = [f"{entity.friendly_name} is {state}"]
        brightness = fresh.attributes.get("brightness")
        if brightness is not None:
            pct = round(brightness / 255 * 100)
            parts.append(f"brightness {pct}%")
        color_temp = fresh.attributes.get("color_temp_kelvin")
        if color_temp is not None:
            parts.append(f"colour temperature {color_temp}K")
        return ", ".join(parts) + "."
