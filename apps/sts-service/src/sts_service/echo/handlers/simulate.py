"""Simulation handlers for Echo STS Service.

Handles test simulation events like simulate:disconnect for E2E testing.
These handlers are for testing purposes only.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sts_service.echo.session import SessionStore

logger = logging.getLogger(__name__)


async def handle_simulate_disconnect(
    sio: Any,
    sid: str,
    data: dict[str, Any],
    session_store: SessionStore,
) -> None:
    """Handle simulate:disconnect event.

    Forces server-side disconnect for reconnection testing.
    Used by E2E tests to validate WorkerRunner reconnection behavior.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        data: The simulate:disconnect payload.
        session_store: Session store instance.

    Payload:
        delay_ms: Delay before disconnect (0 = immediate)
    """
    delay_ms = data.get("delay_ms", 0)
    reason = data.get("reason", "test")

    logger.info(f"Simulate disconnect requested: sid={sid}, delay_ms={delay_ms}, reason={reason}")

    # Send acknowledgment before disconnecting
    ack_payload = {
        "status": "scheduled",
        "disconnect_at_ms": int(time.time() * 1000) + delay_ms,
        "message": f"Disconnect scheduled in {delay_ms}ms",
    }
    await sio.emit("simulate:disconnect:ack", ack_payload, to=sid)

    # Schedule disconnect
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000.0)

    # Check if still connected (client might have disconnected)
    try:
        # Force disconnect from server side
        await sio.disconnect(sid)
        logger.info(f"Simulated disconnect completed: sid={sid}")
    except Exception as e:
        logger.warning(f"Disconnect failed (client may have already left): {e}")


def register_simulate_handlers(
    sio: Any,
    session_store: SessionStore,
) -> None:
    """Register simulation event handlers.

    Args:
        sio: Socket.IO server instance.
        session_store: Session store instance.
    """

    @sio.on("simulate:disconnect")
    async def on_simulate_disconnect(sid: str, data: dict[str, Any]) -> None:
        await handle_simulate_disconnect(sio, sid, data, session_store)

    logger.debug("Simulation handlers registered")
