"""Unit tests for voice selection logic."""

import pytest

from src.tts_proxy import TTSProxy


@pytest.mark.unit
def test_select_english_voice(voice_mapping):
    """Test English language selects correct voice."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    voice = proxy._select_voice("en")

    assert voice == "en_US-lessac-medium"


@pytest.mark.unit
def test_select_spanish_voice(voice_mapping):
    """Test Spanish language selects correct voice."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    voice = proxy._select_voice("es")

    assert voice == "es_ES-mls-medium"


@pytest.mark.unit
def test_select_italian_voice(voice_mapping):
    """Test Italian language selects correct voice."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    voice = proxy._select_voice("it")

    assert voice == "it_IT-riccardo-x_low"


@pytest.mark.unit
def test_select_unmapped_language_uses_default(voice_mapping):
    """Test unmapped language falls back to default voice."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    voice = proxy._select_voice("ja")  # Japanese, not in mapping

    # Should use English as default
    assert voice == "en_US-lessac-medium"


@pytest.mark.unit
def test_default_voice_when_english_not_in_mapping():
    """Test default voice selection when English is not in mapping."""
    custom_mapping = {
        "es": "es_ES-carme",
        "fr": "fr_FR-siwis",
    }
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", custom_mapping)

    # Request English, but it's not mapped
    voice = proxy._select_voice("en")

    # Should use first voice in mapping
    assert voice in custom_mapping.values()


@pytest.mark.unit
def test_empty_voice_mapping():
    """Test behavior with empty voice mapping."""
    empty_mapping = {}
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", empty_mapping)

    # Verify proxy was created without error
    assert proxy is not None
    # With empty mapping, default_voice should be None
    assert proxy.default_voice is None

    # Voice selection should return None when no voices configured
    voice = proxy._select_voice("en")
    assert voice is None
