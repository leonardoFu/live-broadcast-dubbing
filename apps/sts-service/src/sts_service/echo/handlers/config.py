"""Configuration handlers for Echo STS Service.

Handles runtime configuration events like config:error_simulation.
"""

import logging
from typing import Any

from pydantic import ValidationError

from sts_service.echo.models.error import (
    ConfigErrorSimulationAck,
    ErrorPayload,
    ErrorSimulationConfig,
)
from sts_service.echo.session import SessionStore

logger = logging.getLogger(__name__)


async def handle_config_error_simulation(
    sio: Any,
    sid: str,
    data: dict[str, Any],
    session_store: SessionStore,
) -> None:
    """Handle config:error_simulation event.

    Configures error simulation for the session, allowing tests to
    dynamically inject errors into fragment processing.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        data: The config:error_simulation payload.
        session_store: Session store instance.
    """
    session = await session_store.get_by_sid(sid)
    if session is None:
        error = ErrorPayload.from_error_code(
            code="STREAM_NOT_FOUND",
            message="Cannot configure error simulation: no active session",
        )
        await sio.emit("error", error.model_dump(), to=sid)
        return

    try:
        # Validate configuration
        config = ErrorSimulationConfig(**data)

        # Apply to session
        session.error_simulation = config

        # Send acknowledgment
        ack = ConfigErrorSimulationAck(
            status="accepted",
            rules_count=len(config.rules),
        )
        await sio.emit("config:error_simulation:ack", ack.model_dump(), to=sid)

        logger.info(
            f"Error simulation configured: stream_id={session.stream_id}, "
            f"enabled={config.enabled}, rules_count={len(config.rules)}"
        )

    except ValidationError as e:
        logger.warning(f"Invalid error simulation config: {e}")

        ack = ConfigErrorSimulationAck(
            status="rejected",
            rules_count=0,
            message=f"Invalid configuration: {str(e)}",
        )
        await sio.emit("config:error_simulation:ack", ack.model_dump(), to=sid)


def register_config_handlers(
    sio: Any,
    session_store: SessionStore,
) -> None:
    """Register configuration event handlers.

    Args:
        sio: Socket.IO server instance.
        session_store: Session store instance.
    """

    @sio.on("config:error_simulation")
    async def on_config_error_simulation(sid: str, data: dict[str, Any]) -> None:
        await handle_config_error_simulation(sio, sid, data, session_store)
