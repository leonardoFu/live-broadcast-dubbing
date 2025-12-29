"""Integration tests for fragment echo round-trip in Echo STS Service.

Tests full Socket.IO fragment processing with real transport.
"""

import asyncio
import base64

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
        port=8766,
        api_key="test-api-key",
        require_auth=True,
        processing_delay_ms=0,
        auto_disconnect_delay=5,
    )
    set_config(config)
    return config


@pytest.fixture
async def echo_server(test_config):
    """Create and start an echo server for testing."""
    server = EchoServer(test_config)

    import uvicorn

    config = uvicorn.Config(
        server.app,
        host=test_config.host,
        port=test_config.port,
        log_level="warning",
    )
    uvicorn_server = uvicorn.Server(config)

    task = asyncio.create_task(uvicorn_server.serve())
    await asyncio.sleep(0.5)

    yield server

    uvicorn_server.should_exit = True
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.fixture
def sample_audio_base64():
    """Generate sample base64 audio data."""
    # 100ms of silence at 48kHz mono
    audio_bytes = b"\x00" * 9600
    return base64.b64encode(audio_bytes).decode("ascii")


class TestFragmentRoundTrip:
    """Integration tests for fragment round-trip."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_worker_sends_fragments_receives_echo(
        self, echo_server, test_config, sample_audio_base64
    ):
        """Full round-trip with Socket.IO."""
        client = socketio.AsyncClient()
        ready_event = asyncio.Event()
        processed_fragments = []
        ack_fragments = []

        @client.on("stream:ready")
        async def on_ready(data):
            ready_event.set()

        @client.on("fragment:ack")
        async def on_ack(data):
            ack_fragments.append(data)

        @client.on("fragment:processed")
        async def on_processed(data):
            processed_fragments.append(data)

        try:
            # Connect and initialize
            await client.connect(
                f"http://{test_config.host}:{test_config.port}",
                socketio_path="/ws/sts",
                auth={"token": test_config.api_key},
            )

            await client.emit(
                "stream:init",
                {
                    "stream_id": "fragment-test",
                    "worker_id": "worker-1",
                    "config": {},
                },
            )
            await asyncio.wait_for(ready_event.wait(), timeout=5)

            # Send a fragment
            await client.emit(
                "fragment:data",
                {
                    "fragment_id": "frag-001",
                    "stream_id": "fragment-test",
                    "sequence_number": 0,
                    "timestamp": 1703750400000,
                    "audio": {
                        "format": "pcm_s16le",
                        "sample_rate_hz": 48000,
                        "channels": 1,
                        "duration_ms": 100,
                        "data_base64": sample_audio_base64,
                    },
                },
            )

            # Wait for processed fragment
            await asyncio.sleep(0.5)

            # Verify ack received
            assert len(ack_fragments) == 1
            assert ack_fragments[0]["fragment_id"] == "frag-001"
            assert ack_fragments[0]["status"] == "queued"

            # Verify processed fragment
            assert len(processed_fragments) == 1
            p = processed_fragments[0]
            assert p["fragment_id"] == "frag-001"
            assert p["status"] == "success"
            assert p["dubbed_audio"]["data_base64"] == sample_audio_base64

        finally:
            if client.connected:
                await client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_fragments_in_sequence(
        self, echo_server, test_config, sample_audio_base64
    ):
        """10 fragments processed in order."""
        client = socketio.AsyncClient()
        ready_event = asyncio.Event()
        processed_fragments = []

        @client.on("stream:ready")
        async def on_ready(data):
            ready_event.set()

        @client.on("fragment:processed")
        async def on_processed(data):
            processed_fragments.append(data)

        try:
            await client.connect(
                f"http://{test_config.host}:{test_config.port}",
                socketio_path="/ws/sts",
                auth={"token": test_config.api_key},
            )

            await client.emit(
                "stream:init",
                {
                    "stream_id": "sequence-test",
                    "worker_id": "worker-1",
                    "config": {},
                },
            )
            await asyncio.wait_for(ready_event.wait(), timeout=5)

            # Send 10 fragments
            for seq in range(10):
                await client.emit(
                    "fragment:data",
                    {
                        "fragment_id": f"frag-{seq:03d}",
                        "stream_id": "sequence-test",
                        "sequence_number": seq,
                        "timestamp": 1703750400000 + seq * 100,
                        "audio": {
                            "format": "pcm_s16le",
                            "sample_rate_hz": 48000,
                            "channels": 1,
                            "duration_ms": 100,
                            "data_base64": sample_audio_base64,
                        },
                    },
                )

            # Wait for all fragments
            await asyncio.sleep(1)

            # Verify all 10 fragments received
            assert len(processed_fragments) == 10

            # Verify sequence order
            sequence_numbers = [p["sequence_number"] for p in processed_fragments]
            assert sequence_numbers == list(range(10))

        finally:
            if client.connected:
                await client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fragment_worker_ack(self, echo_server, test_config, sample_audio_base64):
        """Worker acknowledgment handled correctly."""
        client = socketio.AsyncClient()
        ready_event = asyncio.Event()
        processed_event = asyncio.Event()

        @client.on("stream:ready")
        async def on_ready(data):
            ready_event.set()

        @client.on("fragment:processed")
        async def on_processed(data):
            # Send ack back to server
            await client.emit(
                "fragment:ack",
                {
                    "fragment_id": data["fragment_id"],
                    "status": "received",
                    "timestamp": 1703750400000,
                },
            )
            processed_event.set()

        try:
            await client.connect(
                f"http://{test_config.host}:{test_config.port}",
                socketio_path="/ws/sts",
                auth={"token": test_config.api_key},
            )

            await client.emit(
                "stream:init",
                {
                    "stream_id": "ack-test",
                    "worker_id": "worker-1",
                    "config": {},
                },
            )
            await asyncio.wait_for(ready_event.wait(), timeout=5)

            await client.emit(
                "fragment:data",
                {
                    "fragment_id": "frag-ack-001",
                    "stream_id": "ack-test",
                    "sequence_number": 0,
                    "timestamp": 1703750400000,
                    "audio": {
                        "format": "pcm_s16le",
                        "sample_rate_hz": 48000,
                        "channels": 1,
                        "duration_ms": 100,
                        "data_base64": sample_audio_base64,
                    },
                },
            )

            # Wait for processed and ack
            await asyncio.wait_for(processed_event.wait(), timeout=5)

            # No error should have occurred
            assert True

        finally:
            if client.connected:
                await client.disconnect()
