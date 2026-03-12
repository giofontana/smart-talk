"""Tool registry and imports for Smart Talk agent tools."""

from __future__ import annotations

from app.agent.tools.base import SmartTalkTool
from app.agent.tools.ha_climate import GetClimateStateTool, SetHvacModeTool, SetTemperatureTool
from app.agent.tools.ha_covers import CloseCoverTool, GetCoverStateTool, OpenCoverTool, SetCoverPositionTool
from app.agent.tools.ha_lights import GetLightStateTool, TurnOffLightTool, TurnOnLightTool
from app.agent.tools.ha_scenes import ActivateSceneTool
from app.agent.tools.ha_sensors import GetSensorValueTool
from app.agent.tools.ha_switches import GetSwitchStateTool, ToggleSwitchTool, TurnOffSwitchTool, TurnOnSwitchTool
from app.agent.tools.registry import ToolRegistry

__all__ = [
    # base
    "SmartTalkTool",
    # lights
    "TurnOnLightTool",
    "TurnOffLightTool",
    "GetLightStateTool",
    # climate
    "SetTemperatureTool",
    "SetHvacModeTool",
    "GetClimateStateTool",
    # switches
    "TurnOnSwitchTool",
    "TurnOffSwitchTool",
    "ToggleSwitchTool",
    "GetSwitchStateTool",
    # sensors
    "GetSensorValueTool",
    # covers
    "OpenCoverTool",
    "CloseCoverTool",
    "SetCoverPositionTool",
    "GetCoverStateTool",
    # scenes
    "ActivateSceneTool",
    # registry
    "ToolRegistry",
]
