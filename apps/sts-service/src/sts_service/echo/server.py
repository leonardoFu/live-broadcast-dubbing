"""Socket.IO AsyncServer setup for Echo STS Service.

Provides the main EchoServer class and ASGI app factory.
"""

import logging

import socketio

from sts_service.echo.config import EchoConfig, get_config
from sts_service.echo.session import SessionStore

logger = logging.getLogger(__name__)


class EchoServer:
    """Echo STS Service Socket.IO server.

    A protocol-compliant mock implementation of the STS Service that
    echoes audio fragments back to the caller.

    Attributes:
        sio: The Socket.IO AsyncServer instance.
        app: The ASGI application.
        session_store: The session store for managing connections.
    """

    def __init__(
        self,
        config: EchoConfig | None = None,
    ) -> None:
        """Initialize the Echo STS Server.

        Args:
            config: Optional configuration. If not provided, uses global config.
        """
        self.config = config or get_config()
        self.session_store = SessionStore()

        # Create Socket.IO server
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins="*",  # Allow all origins for testing
            ping_interval=self.config.ping_interval,
            ping_timeout=self.config.ping_timeout,
            max_http_buffer_size=self.config.max_buffer_size,
            logger=False,  # Use our own logging
            engineio_logger=False,
        )

        # Create ASGI app (using default socketio_path="/socket.io/")
        self.app = socketio.ASGIApp(
            self.sio,
        )

        # Register event handlers
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register all Socket.IO event handlers."""
        # Connection lifecycle
        self._register_connection_handlers()

        # Stream handlers
        from sts_service.echo.handlers.stream import register_stream_handlers

        register_stream_handlers(self.sio, self.session_store)

        # Fragment handlers (will be added in Phase 4)
        try:
            from sts_service.echo.handlers.fragment import register_fragment_handlers

            register_fragment_handlers(self.sio, self.session_store)
        except ImportError:
            logger.debug("Fragment handlers not yet implemented")

        # Config handlers (will be added in Phase 7)
        try:
            from sts_service.echo.handlers.config import register_config_handlers

            register_config_handlers(self.sio, self.session_store)
        except ImportError:
            logger.debug("Config handlers not yet implemented")

        # Simulate handlers (for E2E testing)
        try:
            from sts_service.echo.handlers.simulate import register_simulate_handlers

            register_simulate_handlers(self.sio, self.session_store)
        except ImportError:
            logger.debug("Simulate handlers not yet implemented")

    def _register_connection_handlers(self) -> None:
        """Register connection lifecycle handlers."""

        @self.sio.event
        async def connect(sid: str, environ: dict, auth: dict | None = None) -> bool:
            """Handle new connection (no authentication required).

            Args:
                sid: Socket.IO session ID.
                environ: ASGI environ dict.
                auth: Authentication payload (ignored - no auth required).

            Returns:
                True to accept connection.
            """
            logger.info(f"Client connected: sid={sid}")
            return True

        @self.sio.event
        async def disconnect(sid: str) -> None:
            """Handle client disconnection.

            Args:
                sid: Socket.IO session ID.
            """
            # Clean up session if exists
            session = await self.session_store.delete(sid)

            if session:
                logger.info(
                    f"Client disconnected: sid={sid}, "
                    f"stream_id={session.stream_id}, "
                    f"state={session.state}"
                )
            else:
                logger.info(f"Client disconnected: sid={sid}")


def create_app(config: EchoConfig | None = None):
    """Create an ASGI application for the Echo STS Service with health endpoint.

    This is the main entry point for running the service with an ASGI
    server like uvicorn.

    Args:
        config: Optional configuration. If not provided, uses global config.

    Returns:
        An ASGI application with Socket.IO and HTTP health endpoint.

    Example:
        ```python
        # Run with uvicorn
        import uvicorn
        from sts_service.echo.server import create_app

        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=8000)
        ```
    """
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route, Mount

    server = EchoServer(config)

    async def health(request):
        """Health check endpoint."""
        return JSONResponse({"status": "healthy", "service": "echo-sts"})

    # Create Starlette app with routes
    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Mount("/", server.app),  # Mount Socket.IO app at root
        ]
    )

    return app


def get_server(config: EchoConfig | None = None) -> EchoServer:
    """Create an EchoServer instance.

    Use this when you need access to the server internals (e.g., for testing).

    Args:
        config: Optional configuration. If not provided, uses global config.

    Returns:
        An EchoServer instance.
    """
    return EchoServer(config)
