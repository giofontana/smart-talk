"""Wyoming Polyglot Proxy - Main entry point."""

import asyncio
import logging

from .config import load_config
from .stt_proxy import STTProxy
from .tts_proxy import TTSProxy

_LOGGER = logging.getLogger(__name__)


async def main():
    """Start both STT and TTS proxy servers."""
    # Load add-on configuration
    config = load_config()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config["log_level"].upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    _LOGGER.info("Starting Wyoming Polyglot Proxy")
    _LOGGER.info(f"Whisper upstream: {config['whisper_url']}")
    _LOGGER.info(f"Piper upstream: {config['piper_url']}")
    _LOGGER.info(f"Voice mapping: {len(config['voice_mapping'])} languages")

    # Create proxy instances
    stt_proxy = STTProxy(
        listen_host="0.0.0.0",
        listen_port=10300,
        upstream_url=config["whisper_url"],
    )

    tts_proxy = TTSProxy(
        listen_host="0.0.0.0",
        listen_port=10200,
        upstream_url=config["piper_url"],
        voice_mapping=config["voice_mapping"],
    )

    # Run both servers concurrently
    await asyncio.gather(stt_proxy.run(), tts_proxy.run())


if __name__ == "__main__":
    asyncio.run(main())
