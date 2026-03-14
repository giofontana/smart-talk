"""Unit tests for language detection."""

import pytest

from src.tts_proxy import TTSProxy


@pytest.mark.unit
def test_detect_english(voice_mapping):
    """Test English text detection."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    text = "Hello, how are you doing today? I hope everything is going well."
    detected = proxy._detect_language(text)

    assert detected == "en"


@pytest.mark.unit
def test_detect_spanish(voice_mapping):
    """Test Spanish text detection."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    text = "Hola, ¿cómo estás hoy? Espero que todo esté bien."
    detected = proxy._detect_language(text)

    assert detected == "es"


@pytest.mark.unit
def test_detect_italian(voice_mapping):
    """Test Italian text detection."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    text = "Ciao, come stai oggi? Spero che tu stia bene."
    detected = proxy._detect_language(text)

    assert detected == "it"


@pytest.mark.unit
def test_detect_french(voice_mapping):
    """Test French text detection."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    text = "Bonjour, comment allez-vous aujourd'hui? J'espère que tout va bien."
    detected = proxy._detect_language(text)

    assert detected == "fr"


@pytest.mark.unit
def test_detect_german(voice_mapping):
    """Test German text detection."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    text = "Guten Tag, wie geht es Ihnen heute? Ich hoffe, alles ist gut."
    detected = proxy._detect_language(text)

    assert detected == "de"


@pytest.mark.unit
def test_detect_portuguese(voice_mapping):
    """Test Portuguese text detection."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    text = "Olá, como você está hoje? Espero que esteja tudo bem."
    detected = proxy._detect_language(text)

    assert detected == "pt"


@pytest.mark.unit
def test_detect_short_text_fallback(voice_mapping):
    """Test that short text defaults to English."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    text = "hi"
    detected = proxy._detect_language(text)

    assert detected == "en"


@pytest.mark.unit
def test_detect_empty_text(voice_mapping):
    """Test empty text defaults to English."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    text = ""
    detected = proxy._detect_language(text)

    assert detected == "en"


@pytest.mark.unit
def test_detect_whitespace_only(voice_mapping):
    """Test whitespace-only text defaults to English."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    text = "   \t\n  "
    detected = proxy._detect_language(text)

    assert detected == "en"


@pytest.mark.unit
def test_detect_numbers_only(voice_mapping):
    """Test numbers-only text behavior."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    text = "123 456 789"
    detected = proxy._detect_language(text)

    # Numbers may be detected as various languages or fall back
    # Just ensure it returns a valid language code
    assert isinstance(detected, str)
    assert len(detected) == 2


@pytest.mark.unit
def test_detect_mixed_language(voice_mapping):
    """Test mixed language text detects dominant language."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    # Mostly Spanish with English word
    text = "Hola amigo, ¿cómo estás? I hope you are well today."
    detected = proxy._detect_language(text)

    # Should detect Spanish as dominant
    assert detected in ["es", "en"]  # Could be either depending on algorithm
