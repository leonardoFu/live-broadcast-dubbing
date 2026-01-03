#!/usr/bin/env python3
"""Diagnostic script to test Socket.IO emit behavior."""
import asyncio
import logging
import socketio

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def test_emit():
    """Test Socket.IO emit in ASGI mode."""
    # Create server
    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins="*",
        logger=True,  # Enable Socket.IO's own logging
        engineio_logger=True,
    )

    @sio.on("connect")
    async def on_connect(sid, environ):
        logger.info(f"✅ Client connected: {sid}")
        # Try immediate emit
        logger.info("📤 About to emit 'welcome' event...")
        try:
            await sio.emit("welcome", {"message": "Hello from server!"}, to=sid)
            logger.info("✅ Emit returned successfully")
        except Exception as e:
            logger.error(f"❌ Emit failed: {e}")

    @sio.on("test_request")
    async def on_test(sid, data):
        logger.info(f"📨 Received test_request: {data}")
        logger.info("📤 About to emit 'test_response' event...")
        try:
            await sio.emit("test_response", {"echo": data}, to=sid)
            logger.info("✅ Emit returned successfully")
        except Exception as e:
            logger.error(f"❌ Emit failed: {e}")

    # Create minimal ASGI app
    from fastapi import FastAPI
    fastapi_app = FastAPI()

    @fastapi_app.get("/health")
    def health():
        return {"status": "ok"}

    app = socketio.ASGIApp(
        socketio_server=sio,
        other_asgi_app=fastapi_app,
    )

    # Run server
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=8999, log_level="debug")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    print("Starting diagnostic Socket.IO server on port 8999...")
    print("Run test client with: python -c 'import asyncio; import socketio; sio = socketio.AsyncClient(); asyncio.run(test())'")
    asyncio.run(test_emit())
