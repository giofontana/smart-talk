"""Async Home Assistant WebSocket API client.

Uses the HA WebSocket API (``ws://host:8123/api/websocket``) for all
communication with Home Assistant.  A persistent connection is maintained and
automatically re-established on disconnect.
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from itertools import count
from types import TracebackType
from typing import Any

import websockets
from websockets.connection import State
from websockets.exceptions import ConnectionClosed

from app.ha.models import HAEntity

logger = logging.getLogger(__name__)

_RECONNECT_DELAYS = [1, 2, 5, 10, 30]  # seconds between reconnect attempts


class HAError(Exception):
    """Raised when HA returns a non-successful result."""


class HAClient:
    """Persistent HA WebSocket API client.

    Connects to ``ws(s)://ha_host/api/websocket``, authenticates with a
    long-lived access token, and exposes high-level coroutines that mirror
    the old REST interface so the rest of the codebase is unaffected.

    Usage::

        async with HAClient(url, token) as client:
            states = await client.get_states()
    """

    def __init__(self, url: str, token: str, ssl_verify: bool = True) -> None:
        # Convert http(s):// base URL to ws(s)://…/api/websocket
        ws_url = url.rstrip("/")
        if ws_url.startswith("https://"):
            ws_url = "wss://" + ws_url[len("https://"):]
        elif ws_url.startswith("http://"):
            ws_url = "ws://" + ws_url[len("http://"):]
        self._ws_url = ws_url + "/api/websocket"
        self._token = token
        self._ssl_verify = ssl_verify

        self._ws: websockets.WebSocketClientProtocol | None = None
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._id_counter = count(1)
        self._listener_task: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()
        self._closing = False

    # ── Context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> "HAClient":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.disconnect()

    # ── Connection management ─────────────────────────────────────────────────

    async def connect(self) -> None:
        """Connect and authenticate; start the background listener."""
        self._closing = False
        await self._do_connect()
        self._listener_task = asyncio.create_task(
            self._reconnect_loop(), name="ha-ws-listener"
        )

    async def disconnect(self) -> None:
        """Close the WebSocket connection and stop the listener task."""
        self._closing = True
        self._connected.clear()
        if self._ws:
            await self._ws.close()
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        # Reject all pending futures
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(HAError("Client disconnected"))
        self._pending.clear()
        logger.info("HAClient disconnected")

    async def _do_connect(self) -> None:
        """Open the WebSocket and perform the auth handshake."""
        ssl_ctx: ssl.SSLContext | bool = True
        if not self._ssl_verify:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        logger.info("Connecting to HA WebSocket at %s", self._ws_url)
        self._ws = await websockets.connect(
            self._ws_url,
            ssl=ssl_ctx if self._ws_url.startswith("wss://") else None,
            ping_interval=30,
            ping_timeout=10,
        )

        # ── Auth handshake ──────────────────────────────────────────────────
        msg = json.loads(await self._ws.recv())
        if msg.get("type") != "auth_required":
            raise HAError(f"Unexpected first message: {msg}")

        await self._ws.send(json.dumps({"type": "auth", "access_token": self._token}))
        msg = json.loads(await self._ws.recv())

        if msg.get("type") == "auth_invalid":
            raise HAError("HA authentication failed: invalid token")
        if msg.get("type") != "auth_ok":
            raise HAError(f"Unexpected auth response: {msg}")

        logger.info("HA WebSocket authenticated (ha_version=%s)", msg.get("ha_version", "?"))
        self._connected.set()

    async def _reconnect_loop(self) -> None:
        """Continuously read messages; reconnect on disconnect."""
        delay_iter = iter(_RECONNECT_DELAYS)
        while not self._closing:
            try:
                await self._listen()
            except (ConnectionClosed, OSError) as exc:
                if self._closing:
                    break
                logger.warning("HA WebSocket disconnected: %s", exc)
                self._connected.clear()
                # Reject pending futures so callers don't hang
                for fut in list(self._pending.values()):
                    if not fut.done():
                        fut.set_exception(HAError(f"Connection lost: {exc}"))
                self._pending.clear()

                delay = next(delay_iter, _RECONNECT_DELAYS[-1])
                logger.info("Reconnecting in %ds…", delay)
                await asyncio.sleep(delay)
                try:
                    await self._do_connect()
                    delay_iter = iter(_RECONNECT_DELAYS)  # reset backoff
                except Exception as reconn_err:
                    logger.error("Reconnect failed: %s", reconn_err)

    async def _listen(self) -> None:
        """Read messages from the WebSocket and resolve pending futures."""
        assert self._ws is not None
        async for raw in self._ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Non-JSON WS message from HA: %s", raw)
                continue

            msg_type = msg.get("type")

            if msg_type == "result":
                msg_id = msg.get("id")
                fut = self._pending.pop(msg_id, None)
                if fut and not fut.done():
                    if msg.get("success"):
                        fut.set_result(msg.get("result"))
                    else:
                        error = msg.get("error", {})
                        fut.set_exception(
                            HAError(f"HA error {error.get('code')}: {error.get('message')}")
                        )
            elif msg_type == "event":
                pass  # subscription events — not used by tools yet

    # ── Internal command helper ───────────────────────────────────────────────

    async def _send_command(self, cmd_type: str, timeout: float = 15.0, **kwargs: Any) -> Any:
        """Send a command and wait for the matching result message.

        Args:
            cmd_type: HA WS message type (e.g. ``get_states``, ``call_service``).
            timeout:  Seconds to wait for the response.
            **kwargs: Additional fields merged into the command payload.

        Returns:
            The ``result`` value from the HA response.

        Raises:
            HAError: If HA returns an error or the connection is lost.
            asyncio.TimeoutError: If no response within *timeout* seconds.
        """
        await asyncio.wait_for(self._connected.wait(), timeout=timeout)
        assert self._ws is not None

        msg_id = next(self._id_counter)
        payload = {"id": msg_id, "type": cmd_type, **kwargs}
        fut: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = fut
        await self._ws.send(json.dumps(payload))
        return await asyncio.wait_for(fut, timeout=timeout)

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_states(self) -> list[HAEntity]:
        """Return all entity states from HA."""
        result = await self._send_command("get_states")
        return [HAEntity(**item) for item in result]

    async def get_state(self, entity_id: str) -> HAEntity:
        """Return the current state for a single entity.

        Args:
            entity_id: Full HA entity_id (e.g. ``light.living_room``).
        """
        states = await self.get_states()
        for entity in states:
            if entity.entity_id == entity_id:
                return entity
        raise HAError(f"Entity not found: {entity_id}")

    async def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str | None = None,
        **data: Any,
    ) -> dict[str, Any]:
        """Call a Home Assistant service.

        Args:
            domain:    Service domain (e.g. ``light``).
            service:   Service name (e.g. ``turn_on``).
            entity_id: Target entity; added to ``target`` when provided.
            **data:    Additional service data fields.

        Returns:
            Parsed result from HA (often an empty dict or list of states).
        """
        kwargs: dict[str, Any] = {
            "domain": domain,
            "service": service,
        }
        if data:
            kwargs["service_data"] = data
        if entity_id:
            kwargs["target"] = {"entity_id": entity_id}

        result = await self._send_command("call_service", **kwargs)
        return result or {}

    async def get_services(self) -> dict[str, Any]:
        """Return all available HA services grouped by domain."""
        return await self._send_command("get_services") or {}

    async def fire_event(
        self,
        event_type: str,
        event_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fire a custom HA event.

        Args:
            event_type: Event type string.
            event_data: Optional payload for the event.
        """
        result = await self._send_command(
            "fire_event",
            event_type=event_type,
            event_data=event_data or {},
        )
        return result or {}

    async def ping(self) -> bool:
        """Check whether the HA WebSocket connection is authenticated.

        Returns:
            ``True`` if connected and authenticated, ``False`` otherwise.
        """
        return self._connected.is_set() and self._ws is not None and self._ws.state == State.OPEN
