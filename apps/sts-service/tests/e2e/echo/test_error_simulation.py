"""Integration tests for error simulation in Echo STS Service.

Tests error injection configuration and behavior with real Socket.IO transport.
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
        port=8768,
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
    audio_bytes = b"\x00" * 9600
    return base64.b64encode(audio_bytes).decode("ascii")


class TestErrorSimulation:
    """Integration tests for error simulation."""

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_worker_configures_error_simulation(self, echo_server, test_config):
        """Config accepted via Socket.IO."""
        client = socketio.AsyncClient()
        ready_event = asyncio.Event()
        config_ack_event = asyncio.Event()
        config_ack = {}

        @client.on("stream:ready")
        async def on_ready(data):
            ready_event.set()

        @client.on("config:error_simulation:ack")
        async def on_config_ack(data):
            config_ack.update(data)
            config_ack_event.set()

        try:
            await client.connect(
                f"http://{test_config.host}:{test_config.port}",
                socketio_path="/ws/sts",
            )

            await client.emit(
                "stream:init",
                {
                    "stream_id": "error-sim-test",
                    "worker_id": "worker-1",
                    "config": {},
                },
            )
            await asyncio.wait_for(ready_event.wait(), timeout=5)

            # Configure error simulation
            await client.emit(
                "config:error_simulation",
                {
                    "enabled": True,
                    "rules": [
                        {
                            "trigger": "sequence_number",
                            "value": 2,
                            "error_code": "TIMEOUT",
                            "error_message": "Simulated timeout",
                            "retryable": True,
                        }
                    ],
                },
            )

            # Wait for ack
            await asyncio.wait_for(config_ack_event.wait(), timeout=5)

            assert config_ack["status"] == "accepted"
            assert config_ack["rules_count"] == 1

        finally:
            if client.connected:
                await client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_worker_handles_timeout_error(
        self, echo_server, test_config, sample_audio_base64
    ):
        """Timeout error returned correctly."""
        client = socketio.AsyncClient()
        ready_event = asyncio.Event()
        config_ack_event = asyncio.Event()
        processed_fragments = []

        @client.on("stream:ready")
        async def on_ready(data):
            ready_event.set()

        @client.on("config:error_simulation:ack")
        async def on_config_ack(data):
            config_ack_event.set()

        @client.on("fragment:processed")
        async def on_processed(data):
            processed_fragments.append(data)

        try:
            await client.connect(
                f"http://{test_config.host}:{test_config.port}",
                socketio_path="/ws/sts",
            )

            await client.emit(
                "stream:init",
                {
                    "stream_id": "timeout-error-test",
                    "worker_id": "worker-1",
                    "config": {},
                },
            )
            await asyncio.wait_for(ready_event.wait(), timeout=5)

            # Configure timeout error for fragment 1
            await client.emit(
                "config:error_simulation",
                {
                    "enabled": True,
                    "rules": [
                        {
                            "trigger": "sequence_number",
                            "value": 1,
                            "error_code": "TIMEOUT",
                            "error_message": "Processing timeout",
                            "retryable": True,
                        }
                    ],
                },
            )
            await asyncio.wait_for(config_ack_event.wait(), timeout=5)

            # Send fragments 0 and 1
            for seq in range(2):
                await client.emit(
                    "fragment:data",
                    {
                        "fragment_id": f"frag-{seq:03d}",
                        "stream_id": "timeout-error-test",
                        "sequence_number": seq,
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

            # Wait for processing
            await asyncio.sleep(0.5)

            # Verify fragment 0 succeeded, fragment 1 failed
            assert len(processed_fragments) == 2

            frag0 = next(p for p in processed_fragments if p["sequence_number"] == 0)
            frag1 = next(p for p in processed_fragments if p["sequence_number"] == 1)

            assert frag0["status"] == "success"
            assert frag1["status"] == "failed"
            assert frag1["error"]["code"] == "TIMEOUT"
            assert frag1["error"]["retryable"] is True

        finally:
            if client.connected:
                await client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_worker_handles_model_error(self, echo_server, test_config, sample_audio_base64):
        """Model error returned correctly."""
        client = socketio.AsyncClient()
        ready_event = asyncio.Event()
        config_ack_event = asyncio.Event()
        processed_fragments = []

        @client.on("stream:ready")
        async def on_ready(data):
            ready_event.set()

        @client.on("config:error_simulation:ack")
        async def on_config_ack(data):
            config_ack_event.set()

        @client.on("fragment:processed")
        async def on_processed(data):
            processed_fragments.append(data)

        try:
            await client.connect(
                f"http://{test_config.host}:{test_config.port}",
                socketio_path="/ws/sts",
            )

            await client.emit(
                "stream:init",
                {
                    "stream_id": "model-error-test",
                    "worker_id": "worker-1",
                    "config": {},
                },
            )
            await asyncio.wait_for(ready_event.wait(), timeout=5)

            # Configure model error for fragment 0
            await client.emit(
                "config:error_simulation",
                {
                    "enabled": True,
                    "rules": [
                        {
                            "trigger": "sequence_number",
                            "value": 0,
                            "error_code": "MODEL_ERROR",
                            "error_message": "TTS model failed",
                            "retryable": True,
                            "stage": "tts",
                        }
                    ],
                },
            )
            await asyncio.wait_for(config_ack_event.wait(), timeout=5)

            # Send fragment
            await client.emit(
                "fragment:data",
                {
                    "fragment_id": "frag-model-error",
                    "stream_id": "model-error-test",
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

            # Wait for processing
            await asyncio.sleep(0.5)

            assert len(processed_fragments) == 1
            assert processed_fragments[0]["status"] == "failed"
            assert processed_fragments[0]["error"]["code"] == "MODEL_ERROR"
            assert processed_fragments[0]["error"]["stage"] == "tts"

        finally:
            if client.connected:
                await client.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_error_simulation_multiple_rules(
        self, echo_server, test_config, sample_audio_base64
    ):
        """Multiple rules trigger correctly."""
        client = socketio.AsyncClient()
        ready_event = asyncio.Event()
        config_ack_event = asyncio.Event()
        processed_fragments = []

        @client.on("stream:ready")
        async def on_ready(data):
            ready_event.set()

        @client.on("config:error_simulation:ack")
        async def on_config_ack(data):
            config_ack_event.set()

        @client.on("fragment:processed")
        async def on_processed(data):
            processed_fragments.append(data)

        try:
            await client.connect(
                f"http://{test_config.host}:{test_config.port}",
                socketio_path="/ws/sts",
            )

            await client.emit(
                "stream:init",
                {
                    "stream_id": "multi-rule-test",
                    "worker_id": "worker-1",
                    "config": {},
                },
            )
            await asyncio.wait_for(ready_event.wait(), timeout=5)

            # Configure multiple error rules
            await client.emit(
                "config:error_simulation",
                {
                    "enabled": True,
                    "rules": [
                        {
                            "trigger": "sequence_number",
                            "value": 1,
                            "error_code": "TIMEOUT",
                            "retryable": True,
                        },
                        {
                            "trigger": "sequence_number",
                            "value": 3,
                            "error_code": "GPU_OOM",
                            "retryable": True,
                        },
                    ],
                },
            )
            await asyncio.wait_for(config_ack_event.wait(), timeout=5)

            # Send 5 fragments
            for seq in range(5):
                await client.emit(
                    "fragment:data",
                    {
                        "fragment_id": f"frag-{seq:03d}",
                        "stream_id": "multi-rule-test",
                        "sequence_number": seq,
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

            # Wait for processing
            await asyncio.sleep(0.5)

            # Verify correct fragments failed
            assert len(processed_fragments) == 5

            for p in processed_fragments:
                if p["sequence_number"] == 1:
                    assert p["status"] == "failed"
                    assert p["error"]["code"] == "TIMEOUT"
                elif p["sequence_number"] == 3:
                    assert p["status"] == "failed"
                    assert p["error"]["code"] == "GPU_OOM"
                else:
                    assert p["status"] == "success"

        finally:
            if client.connected:
                await client.disconnect()
