"""
Comprehensive unit tests for STS Socket.IO client.

Tests T040-T052 from tasks.md - Socket.IO client functionality.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from media_service.models.segments import AudioSegment
from media_service.sts.models import (
    BackpressurePayload,
    FragmentProcessedPayload,
    StreamConfig,
)
from media_service.sts.socketio_client import StsSocketIOClient


@pytest.fixture
def mock_socketio():
    """Create a mock Socket.IO client."""
    with patch("media_service.sts.socketio_client.socketio") as mock_sio_module:
        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.emit = AsyncMock()
        mock_client.on = MagicMock()
        mock_sio_module.AsyncClient.return_value = mock_client
        yield mock_client


@pytest.fixture
def sts_client():
    """Create an StsSocketIOClient instance."""
    return StsSocketIOClient(
        server_url="http://sts-service:8000",
        namespace="/",  # Use default namespace
        reconnect_attempts=5,
        reconnect_delay=1.0,
    )


@pytest.fixture
def stream_config():
    """Create a StreamConfig instance."""
    return StreamConfig(
        source_language="en",
        target_language="es",
        voice_profile="default",
        format="m4a",
        sample_rate_hz=48000,
        channels=2,
    )


@pytest.fixture
def audio_segment(tmp_path: Path) -> AudioSegment:
    """Create a test audio segment with a real file."""
    segment_file = tmp_path / "test_segment.m4a"
    # Write some dummy M4A data
    segment_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00" * 100)

    return AudioSegment(
        fragment_id="test-fragment-001",
        stream_id="test-stream",
        batch_number=0,
        t0_ns=0,
        duration_ns=6_000_000_000,
        file_path=segment_file,
    )


class TestStsSocketIOClientInit:
    """Tests for StsSocketIOClient initialization."""

    def test_init_sets_server_url(self) -> None:
        """Test that server URL is set correctly."""
        client = StsSocketIOClient(server_url="http://test:8000")
        assert client.server_url == "http://test:8000"

    def test_init_default_namespace(self) -> None:
        """Test default namespace is /."""
        client = StsSocketIOClient(server_url="http://test:8000")
        assert client.namespace == "/"

    def test_init_custom_namespace(self) -> None:
        """Test custom namespace."""
        client = StsSocketIOClient(server_url="http://test:8000", namespace="/custom")
        assert client.namespace == "/custom"

    def test_init_default_reconnect_attempts(self) -> None:
        """Test default reconnect attempts."""
        client = StsSocketIOClient(server_url="http://test:8000")
        assert client.reconnect_attempts == 5

    def test_init_custom_reconnect_attempts(self) -> None:
        """Test custom reconnect attempts."""
        client = StsSocketIOClient(server_url="http://test:8000", reconnect_attempts=10)
        assert client.reconnect_attempts == 10

    def test_init_not_connected(self) -> None:
        """Test client starts not connected."""
        client = StsSocketIOClient(server_url="http://test:8000")
        assert not client.is_connected

    def test_init_stream_not_ready(self) -> None:
        """Test stream starts not ready."""
        client = StsSocketIOClient(server_url="http://test:8000")
        assert not client.is_stream_ready

    def test_init_sequence_number_zero(self) -> None:
        """Test sequence number starts at zero."""
        client = StsSocketIOClient(server_url="http://test:8000")
        assert client.current_sequence_number == 0

    def test_init_no_session_id(self) -> None:
        """Test session ID starts as None."""
        client = StsSocketIOClient(server_url="http://test:8000")
        assert client.session_id is None

    def test_init_default_max_inflight(self) -> None:
        """Test default max inflight is 3."""
        client = StsSocketIOClient(server_url="http://test:8000")
        assert client.max_inflight == 3


class TestStsSocketIOClientConnect:
    """Tests for connection functionality."""

    @pytest.mark.asyncio
    async def test_connect_creates_socket_client(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock
    ) -> None:
        """Test that connect creates a Socket.IO client."""
        await sts_client.connect()
        assert sts_client._sio is not None

    @pytest.mark.asyncio
    async def test_connect_calls_connect_method(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock
    ) -> None:
        """Test that connect calls the underlying connect method."""
        await sts_client.connect()
        mock_socketio.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_uses_websocket_transport(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock
    ) -> None:
        """Test that connect uses websocket transport."""
        await sts_client.connect()
        call_kwargs = mock_socketio.connect.call_args.kwargs
        assert call_kwargs.get("transports") == ["websocket"]

    @pytest.mark.asyncio
    async def test_connect_uses_correct_namespace(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock
    ) -> None:
        """Test that connect uses the correct namespace."""
        await sts_client.connect()
        call_kwargs = mock_socketio.connect.call_args.kwargs
        assert "/sts" in call_kwargs.get("namespaces", [])

    @pytest.mark.asyncio
    async def test_connect_sets_connected_flag(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock
    ) -> None:
        """Test that successful connection sets connected flag."""
        await sts_client.connect()
        assert sts_client.is_connected

    @pytest.mark.asyncio
    async def test_connect_returns_true_on_success(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock
    ) -> None:
        """Test that connect returns True on success."""
        result = await sts_client.connect()
        assert result is True

    @pytest.mark.asyncio
    async def test_connect_raises_on_failure(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock
    ) -> None:
        """Test that connect raises ConnectionError on failure."""
        mock_socketio.connect.side_effect = Exception("Connection failed")

        with pytest.raises(ConnectionError) as exc_info:
            await sts_client.connect()

        assert "Failed to connect" in str(exc_info.value)


class TestStsSocketIOClientInitStream:
    """Tests for stream initialization."""

    @pytest.mark.asyncio
    async def test_init_stream_requires_connection(
        self, sts_client: StsSocketIOClient, stream_config: StreamConfig
    ) -> None:
        """Test that init_stream requires connection."""
        with pytest.raises(ConnectionError) as exc_info:
            await sts_client.init_stream("test-stream", stream_config)

        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_init_stream_emits_stream_init(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock, stream_config: StreamConfig
    ) -> None:
        """Test that init_stream emits stream:init event."""
        await sts_client.connect()

        # Simulate stream:ready response
        async def emit_and_respond(*args, **kwargs):
            if args[0] == "stream:init":
                await sts_client._handle_stream_ready({
                    "session_id": "session-123",
                    "max_inflight": 3,
                })

        mock_socketio.emit.side_effect = emit_and_respond

        await sts_client.init_stream("test-stream", stream_config)

        # Check that stream:init was emitted
        emit_calls = mock_socketio.emit.call_args_list
        assert any(call.args[0] == "stream:init" for call in emit_calls)

    @pytest.mark.asyncio
    async def test_init_stream_sets_stream_id(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock, stream_config: StreamConfig
    ) -> None:
        """Test that init_stream sets the stream ID."""
        await sts_client.connect()

        async def emit_and_respond(*args, **kwargs):
            if args[0] == "stream:init":
                await sts_client._handle_stream_ready({
                    "session_id": "session-123",
                    "max_inflight": 3,
                })

        mock_socketio.emit.side_effect = emit_and_respond

        await sts_client.init_stream("my-stream-id", stream_config)

        assert sts_client.stream_id == "my-stream-id"

    @pytest.mark.asyncio
    async def test_init_stream_timeout(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock, stream_config: StreamConfig
    ) -> None:
        """Test that init_stream times out if no stream:ready received."""
        await sts_client.connect()

        with pytest.raises(TimeoutError) as exc_info:
            await sts_client.init_stream("test-stream", stream_config, timeout=0.1)

        assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_init_stream_resets_sequence_number(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock, stream_config: StreamConfig
    ) -> None:
        """Test that init_stream resets sequence number."""
        await sts_client.connect()
        sts_client._sequence_number = 10

        async def emit_and_respond(*args, **kwargs):
            if args[0] == "stream:init":
                await sts_client._handle_stream_ready({
                    "session_id": "session-123",
                    "max_inflight": 3,
                })

        mock_socketio.emit.side_effect = emit_and_respond

        await sts_client.init_stream("test-stream", stream_config)

        assert sts_client.current_sequence_number == 0


class TestStsSocketIOClientStreamReady:
    """Tests for stream:ready handling."""

    @pytest.mark.asyncio
    async def test_handle_stream_ready_sets_session_id(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that stream:ready sets session ID."""
        await sts_client._handle_stream_ready({
            "session_id": "session-456",
            "max_inflight": 5,
        })

        assert sts_client.session_id == "session-456"

    @pytest.mark.asyncio
    async def test_handle_stream_ready_sets_max_inflight(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that stream:ready sets max inflight."""
        await sts_client._handle_stream_ready({
            "session_id": "session-456",
            "max_inflight": 10,
        })

        assert sts_client.max_inflight == 10

    @pytest.mark.asyncio
    async def test_handle_stream_ready_default_max_inflight(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that stream:ready uses default max inflight if not provided."""
        await sts_client._handle_stream_ready({
            "session_id": "session-456",
        })

        assert sts_client.max_inflight == 3

    @pytest.mark.asyncio
    async def test_handle_stream_ready_sets_ready_flag(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that stream:ready sets stream ready flag."""
        await sts_client._handle_stream_ready({
            "session_id": "session-456",
        })

        assert sts_client.is_stream_ready


class TestStsSocketIOClientSendFragment:
    """Tests for fragment sending."""

    @pytest.mark.asyncio
    async def test_send_fragment_requires_connection(
        self, sts_client: StsSocketIOClient, audio_segment: AudioSegment
    ) -> None:
        """Test that send_fragment requires connection."""
        with pytest.raises(ConnectionError):
            await sts_client.send_fragment(audio_segment)

    @pytest.mark.asyncio
    async def test_send_fragment_requires_stream_ready(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock, audio_segment: AudioSegment
    ) -> None:
        """Test that send_fragment requires stream to be ready."""
        await sts_client.connect()

        with pytest.raises(ConnectionError) as exc_info:
            await sts_client.send_fragment(audio_segment)

        assert "Stream not ready" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_fragment_emits_fragment_data(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock,
        stream_config: StreamConfig, audio_segment: AudioSegment
    ) -> None:
        """Test that send_fragment emits fragment:data event."""
        await sts_client.connect()

        # Simulate stream ready
        async def emit_and_respond(*args, **kwargs):
            if args[0] == "stream:init":
                await sts_client._handle_stream_ready({
                    "session_id": "session-123",
                    "max_inflight": 3,
                })

        mock_socketio.emit.side_effect = emit_and_respond
        await sts_client.init_stream("test-stream", stream_config)

        # Reset side effect for normal emit
        mock_socketio.emit.side_effect = None

        await sts_client.send_fragment(audio_segment)

        # Check that fragment:data was emitted
        emit_calls = mock_socketio.emit.call_args_list
        assert any(call.args[0] == "fragment:data" for call in emit_calls)

    @pytest.mark.asyncio
    async def test_send_fragment_increments_sequence(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock,
        stream_config: StreamConfig, audio_segment: AudioSegment
    ) -> None:
        """Test that send_fragment increments sequence number."""
        await sts_client.connect()

        async def emit_and_respond(*args, **kwargs):
            if args[0] == "stream:init":
                await sts_client._handle_stream_ready({
                    "session_id": "session-123",
                    "max_inflight": 3,
                })

        mock_socketio.emit.side_effect = emit_and_respond
        await sts_client.init_stream("test-stream", stream_config)
        mock_socketio.emit.side_effect = None

        assert sts_client.current_sequence_number == 0

        await sts_client.send_fragment(audio_segment)
        assert sts_client.current_sequence_number == 1

        await sts_client.send_fragment(audio_segment)
        assert sts_client.current_sequence_number == 2

    @pytest.mark.asyncio
    async def test_send_fragment_returns_fragment_id(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock,
        stream_config: StreamConfig, audio_segment: AudioSegment
    ) -> None:
        """Test that send_fragment returns fragment ID."""
        await sts_client.connect()

        async def emit_and_respond(*args, **kwargs):
            if args[0] == "stream:init":
                await sts_client._handle_stream_ready({
                    "session_id": "session-123",
                    "max_inflight": 3,
                })

        mock_socketio.emit.side_effect = emit_and_respond
        await sts_client.init_stream("test-stream", stream_config)
        mock_socketio.emit.side_effect = None

        fragment_id = await sts_client.send_fragment(audio_segment)

        assert fragment_id == audio_segment.fragment_id

    @pytest.mark.asyncio
    async def test_send_fragment_file_not_found(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock,
        stream_config: StreamConfig, tmp_path: Path
    ) -> None:
        """Test that send_fragment raises FileNotFoundError for missing file."""
        await sts_client.connect()

        async def emit_and_respond(*args, **kwargs):
            if args[0] == "stream:init":
                await sts_client._handle_stream_ready({
                    "session_id": "session-123",
                    "max_inflight": 3,
                })

        mock_socketio.emit.side_effect = emit_and_respond
        await sts_client.init_stream("test-stream", stream_config)
        mock_socketio.emit.side_effect = None

        # Create segment with non-existent file
        segment = AudioSegment(
            fragment_id="test-fragment",
            stream_id="test-stream",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=tmp_path / "nonexistent.m4a",
        )

        with pytest.raises(FileNotFoundError):
            await sts_client.send_fragment(segment)


class TestStsSocketIOClientFragmentProcessed:
    """Tests for fragment:processed handling."""

    @pytest.mark.asyncio
    async def test_handle_fragment_processed_calls_callback(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that fragment:processed calls the callback."""
        callback = AsyncMock()
        sts_client.set_fragment_processed_callback(callback)

        await sts_client._handle_fragment_processed({
            "fragment_id": "frag-001",
            "stream_id": "stream-001",
            "sequence_number": 0,
            "status": "success",
            "processing_time_ms": 500,
        })

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_fragment_processed_passes_payload(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that fragment:processed passes the correct payload."""
        callback = AsyncMock()
        sts_client.set_fragment_processed_callback(callback)

        await sts_client._handle_fragment_processed({
            "fragment_id": "frag-001",
            "stream_id": "stream-001",
            "sequence_number": 5,
            "status": "success",
            "processing_time_ms": 1000,
        })

        payload: FragmentProcessedPayload = callback.call_args[0][0]
        assert payload.fragment_id == "frag-001"
        assert payload.sequence_number == 5
        assert payload.status == "success"
        assert payload.processing_time_ms == 1000

    @pytest.mark.asyncio
    async def test_handle_fragment_processed_no_callback(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that fragment:processed works without callback."""
        # Should not raise
        await sts_client._handle_fragment_processed({
            "fragment_id": "frag-001",
            "stream_id": "stream-001",
            "sequence_number": 0,
            "status": "success",
            "processing_time_ms": 500,
        })


class TestStsSocketIOClientBackpressure:
    """Tests for backpressure handling."""

    @pytest.mark.asyncio
    async def test_handle_backpressure_calls_callback(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that backpressure calls the callback."""
        callback = AsyncMock()
        sts_client.set_backpressure_callback(callback)

        await sts_client._handle_backpressure({
            "stream_id": "stream-001",
            "severity": "medium",
            "current_inflight": 5,
            "queue_depth": 10,
            "action": "slow_down",
            "recommended_delay_ms": 500,
        })

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_backpressure_passes_payload(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that backpressure passes correct payload."""
        callback = AsyncMock()
        sts_client.set_backpressure_callback(callback)

        await sts_client._handle_backpressure({
            "stream_id": "stream-001",
            "severity": "high",
            "current_inflight": 10,
            "queue_depth": 20,
            "action": "pause",
            "recommended_delay_ms": 1000,
        })

        payload: BackpressurePayload = callback.call_args[0][0]
        assert payload.severity == "high"
        assert payload.action == "pause"
        assert payload.recommended_delay_ms == 1000


class TestStsSocketIOClientError:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handle_error_calls_callback(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that error calls the callback."""
        callback = AsyncMock()
        sts_client.set_error_callback(callback)

        await sts_client._handle_error({
            "code": "TIMEOUT",
            "message": "Processing timeout",
            "retryable": True,
        })

        callback.assert_called_once_with("TIMEOUT", "Processing timeout", True)

    @pytest.mark.asyncio
    async def test_handle_error_non_retryable(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that non-retryable error is passed correctly."""
        callback = AsyncMock()
        sts_client.set_error_callback(callback)

        await sts_client._handle_error({
            "code": "INVALID_CONFIG",
            "message": "Invalid stream configuration",
            "retryable": False,
        })

        callback.assert_called_once_with("INVALID_CONFIG", "Invalid stream configuration", False)


class TestStsSocketIOClientEndStream:
    """Tests for stream end functionality."""

    @pytest.mark.asyncio
    async def test_end_stream_emits_event(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock, stream_config: StreamConfig
    ) -> None:
        """Test that end_stream emits stream:end event."""
        await sts_client.connect()

        async def emit_and_respond(*args, **kwargs):
            if args[0] == "stream:init":
                await sts_client._handle_stream_ready({
                    "session_id": "session-123",
                    "max_inflight": 3,
                })

        mock_socketio.emit.side_effect = emit_and_respond
        await sts_client.init_stream("test-stream", stream_config)
        mock_socketio.emit.side_effect = None

        await sts_client.end_stream()

        # Check that stream:end was emitted
        emit_calls = mock_socketio.emit.call_args_list
        assert any(call.args[0] == "stream:end" for call in emit_calls)

    @pytest.mark.asyncio
    async def test_end_stream_clears_stream_ready(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock, stream_config: StreamConfig
    ) -> None:
        """Test that end_stream clears stream ready flag."""
        await sts_client.connect()

        async def emit_and_respond(*args, **kwargs):
            if args[0] == "stream:init":
                await sts_client._handle_stream_ready({
                    "session_id": "session-123",
                    "max_inflight": 3,
                })

        mock_socketio.emit.side_effect = emit_and_respond
        await sts_client.init_stream("test-stream", stream_config)
        mock_socketio.emit.side_effect = None

        assert sts_client.is_stream_ready

        await sts_client.end_stream()

        assert not sts_client.is_stream_ready

    @pytest.mark.asyncio
    async def test_end_stream_no_op_when_not_connected(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that end_stream is no-op when not connected."""
        # Should not raise
        await sts_client.end_stream()


class TestStsSocketIOClientDisconnect:
    """Tests for disconnect functionality."""

    @pytest.mark.asyncio
    async def test_disconnect_calls_disconnect_method(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock
    ) -> None:
        """Test that disconnect calls underlying disconnect."""
        await sts_client.connect()
        await sts_client.disconnect()

        mock_socketio.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_clears_connected_flag(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock
    ) -> None:
        """Test that disconnect clears connected flag."""
        await sts_client.connect()
        assert sts_client.is_connected

        await sts_client.disconnect()

        assert not sts_client.is_connected

    @pytest.mark.asyncio
    async def test_disconnect_clears_stream_ready(
        self, sts_client: StsSocketIOClient, mock_socketio: AsyncMock, stream_config: StreamConfig
    ) -> None:
        """Test that disconnect clears stream ready flag."""
        await sts_client.connect()

        async def emit_and_respond(*args, **kwargs):
            if args[0] == "stream:init":
                await sts_client._handle_stream_ready({
                    "session_id": "session-123",
                    "max_inflight": 3,
                })

        mock_socketio.emit.side_effect = emit_and_respond
        await sts_client.init_stream("test-stream", stream_config)

        await sts_client.disconnect()

        assert not sts_client.is_stream_ready

    @pytest.mark.asyncio
    async def test_disconnect_no_op_when_not_connected(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test that disconnect is no-op when not connected."""
        # Should not raise
        await sts_client.disconnect()


class TestStsSocketIOClientCallbacks:
    """Tests for callback setters."""

    def test_set_fragment_processed_callback(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test setting fragment processed callback."""
        callback = AsyncMock()
        sts_client.set_fragment_processed_callback(callback)

        assert sts_client._on_fragment_processed is callback

    def test_set_backpressure_callback(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test setting backpressure callback."""
        callback = AsyncMock()
        sts_client.set_backpressure_callback(callback)

        assert sts_client._on_backpressure is callback

    def test_set_error_callback(
        self, sts_client: StsSocketIOClient
    ) -> None:
        """Test setting error callback."""
        callback = AsyncMock()
        sts_client.set_error_callback(callback)

        assert sts_client._on_error is callback
