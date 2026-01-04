"""Unit tests for FragmentQueue (in-order delivery).

Tests fragment ordering by sequence_number for ordered emission.
These tests MUST be written FIRST and MUST FAIL before implementation (TDD).

Task ID: T072
"""

import asyncio

import pytest

from sts_service.full.models.fragment import (
    AudioData,
    DurationMetadata,
    FragmentResult,
    ProcessingStatus,
    StageTiming,
)
from sts_service.full.fragment_queue import FragmentQueue


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


def create_fragment_result(
    fragment_id: str,
    sequence_number: int,
    stream_id: str = "stream-abc-123",
) -> FragmentResult:
    """Create a FragmentResult for testing."""
    return FragmentResult(
        fragment_id=fragment_id,
        stream_id=stream_id,
        sequence_number=sequence_number,
        status=ProcessingStatus.SUCCESS,
        dubbed_audio=AudioData(
            format="pcm_s16le",
            sample_rate_hz=48000,
            channels=1,
            duration_ms=6000,
            data_base64="AQIDBAU=",
        ),
        transcript=f"Transcript for {sequence_number}",
        translated_text=f"Translation for {sequence_number}",
        processing_time_ms=4500,
        stage_timings=StageTiming(
            asr_ms=1200,
            translation_ms=150,
            tts_ms=3100,
        ),
        metadata=DurationMetadata(
            original_duration_ms=6000,
            dubbed_duration_ms=6050,
            duration_variance_percent=0.83,
            speed_ratio=0.99,
        ),
    )


# -----------------------------------------------------------------------------
# T072: Fragment ordering by sequence_number
# -----------------------------------------------------------------------------


class TestFragmentQueue:
    """Tests for T072: Fragment ordering by sequence_number."""

    def test_queue_initializes_with_expected_sequence(self):
        """Queue starts expecting sequence_number 0."""
        # Arrange & Act
        queue = FragmentQueue(stream_id="stream-abc-123")

        # Assert
        assert queue.next_expected_sequence == 0

    def test_queue_initializes_with_custom_start_sequence(self):
        """Queue can start from a custom sequence number."""
        # Arrange & Act
        queue = FragmentQueue(stream_id="stream-abc-123", start_sequence=5)

        # Assert
        assert queue.next_expected_sequence == 5

    @pytest.mark.asyncio
    async def test_add_fragment_increments_pending_count(self):
        """Adding a fragment increments the pending count."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")
        result = create_fragment_result("frag-001", sequence_number=0)

        # Act
        queue.add_result(result)

        # Assert
        assert queue.pending_count == 1

    @pytest.mark.asyncio
    async def test_get_next_returns_fragment_in_order(self):
        """get_next_in_order returns fragments in sequence order."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")

        # Add fragments out of order: 2, 0, 1
        result2 = create_fragment_result("frag-003", sequence_number=2)
        result0 = create_fragment_result("frag-001", sequence_number=0)
        result1 = create_fragment_result("frag-002", sequence_number=1)

        queue.add_result(result2)
        queue.add_result(result0)
        queue.add_result(result1)

        # Act - Get fragments in order
        out0 = await queue.get_next_in_order()
        out1 = await queue.get_next_in_order()
        out2 = await queue.get_next_in_order()

        # Assert - Should be in sequence order
        assert out0.sequence_number == 0
        assert out1.sequence_number == 1
        assert out2.sequence_number == 2

    @pytest.mark.asyncio
    async def test_get_next_blocks_until_expected_sequence_available(self):
        """get_next_in_order blocks if expected sequence is not available."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")

        # Add sequence 1 first (not 0)
        result1 = create_fragment_result("frag-002", sequence_number=1)
        queue.add_result(result1)

        # Act - Try to get next (should block because 0 not available)
        async def get_with_timeout():
            try:
                return await asyncio.wait_for(
                    queue.get_next_in_order(),
                    timeout=0.1,  # 100ms timeout
                )
            except asyncio.TimeoutError:
                return None

        result = await get_with_timeout()

        # Assert - Should timeout because sequence 0 is not available
        assert result is None

        # Now add sequence 0
        result0 = create_fragment_result("frag-001", sequence_number=0)
        queue.add_result(result0)

        # Should now get sequence 0
        out = await queue.get_next_in_order()
        assert out.sequence_number == 0

    @pytest.mark.asyncio
    async def test_get_next_updates_expected_sequence(self):
        """get_next_in_order updates next_expected_sequence."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")
        result0 = create_fragment_result("frag-001", sequence_number=0)
        queue.add_result(result0)

        # Assert initial state
        assert queue.next_expected_sequence == 0

        # Act
        await queue.get_next_in_order()

        # Assert
        assert queue.next_expected_sequence == 1

    @pytest.mark.asyncio
    async def test_out_of_order_fragments_buffered(self):
        """Out-of-order fragments are buffered until needed."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")

        # Add sequences 3, 2, 4, 1, 0 (completely out of order)
        for seq in [3, 2, 4, 1, 0]:
            result = create_fragment_result(f"frag-{seq}", sequence_number=seq)
            queue.add_result(result)

        # Assert - All should be buffered
        assert queue.pending_count == 5

        # Act - Get all in order
        results = []
        for _ in range(5):
            r = await queue.get_next_in_order()
            results.append(r)

        # Assert - All came out in order
        assert [r.sequence_number for r in results] == [0, 1, 2, 3, 4]
        assert queue.pending_count == 0

    @pytest.mark.asyncio
    async def test_duplicate_sequence_number_ignored(self):
        """Duplicate sequence numbers are ignored."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")
        result0a = create_fragment_result("frag-001", sequence_number=0)
        result0b = create_fragment_result("frag-001-dup", sequence_number=0)

        # Act
        queue.add_result(result0a)
        queue.add_result(result0b)  # Duplicate

        # Assert - Only one should be buffered
        assert queue.pending_count == 1

    def test_is_complete_false_when_pending(self):
        """is_complete returns False when fragments are pending."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")
        result0 = create_fragment_result("frag-001", sequence_number=0)
        queue.add_result(result0)

        # Assert
        assert queue.is_complete is False

    @pytest.mark.asyncio
    async def test_is_complete_true_when_empty(self):
        """is_complete returns True when queue is empty."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")
        result0 = create_fragment_result("frag-001", sequence_number=0)
        queue.add_result(result0)

        # Act
        await queue.get_next_in_order()

        # Assert
        assert queue.is_complete is True

    @pytest.mark.asyncio
    async def test_try_get_next_returns_none_if_not_ready(self):
        """try_get_next returns None immediately if next sequence not ready."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")
        # Add sequence 1 only (not 0)
        result1 = create_fragment_result("frag-002", sequence_number=1)
        queue.add_result(result1)

        # Act
        result = queue.try_get_next()

        # Assert - Should return None without blocking
        assert result is None

    @pytest.mark.asyncio
    async def test_try_get_next_returns_result_if_ready(self):
        """try_get_next returns result immediately if next sequence is ready."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")
        result0 = create_fragment_result("frag-001", sequence_number=0)
        queue.add_result(result0)

        # Act
        result = queue.try_get_next()

        # Assert
        assert result is not None
        assert result.sequence_number == 0

    def test_clear_removes_all_pending_fragments(self):
        """clear() removes all pending fragments."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")
        for seq in range(5):
            result = create_fragment_result(f"frag-{seq}", sequence_number=seq)
            queue.add_result(result)

        assert queue.pending_count == 5

        # Act
        queue.clear()

        # Assert
        assert queue.pending_count == 0
        assert queue.next_expected_sequence == 0


class TestFragmentQueueConcurrency:
    """Concurrency tests for FragmentQueue."""

    @pytest.mark.asyncio
    async def test_concurrent_add_and_get(self):
        """Multiple concurrent producers and single consumer."""
        # Arrange
        queue = FragmentQueue(stream_id="stream-abc-123")
        received = []
        num_fragments = 10

        async def producer(start_seq: int, count: int):
            """Add fragments with some delay."""
            for i in range(count):
                seq = start_seq + i
                result = create_fragment_result(f"frag-{seq}", sequence_number=seq)
                await asyncio.sleep(0.01 * (seq % 3))  # Variable delay
                queue.add_result(result)

        async def consumer():
            """Consume fragments in order."""
            for _ in range(num_fragments):
                result = await queue.get_next_in_order()
                received.append(result.sequence_number)

        # Act - Run producers and consumer concurrently
        await asyncio.gather(
            producer(0, 5),  # Sequences 0-4
            producer(5, 5),  # Sequences 5-9
            consumer(),
        )

        # Assert - All received in order
        assert received == list(range(num_fragments))
