"""Smart Talk conversation platform.

Registers ``SmartTalkConversationEntity`` as a HA Conversation Agent.
Requests are forwarded via HTTP POST directly to the Smart Talk AI agent.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import aiohttp
from homeassistant.components import conversation
from homeassistant.components.conversation import (
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

try:
    from homeassistant.components.conversation import MATCH_ALL
except ImportError:
    MATCH_ALL = "*"  # fallback for older HA versions

from .const import CONF_AGENT_NAME, CONF_AGENT_URL, DEFAULT_AGENT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Talk conversation entity from a config entry."""
    async_add_entities(
        [SmartTalkConversationEntity(hass, config_entry)],
        update_before_add=False,
    )


class SmartTalkConversationEntity(conversation.ConversationEntity):
    """Conversation agent that delegates to the Smart Talk AI agent."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self._config_entry = config_entry
        self._attr_name = config_entry.data.get(CONF_AGENT_NAME, "Smart Talk")
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}"

    @property
    def supported_languages(self) -> list[str] | str:
        """Return supported languages — MATCH_ALL means any language."""
        return MATCH_ALL

    @property
    def _agent_url(self) -> str:
        return (
            self._config_entry.options.get(CONF_AGENT_URL)
            or self._config_entry.data.get(CONF_AGENT_URL, DEFAULT_AGENT_URL)
        )

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a natural language command and return the agent's response."""
        session_id = user_input.conversation_id or str(uuid4())
        text = user_input.text
        language = user_input.language or "en"

        intent_response = intent.IntentResponse(language=language)

        try:
            http_session = async_get_clientsession(self.hass)
            async with http_session.post(
                self._agent_url,
                json={"session_id": session_id, "text": text, "language": language},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json()

            response_text: str = payload.get("text", "")
            response_language: str = payload.get("language", language)

            intent_response.async_set_speech(response_text)
            intent_response.language = response_language

        except aiohttp.ClientResponseError as exc:
            _LOGGER.error(
                "Smart Talk agent returned HTTP %d for session %s: %s",
                exc.status,
                session_id,
                exc.message,
            )
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Smart Talk agent returned an error (HTTP {exc.status}).",
            )

        except aiohttp.ClientConnectorError:
            _LOGGER.error(
                "Cannot connect to Smart Talk agent at %s (session %s)",
                self._agent_url,
                session_id,
            )
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                "Cannot connect to the Smart Talk agent. Please check the agent is running.",
            )

        except Exception:  # noqa: BLE001
            _LOGGER.exception(
                "Unexpected error processing conversation for session %s", session_id
            )
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                "An unexpected error occurred while contacting the Smart Talk agent.",
            )

        return ConversationResult(
            response=intent_response,
            conversation_id=session_id,
        )
