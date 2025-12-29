"""Unit tests for stream handlers in Echo STS Service.

Tests stream:init, stream:pause, stream:resume, stream:end handlers.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sts_service.echo.handlers.stream import (
    handle_stream_end,
    handle_stream_init,
    handle_stream_pause,
    handle_stream_resume,
)
from sts_service.echo.session import SessionStore


@pytest.fixture
def mock_sio():
    """Create a mock Socket.IO server."""
    sio = MagicMock()
    sio.emit = AsyncMock()
    sio.disconnect = AsyncMock()
    return sio


@pytest.fixture
def session_store():
    """Create a fresh session store."""
    return SessionStore()


class TestHandleStreamInit:
    """Tests for stream:init handler."""

    @pytest.mark.asyncio
    async def test_stream_init_happy_path(self, mock_sio, session_store):
        """Valid init returns stream:ready."""
        payload = {
            "stream_id": "stream-123",
            "worker_id": "worker-456",
            "config": {
                "source_language": "en",
                "target_language": "es",
                "voice_profile": "default",
                "chunk_duration_ms": 1000,
                "sample_rate_hz": 48000,
                "channels": 1,
                "format": "pcm_s16le",
            },
            "max_inflight": 3,
            "timeout_ms": 8000,
        }

        await handle_stream_init(
            sio=mock_sio,
            sid="socket-123",
            data=payload,
            session_store=session_store,
        )

        # Should emit stream:ready
        mock_sio.emit.assert_called_once()
        call_args = mock_sio.emit.call_args
        assert call_args[0][0] == "stream:ready"

        ready_payload = call_args[0][1]
        assert ready_payload["stream_id"] == "stream-123"
        assert "session_id" in ready_payload
        assert ready_payload["max_inflight"] == 3
        assert "capabilities" in ready_payload

        # Session should be created and active
        session = await session_store.get_by_sid("socket-123")
        assert session is not None
        assert session.state == "active"

    @pytest.mark.asyncio
    async def test_stream_init_error_invalid_config(self, mock_sio, session_store):
        """Invalid config returns INVALID_CONFIG error."""
        payload = {
            "stream_id": "stream-123",
            "worker_id": "worker-456",
            "config": {
                "chunk_duration_ms": 50,  # Too low, min is 100
            },
            "max_inflight": 3,
        }

        await handle_stream_init(
            sio=mock_sio,
            sid="socket-123",
            data=payload,
            session_store=session_store,
        )

        # Should emit error
        mock_sio.emit.assert_called_once()
        call_args = mock_sio.emit.call_args
        assert call_args[0][0] == "error"

        error_payload = call_args[0][1]
        assert error_payload["code"] == "INVALID_CONFIG"

    @pytest.mark.asyncio
    async def test_stream_init_error_missing_required_fields(self, mock_sio, session_store):
        """Missing fields rejected."""
        payload = {
            # Missing stream_id and worker_id
            "config": {},
        }

        await handle_stream_init(
            sio=mock_sio,
            sid="socket-123",
            data=payload,
            session_store=session_store,
        )

        # Should emit error
        mock_sio.emit.assert_called_once()
        call_args = mock_sio.emit.call_args
        assert call_args[0][0] == "error"
        assert call_args[0][1]["code"] == "INVALID_CONFIG"


class TestHandleStreamPause:
    """Tests for stream:pause handler."""

    @pytest.mark.asyncio
    async def test_stream_pause_stops_new_fragments(self, mock_sio, session_store):
        """New fragments rejected when paused."""
        # Create an active session
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        payload = {"stream_id": "stream-1", "reason": "backpressure"}

        await handle_stream_pause(
            sio=mock_sio,
            sid="sid-1",
            data=payload,
            session_store=session_store,
        )

        # Session should be paused
        assert session.state == "paused"
        assert session.can_accept_fragments() is False

    @pytest.mark.asyncio
    async def test_stream_pause_completes_inflight(self, mock_sio, session_store):
        """In-flight fragments complete even when paused."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")
        session.increment_inflight()  # Simulate in-flight fragment

        payload = {"stream_id": "stream-1"}

        await handle_stream_pause(
            sio=mock_sio,
            sid="sid-1",
            data=payload,
            session_store=session_store,
        )

        # Session should be paused
        assert session.state == "paused"
        # In-flight count should still be tracked
        assert session.inflight_count == 1


class TestHandleStreamResume:
    """Tests for stream:resume handler."""

    @pytest.mark.asyncio
    async def test_stream_resume_allows_fragments(self, mock_sio, session_store):
        """Fragments accepted after resume."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")
        session.transition_to("paused")

        payload = {"stream_id": "stream-1"}

        await handle_stream_resume(
            sio=mock_sio,
            sid="sid-1",
            data=payload,
            session_store=session_store,
        )

        # Session should be active again
        assert session.state == "active"
        assert session.can_accept_fragments() is True


class TestHandleStreamEnd:
    """Tests for stream:end handler."""

    @pytest.mark.asyncio
    async def test_stream_end_returns_statistics(self, mock_sio, session_store):
        """stream:complete with accurate stats."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        # Record some statistics
        session.statistics.record_fragment("success", 100)
        session.statistics.record_fragment("success", 200)
        session.statistics.record_fragment("failed", 50)

        payload = {"stream_id": "stream-1", "reason": "source_ended"}

        await handle_stream_end(
            sio=mock_sio,
            sid="sid-1",
            data=payload,
            session_store=session_store,
        )

        # Should emit stream:complete
        mock_sio.emit.assert_called()
        # Find the stream:complete call
        complete_call = None
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "stream:complete":
                complete_call = call
                break

        assert complete_call is not None
        complete_payload = complete_call[0][1]
        assert complete_payload["stream_id"] == "stream-1"
        assert complete_payload["total_fragments"] == 3
        assert complete_payload["statistics"]["success_count"] == 2
        assert complete_payload["statistics"]["failed_count"] == 1

    @pytest.mark.asyncio
    async def test_stream_complete_payload_structure(self, mock_sio, session_store):
        """Validates stream:complete schema."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        payload = {"stream_id": "stream-1"}

        await handle_stream_end(
            sio=mock_sio,
            sid="sid-1",
            data=payload,
            session_store=session_store,
        )

        # Verify stream:complete structure
        complete_call = None
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "stream:complete":
                complete_call = call
                break

        assert complete_call is not None
        payload = complete_call[0][1]

        # All required fields present
        assert "stream_id" in payload
        assert "total_fragments" in payload
        assert "total_duration_ms" in payload
        assert "statistics" in payload
        assert "success_count" in payload["statistics"]
        assert "partial_count" in payload["statistics"]
        assert "failed_count" in payload["statistics"]
        assert "avg_processing_time_ms" in payload["statistics"]
        assert "p95_processing_time_ms" in payload["statistics"]
