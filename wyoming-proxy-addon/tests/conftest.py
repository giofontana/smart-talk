"""Shared pytest fixtures for Wyoming Polyglot Proxy tests."""

import asyncio
import json
import socket
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import async_read_event, async_write_event
from wyoming.tts import Synthesize


@pytest.fixture
def voice_mapping():
    """Standard voice mapping for tests."""
    return {
        "en": "en_US-lessac-medium",
        "es": "es_ES-mls-medium",
        "it": "it_IT-riccardo-x_low",
        "pt": "pt_BR-faber-medium",
        "fr": "fr_FR-siwis-medium",
    }


@pytest.fixture
def mock_config(tmp_path, voice_mapping):
    """Mock configuration file."""
    config_file = tmp_path / "options.json"
    config_data = {
        "whisper_url": "tcp://localhost:10300",
        "piper_url": "tcp://localhost:10200",
        "voice_mapping": voice_mapping,
        "log_level": "info",
    }
    config_file.write_text(json.dumps(config_data))
    return config_file


@pytest.fixture
def unused_tcp_port():
    """Get an unused TCP port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture
async def mock_wyoming_server(unused_tcp_port):
    """Create a mock Wyoming server for testing."""
    responses = []

    async def handle_client(reader, writer):
        while True:
            event = await async_read_event(reader)
            if event is None:
                break

            # Store received event
            responses.append(event)

            # Send mock response
            if isinstance(event, Synthesize):
                await async_write_event(
                    AudioStart(rate=22050, width=2, channels=1).event(),
                    writer,
                )
                await async_write_event(
                    AudioChunk(
                        audio=b"\x00" * 1024, rate=22050, width=2, channels=1
                    ).event(),
                    writer,
                )
                await async_write_event(AudioStop().event(), writer)
                break

    server = await asyncio.start_server(handle_client, "127.0.0.1", unused_tcp_port)

    yield unused_tcp_port, responses

    server.close()
    await server.wait_closed()


@pytest.fixture
def mock_stream_reader():
    """Create a mock asyncio.StreamReader."""
    reader = AsyncMock()
    reader.read = AsyncMock(return_value=b"")
    return reader


@pytest.fixture
def mock_stream_writer():
    """Create a mock asyncio.StreamWriter."""
    writer = AsyncMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    return writer
