"""Config flow for the Smart Talk integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AGENT_NAME,
    CONF_CONVERSATION_PROXY_URL,
    DEFAULT_AGENT_NAME,
    DEFAULT_PROXY_URL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONVERSATION_PROXY_URL, default=DEFAULT_PROXY_URL): str,
        vol.Required(CONF_AGENT_NAME, default=DEFAULT_AGENT_NAME): str,
    }
)


async def _validate_proxy_url(hass: Any, proxy_url: str) -> dict[str, str]:
    """Validate the conversation proxy URL by calling its /health endpoint.

    Returns an error dict (suitable for ``errors=``) or an empty dict on
    success.
    """
    # Derive the base URL by stripping the /conversation path segment, if present
    base = proxy_url.rstrip("/")
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
        _LOGGER.exception("Unexpected error validating Smart Talk proxy URL %s", health_url)
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
            errors = await _validate_proxy_url(self.hass, user_input[CONF_CONVERSATION_PROXY_URL])
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_AGENT_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_USER_SCHEMA,
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
            errors = await _validate_proxy_url(
                self.hass, user_input[CONF_CONVERSATION_PROXY_URL]
            )
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CONVERSATION_PROXY_URL,
                    default=current.get(CONF_CONVERSATION_PROXY_URL, DEFAULT_PROXY_URL),
                ): str,
                vol.Required(
                    CONF_AGENT_NAME,
                    default=current.get(CONF_AGENT_NAME, DEFAULT_AGENT_NAME),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
