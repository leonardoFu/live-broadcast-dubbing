"""
Unit tests for FragmentTracker class.

Tests T046-T051 from tasks.md - validating fragment tracking.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from media_service.models.segments import AudioSegment
from media_service.sts.fragment_tracker import FragmentTracker


@pytest.fixture
def mock_audio_segment() -> AudioSegment:
    """Create a mock audio segment."""
    return AudioSegment(
        fragment_id="frag-test-001",
        stream_id="test-stream",
        batch_number=0,
        t0_ns=0,
        duration_ns=6_000_000_000,
        file_path=Path("/tmp/test.m4a"),
    )


class TestFragmentTrackerInit:
    """Tests for FragmentTracker initialization."""

    def test_default_values(self) -> None:
        """Test default tracker values."""
        tracker = FragmentTracker()

        assert tracker.max_inflight == 3
        assert tracker.timeout_ms == 60000  # 60 seconds for 30-second fragments
        assert tracker.inflight_count == 0
        assert tracker.sequence_number == 0

    def test_custom_values(self) -> None:
        """Test custom tracker values."""
        tracker = FragmentTracker(max_inflight=5, timeout_ms=10000)

        assert tracker.max_inflight == 5
        assert tracker.timeout_ms == 10000


class TestFragmentTrackerTrack:
    """Tests for track method."""

    @pytest.mark.asyncio
    async def test_track_creates_inflight(self, mock_audio_segment: AudioSegment) -> None:
        """Test track creates InFlightFragment."""
        tracker = FragmentTracker()

        inflight = await tracker.track(mock_audio_segment)

        assert inflight.fragment_id == mock_audio_segment.fragment_id
        assert inflight.segment == mock_audio_segment
        assert inflight.sequence_number == 0
        assert tracker.inflight_count == 1

    @pytest.mark.asyncio
    async def test_track_increments_sequence(self, mock_audio_segment: AudioSegment) -> None:
        """Test sequence number increments with each track."""
        tracker = FragmentTracker()

        seg1 = AudioSegment(
            fragment_id="frag-1",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/1.m4a"),
        )
        seg2 = AudioSegment(
            fragment_id="frag-2",
            stream_id="test",
            batch_number=1,
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/2.m4a"),
        )

        inflight1 = await tracker.track(seg1)
        inflight2 = await tracker.track(seg2)

        assert inflight1.sequence_number == 0
        assert inflight2.sequence_number == 1
        assert tracker.sequence_number == 2

    @pytest.mark.asyncio
    async def test_track_raises_when_max_inflight_reached(
        self, mock_audio_segment: AudioSegment
    ) -> None:
        """Test track raises when max_inflight limit reached."""
        tracker = FragmentTracker(max_inflight=2)

        # Track 2 fragments
        seg1 = AudioSegment(
            fragment_id="frag-1",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/1.m4a"),
        )
        seg2 = AudioSegment(
            fragment_id="frag-2",
            stream_id="test",
            batch_number=1,
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/2.m4a"),
        )

        await tracker.track(seg1)
        await tracker.track(seg2)

        # Third should raise
        with pytest.raises(RuntimeError, match="Max in-flight limit"):
            await tracker.track(mock_audio_segment)


class TestFragmentTrackerComplete:
    """Tests for complete method."""

    @pytest.mark.asyncio
    async def test_complete_removes_from_tracking(self, mock_audio_segment: AudioSegment) -> None:
        """Test complete removes fragment from tracking."""
        tracker = FragmentTracker()

        await tracker.track(mock_audio_segment)
        assert tracker.inflight_count == 1

        inflight = await tracker.complete(mock_audio_segment.fragment_id)

        assert inflight is not None
        assert inflight.fragment_id == mock_audio_segment.fragment_id
        assert tracker.inflight_count == 0

    @pytest.mark.asyncio
    async def test_complete_returns_none_for_unknown(self) -> None:
        """Test complete returns None for unknown fragment."""
        tracker = FragmentTracker()

        inflight = await tracker.complete("unknown-fragment")

        assert inflight is None

    @pytest.mark.asyncio
    async def test_complete_cancels_timeout_task(self, mock_audio_segment: AudioSegment) -> None:
        """Test complete cancels the timeout task."""
        tracker = FragmentTracker(timeout_ms=5000)

        inflight = await tracker.track(mock_audio_segment)
        assert inflight.timeout_task is not None
        assert not inflight.timeout_task.done()

        await tracker.complete(mock_audio_segment.fragment_id)

        # Task should be cancelled
        await asyncio.sleep(0.01)  # Let cancellation propagate
        assert inflight.timeout_task.done()


class TestFragmentTrackerCapacity:
    """Tests for capacity checking."""

    @pytest.mark.asyncio
    async def test_has_capacity_when_empty(self) -> None:
        """Test has_capacity returns True when empty."""
        tracker = FragmentTracker(max_inflight=3)

        assert tracker.has_capacity() is True

    @pytest.mark.asyncio
    async def test_has_capacity_when_full(self, mock_audio_segment: AudioSegment) -> None:
        """Test has_capacity returns False when full."""
        tracker = FragmentTracker(max_inflight=1)

        await tracker.track(mock_audio_segment)

        assert tracker.has_capacity() is False


class TestFragmentTrackerTimeout:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_timeout_callback_called(self, mock_audio_segment: AudioSegment) -> None:
        """Test timeout callback is called on timeout."""
        tracker = FragmentTracker(timeout_ms=50)  # 50ms timeout

        callback = AsyncMock()
        tracker.set_timeout_callback(callback)

        await tracker.track(mock_audio_segment)

        # Wait for timeout
        await asyncio.sleep(0.1)

        callback.assert_called_once_with(
            mock_audio_segment.fragment_id,
            mock_audio_segment,
        )

    @pytest.mark.asyncio
    async def test_timeout_removes_from_tracking(self, mock_audio_segment: AudioSegment) -> None:
        """Test timeout removes fragment from tracking."""
        tracker = FragmentTracker(timeout_ms=50)

        await tracker.track(mock_audio_segment)
        assert tracker.inflight_count == 1

        # Wait for timeout
        await asyncio.sleep(0.1)

        assert tracker.inflight_count == 0


class TestFragmentTrackerClear:
    """Tests for clear method."""

    @pytest.mark.asyncio
    async def test_clear_removes_all(self, mock_audio_segment: AudioSegment) -> None:
        """Test clear removes all tracked fragments."""
        tracker = FragmentTracker()

        seg1 = AudioSegment(
            fragment_id="frag-1",
            stream_id="test",
            batch_number=0,
            t0_ns=0,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/1.m4a"),
        )
        seg2 = AudioSegment(
            fragment_id="frag-2",
            stream_id="test",
            batch_number=1,
            t0_ns=6_000_000_000,
            duration_ns=6_000_000_000,
            file_path=Path("/tmp/2.m4a"),
        )

        await tracker.track(seg1)
        await tracker.track(seg2)
        assert tracker.inflight_count == 2

        fragments = await tracker.clear()

        assert len(fragments) == 2
        assert tracker.inflight_count == 0


class TestFragmentTrackerGet:
    """Tests for get method."""

    @pytest.mark.asyncio
    async def test_get_returns_inflight(self, mock_audio_segment: AudioSegment) -> None:
        """Test get returns tracked fragment."""
        tracker = FragmentTracker()

        await tracker.track(mock_audio_segment)

        inflight = tracker.get(mock_audio_segment.fragment_id)

        assert inflight is not None
        assert inflight.fragment_id == mock_audio_segment.fragment_id

    @pytest.mark.asyncio
    async def test_get_returns_none_for_unknown(self) -> None:
        """Test get returns None for unknown fragment."""
        tracker = FragmentTracker()

        inflight = tracker.get("unknown")

        assert inflight is None
