"""Tool registry for the Smart Talk LangChain agent."""

from __future__ import annotations

import logging

from langchain.tools import BaseTool

from app.ha.client import HAClient
from app.search.device_resolver import DeviceResolver

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Holds and manages LangChain tools available to the Smart Talk agent.

    Usage::

        registry = ToolRegistry.build_default_tools(ha_client, device_resolver)
        tools = registry.get_tools()
    """

    def __init__(self) -> None:
        self._tools: list[BaseTool] = []

    def register(self, tool: BaseTool) -> None:
        """Register a single tool.

        Args:
            tool: A LangChain :class:`~langchain.tools.BaseTool` instance.
        """
        self._tools.append(tool)
        logger.debug("Registered tool: %s", tool.name)

    def get_tools(self) -> list[BaseTool]:
        """Return all registered tools."""
        return list(self._tools)

    @classmethod
    def build_default_tools(
        cls,
        ha_client: HAClient,
        device_resolver: DeviceResolver,
    ) -> "ToolRegistry":
        """Instantiate all built-in Smart Talk tools and return a populated registry.

        Args:
            ha_client:       Initialised HA REST client.
            device_resolver: Initialised semantic device resolver.
        """
        # Import here to avoid circular imports at module load time
        from app.agent.tools.ha_climate import (
            GetClimateStateTool,
            SetHvacModeTool,
            SetTemperatureTool,
        )
        from app.agent.tools.ha_covers import (
            CloseCoverTool,
            GetCoverStateTool,
            OpenCoverTool,
            SetCoverPositionTool,
        )
        from app.agent.tools.ha_lights import GetLightStateTool, TurnOffLightTool, TurnOnLightTool
        from app.agent.tools.ha_scenes import ActivateSceneTool
        from app.agent.tools.ha_sensors import GetSensorValueTool
        from app.agent.tools.ha_switches import (
            GetSwitchStateTool,
            ToggleSwitchTool,
            TurnOffSwitchTool,
            TurnOnSwitchTool,
        )

        common = {"ha_client": ha_client, "device_resolver": device_resolver}
        registry = cls()

        for tool_cls in (
            TurnOnLightTool,
            TurnOffLightTool,
            GetLightStateTool,
            SetTemperatureTool,
            SetHvacModeTool,
            GetClimateStateTool,
            TurnOnSwitchTool,
            TurnOffSwitchTool,
            ToggleSwitchTool,
            GetSwitchStateTool,
            GetSensorValueTool,
            OpenCoverTool,
            CloseCoverTool,
            SetCoverPositionTool,
            GetCoverStateTool,
            ActivateSceneTool,
        ):
            registry.register(tool_cls(**common))  # type: ignore[arg-type]

        logger.info("ToolRegistry: %d tools registered", len(registry._tools))
        return registry
