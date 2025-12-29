"""Echo STS Service for E2E Testing.

A protocol-compliant mock implementation of the STS Service that echoes
audio fragments back to the caller. Enables comprehensive E2E testing
without GPU resources or ML model dependencies.

Implements the WebSocket Audio Fragment Protocol (spec 016).
"""

__version__ = "0.1.0"

# Public API (populated after implementation)
__all__ = [
    "EchoServer",
    "create_app",
]


# Lazy imports to avoid circular dependencies
def __getattr__(name: str):
    """Lazy import of public API."""
    if name == "EchoServer":
        from sts_service.echo.server import EchoServer

        return EchoServer
    elif name == "create_app":
        from sts_service.echo.server import create_app

        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
