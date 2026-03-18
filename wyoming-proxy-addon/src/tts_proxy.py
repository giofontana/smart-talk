"""TTS proxy - detects language from text, selects voice, forwards to Piper."""

import asyncio
import logging
from typing import Dict
from urllib.parse import urlparse

import langdetect
from langdetect import DetectorFactory
from wyoming.event import async_read_event, async_write_event
from wyoming.tts import Synthesize, SynthesizeVoice

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
        upstream_writer = None
        try:
            # Parse upstream URL
            upstream = urlparse(self.upstream_url)

            # Connect to upstream Piper
            upstream_reader, upstream_writer = await asyncio.open_connection(
                upstream.hostname, upstream.port or 10200
            )

            async def forward_to_piper():
                """HA → Piper: intercept Synthesize events to inject selected voice."""
                while True:
                    event = await async_read_event(reader)
                    if event is None:
                        break

                    if Synthesize.is_type(event):
                        synthesize = Synthesize.from_event(event)
                        text = synthesize.text
                        _LOGGER.debug(f"TTS request: {text[:100]}")

                        language = self._detect_language(text)
                        voice_name = self._select_voice(language)

                        modified = Synthesize(
                            text=text, voice=SynthesizeVoice(name=voice_name)
                        )
                        await async_write_event(modified.event(), upstream_writer)
                    else:
                        await async_write_event(event, upstream_writer)

            async def forward_to_ha():
                """Piper → HA: forward audio responses as-is."""
                while True:
                    response = await async_read_event(upstream_reader)
                    if response is None:
                        break
                    await async_write_event(response, writer)

            # Both directions must run concurrently: HA waits for audio while
            # Piper waits for the request — sequential loops would deadlock.
            await asyncio.gather(forward_to_piper(), forward_to_ha())

        except Exception as e:
            _LOGGER.error(f"TTS proxy error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            if upstream_writer is not None and not upstream_writer.is_closing():
                upstream_writer.close()
