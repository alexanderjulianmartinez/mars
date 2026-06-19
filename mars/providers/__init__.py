"""External system providers consumed by Mars.

Mars depends only on the abstract interfaces in :mod:`mars.providers.base`.
Concrete implementations (the mocks here, real MCP clients later) are drop-in
replacements selected at the edge of the system, never imported by the engine.
"""

from mars.providers.base import AutoDevProvider, CortexProvider
from mars.providers.mock import MockAutoDevProvider, MockCortexProvider

__all__ = [
    "CortexProvider",
    "AutoDevProvider",
    "MockCortexProvider",
    "MockAutoDevProvider",
]
