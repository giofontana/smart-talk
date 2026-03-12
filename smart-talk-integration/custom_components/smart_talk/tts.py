"""Smart Talk TTS platform.

Registers SmartTalkTTSEntity as a HA Text-to-Speech provider.
Text is forwarded to the Smart Talk add-on's Wyoming TTS server (piper-tts)
via the Wyoming TCP protocol on the configured host:port (default 10301).

The Wyoming TTS server returns base64-encoded PCM chunks which are assembled
into a WAV file and returned to HA.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import wave
from typing import Any

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ADDON_HOST,
    CONF_AGENT_NAME,
    CONF_TTS_PORT,
    DEFAULT_ADDON_HOST,
    DEFAULT_TTS_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 10.0
_SYNTHESIZE_TIMEOUT = 60.0

# Piper default output format — must match tts_server.py constants
_DEFAULT_SAMPLE_RATE = 22050
_DEFAULT_SAMPLE_WIDTH = 2   # 16-bit
_DEFAULT_CHANNELS = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Talk TTS entity from a config entry."""
    async_add_entities([SmartTalkTTSEntity(config_entry)], update_before_add=False)


class SmartTalkTTSEntity(TextToSpeechEntity):
    """TTS entity that synthesizes speech via the Smart Talk add-on's Wyoming TTS server."""

    _attr_has_entity_name = True

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry
        name = config_entry.data.get(CONF_AGENT_NAME, "Smart Talk")
        self._attr_name = f"{name} TTS"
        self._attr_unique_id = f"{DOMAIN}_tts_{config_entry.entry_id}"

    @property
    def _host(self) -> str:
        return (
            self._config_entry.options.get(CONF_ADDON_HOST)
            or self._config_entry.data.get(CONF_ADDON_HOST, DEFAULT_ADDON_HOST)
        )

    @property
    def _port(self) -> int:
        return int(
            self._config_entry.options.get(CONF_TTS_PORT)
            or self._config_entry.data.get(CONF_TTS_PORT, DEFAULT_TTS_PORT)
        )

    @property
    def default_language(self) -> str:
        return "en"

    @property
    def supported_languages(self) -> list[str]:
        # Piper supports many languages; list the ones available in the default voice set
        return [
            "de", "en", "es", "fr", "it", "nl", "pl", "pt", "ru", "uk", "zh",
        ]

    @property
    def default_options(self) -> dict[str, Any]:
        return {}

    async def async_get_tts_audio(
        self,
        message: str,
        language: str,
        options: dict[str, Any] | None = None,
    ) -> TtsAudioType:
        """Synthesize message and return (extension, wav_bytes)."""
        try:
            wav_bytes = await asyncio.wait_for(
                self._synthesize(message),
                timeout=_SYNTHESIZE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Smart Talk TTS timed out after %ss (host=%s port=%d)",
                _SYNTHESIZE_TIMEOUT, self._host, self._port,
            )
            return None, None
        except Exception:
            _LOGGER.exception(
                "Smart Talk TTS failed (host=%s port=%d)", self._host, self._port
            )
            return None, None

        return "wav", wav_bytes

    async def _synthesize(self, text: str) -> bytes:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=_CONNECT_TIMEOUT,
        )

        pcm_chunks: list[bytes] = []
        sample_rate = _DEFAULT_SAMPLE_RATE
        sample_width = _DEFAULT_SAMPLE_WIDTH
        channels = _DEFAULT_CHANNELS

        try:
            await _send_event(writer, "synthesize", {
                "text": text,
                "voice": {},
            })

            while True:
                line = await reader.readline()
                if not line:
                    break

                msg = json.loads(line.decode().strip())
                event_type = msg.get("type", "")
                data = msg.get("data", {})

                if event_type == "audio-start":
                    sample_rate = data.get("rate", _DEFAULT_SAMPLE_RATE)
                    sample_width = data.get("width", _DEFAULT_SAMPLE_WIDTH)
                    channels = data.get("channels", _DEFAULT_CHANNELS)

                elif event_type == "audio-chunk":
                    # The Wyoming TTS server encodes PCM as base64 in the JSON data
                    encoded = data.get("audio", "")
                    if encoded:
                        pcm_chunks.append(base64.b64decode(encoded))

                elif event_type == "audio-stop":
                    break

                else:
                    _LOGGER.debug("Unexpected Wyoming TTS event: %s", event_type)

        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

        return _pcm_to_wav(b"".join(pcm_chunks), sample_rate, sample_width, channels)


def _pcm_to_wav(pcm: bytes, rate: int, width: int, channels: int) -> bytes:
    """Wrap raw PCM bytes in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()


async def _send_event(
    writer: asyncio.StreamWriter, event_type: str, data: dict
) -> None:
    payload = json.dumps({"type": event_type, "data": data}) + "\n"
    writer.write(payload.encode())
    await writer.drain()
