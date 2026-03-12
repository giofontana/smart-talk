"""Settings loader for Smart Talk AI Agent.

Loads configuration from a YAML file and/or environment variables.
Environment variables take precedence and use the prefix ``ST_``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_yaml() -> dict[str, Any]:
    """Load settings from the YAML config file if it exists."""
    config_path = Path(os.environ.get("SMART_TALK_CONFIG", "config.yaml"))
    if config_path.exists():
        with config_path.open() as fh:
            return yaml.safe_load(fh) or {}
    return {}


class Settings(BaseSettings):
    """Application settings resolved from YAML file then environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="ST_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "sk-no-key"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048

    # ── Home Assistant ────────────────────────────────────────────────────────
    ha_url: str = "http://homeassistant.local:8123"
    ha_token: str = ""
    ha_ssl_verify: bool = True

    # ── Server ────────────────────────────────────────────────────────────────
    server_host: str = "0.0.0.0"
    server_port: int = 8765
    log_level: str = "INFO"

    # ── Semantic search ───────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    similarity_threshold: float = 0.35
    device_refresh_interval: int = 300

    # ── Ambiguity detection ───────────────────────────────────────────────────
    # When ≥ ambiguity_min_matches candidates score above the threshold AND their
    # score spread (max − min) is below ambiguity_spread_threshold, the resolver
    # flags the result as ambiguous and the tool asks the user to clarify.
    ambiguity_spread_threshold: float = 0.08
    ambiguity_min_matches: int = 2

    # ── Translation ───────────────────────────────────────────────────────────
    # When enabled, entity friendly names and user queries are translated to
    # English before being stored in / searched against the embedding index.
    # This allows devices named in any language and users speaking any language
    # to work correctly with the semantic resolver.
    enable_translation: bool = True

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

    @classmethod
    def from_yaml_and_env(cls) -> "Settings":
        """Create a Settings instance, seeding defaults from the YAML file."""
        yaml_values = _load_yaml()
        return cls(**yaml_values)
