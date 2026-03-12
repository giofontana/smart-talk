"""Smart Talk STT platform.

Registers SmartTalkSTTEntity as a HA Speech-to-Text provider.
Audio is forwarded to the Smart Talk add-on's Wyoming STT server (faster-whisper)
via the Wyoming TCP protocol on the configured host:port (default 10300).
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from typing import AsyncIterable

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    SpeechToTextEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ADDON_HOST,
    CONF_AGENT_NAME,
    CONF_STT_PORT,
    DEFAULT_ADDON_HOST,
    DEFAULT_STT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 10.0
_TRANSCRIBE_TIMEOUT = 60.0

# Languages supported by Whisper (common subset; add more as needed)
_WHISPER_LANGUAGES = [
    "af", "am", "ar", "az", "be", "bg", "bn", "bo", "br", "bs", "ca", "cs",
    "cy", "da", "de", "el", "en", "es", "et", "eu", "fa", "fi", "fr", "gl",
    "gu", "ha", "hi", "hr", "hu", "hy", "id", "is", "it", "ja", "ka", "kk",
    "km", "kn", "ko", "lb", "lt", "lv", "mi", "mk", "ml", "mn", "mr", "ms",
    "mt", "my", "ne", "nl", "nn", "no", "pa", "pl", "ps", "pt", "ro", "ru",
    "sd", "si", "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw", "ta",
    "te", "tg", "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi", "yi",
    "yo", "zh",
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Talk STT entity from a config entry."""
    async_add_entities([SmartTalkSTTEntity(config_entry)], update_before_add=False)


class SmartTalkSTTEntity(SpeechToTextEntity):
    """STT entity that sends audio to the Smart Talk add-on's Wyoming STT server."""

    _attr_has_entity_name = True

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry
        name = config_entry.data.get(CONF_AGENT_NAME, "Smart Talk")
        self._attr_name = f"{name} STT"
        self._attr_unique_id = f"{DOMAIN}_stt_{config_entry.entry_id}"

    @property
    def _host(self) -> str:
        return (
            self._config_entry.options.get(CONF_ADDON_HOST)
            or self._config_entry.data.get(CONF_ADDON_HOST, DEFAULT_ADDON_HOST)
        )

    @property
    def _port(self) -> int:
        return int(
            self._config_entry.options.get(CONF_STT_PORT)
            or self._config_entry.data.get(CONF_STT_PORT, DEFAULT_STT_PORT)
        )

    @property
    def supported_languages(self) -> list[str]:
        return _WHISPER_LANGUAGES

    @property
    def supported_formats(self) -> list[AudioFormats]:
        return [AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        return [AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> SpeechResult:
        """Buffer the full audio stream then transcribe via Wyoming STT."""
        buf = io.BytesIO()
        async for chunk in stream:
            buf.write(chunk)

        audio = buf.getvalue()
        if not audio:
            return SpeechResult(None, SpeechResultState.ERROR)

        try:
            text = await asyncio.wait_for(
                self._transcribe(audio, metadata),
                timeout=_TRANSCRIBE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Smart Talk STT timed out after %ss (host=%s port=%d)",
                _TRANSCRIBE_TIMEOUT, self._host, self._port,
            )
            return SpeechResult(None, SpeechResultState.ERROR)
        except Exception:
            _LOGGER.exception(
                "Smart Talk STT failed (host=%s port=%d)", self._host, self._port
            )
            return SpeechResult(None, SpeechResultState.ERROR)

        if text is None:
            return SpeechResult(None, SpeechResultState.ERROR)

        return SpeechResult(text, SpeechResultState.SUCCESS)

    async def _transcribe(self, audio: bytes, metadata: SpeechMetadata) -> str | None:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=_CONNECT_TIMEOUT,
        )
        try:
            # audio-start: describe the incoming audio format
            await _send_event(writer, "audio-start", {
                "rate": int(metadata.sample_rate),
                "width": int(metadata.bit_rate) // 8,
                "channels": int(metadata.channel),
            })

            # audio-chunk: send the full audio as a single chunk with a binary payload
            await _send_event(writer, "audio-chunk", {
                "rate": int(metadata.sample_rate),
                "width": int(metadata.bit_rate) // 8,
                "channels": int(metadata.channel),
                "payload_length": len(audio),
            })
            writer.write(audio)
            await writer.drain()

            # audio-stop: signal end of audio
            await _send_event(writer, "audio-stop", {})

            # Read transcript response
            line = await reader.readline()
            if not line:
                _LOGGER.warning("Smart Talk STT server closed connection without a response")
                return None

            msg = json.loads(line.decode().strip())
            if msg.get("type") == "transcript":
                return msg.get("data", {}).get("text") or ""

            _LOGGER.warning("Unexpected Wyoming STT response type: %s", msg.get("type"))
            return None

        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


async def _send_event(
    writer: asyncio.StreamWriter, event_type: str, data: dict
) -> None:
    payload = json.dumps({"type": event_type, "data": data}) + "\n"
    writer.write(payload.encode())
    await writer.drain()
