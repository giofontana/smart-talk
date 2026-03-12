"""Unit tests for individual LangChain tools.

All tests use ``mock_ha_client`` and a per-test mock DeviceResolver so
no real HA connection or embedding model is needed.  Tools are constructed
via ``model_construct()`` to bypass Pydantic's isinstance checks on the
typed ``ha_client`` / ``device_resolver`` fields.  ``_resolve_entity`` and
``_resolve_entities`` are patched on the tool *instance* (not the class).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agent.tools.ha_climate import SetTemperatureTool
from app.agent.tools.ha_covers import CloseCoverTool, GetCoverStateTool, OpenCoverTool
from app.agent.tools.ha_lights import GetLightStateTool, TurnOffLightTool, TurnOnLightTool
from app.agent.tools.ha_sensors import GetSensorValueTool
from app.agent.tools.ha_switches import GetSwitchStateTool
from app.ha.models import HAEntity, ResolveResult


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_tool(cls, ha_client, device_resolver=None):
    """Construct a tool bypassing Pydantic isinstance validation."""
    if device_resolver is None:
        device_resolver = AsyncMock()
    return cls.model_construct(ha_client=ha_client, device_resolver=device_resolver)


def _unambiguous(entity: HAEntity) -> ResolveResult:
    """Wrap a single entity in a non-ambiguous ResolveResult."""
    return ResolveResult(entities=[entity], is_ambiguous=False, candidates_description="")


def _ambiguous(entities: list[HAEntity]) -> ResolveResult:
    """Wrap multiple entities in an ambiguous ResolveResult."""
    desc = " and ".join(f"'{e.friendly_name}'" for e in entities)
    return ResolveResult(entities=entities, is_ambiguous=True, candidates_description=desc)


def _empty() -> ResolveResult:
    """Return an empty ResolveResult (no match found)."""
    return ResolveResult()


# ── TurnOnLightTool ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_turn_on_light_tool(mock_ha_client):
    entity = HAEntity(
        entity_id="light.kitchen_light",
        state="off",
        attributes={"friendly_name": "Kitchen Light"},
    )
    tool = _make_tool(TurnOnLightTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_unambiguous(entity))

    result = await tool._arun("kitchen light")

    mock_ha_client.call_service.assert_called_once_with(
        "light", "turn_on", "light.kitchen_light"
    )
    assert "Kitchen Light" in result


@pytest.mark.asyncio
async def test_turn_on_light_with_brightness(mock_ha_client):
    entity = HAEntity(
        entity_id="light.kitchen_light",
        state="off",
        attributes={"friendly_name": "Kitchen Light"},
    )
    tool = _make_tool(TurnOnLightTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_unambiguous(entity))

    result = await tool._arun("kitchen light", brightness=75)

    mock_ha_client.call_service.assert_called_once_with(
        "light", "turn_on", "light.kitchen_light", brightness_pct=75
    )
    assert "75" in result


# ── TurnOffLightTool ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_turn_off_light_tool(mock_ha_client):
    entity = HAEntity(
        entity_id="light.kitchen_light",
        state="on",
        attributes={"friendly_name": "Kitchen Light"},
    )
    tool = _make_tool(TurnOffLightTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_unambiguous(entity))

    result = await tool._arun("kitchen light")

    mock_ha_client.call_service.assert_called_once_with(
        "light", "turn_off", "light.kitchen_light"
    )
    assert "Kitchen Light" in result


@pytest.mark.asyncio
async def test_turn_on_light_entity_not_found(mock_ha_client):
    tool = _make_tool(TurnOnLightTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_empty())

    result = await tool._arun("nonexistent lamp")

    mock_ha_client.call_service.assert_not_called()
    assert "couldn't find" in result


# ── Ambiguity: ask clarification ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ambiguous_cover_returns_clarification(mock_ha_client):
    """Ambiguous query without target_all must return a clarification question."""
    entities = [
        HAEntity(entity_id="cover.office_window_1", state="open", attributes={"friendly_name": "Office Window 1"}),
        HAEntity(entity_id="cover.office_window_2", state="open", attributes={"friendly_name": "Office Window 2"}),
    ]
    tool = _make_tool(CloseCoverTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_ambiguous(entities))

    result = await tool._arun("office window")

    mock_ha_client.call_service.assert_not_called()
    assert "Office Window 1" in result or "Office Window 2" in result
    assert "?" in result  # clarification question


@pytest.mark.asyncio
async def test_ambiguous_cover_target_all_closes_both(mock_ha_client):
    """target_all=True on an ambiguous result applies to all candidates."""
    entities = [
        HAEntity(entity_id="cover.office_window_1", state="open", attributes={"friendly_name": "Office Window 1"}),
        HAEntity(entity_id="cover.office_window_2", state="open", attributes={"friendly_name": "Office Window 2"}),
    ]
    tool = _make_tool(CloseCoverTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_ambiguous(entities))

    result = await tool._arun("office window", target_all=True)

    assert mock_ha_client.call_service.call_count == 2
    calls = [str(c) for c in mock_ha_client.call_service.call_args_list]
    assert any("office_window_1" in c for c in calls)
    assert any("office_window_2" in c for c in calls)
    assert "Office Window 1" in result
    assert "Office Window 2" in result


@pytest.mark.asyncio
async def test_target_all_on_single_result_still_works(mock_ha_client):
    """target_all=True with a single non-ambiguous result still acts on that entity."""
    entity = HAEntity(entity_id="cover.garage_door", state="closed", attributes={"friendly_name": "Garage Door"})
    tool = _make_tool(OpenCoverTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_unambiguous(entity))

    result = await tool._arun("garage door", target_all=True)

    mock_ha_client.call_service.assert_called_once_with("cover", "open_cover", "cover.garage_door")
    assert "Garage Door" in result


# ── SetTemperatureTool ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_temperature_tool(mock_ha_client):
    entity = HAEntity(
        entity_id="climate.bedroom_ac",
        state="cool",
        attributes={
            "friendly_name": "Bedroom AC",
            "temperature": 22.0,
            "current_temperature": 24.0,
        },
    )
    tool = _make_tool(SetTemperatureTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_unambiguous(entity))

    result = await tool._arun("bedroom ac", temperature=24.0)

    mock_ha_client.call_service.assert_called_once_with(
        "climate", "set_temperature", "climate.bedroom_ac", temperature=24.0
    )
    assert "Bedroom AC" in result
    assert "24" in result


# ── GetSensorValueTool ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_sensor_value_tool(mock_ha_client):
    sensor_entity = HAEntity(
        entity_id="sensor.outdoor_temperature",
        state="18.5",
        attributes={
            "friendly_name": "Outdoor Temperature",
            "unit_of_measurement": "°C",
        },
    )
    mock_ha_client.get_state.return_value = sensor_entity

    tool = _make_tool(GetSensorValueTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_unambiguous(sensor_entity))

    result = await tool._arun("outdoor temperature")

    mock_ha_client.get_state.assert_called_once_with("sensor.outdoor_temperature")
    assert "18.5" in result
    assert "°C" in result


# ── GetLightStateTool ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_light_state_on_with_brightness(mock_ha_client):
    light = HAEntity(
        entity_id="light.kitchen",
        state="on",
        attributes={"friendly_name": "Kitchen", "brightness": 204, "color_temp_kelvin": 3000},
    )
    mock_ha_client.get_state.return_value = light

    tool = _make_tool(GetLightStateTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_unambiguous(light))

    result = await tool._arun("kitchen light")

    mock_ha_client.get_state.assert_called_once_with("light.kitchen")
    assert "on" in result
    assert "80%" in result        # 204/255 ≈ 80%
    assert "3000K" in result


@pytest.mark.asyncio
async def test_get_light_state_off(mock_ha_client):
    light = HAEntity(
        entity_id="light.bedroom",
        state="off",
        attributes={"friendly_name": "Bedroom"},
    )
    mock_ha_client.get_state.return_value = light

    tool = _make_tool(GetLightStateTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_unambiguous(light))

    result = await tool._arun("bedroom light")
    assert "off" in result


@pytest.mark.asyncio
async def test_get_light_state_not_found(mock_ha_client):
    tool = _make_tool(GetLightStateTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_empty())

    result = await tool._arun("ghost light")
    assert "couldn't find" in result


# ── GetCoverStateTool ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_cover_state_closed(mock_ha_client):
    cover = HAEntity(
        entity_id="cover.office_window_1",
        state="closed",
        attributes={"friendly_name": "Office Window 1", "current_position": 0},
    )
    mock_ha_client.get_state.return_value = cover

    tool = _make_tool(GetCoverStateTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_unambiguous(cover))

    result = await tool._arun("office window")

    mock_ha_client.get_state.assert_called_once_with("cover.office_window_1")
    assert "closed" in result
    assert "0%" in result


@pytest.mark.asyncio
async def test_get_cover_state_open(mock_ha_client):
    cover = HAEntity(
        entity_id="cover.office_window_1",
        state="open",
        attributes={"friendly_name": "Office Window 1", "current_position": 75},
    )
    mock_ha_client.get_state.return_value = cover

    tool = _make_tool(GetCoverStateTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_unambiguous(cover))

    result = await tool._arun("office window")
    assert "open" in result
    assert "75%" in result


@pytest.mark.asyncio
async def test_get_cover_state_ambiguous(mock_ha_client):
    cover1 = HAEntity(entity_id="cover.office_window_1", state="closed",
                      attributes={"friendly_name": "Office Window 1"})
    cover2 = HAEntity(entity_id="cover.office_window_2", state="open",
                      attributes={"friendly_name": "Office Window 2"})

    tool = _make_tool(GetCoverStateTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_ambiguous([cover1, cover2]))

    result = await tool._arun("office window")
    assert "Office Window 1" in result and "Office Window 2" in result
    assert "?" in result
    mock_ha_client.get_state.assert_not_called()


# ── GetSwitchStateTool ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_switch_state_on(mock_ha_client):
    sw = HAEntity(
        entity_id="switch.garden_pump",
        state="on",
        attributes={"friendly_name": "Garden Pump"},
    )
    mock_ha_client.get_state.return_value = sw

    tool = _make_tool(GetSwitchStateTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_unambiguous(sw))

    result = await tool._arun("garden pump")

    mock_ha_client.get_state.assert_called_once_with("switch.garden_pump")
    assert "on" in result


@pytest.mark.asyncio
async def test_get_switch_state_not_found(mock_ha_client):
    tool = _make_tool(GetSwitchStateTool, mock_ha_client)
    tool._resolve_entities = AsyncMock(return_value=_empty())

    result = await tool._arun("ghost switch")
    assert "couldn't find" in result
