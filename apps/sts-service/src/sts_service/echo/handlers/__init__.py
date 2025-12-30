"""Socket.IO event handlers for Echo STS Service.

Handlers are organized by event category:
- stream: Connection lifecycle (init, pause, resume, end)
- fragment: Audio fragment processing (data, ack)
- config: Runtime configuration (error_simulation)
- simulate: Test simulation (disconnect for E2E testing)
"""

__all__ = [
    "register_stream_handlers",
    "register_fragment_handlers",
    "register_config_handlers",
    "register_simulate_handlers",
]


def __getattr__(name: str):
    """Lazy import of handler registration functions."""
    if name == "register_stream_handlers":
        from sts_service.echo.handlers.stream import register_stream_handlers

        return register_stream_handlers
    elif name == "register_fragment_handlers":
        from sts_service.echo.handlers.fragment import register_fragment_handlers

        return register_fragment_handlers
    elif name == "register_config_handlers":
        from sts_service.echo.handlers.config import register_config_handlers

        return register_config_handlers
    elif name == "register_simulate_handlers":
        from sts_service.echo.handlers.simulate import register_simulate_handlers

        return register_simulate_handlers
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
