"""Integration tests for the FastAPI HTTP endpoints.

The ``app_client`` fixture (defined in conftest.py) replaces the lifespan
with a no-op and pre-patches all module-level globals so no real HA or LLM
connection is attempted.

Tests that need different mock behaviour simply mutate the already-patched
globals on ``app.main`` via ``monkeypatch`` or direct attribute assignment.
"""

from __future__ import annotations

import pytest

import app.main as main_module
from app.ha.models import HAEntity


# ── /health ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_ok(app_client):
    # The app_client fixture sets ha_client.ping → True by default
    response = await app_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ha_connected"] is True


@pytest.mark.asyncio
async def test_health_ha_down(app_client):
    main_module.ha_client.ping.return_value = False

    response = await app_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["ha_connected"] is False


# ── /conversation ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_conversation_success(app_client):
    main_module.agent.chat.return_value = "Kitchen light is now on."

    response = await app_client.post(
        "/conversation",
        json={
            "session_id": "test-session-1",
            "text": "Turn on the kitchen light",
            "language": "en",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "text" in data
    assert data["text"] == "Kitchen light is now on."
    assert data["session_id"] == "test-session-1"


@pytest.mark.asyncio
async def test_conversation_missing_text(app_client):
    response = await app_client.post(
        "/conversation",
        json={"session_id": "test-session-2", "language": "en"},
    )
    assert response.status_code == 422


# ── /entities ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_entities_endpoint(app_client):
    main_module.device_resolver.cached_entities = [
        HAEntity(
            entity_id="light.kitchen_light",
            state="off",
            attributes={"friendly_name": "Kitchen Light"},
        ),
        HAEntity(
            entity_id="switch.garden_sprinkler",
            state="off",
            attributes={"friendly_name": "Garden Sprinkler"},
        ),
    ]

    response = await app_client.get("/entities")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    entity_ids = {e["entity_id"] for e in data}
    assert "light.kitchen_light" in entity_ids
    assert "switch.garden_sprinkler" in entity_ids
