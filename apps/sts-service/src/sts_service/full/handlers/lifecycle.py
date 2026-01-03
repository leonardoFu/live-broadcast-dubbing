"""Connection lifecycle handlers for Full STS Service.

Handles connect and disconnect events as defined in spec 021.
"""

import logging
from typing import Any

from sts_service.full.session import SessionStore

logger = logging.getLogger(__name__)


async def handle_connect(
    sio: Any,
    sid: str,
    environ: dict[str, Any],
    session_store: SessionStore,
) -> None:
    """Handle connect event.

    Extracts metadata from headers and creates initial session.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        environ: WSGI environ dict containing headers.
        session_store: Session store instance.
    """
    # Extract metadata from headers (optional)
    stream_id = environ.get("HTTP_X_STREAM_ID", f"stream-{sid[:8]}")
    worker_id = environ.get("HTTP_X_WORKER_ID", f"worker-{sid[:8]}")

    # Create session (state=INITIALIZING, will transition to READY on stream:init)
    await session_store.create(
        sid=sid,
        stream_id=stream_id,
        worker_id=worker_id,
    )

    logger.info(f"Client connected: stream_id={stream_id}, worker_id={worker_id}, sid={sid}")


async def handle_disconnect(
    sio: Any,
    sid: str,
    session_store: SessionStore,
) -> None:
    """Handle disconnect event.

    Cleans up session resources and in-flight fragments.

    Args:
        sio: Socket.IO server instance.
        sid: Socket.IO session ID.
        session_store: Session store instance.
    """
    session = await session_store.get_by_sid(sid)

    if session is None:
        logger.debug(f"Disconnect from unknown session: sid={sid}")
        return

    # Log disconnect details
    logger.info(
        f"Client disconnected: stream_id={session.stream_id}, "
        f"worker_id={session.worker_id}, state={session.state.value}, "
        f"inflight={session.inflight_count}, sid={sid}"
    )

    # Clean up resources
    # Cancel any in-flight tasks if needed
    # (In our implementation, tasks are background asyncio tasks that will complete)

    # Delete session
    await session_store.delete(sid)


def register_lifecycle_handlers(
    sio: Any,
    session_store: SessionStore,
) -> None:
    """Register connection lifecycle event handlers.

    Args:
        sio: Socket.IO server instance.
        session_store: Session store instance.
    """

    @sio.on("connect")
    async def on_connect(sid: str, environ: dict[str, Any]) -> None:
        await handle_connect(sio, sid, environ, session_store)

    @sio.on("disconnect")
    async def on_disconnect(sid: str) -> None:
        await handle_disconnect(sio, sid, session_store)
