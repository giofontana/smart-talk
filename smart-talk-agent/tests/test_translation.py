"""Unit tests for TranslationService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.translation.service import TranslationService


def _make_service() -> TranslationService:
    """Create a TranslationService with a mocked openai client."""
    svc = TranslationService(
        base_url="http://localhost:11434/v1",
        api_key="test-key",
        model="test-model",
    )
    return svc


def _mock_llm_response(text: str) -> MagicMock:
    """Build a mock that mimics an openai chat completion response."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    return response


# ── translate_to_english ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_portuguese_to_english():
    svc = _make_service()
    svc._client.chat.completions.create = AsyncMock(
        return_value=_mock_llm_response("living room")
    )

    result = await svc.translate_to_english("sala de estar")

    assert result == "living room"
    svc._client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_translate_returns_original_for_english():
    svc = _make_service()
    svc._client.chat.completions.create = AsyncMock(
        return_value=_mock_llm_response("kitchen light")
    )

    result = await svc.translate_to_english("kitchen light")
    assert result == "kitchen light"


@pytest.mark.asyncio
async def test_translate_caches_result():
    svc = _make_service()
    svc._client.chat.completions.create = AsyncMock(
        return_value=_mock_llm_response("living room")
    )

    # First call — hits LLM
    r1 = await svc.translate_to_english("sala de estar")
    # Second call — must use cache
    r2 = await svc.translate_to_english("sala de estar")

    assert r1 == r2 == "living room"
    # LLM called exactly once despite two translate calls
    assert svc._client.chat.completions.create.await_count == 1
    assert svc.cache_size == 1


@pytest.mark.asyncio
async def test_translate_empty_string_returns_as_is():
    svc = _make_service()
    svc._client.chat.completions.create = AsyncMock()

    result = await svc.translate_to_english("   ")

    assert result == "   "
    svc._client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_translate_falls_back_on_llm_error():
    svc = _make_service()
    svc._client.chat.completions.create = AsyncMock(side_effect=RuntimeError("LLM down"))

    result = await svc.translate_to_english("sala de estar")

    # Falls back gracefully to original text
    assert result == "sala de estar"


# ── translate_batch_to_english ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_translate_batch_returns_same_order():
    svc = _make_service()
    translations = ["living room", "bedroom", "kitchen"]
    svc._client.chat.completions.create = AsyncMock(
        side_effect=[_mock_llm_response(t) for t in translations]
    )

    results = await svc.translate_batch_to_english(
        ["sala de estar", "quarto", "cozinha"]
    )

    assert results == ["living room", "bedroom", "kitchen"]


@pytest.mark.asyncio
async def test_translate_batch_uses_cache_for_duplicates():
    svc = _make_service()
    svc._client.chat.completions.create = AsyncMock(
        return_value=_mock_llm_response("living room")
    )

    # Same text twice in the batch
    results = await svc.translate_batch_to_english(
        ["sala de estar", "sala de estar"]
    )

    assert results == ["living room", "living room"]
    # LLM only called once due to caching
    assert svc._client.chat.completions.create.await_count == 1
