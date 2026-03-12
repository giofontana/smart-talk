"""HTTP conversation proxy — forwards HA conversation requests to the Smart Talk Agent via REST."""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path

from aiohttp import web, ClientSession, ClientTimeout, ClientConnectorError, ClientResponseError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [proxy] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("conversation_proxy")


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
        "agent_url": opts.get("agent_url") or os.environ.get(
            "AGENT_URL", "http://localhost:8765/conversation"
        ),
        "proxy_port": int(os.environ.get("PROXY_PORT", "8080")),
        "agent_timeout": float(os.environ.get("AGENT_TIMEOUT", "60")),
    }


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

async def handle_conversation(request: web.Request) -> web.Response:
    config: dict = request.app["config"]
    http_session: ClientSession = request.app["http_session"]

    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(reason="Invalid JSON body")

    session_id = body.get("session_id") or str(uuid.uuid4())
    text = (body.get("text") or "").strip()
    language = body.get("language", "en")

    if not text:
        raise web.HTTPBadRequest(reason="'text' field is required")

    logger.info("Conversation request session=%s text=%r", session_id, text[:80])

    agent_payload = {"session_id": session_id, "text": text, "language": language}
    timeout = ClientTimeout(total=config["agent_timeout"])

    try:
        async with http_session.post(
            config["agent_url"],
            json=agent_payload,
            timeout=timeout,
        ) as resp:
            resp.raise_for_status()
            result = await resp.json()

    except ClientConnectorError as exc:
        logger.error("Cannot connect to Smart Talk Agent at %s: %s", config["agent_url"], exc)
        raise web.HTTPBadGateway(reason=f"Cannot connect to Smart Talk Agent: {exc}")
    except ClientResponseError as exc:
        logger.error("Smart Talk Agent returned HTTP %d: %s", exc.status, exc.message)
        raise web.HTTPBadGateway(reason=f"Agent returned HTTP {exc.status}")
    except Exception as exc:
        logger.exception("Unexpected error forwarding to agent: %s", exc)
        raise web.HTTPInternalServerError(reason="Proxy internal error")

    response_text = result.get("text", "")
    response_language = result.get("language", language)

    logger.info("Conversation response session=%s text=%r", session_id, response_text[:80])
    return web.json_response({"text": response_text, "language": response_language})


async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

async def on_startup(app: web.Application) -> None:
    app["http_session"] = ClientSession()
    logger.info(
        "Conversation proxy started — forwarding to %s", app["config"]["agent_url"]
    )


async def on_cleanup(app: web.Application) -> None:
    session: ClientSession = app["http_session"]
    await session.close()
    logger.info("Conversation proxy stopped")


def build_app(config: dict) -> web.Application:
    app = web.Application()
    app["config"] = config
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_post("/conversation", handle_conversation)
    app.router.add_get("/health", handle_health)
    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    config = _get_config()
    logger.info(
        "Conversation proxy config: agent_url=%s port=%d",
        config["agent_url"],
        config["proxy_port"],
    )
    app = build_app(config)
    web.run_app(app, host="0.0.0.0", port=config["proxy_port"], access_log=logger)


if __name__ == "__main__":
    main()
