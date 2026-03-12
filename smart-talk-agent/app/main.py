"""Smart Talk AI Agent — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException

from app.agent.core import SmartTalkAgent
from app.agent.tools.registry import ToolRegistry
from app.config import Settings
from app.ha.client import HAClient
from app.search.device_resolver import DeviceResolver
from app.translation.service import TranslationService
from app.ws.server import ConversationRequest, ConversationResponse

# ── Application state (populated during lifespan) ─────────────────────────────

settings: Settings
ha_client: HAClient
device_resolver: DeviceResolver
tool_registry: ToolRegistry
agent: SmartTalkAgent


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start and stop all application resources."""
    global settings, ha_client, device_resolver, tool_registry, agent

    settings = Settings.from_yaml_and_env()

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Smart Talk AI Agent starting…")

    ha_client = HAClient(
        url=settings.ha_url,
        token=settings.ha_token,
        ssl_verify=settings.ha_ssl_verify,
    )
    await ha_client.__aenter__()

    translation_service: TranslationService | None = None
    if settings.enable_translation:
        translation_service = TranslationService(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
        logger.info("Translation service enabled (model=%s)", settings.llm_model)
    else:
        logger.info("Translation service disabled")

    device_resolver = DeviceResolver(
        ha_client=ha_client,
        embedding_model=settings.embedding_model,
        similarity_threshold=settings.similarity_threshold,
        refresh_interval=settings.device_refresh_interval,
        ambiguity_spread_threshold=settings.ambiguity_spread_threshold,
        ambiguity_min_matches=settings.ambiguity_min_matches,
        translation_service=translation_service,
    )
    await device_resolver.start()

    tool_registry = ToolRegistry.build_default_tools(ha_client, device_resolver)
    agent = SmartTalkAgent(settings, ha_client, device_resolver, tool_registry)

    logger.info("Smart Talk AI Agent ready on %s:%d", settings.server_host, settings.server_port)

    yield  # application runs here

    logger.info("Smart Talk AI Agent shutting down…")
    await device_resolver.stop()
    await ha_client.__aexit__(None, None, None)


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Smart Talk AI Agent",
    description="Conversational AI agent for Home Assistant.",
    version="1.0.0",
    lifespan=lifespan,
)

logger = logging.getLogger(__name__)


# ── HTTP endpoints ────────────────────────────────────────────────────────────

@app.get(
    "/health",
    tags=["Health"],
    summary="Liveness probe",
    description=(
        "Returns the service health status and whether the Home Assistant "
        "connection is currently active. Safe to call at any time."
    ),
    responses={
        200: {
            "description": "Service is up. `ha_connected` reflects live HA reachability.",
            "content": {
                "application/json": {
                    "example": {"status": "ok", "ha_connected": True}
                }
            },
        }
    },
)
async def health() -> dict:
    """Liveness probe — returns HA connectivity status."""
    ha_connected = await ha_client.ping()
    return {"status": "ok", "ha_connected": ha_connected}


@app.get(
    "/entities",
    tags=["Entities"],
    summary="List cached entities",
    description=(
        "Returns all Home Assistant entities currently held in the device "
        "resolver's in-memory index. Useful for debugging semantic search "
        "coverage without querying HA directly."
    ),
    responses={
        200: {
            "description": "Flat list of cached entity summaries.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "entity_id": "light.kitchen_light",
                            "friendly_name": "Kitchen Light",
                            "domain": "light",
                            "state": "off",
                        }
                    ]
                }
            },
        }
    },
)
async def entities() -> list[dict]:
    """Return all entities currently in the device resolver cache (for debugging)."""
    return [
        {
            "entity_id": e.entity_id,
            "friendly_name": e.friendly_name,
            "domain": e.domain,
            "state": e.state,
        }
        for e in device_resolver.cached_entities
    ]


@app.post(
    "/conversation",
    response_model=ConversationResponse,
    tags=["Conversation"],
    summary="Send a conversational message to the AI agent",
    description=(
        "Accepts a natural-language message from the user and returns the "
        "agent's response. The agent uses semantic device resolution and "
        "LangChain tools to carry out Home Assistant actions when requested.\n\n"
        "Session history is maintained in memory keyed by `session_id`; "
        "use a stable identifier (e.g. the HA conversation ID) to preserve "
        "multi-turn context."
    ),
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "turn_on_light": {
                            "summary": "Turn on a light with brightness",
                            "value": {
                                "session_id": "session-abc123",
                                "text": "Turn on the kitchen light at 70% brightness.",
                                "language": "en",
                            },
                        },
                        "query_sensor": {
                            "summary": "Read a sensor value",
                            "value": {
                                "session_id": "session-abc123",
                                "text": "What is the outdoor temperature?",
                                "language": "en",
                            },
                        },
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "Agent replied successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "session-abc123",
                        "text": "Done! Kitchen Light is now on at 70% brightness.",
                        "language": "en",
                    }
                }
            },
        },
        422: {"description": "Request body validation error."},
        500: {"description": "Internal agent or LLM error."},
    },
)
async def conversation(request: ConversationRequest) -> ConversationResponse:
    """Process a natural language message and return the agent's response.

    This is the primary endpoint called by the Smart Talk HA Add-on's
    conversation proxy.
    """
    logger.info(
        "Conversation request session=%s lang=%s text=%r",
        request.session_id,
        request.language,
        request.text[:80],
    )
    try:
        reply_text = await agent.chat(request.session_id, request.text)
    except Exception as exc:
        logger.error(
            "Agent error for session=%s: %s", request.session_id, exc, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal agent error") from exc

    logger.info(
        "Conversation response session=%s text=%r", request.session_id, reply_text[:80]
    )
    return ConversationResponse(
        session_id=request.session_id,
        text=reply_text,
        language=request.language,
    )


# ── Dev launcher ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _settings = Settings.from_yaml_and_env()
    uvicorn.run(
        "app.main:app",
        host=_settings.server_host,
        port=_settings.server_port,
        log_level=_settings.log_level.lower(),
        reload=False,
    )
