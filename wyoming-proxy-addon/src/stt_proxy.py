"""STT proxy - forwards audio to Whisper, returns transcript unchanged."""

import asyncio
import logging
from urllib.parse import urlparse

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import async_read_event, async_write_event

_LOGGER = logging.getLogger(__name__)


class STTProxy:
    """Transparent proxy for Wyoming STT (Whisper)."""

    def __init__(self, listen_host: str, listen_port: int, upstream_url: str):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.upstream_url = upstream_url

    async def run(self):
        """Start the STT proxy server."""
        _LOGGER.info(f"STT proxy listening on {self.listen_host}:{self.listen_port}")
        server = await asyncio.start_server(
            self._handle_client, self.listen_host, self.listen_port
        )
        async with server:
            await server.serve_forever()

    async def _handle_client(self, reader, writer):
        """Handle incoming STT request from HA - forward to Whisper."""
        client = writer.get_extra_info("peername", ("?", "?"))
        _LOGGER.info(f"[STT] New connection from {client[0]}:{client[1]}")
        try:
            upstream = urlparse(self.upstream_url)
            upstream_reader, upstream_writer = await asyncio.open_connection(
                upstream.hostname, upstream.port or 10300
            )

            await asyncio.gather(
                self._forward_to_whisper(reader, upstream_writer),
                self._forward_to_ha(upstream_reader, writer),
            )

        except Exception as e:
            _LOGGER.error(f"[STT] Proxy error: {e}")
        finally:
            _LOGGER.info(f"[STT] Connection closed from {client[0]}:{client[1]}")
            writer.close()
            await writer.wait_closed()

    async def _forward_to_whisper(self, reader, writer):
        """HA → Whisper: log notable events, forward everything."""
        chunk_count = 0
        try:
            while True:
                event = await async_read_event(reader)
                if event is None:
                    break
                if Transcribe.is_type(event):
                    transcribe = Transcribe.from_event(event)
                    _LOGGER.info(
                        f"[STT] Transcribe request — language hint: {transcribe.language or 'none'}"
                    )
                elif AudioStart.is_type(event):
                    chunk_count = 0
                    _LOGGER.debug("[STT] AudioStart received")
                elif AudioChunk.is_type(event):
                    chunk_count += 1
                elif AudioStop.is_type(event):
                    _LOGGER.info(f"[STT] AudioStop received — forwarded {chunk_count} chunks to Whisper")
                await async_write_event(event, writer)
        except Exception as e:
            _LOGGER.debug(f"[STT] HA→Whisper closed: {e}")

    async def _forward_to_ha(self, reader, writer):
        """Whisper → HA: log transcript result, forward everything."""
        try:
            while True:
                event = await async_read_event(reader)
                if event is None:
                    break
                if Transcript.is_type(event):
                    transcript = Transcript.from_event(event)
                    _LOGGER.info(f"[STT] Transcript result: '{transcript.text}'")
                await async_write_event(event, writer)
        except Exception as e:
            _LOGGER.debug(f"[STT] Whisper→HA closed: {e}")
