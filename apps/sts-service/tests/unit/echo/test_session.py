"""Unit tests for session management in Echo STS Service.

Tests SessionStore and StreamSession behavior.
"""

import pytest
from sts_service.echo.session import (
    SessionStatistics,
    SessionStore,
    StreamSession,
)


class TestStreamSession:
    """Tests for StreamSession dataclass."""

    def test_session_create(self):
        """Session created with correct initial state."""
        session = StreamSession(
            sid="socket-123",
            stream_id="stream-456",
            worker_id="worker-789",
        )

        assert session.sid == "socket-123"
        assert session.stream_id == "stream-456"
        assert session.worker_id == "worker-789"
        assert session.state == "initializing"
        assert session.session_id is not None  # Auto-generated UUID
        assert session.inflight_count == 0
        assert session.next_sequence_to_emit == 0

    def test_session_state_transition_to_active(self):
        """initializing -> active on stream:ready."""
        session = StreamSession(
            sid="s",
            stream_id="st",
            worker_id="w",
        )

        assert session.state == "initializing"
        result = session.transition_to("active")

        assert result is True
        assert session.state == "active"

    def test_session_state_active_to_paused(self):
        """active -> paused on stream:pause."""
        session = StreamSession(sid="s", stream_id="st", worker_id="w")
        session.transition_to("active")

        result = session.transition_to("paused")

        assert result is True
        assert session.state == "paused"

    def test_session_state_paused_to_active(self):
        """paused -> active on stream:resume."""
        session = StreamSession(sid="s", stream_id="st", worker_id="w")
        session.transition_to("active")
        session.transition_to("paused")

        result = session.transition_to("active")

        assert result is True
        assert session.state == "active"

    def test_session_state_active_to_ending(self):
        """active -> ending on stream:end."""
        session = StreamSession(sid="s", stream_id="st", worker_id="w")
        session.transition_to("active")

        result = session.transition_to("ending")

        assert result is True
        assert session.state == "ending"

    def test_session_state_paused_to_ending(self):
        """paused -> ending on stream:end."""
        session = StreamSession(sid="s", stream_id="st", worker_id="w")
        session.transition_to("active")
        session.transition_to("paused")

        result = session.transition_to("ending")

        assert result is True
        assert session.state == "ending"

    def test_session_state_ending_to_completed(self):
        """ending -> completed when all fragments processed."""
        session = StreamSession(sid="s", stream_id="st", worker_id="w")
        session.transition_to("active")
        session.transition_to("ending")

        result = session.transition_to("completed")

        assert result is True
        assert session.state == "completed"

    def test_session_invalid_state_transition(self):
        """Invalid state transitions should return False."""
        session = StreamSession(sid="s", stream_id="st", worker_id="w")

        # Can't go from initializing to paused
        result = session.transition_to("paused")
        assert result is False
        assert session.state == "initializing"

        # Can't go from initializing to ending
        result = session.transition_to("ending")
        assert result is False

    def test_session_can_accept_fragments(self):
        """Only active state can accept fragments."""
        session = StreamSession(sid="s", stream_id="st", worker_id="w")

        assert session.can_accept_fragments() is False

        session.transition_to("active")
        assert session.can_accept_fragments() is True

        session.transition_to("paused")
        assert session.can_accept_fragments() is False

    def test_session_inflight_tracking(self):
        """In-flight count should be tracked correctly."""
        session = StreamSession(sid="s", stream_id="st", worker_id="w")

        session.increment_inflight()
        assert session.inflight_count == 1
        assert session.fragment_count == 1

        session.increment_inflight()
        assert session.inflight_count == 2
        assert session.fragment_count == 2

        session.decrement_inflight()
        assert session.inflight_count == 1
        # fragment_count should not decrease
        assert session.fragment_count == 2

    def test_session_is_complete(self):
        """Session is complete when stream:end received and no in-flight."""
        session = StreamSession(sid="s", stream_id="st", worker_id="w")
        session.transition_to("active")

        # Not complete - stream:end not received
        assert session.is_complete() is False

        # Not complete - has in-flight
        session.increment_inflight()
        session.mark_stream_end()
        assert session.is_complete() is False

        # Complete - no in-flight
        session.decrement_inflight()
        assert session.is_complete() is True


class TestSessionStatistics:
    """Tests for SessionStatistics."""

    def test_session_statistics_tracking(self):
        """Statistics updated correctly."""
        stats = SessionStatistics()

        stats.record_fragment("success", 100)
        stats.record_fragment("success", 200)
        stats.record_fragment("failed", 50)

        assert stats.total_fragments == 3
        assert stats.success_count == 2
        assert stats.failed_count == 1
        assert stats.total_processing_time_ms == 350

    def test_session_statistics_avg(self):
        """Average processing time calculated correctly."""
        stats = SessionStatistics()

        stats.record_fragment("success", 100)
        stats.record_fragment("success", 200)
        stats.record_fragment("success", 300)

        assert stats.avg_processing_time_ms == 200.0

    def test_session_statistics_avg_empty(self):
        """Average should be 0 for empty stats."""
        stats = SessionStatistics()
        assert stats.avg_processing_time_ms == 0.0

    def test_session_statistics_p95(self):
        """P95 processing time calculated correctly."""
        stats = SessionStatistics()

        # Add 100 fragments with processing times 1-100
        for i in range(1, 101):
            stats.record_fragment("success", i)

        # P95 should be around 95
        assert stats.p95_processing_time_ms >= 95


class TestSessionStore:
    """Tests for SessionStore."""

    @pytest.mark.asyncio
    async def test_session_store_create(self):
        """Session created and stored correctly."""
        store = SessionStore()

        session = await store.create(
            sid="socket-123",
            stream_id="stream-456",
            worker_id="worker-789",
        )

        assert session.sid == "socket-123"
        assert session.stream_id == "stream-456"
        assert store.count() == 1

    @pytest.mark.asyncio
    async def test_session_store_get_by_sid(self):
        """Retrieve session by Socket.IO ID."""
        store = SessionStore()

        created = await store.create("sid-1", "stream-1", "worker-1")
        retrieved = await store.get_by_sid("sid-1")

        assert retrieved is created
        assert retrieved.session_id == created.session_id

    @pytest.mark.asyncio
    async def test_session_store_get_by_sid_not_found(self):
        """Return None for non-existent sid."""
        store = SessionStore()

        result = await store.get_by_sid("non-existent")

        assert result is None

    @pytest.mark.asyncio
    async def test_session_store_get_by_stream_id(self):
        """Retrieve session by stream ID."""
        store = SessionStore()

        created = await store.create("sid-1", "stream-1", "worker-1")
        retrieved = await store.get_by_stream_id("stream-1")

        assert retrieved is created

    @pytest.mark.asyncio
    async def test_session_store_get_by_stream_id_not_found(self):
        """Return None for non-existent stream_id."""
        store = SessionStore()

        result = await store.get_by_stream_id("non-existent")

        assert result is None

    @pytest.mark.asyncio
    async def test_session_store_delete(self):
        """Delete session removes from both indexes."""
        store = SessionStore()

        await store.create("sid-1", "stream-1", "worker-1")
        assert store.count() == 1

        deleted = await store.delete("sid-1")

        assert deleted is not None
        assert store.count() == 0
        assert await store.get_by_sid("sid-1") is None
        assert await store.get_by_stream_id("stream-1") is None

    @pytest.mark.asyncio
    async def test_session_store_multiple_sessions(self):
        """Multiple concurrent sessions handled correctly."""
        store = SessionStore()

        await store.create("sid-1", "stream-1", "worker-1")
        await store.create("sid-2", "stream-2", "worker-2")
        await store.create("sid-3", "stream-3", "worker-3")

        assert store.count() == 3

        s1 = await store.get_by_sid("sid-1")
        s2 = await store.get_by_stream_id("stream-2")

        assert s1.stream_id == "stream-1"
        assert s2.sid == "sid-2"
