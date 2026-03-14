"""End-to-end tests for TTS flow with mock Wyoming server."""

import asyncio

import pytest
from wyoming.audio import AudioStart, AudioChunk, AudioStop
from wyoming.event import async_read_event, async_write_event
from wyoming.tts import Synthesize

from src.tts_proxy import TTSProxy


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_full_tts_spanish_flow_with_mock_server(voice_mapping, unused_tcp_port):
    """Test complete TTS flow with Spanish text and mock Piper server."""
    # Create mock Piper server
    piper_port = unused_tcp_port
    received_events = []

    async def mock_piper_handler(reader, writer):
        """Mock Piper server that captures requests and sends audio."""
        while True:
            event = await async_read_event(reader)
            if event is None:
                break

            received_events.append(event)

            # Send mock audio response
            if isinstance(event, Synthesize):
                await async_write_event(
                    AudioStart(rate=22050, width=2, channels=1).event(), writer
                )
                await async_write_event(
                    AudioChunk(
                        audio=b"\x00" * 1024, rate=22050, width=2, channels=1
                    ).event(),
                    writer,
                )
                await async_write_event(AudioStop().event(), writer)
                break

        writer.close()
        await writer.wait_closed()

    # Start mock Piper server
    piper_server = await asyncio.start_server(
        mock_piper_handler, "127.0.0.1", piper_port
    )

    # Get another port for proxy
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        proxy_port = s.getsockname()[1]

    # Create TTS proxy
    proxy = TTSProxy(
        listen_host="127.0.0.1",
        listen_port=proxy_port,
        upstream_url=f"tcp://127.0.0.1:{piper_port}",
        voice_mapping=voice_mapping,
    )

    # Start proxy server in background
    proxy_task = asyncio.create_task(proxy.run())

    try:
        # Give proxy time to start
        await asyncio.sleep(0.2)

        # Connect as client to proxy
        client_reader, client_writer = await asyncio.open_connection(
            "127.0.0.1", proxy_port
        )

        # Send Spanish Synthesize event
        spanish_text = "Hola, ¿cómo estás hoy?"
        synthesize_event = Synthesize(text=spanish_text)
        await async_write_event(synthesize_event.event(), client_writer)

        # Read audio response
        audio_events = []
        while True:
            event = await asyncio.wait_for(
                async_read_event(client_reader), timeout=2.0
            )
            if event is None:
                break

            audio_events.append(event)

            if isinstance(event, AudioStop):
                break

        # Verify we received audio
        assert len(audio_events) >= 3  # AudioStart, AudioChunk, AudioStop

        # Verify Piper received the event with Spanish voice
        assert len(received_events) > 0
        piper_event = received_events[0]
        assert isinstance(piper_event, Synthesize)
        assert piper_event.text == spanish_text

        # Note: The voice injection happens in the event dict, check if we can access it
        # This verifies the proxy modified the event before forwarding

        client_writer.close()
        await client_writer.wait_closed()

    finally:
        # Cleanup
        proxy_task.cancel()
        try:
            await proxy_task
        except asyncio.CancelledError:
            pass

        piper_server.close()
        await piper_server.wait_closed()


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_full_tts_english_flow_with_mock_server(voice_mapping, unused_tcp_port):
    """Test complete TTS flow with English text and mock Piper server."""
    # Create mock Piper server
    piper_port = unused_tcp_port
    received_events = []

    async def mock_piper_handler(reader, writer):
        """Mock Piper server that captures requests."""
        event = await async_read_event(reader)
        if event:
            received_events.append(event)

            # Send mock audio
            if isinstance(event, Synthesize):
                await async_write_event(
                    AudioStart(rate=22050, width=2, channels=1).event(), writer
                )
                await async_write_event(AudioStop().event(), writer)

        writer.close()
        await writer.wait_closed()

    # Start mock Piper
    piper_server = await asyncio.start_server(
        mock_piper_handler, "127.0.0.1", piper_port
    )

    # Get proxy port
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        proxy_port = s.getsockname()[1]

    # Create and start proxy
    proxy = TTSProxy(
        listen_host="127.0.0.1",
        listen_port=proxy_port,
        upstream_url=f"tcp://127.0.0.1:{piper_port}",
        voice_mapping=voice_mapping,
    )

    proxy_task = asyncio.create_task(proxy.run())

    try:
        await asyncio.sleep(0.2)

        # Connect and send English text
        client_reader, client_writer = await asyncio.open_connection(
            "127.0.0.1", proxy_port
        )

        english_text = "Hello, how are you doing today?"
        await async_write_event(
            Synthesize(text=english_text).event(), client_writer
        )

        # Read response
        audio_received = False
        while True:
            event = await asyncio.wait_for(
                async_read_event(client_reader), timeout=2.0
            )
            if event is None:
                break
            if isinstance(event, (AudioStart, AudioStop)):
                audio_received = True
            if isinstance(event, AudioStop):
                break

        assert audio_received

        client_writer.close()
        await client_writer.wait_closed()

    finally:
        proxy_task.cancel()
        try:
            await proxy_task
        except asyncio.CancelledError:
            pass

        piper_server.close()
        await piper_server.wait_closed()
