"""Wyoming TTS server powered by piper-tts."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import struct
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [tts] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("tts_server")

PIPER_VOICES_BASE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
)

# Audio constants for piper output (22050 Hz, 16-bit mono)
PIPER_SAMPLE_RATE = 22050
PIPER_SAMPLE_WIDTH = 2
PIPER_CHANNELS = 1

# Chunk size when streaming audio back (0.5 s worth of samples)
AUDIO_CHUNK_SAMPLES = PIPER_SAMPLE_RATE // 2


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
        "tts_voice": opts.get("tts_voice") or os.environ.get("TTS_VOICE", "en_US-lessac-medium"),
        "tts_language": opts.get("tts_language") or os.environ.get("TTS_LANGUAGE", "en"),
        "tts_port": int(os.environ.get("TTS_PORT", "10301")),
        "piper_model_dir": os.environ.get("PIPER_MODEL_DIR", "/share/smart_talk/piper_models"),
    }


# ---------------------------------------------------------------------------
# Voice model management
# ---------------------------------------------------------------------------

def _voice_to_path_parts(voice_name: str) -> tuple[str, str, str, str]:
    """Convert 'en_US-lessac-medium' → ('en', 'en_US', 'lessac', 'medium').

    Piper voices repo (v1.0.0) uses the structure:
      {lang}/{lang_region}/{speaker}/{quality}/{voice_name}.onnx
    """
    parts = voice_name.split("-")
    lang_region = parts[0]            # e.g. en_US
    lang = lang_region.split("_")[0]  # e.g. en
    speaker = parts[1] if len(parts) > 1 else "default"
    quality = parts[2] if len(parts) > 2 else "medium"
    return lang, lang_region, speaker, quality


def _ensure_voice_model(model_dir: str, voice_name: str) -> Path:
    """Return path to .onnx file, downloading if necessary."""
    model_path = Path(model_dir)
    model_path.mkdir(parents=True, exist_ok=True)

    onnx_file = model_path / f"{voice_name}.onnx"
    config_file = model_path / f"{voice_name}.onnx.json"

    if onnx_file.exists() and config_file.exists():
        logger.debug("Voice model already present: %s", onnx_file)
        return onnx_file

    lang, lang_region, speaker, quality = _voice_to_path_parts(voice_name)

    for fname in [f"{voice_name}.onnx", f"{voice_name}.onnx.json"]:
        url = f"{PIPER_VOICES_BASE_URL}/{lang}/{lang_region}/{speaker}/{quality}/{fname}"
        dest = model_path / fname
        logger.info("Downloading piper voice file: %s → %s", url, dest)
        try:
            urllib.request.urlretrieve(url, dest)  # noqa: S310
        except Exception as exc:
            raise RuntimeError(
                f"Failed to download piper voice {fname} from {url}: {exc}"
            ) from exc

    logger.info("Piper voice model ready: %s", onnx_file)
    return onnx_file


# ---------------------------------------------------------------------------
# Wyoming protocol helpers
# ---------------------------------------------------------------------------

async def _send_event(writer: asyncio.StreamWriter, event_type: str, data: dict) -> None:
    payload = json.dumps({"type": event_type, "data": data}) + "\n"
    writer.write(payload.encode())
    await writer.drain()


async def _read_event(reader: asyncio.StreamReader) -> tuple[str, dict]:
    """Read one Wyoming event line. TTS requests carry no binary payload."""
    line = await reader.readline()
    if not line:
        return "", {}
    try:
        msg = json.loads(line.decode().strip())
    except json.JSONDecodeError as exc:
        logger.warning("Invalid JSON line: %s — %s", line, exc)
        return "", {}
    return msg.get("type", ""), msg.get("data", {})


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _read_wav_pcm(wav_bytes: bytes) -> bytes:
    """Strip WAV header and return raw PCM bytes."""
    buf = io.BytesIO(wav_bytes)
    # Minimal WAV parsing: skip RIFF header to find 'data' chunk
    buf.seek(12)  # skip RIFF + filesize + WAVE
    while True:
        chunk_id = buf.read(4)
        if len(chunk_id) < 4:
            break
        (chunk_size,) = struct.unpack("<I", buf.read(4))
        if chunk_id == b"data":
            return buf.read(chunk_size)
        buf.seek(chunk_size, 1)
    return wav_bytes  # fallback: return as-is


def _chunk_pcm(pcm: bytes, chunk_samples: int, sample_width: int) -> list[bytes]:
    chunk_bytes = chunk_samples * sample_width
    return [pcm[i: i + chunk_bytes] for i in range(0, len(pcm), chunk_bytes)]


# ---------------------------------------------------------------------------
# TTS synthesis
# ---------------------------------------------------------------------------

def _synthesize_sync(text: str, onnx_path: Path, config_path: Path) -> bytes:
    """Blocking piper synthesis. Returns raw WAV bytes."""
    from piper import PiperVoice  # noqa: PLC0415

    voice = PiperVoice.load(str(onnx_path), config_path=str(config_path))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        voice.synthesize(text, wav_file)
    return buf.getvalue()


# Import wave at module level for the above function
import wave  # noqa: E402


# ---------------------------------------------------------------------------
# TTS server
# ---------------------------------------------------------------------------

class WyomingTTSServer:
    def __init__(self, config: dict) -> None:
        self.config = config
        self._onnx_path: Path | None = None
        self._model_lock = asyncio.Lock()

    async def _get_model_path(self) -> Path:
        async with self._model_lock:
            if self._onnx_path is None:
                voice = self.config["tts_voice"]
                loop = asyncio.get_event_loop()
                self._onnx_path = await loop.run_in_executor(
                    None,
                    _ensure_voice_model,
                    self.config["piper_model_dir"],
                    voice,
                )
        return self._onnx_path

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        logger.info("TTS client connected: %s", peer)
        try:
            while True:
                event_type, data = await _read_event(reader)
                if not event_type:
                    break

                if event_type == "synthesize":
                    text = data.get("text", "").strip()
                    voice_info = data.get("voice", {})
                    voice_name = (
                        voice_info.get("name")
                        or self.config["tts_voice"]
                    )
                    logger.info("Synthesizing %d chars with voice %r", len(text), voice_name)

                    if not text:
                        await _send_event(writer, "audio-start", {
                            "rate": PIPER_SAMPLE_RATE,
                            "width": PIPER_SAMPLE_WIDTH,
                            "channels": PIPER_CHANNELS,
                        })
                        await _send_event(writer, "audio-stop", {})
                        continue

                    await self._synthesize_and_stream(writer, text, voice_name)

                else:
                    logger.debug("Ignoring unknown TTS event: %s", event_type)

        except asyncio.IncompleteReadError:
            logger.debug("TTS client %s disconnected", peer)
        except Exception as exc:
            logger.exception("Error handling TTS client %s: %s", peer, exc)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.info("TTS client disconnected: %s", peer)

    async def _synthesize_and_stream(
        self,
        writer: asyncio.StreamWriter,
        text: str,
        voice_name: str,
    ) -> None:
        onnx_path = await self._get_model_path()
        config_path = onnx_path.with_suffix(".onnx.json")

        loop = asyncio.get_event_loop()
        try:
            wav_bytes = await loop.run_in_executor(
                None,
                _synthesize_sync,
                text,
                onnx_path,
                config_path,
            )
        except Exception as exc:
            logger.error("Piper synthesis failed: %s", exc)
            await _send_event(writer, "audio-start", {
                "rate": PIPER_SAMPLE_RATE,
                "width": PIPER_SAMPLE_WIDTH,
                "channels": PIPER_CHANNELS,
            })
            await _send_event(writer, "audio-stop", {})
            return

        pcm = _read_wav_pcm(wav_bytes)
        chunks = _chunk_pcm(pcm, AUDIO_CHUNK_SAMPLES, PIPER_SAMPLE_WIDTH)

        await _send_event(writer, "audio-start", {
            "rate": PIPER_SAMPLE_RATE,
            "width": PIPER_SAMPLE_WIDTH,
            "channels": PIPER_CHANNELS,
        })

        for chunk in chunks:
            encoded = base64.b64encode(chunk).decode()
            await _send_event(writer, "audio-chunk", {
                "rate": PIPER_SAMPLE_RATE,
                "width": PIPER_SAMPLE_WIDTH,
                "channels": PIPER_CHANNELS,
                "audio": encoded,
            })

        await _send_event(writer, "audio-stop", {})
        logger.info("TTS stream complete — %d chunks sent", len(chunks))

    async def start(self) -> None:
        host = "0.0.0.0"
        port = self.config["tts_port"]
        server = await asyncio.start_server(self.handle_client, host, port)
        logger.info("Wyoming TTS server listening on %s:%d", host, port)
        async with server:
            await server.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    config = _get_config()
    logger.info(
        "TTS config: voice=%s language=%s port=%d",
        config["tts_voice"],
        config["tts_language"],
        config["tts_port"],
    )
    server = WyomingTTSServer(config)
    # Pre-download voice model at startup
    try:
        await server._get_model_path()
    except Exception as exc:
        logger.error("Failed to pre-load TTS voice model: %s", exc)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
