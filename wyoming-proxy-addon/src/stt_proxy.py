"""STT proxy - forwards audio to Whisper, returns transcript unchanged."""

import asyncio
import logging
from urllib.parse import urlparse

from wyoming.server import AsyncTcpServer

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
        server = AsyncTcpServer.create(
            self.listen_host, self.listen_port, self._handle_client
        )
        await server.run()

    async def _handle_client(self, reader, writer):
        """Handle incoming STT request from HA - forward to Whisper."""
        try:
            # Parse upstream URL
            upstream = urlparse(self.upstream_url)

            # Connect to upstream Whisper
            upstream_reader, upstream_writer = await asyncio.open_connection(
                upstream.hostname, upstream.port or 10300
            )

            # Bidirectional forwarding: HA <-> Whisper
            await asyncio.gather(
                self._forward(reader, upstream_writer, "HA→Whisper"),
                self._forward(upstream_reader, writer, "Whisper→HA"),
            )

        except Exception as e:
            _LOGGER.error(f"STT proxy error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _forward(self, reader, writer, direction: str):
        """Forward data from reader to writer."""
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except Exception as e:
            _LOGGER.debug(f"Forward {direction} closed: {e}")
