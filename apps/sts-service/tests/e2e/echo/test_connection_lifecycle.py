"""Integration tests for connection lifecycle in Echo STS Service.

Tests full Socket.IO connection flow with real transport.
"""

import asyncio

import pytest
import socketio
from sts_service.echo.config import EchoConfig, reset_config, set_config
from sts_service.echo.server import EchoServer


@pytest.fixture(autouse=True)
def reset_config_fixture():
    """Reset config before and after each test."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def test_config():
    """Create test configuration."""
    config = EchoConfig(
        host="127.0.0.1",
        port=8765,
        processing_delay_ms=0,
        auto_disconnect_delay=1,  # Short for testing
    )
    set_config(config)
    return config


@pytest.fixture
async def echo_server(test_config):
    """Create and start an echo server for testing."""
    server = EchoServer(test_config)

    # Start server in background
    import uvicorn

    config = uvicorn.Config(
        server.app,
        host=test_config.host,
        port=test_config.port,
        log_level="warning",
    )
    uvicorn_server = uvicorn.Server(config)

    # Run server in background task
    task = asyncio.create_task(uvicorn_server.serve())

    # Wait for server to start
    await asyncio.sleep(0.5)

    yield server

    # Cleanup
    uvicorn_server.should_exit = True
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


class TestConnectionLifecycle:
    """Integration tests for connection lifecycle."""

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_worker_connects_and_initializes(self, echo_server, test_config):
        """Full connection flow with Socket.IO client."""
        client = socketio.AsyncClient()
        ready_event = asyncio.Event()
        ready_payload = {}

        @client.on("stream:ready")
        async def on_stream_ready(data):
            ready_payload.update(data)
            ready_event.set()

        try:
            # Connect (no authentication required)
            await client.connect(
                f"http://{test_config.host}:{test_config.port}",
                socketio_path="/ws/sts",
                wait_timeout=5,
            )

            assert client.connected

            # Send stream:init
            await client.emit(
                "stream:init",
                {
                    "stream_id": "test-stream-1",
                    "worker_id": "test-worker-1",
                    "config": {
                        "source_language": "en",
                        "target_language": "es",
                        "voice_profile": "default",
                        "chunk_duration_ms": 1000,
                        "sample_rate_hz": 48000,
                        "channels": 1,
                        "format": "m4a",
                    },
                    "max_inflight": 3,
                    "timeout_ms": 8000,
                },
            )

            # Wait for stream:ready
            await asyncio.wait_for(ready_event.wait(), timeout=5)

            # Verify response
            assert ready_payload["stream_id"] == "test-stream-1"
            assert "session_id" in ready_payload
            assert ready_payload["max_inflight"] == 3
            assert "capabilities" in ready_payload

        finally:
            if client.connected:
                await client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_multiple_concurrent_sessions(self, echo_server, test_config):
        """10 concurrent sessions handled correctly."""
        num_clients = 10
        clients = []
        ready_events = []

        try:
            # Create and connect clients
            for i in range(num_clients):
                client = socketio.AsyncClient()
                ready_event = asyncio.Event()

                @client.on("stream:ready")
                async def on_stream_ready(data, evt=ready_event):
                    evt.set()

                await client.connect(
                    f"http://{test_config.host}:{test_config.port}",
                    socketio_path="/ws/sts",
                    wait_timeout=5,
                )

                clients.append(client)
                ready_events.append(ready_event)

            # All clients should be connected
            assert all(c.connected for c in clients)

            # Initialize all streams
            for i, client in enumerate(clients):
                await client.emit(
                    "stream:init",
                    {
                        "stream_id": f"stream-{i}",
                        "worker_id": f"worker-{i}",
                        "config": {},
                        "max_inflight": 3,
                    },
                )

            # Wait for all stream:ready events
            await asyncio.wait_for(
                asyncio.gather(*[e.wait() for e in ready_events]),
                timeout=10,
            )

            # Verify session count
            assert echo_server.session_store.count() == num_clients

        finally:
            # Cleanup
            for client in clients:
                if client.connected:
                    await client.disconnect()


class TestLifecycleFlow:
    """Integration tests for full lifecycle flow."""

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_worker_pause_resume_end_lifecycle(self, echo_server, test_config):
        """Full lifecycle flow: connect -> init -> pause -> resume -> end."""
        client = socketio.AsyncClient()
        events_received = []

        @client.on("stream:ready")
        async def on_stream_ready(data):
            events_received.append(("stream:ready", data))

        @client.on("stream:complete")
        async def on_stream_complete(data):
            events_received.append(("stream:complete", data))

        try:
            # Connect (no authentication required)
            await client.connect(
                f"http://{test_config.host}:{test_config.port}",
                socketio_path="/ws/sts",
                wait_timeout=5,
            )

            # Initialize
            await client.emit(
                "stream:init",
                {
                    "stream_id": "lifecycle-test",
                    "worker_id": "worker-1",
                    "config": {},
                },
            )
            await asyncio.sleep(0.2)

            # Pause
            await client.emit(
                "stream:pause",
                {"stream_id": "lifecycle-test", "reason": "test"},
            )
            await asyncio.sleep(0.1)

            # Resume
            await client.emit(
                "stream:resume",
                {"stream_id": "lifecycle-test"},
            )
            await asyncio.sleep(0.1)

            # End
            await client.emit(
                "stream:end",
                {"stream_id": "lifecycle-test", "reason": "test_complete"},
            )
            await asyncio.sleep(0.5)

            # Verify events
            assert len(events_received) >= 2
            assert events_received[0][0] == "stream:ready"
            assert any(e[0] == "stream:complete" for e in events_received)

        finally:
            if client.connected:
                await client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_stream_complete_auto_disconnect(self, echo_server, test_config):
        """Connection closes after 5 seconds (configured to 1s for test)."""
        client = socketio.AsyncClient()
        disconnected = asyncio.Event()

        @client.on("disconnect")
        async def on_disconnect():
            disconnected.set()

        @client.on("stream:ready")
        async def on_ready(data):
            pass

        try:
            # Connect and initialize (no authentication required)
            await client.connect(
                f"http://{test_config.host}:{test_config.port}",
                socketio_path="/ws/sts",
            )

            await client.emit(
                "stream:init",
                {
                    "stream_id": "auto-disconnect-test",
                    "worker_id": "worker-1",
                    "config": {},
                },
            )
            await asyncio.sleep(0.2)

            # End stream
            await client.emit(
                "stream:end",
                {"stream_id": "auto-disconnect-test"},
            )

            # Wait for auto-disconnect (configured to 1 second)
            await asyncio.wait_for(disconnected.wait(), timeout=3)

            # Should be disconnected
            assert not client.connected

        except asyncio.TimeoutError:
            pytest.fail("Client was not auto-disconnected within timeout")
        finally:
            if client.connected:
                await client.disconnect()
