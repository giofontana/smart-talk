"""Integration tests for STT proxy."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.stt_proxy import STTProxy


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stt_forwards_bidirectionally(mock_stream_reader, mock_stream_writer):
    """Test STT proxy forwards data in both directions."""
    proxy = STTProxy("127.0.0.1", 10300, "tcp://localhost:10301")

    # Mock data flowing through
    test_data_ha_to_whisper = b"audio_data_from_ha"
    test_data_whisper_to_ha = b"transcript_from_whisper"

    mock_stream_reader.read = AsyncMock(side_effect=[test_data_ha_to_whisper, b""])

    upstream_reader = AsyncMock()
    upstream_writer = AsyncMock()
    upstream_reader.read = AsyncMock(
        side_effect=[test_data_whisper_to_ha, b""]
    )

    with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = (upstream_reader, upstream_writer)

        await proxy._handle_client(mock_stream_reader, mock_stream_writer)

        # Verify connection was established
        mock_connect.assert_called_once()

        # Verify data was forwarded to Whisper
        assert upstream_writer.write.called

        # Verify writer was closed
        mock_stream_writer.close.assert_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stt_handles_connection_error(mock_stream_reader, mock_stream_writer):
    """Test STT proxy handles upstream connection errors gracefully."""
    proxy = STTProxy("127.0.0.1", 10300, "tcp://localhost:10301")

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
async def test_stt_closes_connections_properly(mock_stream_reader, mock_stream_writer):
    """Test STT proxy closes connections in finally block."""
    proxy = STTProxy("127.0.0.1", 10300, "tcp://localhost:10301")

    mock_stream_reader.read = AsyncMock(return_value=b"")

    upstream_reader = AsyncMock()
    upstream_writer = AsyncMock()
    upstream_reader.read = AsyncMock(return_value=b"")

    with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_connect:
        mock_connect.return_value = (upstream_reader, upstream_writer)

        await proxy._handle_client(mock_stream_reader, mock_stream_writer)

        # Verify connections were closed
        mock_stream_writer.close.assert_called()
        mock_stream_writer.wait_closed.assert_called()
