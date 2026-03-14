"""Integration tests for TTS proxy."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from wyoming.tts import Synthesize
from wyoming.audio import AudioStart

from src.tts_proxy import TTSProxy


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_detects_language_from_synthesize(
    voice_mapping, mock_stream_reader, mock_stream_writer
):
    """Test TTS proxy detects language from Synthesize event."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    # Create Spanish synthesize event
    spanish_text = "Hola, ¿cómo estás hoy?"
    synthesize_event = Synthesize(text=spanish_text)
    event_json = json.dumps(synthesize_event.event()) + "\n"

    # Mock reading the event
    mock_stream_reader.read = AsyncMock(side_effect=[event_json.encode(), b""])

    # Mock upstream connection
    upstream_reader = AsyncMock()
    upstream_writer = AsyncMock()
    upstream_reader.read = AsyncMock(return_value=b"")

    with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = (upstream_reader, upstream_writer)

        # Patch async_read_event to return our event
        with patch("src.tts_proxy.async_read_event") as mock_read:
            mock_read.side_effect = [synthesize_event, None]

            # Patch async_write_event to capture written events
            written_events = []

            async def capture_write(event, writer):
                written_events.append(event)

            with patch("src.tts_proxy.async_write_event", side_effect=capture_write):
                await proxy._handle_client(mock_stream_reader, mock_stream_writer)

            # Verify voice was injected
            assert len(written_events) > 0
            first_event = written_events[0]
            assert "data" in first_event
            assert "voice" in first_event["data"]
            assert first_event["data"]["voice"]["name"] == "es_ES-mls-medium"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_forwards_non_synthesize_unchanged(
    voice_mapping, mock_stream_reader, mock_stream_writer
):
    """Test TTS proxy forwards non-Synthesize events unchanged."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    # Create a non-Synthesize event (AudioStart)
    audio_start_event = AudioStart(rate=22050, width=2, channels=1)

    # Mock upstream connection
    upstream_reader = AsyncMock()
    upstream_writer = AsyncMock()
    upstream_reader.read = AsyncMock(return_value=b"")

    with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = (upstream_reader, upstream_writer)

        # Patch async_read_event to return our event
        with patch("src.tts_proxy.async_read_event") as mock_read:
            mock_read.side_effect = [audio_start_event, None]

            # Patch async_write_event to capture written events
            written_events = []

            async def capture_write(event, writer):
                written_events.append(event)

            with patch("src.tts_proxy.async_write_event", side_effect=capture_write):
                await proxy._handle_client(mock_stream_reader, mock_stream_writer)

            # Verify event was forwarded unchanged (no voice injection)
            assert len(written_events) > 0
            first_event = written_events[0]
            # AudioStart events don't have voice field
            if "data" in first_event:
                assert "voice" not in first_event.get("data", {})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_handles_connection_error(
    voice_mapping, mock_stream_reader, mock_stream_writer
):
    """Test TTS proxy handles upstream connection errors gracefully."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    with patch(
        "asyncio.open_connection",
        new_callable=AsyncMock,
        side_effect=ConnectionRefusedError("Connection refused"),
    ):
        # Should not raise exception
        await proxy._handle_client(mock_stream_reader, mock_stream_writer)

        # Connection should be closed
        mock_stream_writer.close.assert_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_english_voice_selection(voice_mapping):
    """Test TTS proxy selects English voice for English text."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    # Use longer, more distinctive English text for reliable detection
    text = "Good morning! How are you doing today? I hope everything is going well."
    language = proxy._detect_language(text)
    voice = proxy._select_voice(language)

    assert language == "en"
    assert voice == "en_US-lessac-medium"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_italian_voice_selection(voice_mapping):
    """Test TTS proxy selects Italian voice for Italian text."""
    proxy = TTSProxy("127.0.0.1", 10200, "tcp://localhost:10201", voice_mapping)

    text = "Ciao, come stai oggi?"
    language = proxy._detect_language(text)
    voice = proxy._select_voice(language)

    assert language == "it"
    assert voice == "it_IT-riccardo-x_low"
