"""Wyoming STT server powered by faster-whisper."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import os
import tempfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [stt] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("stt_server")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_options() -> dict:
    options_path = Path("/data/options.json")
    if options_path.exists():
        try:
            with options_path.open() as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Could not read /data/options.json: %s", exc)
    return {}


def _get_config() -> dict:
    opts = _load_options()
    return {
        "stt_model": opts.get("stt_model") or os.environ.get("STT_MODEL", "tiny"),
        "stt_language": opts.get("stt_language") or os.environ.get("STT_LANGUAGE", "auto"),
        "stt_port": int(os.environ.get("STT_PORT", "10300")),
        "whisper_model_dir": os.environ.get("WHISPER_MODEL_DIR", "/share/smart_talk/whisper_models"),
    }


# ---------------------------------------------------------------------------
# Wyoming protocol helpers
# ---------------------------------------------------------------------------

async def _send_event(writer: asyncio.StreamWriter, event_type: str, data: dict) -> None:
    payload = json.dumps({"type": event_type, "data": data}) + "\n"
    writer.write(payload.encode())
    await writer.drain()


async def _read_event(reader: asyncio.StreamReader) -> tuple[str, dict, bytes]:
    """Read one Wyoming event line + optional binary payload.

    Returns (event_type, data_dict, binary_payload).
    """
    line = await reader.readline()
    if not line:
        return "", {}, b""
    try:
        msg = json.loads(line.decode().strip())
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON line: %s — %s", line, exc)
        return "", {}, b""

    event_type = msg.get("type", "")
    data = msg.get("data", {})

    # Read binary payload when present (audio-chunk carries raw PCM)
    payload = b""
    payload_length = data.get("payload_length") or data.get("samples")
    if payload_length:
        payload = await reader.readexactly(int(payload_length))

    return event_type, data, payload


# ---------------------------------------------------------------------------
# STT server
# ---------------------------------------------------------------------------

class WyomingSTTServer:
    def __init__(self, config: dict) -> None:
        self.config = config
        self._model = None
        self._model_lock = asyncio.Lock()

    async def _get_model(self):
        async with self._model_lock:
            if self._model is None:
                logger.info(
                    "Loading Whisper model '%s' (this may take a moment)…",
                    self.config["stt_model"],
                )
                loop = asyncio.get_event_loop()
                self._model = await loop.run_in_executor(
                    None, self._load_model
                )
                logger.info("Whisper model loaded.")
        return self._model

    def _load_model(self):
        from faster_whisper import WhisperModel  # noqa: PLC0415

        return WhisperModel(
            self.config["stt_model"],
            device="cpu",
            download_root=self.config["whisper_model_dir"],
        )

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        logger.info("STT client connected: %s", peer)
        audio_buffer = io.BytesIO()
        audio_params: dict = {}

        try:
            while True:
                event_type, data, payload = await _read_event(reader)

                if not event_type:
                    break

                if event_type == "audio-start":
                    audio_buffer = io.BytesIO()
                    audio_params = data
                    logger.debug("audio-start: %s", audio_params)

                elif event_type == "audio-chunk":
                    if payload:
                        audio_buffer.write(payload)
                    logger.debug("audio-chunk: %d bytes buffered", len(payload))

                elif event_type == "audio-stop":
                    logger.info("audio-stop — transcribing %d bytes…", audio_buffer.tell())
                    text = await self._transcribe(audio_buffer, audio_params)
                    language = (
                        self.config["stt_language"]
                        if self.config["stt_language"] != "auto"
                        else "en"
                    )
                    await _send_event(
                        writer,
                        "transcript",
                        {"text": text, "language": language},
                    )
                    logger.info("Transcript sent: %r", text)
                    # Reset for potential next utterance on same connection
                    audio_buffer = io.BytesIO()

                else:
                    logger.debug("Ignoring unknown event: %s", event_type)

        except asyncio.IncompleteReadError:
            logger.debug("Client %s disconnected mid-stream", peer)
        except Exception as exc:
            logger.exception("Error handling STT client %s: %s", peer, exc)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("STT client disconnected: %s", peer)

    async def _transcribe(self, audio_buffer: io.BytesIO, audio_params: dict) -> str:
        audio_buffer.seek(0)
        raw_bytes = audio_buffer.read()
        if not raw_bytes:
            return ""

        language = self.config["stt_language"]
        if language == "auto":
            language = None

        loop = asyncio.get_event_loop()
        try:
            model = await self._get_model()

            # Write to a named temp file so ffmpeg can detect the format from
            # the .wav extension. Passing io.BytesIO directly causes ffmpeg to
            # see '<none>' as the input name and fail with AVERROR_INVALIDDATA.
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(raw_bytes)
                tmp_path = tmp.name

            try:
                segments, info = await loop.run_in_executor(
                    None,
                    lambda: model.transcribe(
                        tmp_path,
                        language=language,
                        beam_size=5,
                    ),
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
                logger.debug(
                    "Transcription done — detected language: %s (prob=%.2f)",
                    info.language,
                    info.language_probability,
                )
                return text
            finally:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)

        except Exception as exc:
            logger.error("Transcription failed: %s", exc)
            return ""

    async def start(self) -> None:
        host = "0.0.0.0"
        port = self.config["stt_port"]
        server = await asyncio.start_server(self.handle_client, host, port)
        logger.info("Wyoming STT server listening on %s:%d", host, port)
        async with server:
            await server.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    config = _get_config()
    logger.info("STT config: model=%s language=%s port=%d",
                config["stt_model"], config["stt_language"], config["stt_port"])
    server = WyomingSTTServer(config)
    # Eagerly load the model at startup so first request is fast
    try:
        await server._get_model()
    except Exception as exc:
        logger.error("Failed to pre-load Whisper model: %s", exc)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
