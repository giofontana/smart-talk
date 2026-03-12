"""Unit tests for app.ha.models."""

from __future__ import annotations

import pytest

from app.ha.models import HAEntity


def test_entity_domain_extracted():
    entity = HAEntity(entity_id="light.kitchen", state="off", attributes={})
    assert entity.domain == "light"


def test_entity_friendly_name_from_attributes():
    entity = HAEntity(
        entity_id="light.kitchen",
        state="off",
        attributes={"friendly_name": "Kitchen Ceiling"},
    )
    assert entity.friendly_name == "Kitchen Ceiling"


def test_entity_friendly_name_fallback():
    entity = HAEntity(entity_id="light.kitchen", state="off", attributes={})
    assert entity.friendly_name == "light.kitchen"
