"""Shared pytest fixtures for the Smart Talk Agent test suite."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import Settings
from app.ha.models import HAEntity
from app.search.device_resolver import DeviceResolver

# ── Canonical test entity set (used by all test modules) ──────────────────────

TEST_ENTITIES: list[HAEntity] = [
    HAEntity(
        entity_id="light.kitchen_light",
        state="off",
        attributes={"friendly_name": "Kitchen Light"},
    ),
    HAEntity(
        entity_id="light.living_room_lamp",
        state="on",
        attributes={"friendly_name": "Living Room Lamp"},
    ),
    HAEntity(
        entity_id="switch.garden_sprinkler",
        state="off",
        attributes={"friendly_name": "Garden Sprinkler"},
    ),
    HAEntity(
        entity_id="sensor.outdoor_temperature",
        state="18.5",
        attributes={
            "friendly_name": "Outdoor Temperature",
            "unit_of_measurement": "°C",
        },
    ),
    HAEntity(
        entity_id="climate.bedroom_ac",
        state="cool",
        attributes={
            "friendly_name": "Bedroom AC",
            "temperature": 22.0,
            "current_temperature": 24.0,
        },
    ),
    # These two are intentionally similar to trigger ambiguity detection
    HAEntity(
        entity_id="cover.office_window_1",
        state="open",
        attributes={"friendly_name": "Office Window 1"},
    ),
    HAEntity(
        entity_id="cover.office_window_2",
        state="open",
        attributes={"friendly_name": "Office Window 2"},
    ),
]


# ── settings fixture ──────────────────────────────────────────────────────────

@pytest.fixture
def settings() -> Settings:
    """A Settings instance populated with safe test values (no YAML file needed)."""
    return Settings(
        ha_url="http://test-ha:8123",
        ha_token="test-token-abc",
        ha_ssl_verify=False,
        llm_base_url="http://test-llm/v1",
        llm_api_key="sk-test",
        llm_model="test-model",
        llm_temperature=0.0,
        server_host="127.0.0.1",
        server_port=8765,
        log_level="WARNING",
        embedding_model="all-MiniLM-L6-v2",
        similarity_threshold=0.35,
        device_refresh_interval=300,
    )


# ── mock_ha_client fixture ────────────────────────────────────────────────────

@pytest.fixture
def mock_ha_client() -> AsyncMock:
    """AsyncMock of HAClient pre-loaded with the canonical TEST_ENTITIES."""
    mock = AsyncMock()
    mock.get_states.return_value = list(TEST_ENTITIES)
    mock.get_state.return_value = TEST_ENTITIES[0]
    mock.call_service.return_value = {}
    mock.ping.return_value = True
    connected = MagicMock()
    connected.is_set.return_value = True
    mock._connected = connected
    return mock


# ── device_resolver fixture (module-scoped, real model) ───────────────────────

@pytest.fixture(scope="module")
async def device_resolver() -> DeviceResolver:
    """Real DeviceResolver backed by a mock HA client, loaded once per module.

    Uses the actual sentence-transformers model to validate that semantic
    search works end-to-end.  The fixture is module-scoped so the model
    is downloaded/loaded only once per test module.
    """
    mock_ha = AsyncMock()
    mock_ha.get_states.return_value = list(TEST_ENTITIES)

    resolver = DeviceResolver(
        ha_client=mock_ha,
        embedding_model="all-MiniLM-L6-v2",
        similarity_threshold=0.35,
    )
    await resolver.refresh()
    return resolver


# ── app_client fixture ────────────────────────────────────────────────────────

@pytest.fixture
async def app_client(monkeypatch):
    """Async HTTP test client for the FastAPI app.

    Replaces the app lifespan with a no-op and pre-sets all module-level
    globals in ``app.main`` with AsyncMock / MagicMock instances so that
    no real HA or LLM connections are made.
    """
    import httpx

    import app.main as main_module
    from app.main import app

    # Build default mocks
    mock_ha = AsyncMock()
    mock_ha.ping.return_value = True
    connected = MagicMock()
    connected.is_set.return_value = True
    mock_ha._connected = connected

    mock_resolver = MagicMock()
    mock_resolver.cached_entities = []

    mock_registry = MagicMock()

    mock_agent = AsyncMock()
    mock_agent.chat.return_value = "OK"

    # Patch module-level globals (raising=False because they are annotations,
    # not actual assignments, until the lifespan runs)
    monkeypatch.setattr(main_module, "ha_client", mock_ha, raising=False)
    monkeypatch.setattr(main_module, "device_resolver", mock_resolver, raising=False)
    monkeypatch.setattr(main_module, "tool_registry", mock_registry, raising=False)
    monkeypatch.setattr(main_module, "agent", mock_agent, raising=False)

    # Replace the lifespan with a no-op so startup/shutdown never run
    @asynccontextmanager
    async def null_lifespan(_app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = null_lifespan

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.router.lifespan_context = original_lifespan
