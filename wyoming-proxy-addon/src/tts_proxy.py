"""TTS proxy - detects language from text, selects voice, forwards to Piper."""

import asyncio
import logging
from typing import Dict
from urllib.parse import urlparse

import langdetect
from langdetect import DetectorFactory
from wyoming.event import async_read_event, async_write_event
from wyoming.tts import Synthesize

# Set seed for consistent results
DetectorFactory.seed = 0

_LOGGER = logging.getLogger(__name__)


class TTSProxy:
    """Wyoming TTS proxy with automatic voice selection."""

    def __init__(
        self,
        listen_host: str,
        listen_port: int,
        upstream_url: str,
        voice_mapping: Dict[str, str],
    ):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.upstream_url = upstream_url
        self.voice_mapping = voice_mapping
        # Set default voice: prefer English, fallback to first voice, or None
        if "en" in voice_mapping:
            self.default_voice = voice_mapping["en"]
        elif voice_mapping:
            self.default_voice = list(voice_mapping.values())[0]
        else:
            self.default_voice = None  # No voices configured

    async def run(self):
        """Start the TTS proxy server."""
        _LOGGER.info(f"TTS proxy listening on {self.listen_host}:{self.listen_port}")
        _LOGGER.info(f"Voice mapping: {self.voice_mapping}")
        server = await asyncio.start_server(
            self._handle_client, self.listen_host, self.listen_port
        )
        async with server:
            await server.serve_forever()

    def _detect_language(self, text: str) -> str:
        """Detect language from text."""
        try:
            if len(text.strip()) < 5:
                # Too short, use default
                return "en"

            detections = langdetect.detect_langs(text)
            if detections:
                lang = detections[0].lang
                confidence = detections[0].prob
                _LOGGER.debug(
                    f"Detected language: {lang} (confidence: {confidence:.2f})"
                )
                return lang
        except Exception as e:
            _LOGGER.warning(f"Language detection failed: {e}")

        return "en"

    def _select_voice(self, language: str) -> str:
        """Select voice based on detected language."""
        voice = self.voice_mapping.get(language, self.default_voice)
        _LOGGER.info(f"Language '{language}' → Voice '{voice}'")
        return voice

    async def _handle_client(self, reader, writer):
        """Handle incoming TTS request from HA."""
        try:
            # Parse upstream URL
            upstream = urlparse(self.upstream_url)

            # Connect to upstream Piper
            upstream_reader, upstream_writer = await asyncio.open_connection(
                upstream.hostname, upstream.port or 10200
            )

            # Read events from HA
            while True:
                event = await async_read_event(reader)
                if event is None:
                    break

                # Intercept synthesize events to inject voice
                if isinstance(event, Synthesize):
                    text = event.text
                    _LOGGER.debug(f"TTS request: {text[:100]}")

                    # Detect language
                    language = self._detect_language(text)

                    # Select voice
                    voice_name = self._select_voice(language)

                    # Modify event to include voice
                    event_dict = event.event()
                    event_dict["data"]["voice"] = {"name": voice_name}

                    # Forward modified event to Piper
                    await async_write_event(event_dict, upstream_writer)
                else:
                    # Forward other events unchanged
                    await async_write_event(event.event(), upstream_writer)

            # Forward responses from Piper back to HA
            while True:
                response = await async_read_event(upstream_reader)
                if response is None:
                    break
                await async_write_event(response.event(), writer)

        except Exception as e:
            _LOGGER.error(f"TTS proxy error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
