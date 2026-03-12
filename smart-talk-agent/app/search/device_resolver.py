"""Semantic device/entity resolver backed by sentence-transformers.

Builds an in-memory index of HA entity embeddings and provides
fuzzy/semantic resolution from natural-language queries.

When a :class:`~app.translation.service.TranslationService` is provided, entity
names and user queries are normalised to English before indexing / searching,
so devices named in any language and users speaking any language all work
correctly with the same embedding model.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from sentence_transformers import SentenceTransformer

from app.ha.client import HAClient
from app.ha.models import HAEntity, ResolveResult

if TYPE_CHECKING:
    from app.translation.service import TranslationService

logger = logging.getLogger(__name__)


class DeviceResolver:
    """Resolves natural-language device queries to Home Assistant entities.

    Uses sentence-transformers to embed entity metadata and performs
    cosine-similarity search at query time.

    Args:
        ha_client:                   Initialised :class:`~app.ha.client.HAClient`.
        embedding_model:             sentence-transformers model name.
        similarity_threshold:        Minimum cosine similarity (0–1) for a match.
        refresh_interval:            Seconds between automatic background refreshes.
        ambiguity_spread_threshold:  When the score spread between the top candidates
                                     is smaller than this value, the result is marked
                                     ambiguous so the user can be asked to clarify.
        ambiguity_min_matches:       Minimum number of above-threshold candidates
                                     required before ambiguity can be triggered.
        translation_service:         Optional service that translates text to English
                                     before indexing and searching.  When ``None``,
                                     text is used as-is.
    """

    def __init__(
        self,
        ha_client: HAClient,
        embedding_model: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.35,
        refresh_interval: int = 300,
        ambiguity_spread_threshold: float = 0.08,
        ambiguity_min_matches: int = 2,
        translation_service: "TranslationService | None" = None,
    ) -> None:
        self._ha_client = ha_client
        self._similarity_threshold = similarity_threshold
        self._refresh_interval = refresh_interval
        self._ambiguity_spread_threshold = ambiguity_spread_threshold
        self._ambiguity_min_matches = ambiguity_min_matches
        self._translation_service = translation_service
        self._model = SentenceTransformer(embedding_model)
        # Index: parallel lists kept in sync
        self._entities: list[HAEntity] = []
        self._embeddings: np.ndarray | None = None  # shape (N, D)
        self._refresh_task: asyncio.Task[Any] | None = None
        self._lock = asyncio.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Perform the first refresh and start the background refresh loop."""
        await self.refresh()
        self._refresh_task = asyncio.create_task(self._background_refresh())

    async def stop(self) -> None:
        """Cancel the background refresh task."""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

    async def refresh(self) -> None:
        """Fetch all HA states and rebuild the embedding index.

        When a :attr:`_translation_service` is configured, the human-readable
        parts of each entity's index text (friendly name, area) are translated
        to English before embedding.  The original entity data is preserved
        unchanged so the correct entity IDs are used when calling HA services.
        """
        logger.info("DeviceResolver: refreshing entity index…")
        try:
            entities = await self._ha_client.get_states()

            # Translate human-readable entity fields to English for the index.
            if self._translation_service:
                texts = await self._translated_entity_texts(entities)
            else:
                texts = [self._entity_text(e) for e in entities]

            embeddings = await asyncio.get_event_loop().run_in_executor(
                None, self._model.encode, texts
            )
            async with self._lock:
                self._entities = entities
                self._embeddings = np.array(embeddings)
            logger.info("DeviceResolver: indexed %d entities", len(entities))
        except Exception as exc:
            logger.error("DeviceResolver: refresh failed: %s", exc)

    async def resolve(
        self,
        query: str,
        domain_filter: list[str] | None = None,
        top_n: int = 5,
    ) -> list[HAEntity]:
        """Return the top-N entities semantically closest to *query*.

        Args:
            query:         Natural-language device name / description.
            domain_filter: When provided, only consider entities in these domains.
            top_n:         Maximum number of results to return.

        Returns:
            Ordered list of matching :class:`~app.ha.models.HAEntity` objects
            (best match first).
        """
        scored = await self._resolve_scored(query, domain_filter=domain_filter, top_n=top_n)
        return [entity for entity, _ in scored]

    async def resolve_with_ambiguity(
        self,
        query: str,
        domain_filter: list[str] | None = None,
        top_n: int = 5,
    ) -> ResolveResult:
        """Resolve a query and detect whether the result is ambiguous.

        Ambiguity is flagged when at least *ambiguity_min_matches* candidates
        score above the similarity threshold **and** their score spread
        (best score − worst score) is below *ambiguity_spread_threshold* —
        meaning no candidate is clearly better than the others.

        Args:
            query:         Natural-language device name / description.
            domain_filter: When provided, only consider entities in these domains.
            top_n:         Maximum number of candidates to consider.

        Returns:
            A :class:`~app.ha.models.ResolveResult` with entities, the
            ambiguity flag, and a human-readable candidates description.
        """
        scored = await self._resolve_scored(query, domain_filter=domain_filter, top_n=top_n)
        if not scored:
            return ResolveResult()

        entities = [entity for entity, _ in scored]
        scores = [score for _, score in scored]

        is_ambiguous = (
            len(scored) >= self._ambiguity_min_matches
            and (scores[0] - scores[1]) < self._ambiguity_spread_threshold
        )

        candidates_description = self._build_candidates_description(entities)
        return ResolveResult(
            entities=entities,
            is_ambiguous=is_ambiguous,
            candidates_description=candidates_description,
        )

    def resolve_sync(
        self,
        query: str,
        domain_filter: list[str] | None = None,
        top_n: int = 5,
    ) -> list[HAEntity]:
        """Synchronous wrapper around :meth:`resolve` for non-async callers."""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.resolve(query, domain_filter, top_n))

    @property
    def cached_entities(self) -> list[HAEntity]:
        """Read-only snapshot of the current entity cache."""
        return list(self._entities)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _resolve_scored(
        self,
        query: str,
        domain_filter: list[str] | None = None,
        top_n: int = 5,
    ) -> list[tuple[HAEntity, float]]:
        """Return (entity, score) pairs above the threshold, best first.

        Translates *query* to English when a translation service is configured.
        """
        async with self._lock:
            entities = list(self._entities)
            embeddings = self._embeddings

        if not entities or embeddings is None:
            logger.warning("DeviceResolver: index is empty; skipping resolve")
            return []

        # Normalise the query to English so it matches the (English) index.
        search_query = query
        if self._translation_service:
            search_query = await self._translation_service.translate_to_english(query)
            if search_query != query:
                logger.debug("Query translated: %r → %r", query, search_query)

        if domain_filter:
            domain_set = set(domain_filter)
            indices = [i for i, e in enumerate(entities) if e.domain in domain_set]
            if not indices:
                return []
            filtered_entities = [entities[i] for i in indices]
            filtered_embeddings = embeddings[indices]
        else:
            filtered_entities = entities
            filtered_embeddings = embeddings

        query_embedding = await asyncio.get_event_loop().run_in_executor(
            None, self._model.encode, [search_query]
        )
        query_vec = np.array(query_embedding[0])

        scores = self._cosine_similarity_batch(query_vec, filtered_embeddings)
        top_indices = np.argsort(scores)[::-1][:top_n]

        results: list[tuple[HAEntity, float]] = []
        for idx in top_indices:
            if scores[idx] >= self._similarity_threshold:
                results.append((filtered_entities[idx], float(scores[idx])))
        return results

    async def _translated_entity_texts(self, entities: list[HAEntity]) -> list[str]:
        """Build index texts for *entities*, translating human-readable fields to English.

        Translates ``friendly_name`` and ``area`` (if present) for each entity,
        then combines them with the raw ``entity_id`` and ``device_class`` into
        the final index text.  The entity objects themselves are not modified.
        """
        assert self._translation_service is not None  # guarded by caller

        # Collect the strings that need translation.
        friendly_names = [e.friendly_name for e in entities]
        areas = [
            str(e.attributes.get("area") or e.attributes.get("area_id") or "")
            for e in entities
        ]

        # Translate all friendly names and areas concurrently.
        translated_names, translated_areas = await asyncio.gather(
            self._translation_service.translate_batch_to_english(friendly_names),
            self._translation_service.translate_batch_to_english(areas),
        )

        texts: list[str] = []
        for entity, t_name, t_area in zip(entities, translated_names, translated_areas):
            parts = [entity.entity_id, t_name]
            if t_area:
                parts.append(t_area)
            device_class = entity.attributes.get("device_class")
            if device_class:
                parts.append(str(device_class))
            texts.append(" ".join(parts))
        return texts

    @staticmethod
    def _build_candidates_description(entities: list[HAEntity]) -> str:
        """Build a human-readable comma-separated list of candidate friendly names."""
        parts = [e.friendly_name for e in entities]
        if len(parts) <= 2:
            return " and ".join(parts)
        return ", ".join(parts[:-1]) + f", and {parts[-1]}"

    @staticmethod
    def _entity_text(entity: HAEntity) -> str:
        """Build the text string that represents an entity in the index (no translation)."""
        parts = [entity.entity_id, entity.friendly_name]
        area = entity.attributes.get("area") or entity.attributes.get("area_id")
        if area:
            parts.append(str(area))
        device_class = entity.attributes.get("device_class")
        if device_class:
            parts.append(str(device_class))
        return " ".join(parts)

    @staticmethod
    def _cosine_similarity_batch(
        query: np.ndarray,
        matrix: np.ndarray,
    ) -> np.ndarray:
        """Compute cosine similarity between *query* and every row in *matrix*."""
        query_norm = query / (np.linalg.norm(query) + 1e-10)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10
        normalised = matrix / norms
        return normalised @ query_norm

    async def _background_refresh(self) -> None:
        """Periodically refresh the entity index."""
        while True:
            await asyncio.sleep(self._refresh_interval)
            await self.refresh()

