"""Unit tests for configuration loading."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import load_config


@pytest.mark.unit
def test_load_config_from_file(tmp_path):
    """Test loading configuration from options.json file."""
    config_file = tmp_path / "options.json"
    config_data = {
        "whisper_url": "tcp://192.168.1.100:10300",
        "piper_url": "tcp://192.168.1.200:10200",
        "voice_mapping": {"en": "en_US-ryan", "es": "es_ES-carme"},
        "log_level": "debug",
    }
    config_file.write_text(json.dumps(config_data))

    with patch("src.config.Path") as mock_path:
        mock_path.return_value.exists.return_value = True
        mock_path.return_value.open.return_value.__enter__.return_value = config_file.open()

        config = load_config()

    assert config["whisper_url"] == "tcp://192.168.1.100:10300"
    assert config["piper_url"] == "tcp://192.168.1.200:10200"
    assert config["voice_mapping"]["en"] == "en_US-ryan"
    assert config["log_level"] == "debug"


@pytest.mark.unit
def test_load_config_file_missing():
    """Test configuration fallback when file is missing."""
    with patch("src.config.Path") as mock_path:
        mock_path.return_value.exists.return_value = False

        config = load_config()

    # Should return default configuration
    assert "whisper_url" in config
    assert "piper_url" in config
    assert "voice_mapping" in config
    assert "log_level" in config
    assert config["log_level"] == "info"


@pytest.mark.unit
def test_load_config_defaults():
    """Test default configuration values."""
    with patch("src.config.Path") as mock_path:
        mock_path.return_value.exists.return_value = False

        config = load_config()

    assert config["whisper_url"] == "tcp://localhost:10301"
    assert config["piper_url"] == "tcp://localhost:10201"
    assert "en" in config["voice_mapping"]
    assert "es" in config["voice_mapping"]
    assert "it" in config["voice_mapping"]


@pytest.mark.unit
def test_load_config_invalid_json(tmp_path):
    """Test error handling for invalid JSON."""
    config_file = tmp_path / "options.json"
    config_file.write_text("{invalid json content")

    with patch("src.config.Path") as mock_path:
        mock_path.return_value.exists.return_value = True
        mock_path.return_value.open.return_value.__enter__.return_value = config_file.open()

        with pytest.raises(json.JSONDecodeError):
            load_config()
