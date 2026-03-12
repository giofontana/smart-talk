"""Core LangChain agent for Smart Talk."""

from __future__ import annotations

import logging

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from app.agent.prompts import build_prompt
from app.agent.tools.registry import ToolRegistry
from app.config import Settings
from app.ha.client import HAClient
from app.search.device_resolver import DeviceResolver

logger = logging.getLogger(__name__)


class SmartTalkAgent:
    """LangChain-powered conversational agent for Smart Talk.

    Uses LangChain 1.x ``create_agent`` (LangGraph-backed) with an in-memory
    checkpointer so each ``session_id`` gets isolated conversation history.

    Args:
        settings:        Application settings.
        ha_client:       Initialised HA WebSocket client.
        device_resolver: Initialised semantic device resolver.
        tool_registry:   Populated tool registry.
    """

    def __init__(
        self,
        settings: Settings,
        ha_client: HAClient,
        device_resolver: DeviceResolver,
        tool_registry: ToolRegistry,
    ) -> None:
        self._settings = settings

        llm = ChatOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,  # type: ignore[arg-type]
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

        system_prompt = build_prompt()
        tools = tool_registry.get_tools()

        # MemorySaver keeps per-thread (session) history in-process.
        self._checkpointer = MemorySaver()
        self._agent = create_agent(
            llm,
            tools=tools,
            system_prompt=system_prompt,
            checkpointer=self._checkpointer,
        )

        # Track known session IDs for monitoring
        self._sessions: set[str] = set()

    # ── Public API ────────────────────────────────────────────────────────────

    async def chat(self, session_id: str, message: str) -> str:
        """Process a user message and return the agent's reply.

        Args:
            session_id: Opaque identifier for the conversation session.
                        Used as LangGraph ``thread_id`` so each session has
                        its own isolated conversation history.
            message:    The user's natural-language input.

        Returns:
            Agent response string.
        """
        self._sessions.add(session_id)
        config = {"configurable": {"thread_id": session_id}}

        logger.info("session=%s user=%r", session_id, message)
        try:
            result = await self._agent.ainvoke(
                {"messages": [("human", message)]},
                config=config,
            )
            # result["messages"] is a list of BaseMessage; last is the AI reply
            messages = result.get("messages", [])
            response = messages[-1].content if messages else ""
            logger.info("session=%s agent=%r", session_id, str(response)[:120])
            return str(response)
        except Exception as exc:
            logger.error("session=%s agent error: %s", session_id, exc, exc_info=True)
            return "I'm sorry, I encountered an error while processing your request."

    def get_sessions(self) -> list[str]:
        """Return all active session IDs."""
        return list(self._sessions)
