"""Unit tests for polyglot language detection implementation."""

from __future__ import annotations

import pytest

from app.agent.language_detector import get_detector, LanguageDetector
from app.agent.prompts import build_prompt


# ── Language Detection Tests ──────────────────────────────────────────────────


def test_detect_english():
    """Test detection of English text."""
    detector = get_detector()
    detected_lang, confidence = detector.detect(
        "Hello, how are you today? I hope everything is going well.",
        "test-session-en",
        None,
    )
    assert detected_lang == "en"
    assert confidence >= 0.5


def test_detect_spanish():
    """Test detection of Spanish text."""
    detector = get_detector()
    detected_lang, confidence = detector.detect(
        "Hola, ¿cómo estás hoy?", "test-session-es", None
    )
    assert detected_lang == "es"
    assert confidence > 0.85


def test_detect_italian():
    """Test detection of Italian text with longer phrase."""
    detector = get_detector()
    detected_lang, confidence = detector.detect(
        "Ciao, come stai oggi? Spero che tu stia bene.",
        "test-session-it",
        None,
    )
    assert detected_lang == "it"
    assert confidence > 0.85


def test_detect_french():
    """Test detection of French text."""
    detector = get_detector()
    detected_lang, confidence = detector.detect(
        "Bonjour, comment allez-vous aujourd'hui?", "test-session-fr", None
    )
    assert detected_lang == "fr"
    assert confidence > 0.85


def test_detect_german():
    """Test detection of German text."""
    detector = get_detector()
    detected_lang, confidence = detector.detect(
        "Guten Tag, wie geht es Ihnen heute?", "test-session-de", None
    )
    assert detected_lang == "de"
    assert confidence > 0.85


# ── Session Caching Tests ─────────────────────────────────────────────────────


def test_session_cache_english():
    """Test that short messages use cached language for English session."""
    detector = LanguageDetector()  # Use fresh instance

    # Establish language with long message
    lang1, conf1 = detector.detect(
        "Good morning! How can I help you today?", "cache-session-1", None
    )
    assert lang1 == "en"

    # Short message should use cached language
    lang2, conf2 = detector.detect("ok", "cache-session-1", None)
    assert lang2 == "en"
    assert conf2 == 1.0  # From cache


def test_session_cache_spanish():
    """Test that short messages use cached language for Spanish session."""
    detector = LanguageDetector()  # Use fresh instance

    # Establish language with long message
    lang1, conf1 = detector.detect(
        "Buenos días, ¿cómo puedo ayudarte hoy?", "cache-session-2", None
    )
    assert lang1 == "es"

    # Short message should use cached language
    lang2, conf2 = detector.detect("si", "cache-session-2", None)
    assert lang2 == "es"
    assert conf2 == 1.0  # From cache


def test_session_isolation():
    """Test that different sessions maintain separate language caches."""
    detector = LanguageDetector()  # Use fresh instance

    # Session 1: English
    detector.detect(
        "Hello there! How are you doing today?", "isolated-session-1", None
    )
    lang1, _ = detector.detect("yes", "isolated-session-1", None)

    # Session 2: Spanish
    detector.detect(
        "¡Hola amigo! ¿Cómo estás hoy?", "isolated-session-2", None
    )
    lang2, _ = detector.detect("si", "isolated-session-2", None)

    assert lang1 == "en"
    assert lang2 == "es"


def test_get_session_language():
    """Test retrieving cached session language."""
    detector = LanguageDetector()

    # No cache initially
    assert detector.get_session_language("no-cache-session") is None

    # Detect language with longer text to ensure caching
    detector.detect(
        "Hello world! How are you doing today? I hope everything is well.",
        "cached-lang-session",
        None,
    )

    # Should now be cached
    assert detector.get_session_language("cached-lang-session") == "en"


def test_clear_session_cache():
    """Test clearing session cache."""
    detector = LanguageDetector()

    # Establish cached language
    detector.detect("Hello world!", "clear-test-session", None)
    assert detector.get_session_language("clear-test-session") == "en"

    # Clear cache
    detector.clear_session_cache("clear-test-session")
    assert detector.get_session_language("clear-test-session") is None


# ── Fallback Behavior Tests ───────────────────────────────────────────────────


def test_fallback_on_empty_text():
    """Test that empty text falls back to default language."""
    detector = LanguageDetector()
    detected_lang, confidence = detector.detect("", "empty-session", None)
    assert detected_lang == "en"  # Default fallback


def test_fallback_on_very_short_text():
    """Test that very short text falls back to default when no cache."""
    detector = LanguageDetector()
    detected_lang, confidence = detector.detect("ok", "short-session", None)
    assert detected_lang == "en"  # Default fallback


def test_fallback_with_provided_fallback():
    """Test that provided fallback is used for short text without cache."""
    detector = LanguageDetector()
    detected_lang, confidence = detector.detect(
        "ok", "fallback-session", fallback_language="es"
    )
    assert detected_lang == "es"  # Uses provided fallback


# ── Prompt Generation Tests ───────────────────────────────────────────────────


def test_prompt_english_has_no_language_instruction():
    """Test that English prompt does not have CRITICAL language instruction."""
    prompt = build_prompt("en")
    assert "CRITICAL" not in prompt
    assert "English" not in prompt or "English" in "Smart Talk, a multilingual"


def test_prompt_spanish_has_language_instruction():
    """Test that Spanish prompt includes language-specific instruction."""
    prompt = build_prompt("es")
    assert "CRITICAL" in prompt
    assert "Spanish" in prompt
    assert "EXCLUSIVELY in Spanish" in prompt


def test_prompt_italian_has_language_instruction():
    """Test that Italian prompt includes language-specific instruction."""
    prompt = build_prompt("it")
    assert "CRITICAL" in prompt
    assert "Italian" in prompt
    assert "EXCLUSIVELY in Italian" in prompt


def test_prompt_portuguese_has_language_instruction():
    """Test that Portuguese prompt includes language-specific instruction."""
    prompt = build_prompt("pt")
    assert "CRITICAL" in prompt
    assert "Portuguese" in prompt


def test_prompt_french_has_language_instruction():
    """Test that French prompt includes language-specific instruction."""
    prompt = build_prompt("fr")
    assert "CRITICAL" in prompt
    assert "French" in prompt


def test_prompt_lengths_differ():
    """Test that non-English prompts are longer than English prompt."""
    en_prompt = build_prompt("en")
    es_prompt = build_prompt("es")

    assert len(es_prompt) > len(en_prompt)
    # Spanish prompt should be ~200 chars longer due to language instruction
    assert len(es_prompt) - len(en_prompt) > 100


# ── Confidence Threshold Tests ────────────────────────────────────────────────


def test_confidence_threshold_behavior():
    """Test that detector respects confidence threshold."""
    detector = LanguageDetector(confidence_threshold=0.95)  # High threshold

    # Long, clear text should still work
    detected_lang, confidence = detector.detect(
        "Bonjour, comment allez-vous aujourd'hui?", "threshold-test", None
    )
    # Even if confidence is lower, should detect or fallback gracefully
    assert detected_lang in ["fr", "en"]


def test_detector_singleton():
    """Test that get_detector returns the same instance."""
    detector1 = get_detector()
    detector2 = get_detector()
    assert detector1 is detector2
