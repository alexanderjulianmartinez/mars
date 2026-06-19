"""External system providers consumed by Mars.

Mars depends only on the abstract interfaces in :mod:`mars.providers.base`.
Concrete implementations (mocks, or the real MCP-backed providers) are drop-in
replacements selected at the edge of the system, never imported by the engine.
"""

from mars.providers.autodev_mcp import AutoDevMCPProvider
from mars.providers.base import AutoDevProvider, CortexProvider
from mars.providers.mcp_client import MCPServerConfig, MCPToolCaller, ToolCaller
from mars.providers.mock import MockAutoDevProvider, MockCortexProvider

__all__ = [
    "CortexProvider",
    "AutoDevProvider",
    "MockCortexProvider",
    "MockAutoDevProvider",
    "AutoDevMCPProvider",
    "MCPServerConfig",
    "MCPToolCaller",
    "ToolCaller",
]
