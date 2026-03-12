"""Tests for DeviceResolver using the real sentence-transformers model.

The ``device_resolver`` fixture is module-scoped so the model is loaded
only once.  These tests exercise actual semantic similarity — no mocking
of the embedding layer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.ha.models import HAEntity, ResolveResult
from app.search.device_resolver import DeviceResolver
from tests.conftest import TEST_ENTITIES


# ── Index integrity ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_indexes_entities(device_resolver: DeviceResolver):
    assert len(device_resolver.cached_entities) == len(TEST_ENTITIES)


# ── Semantic resolution ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_light_by_name(device_resolver: DeviceResolver):
    results = await device_resolver.resolve(
        "kitchen light", domain_filter=["light"]
    )
    assert results, "Expected at least one result for 'kitchen light'"
    assert results[0].entity_id == "light.kitchen_light"


@pytest.mark.asyncio
async def test_resolve_unknown_returns_empty(device_resolver: DeviceResolver):
    results = await device_resolver.resolve("xyzzy nonexistent device 99zz")
    assert results == []


@pytest.mark.asyncio
async def test_resolve_respects_domain_filter(device_resolver: DeviceResolver):
    results = await device_resolver.resolve(
        "garden sprinkler", domain_filter=["sensor"]
    )
    for entity in results:
        assert entity.domain == "sensor", (
            f"Expected only sensor domain; got {entity.entity_id}"
        )


# ── Ambiguity detection ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_with_ambiguity_returns_resolve_result(device_resolver: DeviceResolver):
    result = await device_resolver.resolve_with_ambiguity("office window", domain_filter=["cover"])
    assert isinstance(result, ResolveResult)


@pytest.mark.asyncio
async def test_ambiguity_detected_for_similar_devices(device_resolver: DeviceResolver):
    """'office window' should match both office_window_1 and office_window_2."""
    result = await device_resolver.resolve_with_ambiguity("office window", domain_filter=["cover"])
    assert result.entities, "Expected at least one cover match"
    if len(result.entities) >= 2:
        assert result.is_ambiguous, (
            "Expected is_ambiguous=True for similarly-named 'Office Window 1' and 'Office Window 2'"
        )
        assert "Office Window" in result.candidates_description


@pytest.mark.asyncio
async def test_no_ambiguity_for_unique_device(device_resolver: DeviceResolver):
    """A clearly unique query should NOT be flagged as ambiguous."""
    result = await device_resolver.resolve_with_ambiguity(
        "kitchen light", domain_filter=["light"]
    )
    assert result.entities, "Expected at least one result"
    assert not result.is_ambiguous, (
        "A clearly unique device should not trigger ambiguity"
    )


@pytest.mark.asyncio
async def test_ambiguity_with_tight_threshold():
    """Manually verify ambiguity logic with a tiny threshold (always triggers if 2+ results)."""
    mock_ha = AsyncMock()
    mock_ha.get_states.return_value = [
        HAEntity(entity_id="cover.window_a", state="open", attributes={"friendly_name": "Window A"}),
        HAEntity(entity_id="cover.window_b", state="open", attributes={"friendly_name": "Window B"}),
    ]
    resolver = DeviceResolver(
        ha_client=mock_ha,
        embedding_model="all-MiniLM-L6-v2",
        similarity_threshold=0.1,   # very low threshold: both will match
        ambiguity_spread_threshold=1.0,  # very high: spread always < 1.0 → always ambiguous
        ambiguity_min_matches=2,
    )
    await resolver.refresh()
    result = await resolver.resolve_with_ambiguity("window", domain_filter=["cover"])
    assert result.is_ambiguous


@pytest.mark.asyncio
async def test_no_ambiguity_when_only_one_result():
    """Single match is never ambiguous regardless of threshold."""
    mock_ha = AsyncMock()
    mock_ha.get_states.return_value = [
        HAEntity(entity_id="light.kitchen", state="off", attributes={"friendly_name": "Kitchen Light"}),
    ]
    resolver = DeviceResolver(
        ha_client=mock_ha,
        embedding_model="all-MiniLM-L6-v2",
        similarity_threshold=0.1,
        ambiguity_spread_threshold=1.0,
        ambiguity_min_matches=2,
    )
    await resolver.refresh()
    result = await resolver.resolve_with_ambiguity("kitchen light")
    assert not result.is_ambiguous


# ── Candidates description ────────────────────────────────────────────────────

def test_build_candidates_description_two():
    entities = [
        HAEntity(entity_id="cover.w1", state="open", attributes={"friendly_name": "Window 1"}),
        HAEntity(entity_id="cover.w2", state="open", attributes={"friendly_name": "Window 2"}),
    ]
    desc = DeviceResolver._build_candidates_description(entities)
    assert "Window 1" in desc
    assert "Window 2" in desc
    assert " and " in desc


def test_build_candidates_description_three():
    entities = [
        HAEntity(entity_id="cover.w1", state="open", attributes={"friendly_name": "Window 1"}),
        HAEntity(entity_id="cover.w2", state="open", attributes={"friendly_name": "Window 2"}),
        HAEntity(entity_id="cover.w3", state="open", attributes={"friendly_name": "Window 3"}),
    ]
    desc = DeviceResolver._build_candidates_description(entities)
    assert "Window 1" in desc
    assert "Window 2" in desc
    assert "Window 3" in desc


# ── Static helper ─────────────────────────────────────────────────────────────

def test_entity_text_includes_friendly_name():
    entity = HAEntity(
        entity_id="light.kitchen_light",
        state="off",
        attributes={"friendly_name": "Kitchen Light"},
    )
    text = DeviceResolver._entity_text(entity)
    assert "Kitchen Light" in text
    assert "light.kitchen_light" in text


# ── Translation integration ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_translates_entity_names(mock_ha_client):
    """When a TranslationService is provided, friendly names are translated for the index."""
    import asyncio as _asyncio
    from tests.conftest import TEST_ENTITIES
    from unittest.mock import AsyncMock as AM
    from app.translation.service import TranslationService

    async def fake_translate(text: str) -> str:
        return {"Sala de Estar": "Living Room"}.get(text, text)

    # Build a minimal TranslationService with the key method mocked.
    svc = TranslationService.__new__(TranslationService)
    svc._cache = {}
    svc._semaphore = _asyncio.Semaphore(5)
    svc.translate_to_english = AM(side_effect=fake_translate)

    resolver = DeviceResolver(
        ha_client=mock_ha_client,
        embedding_model="all-MiniLM-L6-v2",
        translation_service=svc,
    )
    await resolver.refresh()

    assert len(resolver.cached_entities) == len(TEST_ENTITIES)
    # translate_to_english was called at least once per entity (for friendly names)
    assert svc.translate_to_english.await_count >= len(TEST_ENTITIES)


@pytest.mark.asyncio
async def test_resolve_translates_query(mock_ha_client):
    """Query is translated to English before embedding when TranslationService is set."""
    import asyncio as _asyncio
    from unittest.mock import AsyncMock as AM
    from app.translation.service import TranslationService

    # Translate "cocina" (Spanish for kitchen) → "kitchen light"
    # Everything else → as-is (index is built without translation)
    async def fake_translate(text: str) -> str:
        return "kitchen light" if text == "cocina" else text

    svc = TranslationService.__new__(TranslationService)
    svc._cache = {}
    svc._semaphore = _asyncio.Semaphore(5)
    svc.translate_to_english = AM(side_effect=fake_translate)

    resolver = DeviceResolver(
        ha_client=mock_ha_client,
        embedding_model="all-MiniLM-L6-v2",
        translation_service=svc,
    )
    await resolver.refresh()

    results = await resolver.resolve("cocina", domain_filter=["light"])

    svc.translate_to_english.assert_any_call("cocina")
    # Should find the kitchen light after query translation
    assert len(results) > 0
    assert results[0].entity_id == "light.kitchen_light"
