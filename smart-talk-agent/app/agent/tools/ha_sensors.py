"""Sensor read tool for Smart Talk."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel, Field

from app.agent.tools.base import SmartTalkTool


class GetSensorValueInput(BaseModel):
    entity_name: str = Field(
        ...,
        description="Name or description of the sensor (e.g. 'living room temperature sensor')",
    )


class GetSensorValueTool(SmartTalkTool):
    """Read the current value of a sensor or binary sensor."""

    name: str = "get_sensor_value"
    description: str = (
        "Read the current state or measurement of a sensor or binary sensor. "
        "Returns a human-readable description of the value and its unit."
    )
    args_schema: Type[BaseModel] = GetSensorValueInput

    async def _arun(self, entity_name: str) -> str:  # type: ignore[override]
        result = await self._resolve_entities(
            entity_name, domain_filter=["sensor", "binary_sensor"]
        )
        if not result.entities:
            return f"Sorry, I couldn't find a sensor matching '{entity_name}'."
        if result.is_ambiguous:
            return self._ambiguity_clarification(
                result.candidates_description, "check", allow_all=False
            )
        entity = result.entities[0]
        fresh = await self.ha_client.get_state(entity.entity_id)
        unit = fresh.attributes.get("unit_of_measurement", "")
        unit_str = f" {unit}" if unit else ""
        return f"The {fresh.friendly_name} reads {fresh.state}{unit_str}."
