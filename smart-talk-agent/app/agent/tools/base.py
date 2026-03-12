"""Abstract base class for all Smart Talk LangChain tools."""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any

from langchain.tools import BaseTool
from pydantic import ConfigDict

from app.ha.client import HAClient
from app.ha.models import HAEntity, ResolveResult
from app.search.device_resolver import DeviceResolver

logger = logging.getLogger(__name__)


class SmartTalkTool(BaseTool):
    """Base class for all Smart Talk tools.

    Subclasses must implement :meth:`_arun` and may call
    :meth:`_resolve_entity` (single best match) or :meth:`_resolve_entities`
    (all matches with ambiguity detection) to locate HA entities.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ha_client: HAClient
    device_resolver: DeviceResolver

    # Prevent LangChain from trying to call a sync _run unless explicitly overridden
    def _run(self, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        raise NotImplementedError("Use the async _arun interface.")

    @abstractmethod
    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        """Execute the tool action asynchronously."""

    async def _resolve_entity(
        self,
        query: str,
        domain_filter: list[str] | None = None,
    ) -> HAEntity | None:
        """Resolve a query to the single best-matching HA entity.

        Returns the best-matching entity or ``None`` when nothing meets the
        similarity threshold.  Does not perform ambiguity detection — use
        :meth:`_resolve_entities` when multiple candidates are possible.

        Args:
            query:         Device description from the user's message.
            domain_filter: Optional list of HA domains to restrict the search.
        """
        results = await self.device_resolver.resolve(query, domain_filter=domain_filter)
        if not results:
            logger.info("No entity resolved for query=%r domain_filter=%s", query, domain_filter)
            return None
        logger.debug(
            "Resolved query=%r → %s (top result of %d)", query, results[0].entity_id, len(results)
        )
        return results[0]

    async def _resolve_entities(
        self,
        query: str,
        domain_filter: list[str] | None = None,
    ) -> ResolveResult:
        """Resolve a query with ambiguity detection.

        Returns a :class:`~app.ha.models.ResolveResult` containing all
        above-threshold candidates, an ``is_ambiguous`` flag, and a
        human-readable description of the candidates for use in clarification
        questions.

        Args:
            query:         Device description from the user's message.
            domain_filter: Optional list of HA domains to restrict the search.
        """
        result = await self.device_resolver.resolve_with_ambiguity(
            query, domain_filter=domain_filter
        )
        if not result.entities:
            logger.info(
                "No entities resolved for query=%r domain_filter=%s", query, domain_filter
            )
        elif result.is_ambiguous:
            logger.info(
                "Ambiguous resolution for query=%r — %d candidates: %s",
                query,
                len(result.entities),
                result.candidates_description,
            )
        else:
            logger.debug("Resolved query=%r → %s", query, result.entities[0].entity_id)
        return result

    @staticmethod
    def _ambiguity_clarification(
        candidates_description: str,
        verb: str,
        allow_all: bool = True,
    ) -> str:
        """Build a natural disambiguation message that names the found devices.

        Args:
            candidates_description: Human-readable list of matching device names.
            verb:                   Action verb for the question, e.g. "close", "turn on".
            allow_all:              When True, offer the "all of them" option.
        """
        suffix = f" You can also ask me to {verb} all of them." if allow_all else ""
        return (
            f"I found {candidates_description}. "
            f"Which one would you like to {verb}?{suffix}"
        )
