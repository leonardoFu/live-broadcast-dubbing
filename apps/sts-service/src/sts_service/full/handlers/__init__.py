"""Full STS Service event handlers.

Exports all handler registration functions for use in server setup.
"""

from sts_service.full.handlers.fragment import register_fragment_handlers
from sts_service.full.handlers.lifecycle import register_lifecycle_handlers
from sts_service.full.handlers.stream import register_stream_handlers

__all__ = [
    "register_fragment_handlers",
    "register_lifecycle_handlers",
    "register_stream_handlers",
]
