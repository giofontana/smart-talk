"""Pydantic models for Home Assistant entities and service calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, computed_field


class HAEntity(BaseModel):
    """Represents a single Home Assistant entity state."""

    entity_id: str
    state: str
    attributes: dict[str, Any] = {}

    @computed_field  # type: ignore[misc]
    @property
    def friendly_name(self) -> str:
        """Human-readable name from HA attributes, falling back to entity_id."""
        return self.attributes.get("friendly_name") or self.entity_id

    @computed_field  # type: ignore[misc]
    @property
    def domain(self) -> str:
        """HA domain extracted from entity_id (e.g. 'light', 'switch')."""
        return self.entity_id.split(".")[0]


class HAServiceCall(BaseModel):
    """Payload for calling a Home Assistant service."""

    domain: str
    service: str
    entity_id: str | None = None
    data: dict[str, Any] = {}


@dataclass
class ResolveResult:
    """Result of a device resolution with optional ambiguity detection.

    Attributes:
        entities:              Matching entities above the similarity threshold,
                               ordered by descending similarity score.
        is_ambiguous:          True when 2+ entities scored close to each other,
                               meaning the user query does not clearly identify one.
        candidates_description: Human-readable comma-separated list of candidate
                               names, ready to embed in a clarification question.
    """

    entities: list[HAEntity] = field(default_factory=list)
    is_ambiguous: bool = False
    candidates_description: str = ""

    @property
    def top(self) -> HAEntity | None:
        """Return the best-scoring entity, or None if no matches."""
        return self.entities[0] if self.entities else None
