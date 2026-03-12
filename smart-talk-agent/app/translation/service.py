"""LLM-backed translation service for Smart Talk.

Translates arbitrary text to English so the semantic device resolver can
work with entity names and user queries regardless of their original language.

All translated results are cached in-memory for the lifetime of the service,
so repeated queries (e.g. the same entity names across multiple refreshes)
do not incur additional LLM calls.
"""

from __future__ import annotations

import asyncio
import logging

import openai

logger = logging.getLogger(__name__)

_TRANSLATE_SYSTEM_PROMPT = (
    "Translate the following text to English. "
    "Return only the translated text with no explanation, quotes, or punctuation changes. "
    "If the text is already in English, return it unchanged exactly as given."
)

# Maximum concurrent translation requests sent to the LLM at once.
_MAX_CONCURRENCY = 5


class TranslationService:
    """Translates text to English using the configured LLM.

    Uses the same OpenAI-compatible endpoint as the main agent.  Results are
    cached in-memory so identical inputs are only translated once per process
    lifetime.

    Args:
        base_url:  OpenAI-compatible API base URL.
        api_key:   API key (may be a placeholder for local LLMs).
        model:     Model name to use for translation.
    """

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._client = openai.AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._model = model
        self._cache: dict[str, str] = {}
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)

    async def translate_to_english(self, text: str) -> str:
        """Translate *text* to English, returning the cached result on repeat calls.

        Args:
            text: The text to translate.

        Returns:
            The English translation, or the original *text* if translation fails.
        """
        stripped = text.strip()
        if not stripped:
            return text

        if stripped in self._cache:
            return self._cache[stripped]

        try:
            async with self._semaphore:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": _TRANSLATE_SYSTEM_PROMPT},
                        {"role": "user", "content": stripped},
                    ],
                    max_tokens=256,
                    temperature=0,
                )
            translated = (response.choices[0].message.content or stripped).strip()
            self._cache[stripped] = translated
            if translated != stripped:
                logger.debug("Translated %r → %r", stripped, translated)
            return translated
        except Exception as exc:
            logger.warning("Translation failed for %r: %s — using original", stripped, exc)
            # Fall back to original text so the resolver still works
            self._cache[stripped] = stripped
            return stripped

    async def translate_batch_to_english(self, texts: list[str]) -> list[str]:
        """Translate a list of texts to English concurrently.

        Already-cached entries are returned immediately without an LLM call.
        Up to ``_MAX_CONCURRENCY`` in-flight requests run at once.

        Args:
            texts: List of texts to translate.

        Returns:
            List of English translations in the same order as *texts*.
        """
        tasks = [self.translate_to_english(t) for t in texts]
        return list(await asyncio.gather(*tasks))

    @property
    def cache_size(self) -> int:
        """Number of cached translations."""
        return len(self._cache)
