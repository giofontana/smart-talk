"""Config flow for the Smart Talk integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AGENT_NAME,
    CONF_AGENT_URL,
    CONF_ADDON_HOST,
    CONF_STT_PORT,
    CONF_TTS_PORT,
    DEFAULT_ADDON_HOST,
    DEFAULT_AGENT_NAME,
    DEFAULT_AGENT_URL,
    DEFAULT_STT_PORT,
    DEFAULT_TTS_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

def _default_addon_host(agent_url: str) -> str:
    """Extract hostname from the agent URL to use as default add-on host."""
    try:
        return urlparse(agent_url).hostname or DEFAULT_ADDON_HOST
    except Exception:
        return DEFAULT_ADDON_HOST


def _build_user_schema(
    agent_url: str = DEFAULT_AGENT_URL,
    agent_name: str = DEFAULT_AGENT_NAME,
    addon_host: str = DEFAULT_ADDON_HOST,
    stt_port: int = DEFAULT_STT_PORT,
    tts_port: int = DEFAULT_TTS_PORT,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_AGENT_URL, default=agent_url): str,
            vol.Required(CONF_AGENT_NAME, default=agent_name): str,
            vol.Required(CONF_ADDON_HOST, default=addon_host): str,
            vol.Required(CONF_STT_PORT, default=stt_port): int,
            vol.Required(CONF_TTS_PORT, default=tts_port): int,
        }
    )


_USER_SCHEMA = _build_user_schema()


async def _validate_agent_url(hass: Any, agent_url: str) -> dict[str, str]:
    """Validate the agent URL by calling its /health endpoint.

    Returns an error dict (suitable for ``errors=``) or an empty dict on
    success.
    """
    base = agent_url.rstrip("/")
    if base.endswith("/conversation"):
        base = base[: -len("/conversation")]
    health_url = f"{base}/health"

    session = async_get_clientsession(hass)
    try:
        async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                _LOGGER.warning(
                    "Smart Talk health check returned status %d for %s", resp.status, health_url
                )
                return {"base": "cannot_connect"}
    except aiohttp.ClientConnectorError:
        return {"base": "cannot_connect"}
    except aiohttp.InvalidURL:
        return {"base": "invalid_url"}
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Unexpected error validating Smart Talk agent URL %s", health_url)
        return {"base": "unknown"}

    return {}


class SmartTalkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow handler for Smart Talk."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await _validate_agent_url(self.hass, user_input[CONF_AGENT_URL])
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_AGENT_NAME],
                    data=user_input,
                )

        agent_url = (user_input or {}).get(CONF_AGENT_URL, DEFAULT_AGENT_URL)
        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(
                agent_url=agent_url,
                addon_host=_default_addon_host(agent_url),
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> SmartTalkOptionsFlow:
        """Return the options flow handler."""
        return SmartTalkOptionsFlow(config_entry)


class SmartTalkOptionsFlow(config_entries.OptionsFlow):
    """Options flow — lets the user edit settings after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options form."""
        errors: dict[str, str] = {}
        current = self._config_entry.data

        if user_input is not None:
            errors = await _validate_agent_url(
                self.hass, user_input[CONF_AGENT_URL]
            )
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        agent_url = (user_input or current).get(CONF_AGENT_URL, DEFAULT_AGENT_URL)
        return self.async_show_form(
            step_id="init",
            data_schema=_build_user_schema(
                agent_url=agent_url,
                agent_name=current.get(CONF_AGENT_NAME, DEFAULT_AGENT_NAME),
                addon_host=current.get(CONF_ADDON_HOST, _default_addon_host(agent_url)),
                stt_port=current.get(CONF_STT_PORT, DEFAULT_STT_PORT),
                tts_port=current.get(CONF_TTS_PORT, DEFAULT_TTS_PORT),
            ),
            errors=errors,
        )
