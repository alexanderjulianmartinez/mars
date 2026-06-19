"""Real CortexProvider backed by a Cortex MCP server.

Phase 1 drop-in for ``MockCortexProvider``, symmetric to
:class:`~mars.providers.autodev_mcp.AutoDevMCPProvider` and sharing the same
transport seam (:mod:`mars.providers.mcp_client`). The engine and Apollo are
unchanged because both depend only on the ``CortexProvider`` ABC.

## Tool contract

| Tool | Arguments | Returns |
| --- | --- | --- |
| ``list_profiles`` | – | ``{profiles: [...]}`` or a bare ``[...]`` |
| ``get_context_package`` | ``profile`` | ``{id?, profile?, version?, generated_at?, metadata?}`` |
| ``get_context_metadata`` | ``profile`` | arbitrary metadata mapping |
| ``get_context_for_case`` | ``case_id, profile, task_prompt`` | a context-package mapping (as above) |

Servers that only implement ``get_context_package`` still work: the per-case
path falls back to it when ``get_context_for_case`` is not configured.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime

from mars.models import ContextPackage, EvalCase
from mars.providers.base import CortexProvider
from mars.providers.mcp_client import MCPServerConfig, MCPToolCaller, ToolCaller

DEFAULT_TOOL_NAMES = {
    "list_profiles": "list_profiles",
    "get_context_package": "get_context_package",
    "get_context_metadata": "get_context_metadata",
    "get_context_for_case": "get_context_for_case",
}


def config_from_env() -> MCPServerConfig | None:
    """Read Cortex MCP connection settings from the environment.

    Returns ``None`` when no transport is configured. Recognized vars:
    ``MARS_CORTEX_MCP_URL`` (http) or ``MARS_CORTEX_MCP_COMMAND`` (stdio), plus
    optional ``MARS_CORTEX_MCP_ARGS`` and ``MARS_CORTEX_MCP_TRANSPORT``.
    """
    url = os.environ.get("MARS_CORTEX_MCP_URL")
    command = os.environ.get("MARS_CORTEX_MCP_COMMAND")
    if not url and not command:
        return None
    return MCPServerConfig(
        url=url,
        command=command,
        args=os.environ.get("MARS_CORTEX_MCP_ARGS", "").split(),
        transport=os.environ.get("MARS_CORTEX_MCP_TRANSPORT", "streamable-http"),
    )


def _parse_generated_at(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class CortexMCPProvider(CortexProvider):
    """Fetches context packages from a real Cortex over MCP."""

    def __init__(
        self,
        caller: ToolCaller,
        *,
        tool_names: dict[str, str] | None = None,
        per_case: bool = True,
    ) -> None:
        self._caller = caller
        self._tools = {**DEFAULT_TOOL_NAMES, **(tool_names or {})}
        # When False, per-case retrieval falls back to profile-based lookup.
        self._per_case = per_case

    # -- construction helpers --------------------------------------------- #

    @classmethod
    def from_config(cls, config: MCPServerConfig, **kwargs) -> "CortexMCPProvider":
        return cls(MCPToolCaller(config), **kwargs)

    @classmethod
    def from_env(cls, **kwargs):
        """Build from env, or ``None`` when no Cortex MCP server is configured."""
        config = config_from_env()
        if config is None:
            return None
        return cls.from_config(config, **kwargs)

    # -- CortexProvider --------------------------------------------------- #

    def list_profiles(self) -> list[str]:
        data = self._caller.call_tool(self._tools["list_profiles"], {})
        if isinstance(data, list):
            return [str(p) for p in data]
        profiles = data.get("profiles", []) if isinstance(data, dict) else []
        return [str(p) for p in profiles]

    def get_context_metadata(self, profile: str) -> dict:
        data = self._caller.call_tool(self._tools["get_context_metadata"], {"profile": profile})
        return data if isinstance(data, dict) else {"value": data}

    def get_context_package(self, profile: str) -> ContextPackage:
        data = self._caller.call_tool(self._tools["get_context_package"], {"profile": profile})
        return self._to_package(data, default_profile=profile)

    def get_context_for_case(self, case: EvalCase) -> ContextPackage:
        if not self._per_case:
            return self.get_context_package(case.context_profile)
        data = self._caller.call_tool(
            self._tools["get_context_for_case"],
            {
                "case_id": case.id,
                "profile": case.context_profile,
                "task_prompt": case.task_prompt,
            },
        )
        return self._to_package(data, default_profile=case.context_profile)

    def close(self) -> None:
        self._caller.close()

    # -- mapping ---------------------------------------------------------- #

    @staticmethod
    def _to_package(data: dict, *, default_profile: str) -> ContextPackage:
        data = data if isinstance(data, dict) else {}
        kwargs = {
            "id": data.get("id") or f"ctx-{uuid.uuid4().hex[:12]}",
            "profile": data.get("profile", default_profile),
            "version": data.get("version", "unknown"),
            "metadata": data.get("metadata", {}) or {},
        }
        generated = _parse_generated_at(data.get("generated_at"))
        if generated is not None:
            kwargs["generated_at"] = generated
        return ContextPackage(**kwargs)
