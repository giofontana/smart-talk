"""Configuration loader for Wyoming Polyglot Proxy."""

import json
from pathlib import Path


def _parse_voice_mapping(raw: list[str] | dict) -> dict[str, str]:
    """Convert voice_mapping from HA list format (['en:voice', ...]) to dict."""
    if isinstance(raw, dict):
        return raw
    result = {}
    for entry in raw:
        if ":" in entry:
            lang, voice = entry.split(":", 1)
            result[lang.strip()] = voice.strip()
    return result


def load_config() -> dict:
    """Load configuration from /data/options.json (HA add-on standard)."""
    options_file = Path("/data/options.json")

    if options_file.exists():
        with options_file.open() as f:
            config = json.load(f)
        config["voice_mapping"] = _parse_voice_mapping(config.get("voice_mapping", []))
        return config

    # Fallback for development/testing
    return {
        "whisper_url": "tcp://localhost:10301",
        "piper_url": "tcp://localhost:10201",
        "voice_mapping": {
            "en": "en_US-lessac-medium",
            "es": "es_ES-mls-medium",
            "it": "it_IT-riccardo-x_low",
        },
        "log_level": "info",
    }
