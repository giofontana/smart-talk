"""Automatic language detection for Smart Talk conversations."""

from __future__ import annotations

import logging
from typing import Optional

from langdetect import detect_langs, LangDetectException

logger = logging.getLogger(__name__)


class LanguageDetector:
    """Detects the language of user input with session-based caching.

    Uses Google's langdetect library for fast, accurate language detection.
    Maintains a session cache to handle very short messages that may not
    have enough text for reliable detection.

    Args:
        confidence_threshold: Minimum confidence (0-1) required for detection.
                             Below this, falls back to session cache or default.
        min_text_length:     Minimum text length (chars) required for detection.
                             Very short messages use session cache.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.85,
        min_text_length: int = 5,
    ) -> None:
        self._confidence_threshold = confidence_threshold
        self._min_text_length = min_text_length
        # Cache the last detected language per session
        self._session_cache: dict[str, str] = {}

    def detect(
        self,
        text: str,
        session_id: str,
        fallback_language: Optional[str] = None,
    ) -> tuple[str, float]:
        """Detect the language of the given text.

        Args:
            text:              User input text to analyze.
            session_id:        Session identifier for caching.
            fallback_language: Language to use if detection fails (before default "en").

        Returns:
            Tuple of (language_code, confidence).
            Language code is ISO 639-1 (e.g., "en", "es", "it").
            Confidence is 0.0-1.0, where 1.0 is certain.
        """
        # Handle empty or very short text
        if not text or len(text.strip()) < self._min_text_length:
            cached = self._session_cache.get(session_id)
            if cached:
                logger.debug(
                    "Text too short for detection; using session cache: %s", cached
                )
                return (cached, 1.0)
            if fallback_language:
                logger.debug("Text too short; using fallback: %s", fallback_language)
                return (fallback_language, 0.5)
            logger.debug("Text too short; using default: en")
            return ("en", 0.5)

        # Attempt language detection
        try:
            detections = detect_langs(text)
            if not detections:
                return self._fallback(session_id, fallback_language)

            # Get the top match
            top_match = detections[0]
            language = top_match.lang
            confidence = top_match.prob

            logger.debug(
                "Detected language=%s (confidence=%.2f) for text=%r",
                language,
                confidence,
                text[:50],
            )

            # If confidence is too low, use fallback chain
            if confidence < self._confidence_threshold:
                logger.info(
                    "Low confidence (%.2f < %.2f); falling back",
                    confidence,
                    self._confidence_threshold,
                )
                return self._fallback(session_id, fallback_language)

            # Success: cache and return
            self._session_cache[session_id] = language
            return (language, confidence)

        except LangDetectException as exc:
            logger.warning("Language detection failed: %s", exc)
            return self._fallback(session_id, fallback_language)

    def get_session_language(self, session_id: str) -> Optional[str]:
        """Get the cached language for a session, if any.

        Args:
            session_id: Session identifier.

        Returns:
            Cached language code, or None if not cached.
        """
        return self._session_cache.get(session_id)

    def clear_session_cache(self, session_id: str) -> None:
        """Clear the cached language for a session.

        Args:
            session_id: Session identifier.
        """
        self._session_cache.pop(session_id, None)
        logger.debug("Cleared language cache for session=%s", session_id)

    def _fallback(
        self, session_id: str, fallback_language: Optional[str]
    ) -> tuple[str, float]:
        """Apply fallback chain: session cache → fallback_language → 'en'.

        Args:
            session_id:        Session identifier.
            fallback_language: Optional explicit fallback.

        Returns:
            Tuple of (language_code, confidence).
        """
        # Try session cache first
        cached = self._session_cache.get(session_id)
        if cached:
            logger.debug("Using session cache fallback: %s", cached)
            return (cached, 0.7)

        # Try provided fallback
        if fallback_language:
            logger.debug("Using provided fallback: %s", fallback_language)
            return (fallback_language, 0.5)

        # Default to English
        logger.debug("Using default fallback: en")
        return ("en", 0.5)


# Singleton instance for application-wide use
_detector: Optional[LanguageDetector] = None


def get_detector() -> LanguageDetector:
    """Get the singleton LanguageDetector instance.

    Returns:
        The global LanguageDetector instance.
    """
    global _detector
    if _detector is None:
        _detector = LanguageDetector()
        logger.info("Initialized LanguageDetector (singleton)")
    return _detector
