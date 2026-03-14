"""Configuration loader for Wyoming Polyglot Proxy."""

import json
from pathlib import Path


def load_config() -> dict:
    """Load configuration from /data/options.json (HA add-on standard)."""
    options_file = Path("/data/options.json")

    if options_file.exists():
        with options_file.open() as f:
            return json.load(f)

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
