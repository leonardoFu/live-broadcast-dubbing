"""Fragment Queue for in-order delivery.

Implements a priority queue that buffers fragments and emits them
in sequence_number order, regardless of processing completion order.

Task ID: T084
"""

import asyncio
import heapq

from .models.fragment import FragmentResult


class FragmentQueue:
    """Priority queue for in-order fragment delivery.

    Buffers processed fragments and emits them in sequence_number order.
    Fragments that complete out of order are held until the expected
    sequence becomes available.

    Features:
    - Priority queue based on sequence_number
    - Async blocking get for ordered delivery
    - Non-blocking try_get for polling
    - Duplicate detection
    """

    def __init__(
        self,
        stream_id: str,
        start_sequence: int = 0,
    ):
        """Initialize the fragment queue.

        Args:
            stream_id: Stream identifier for this queue
            start_sequence: Initial expected sequence number (default 0)
        """
        self._stream_id = stream_id
        self._next_expected_sequence = start_sequence

        # Priority queue: (sequence_number, FragmentResult)
        self._heap: list[tuple[int, FragmentResult]] = []

        # Track seen sequence numbers to detect duplicates
        self._seen_sequences: set[int] = set()

        # Event for signaling when new results are available
        self._new_result_event = asyncio.Event()

        # Lock for thread safety
        self._lock = asyncio.Lock()

    @property
    def stream_id(self) -> str:
        """Return the stream ID for this queue."""
        return self._stream_id

    @property
    def next_expected_sequence(self) -> int:
        """Return the next expected sequence number."""
        return self._next_expected_sequence

    @property
    def pending_count(self) -> int:
        """Return the number of pending (buffered) fragments."""
        return len(self._heap)

    @property
    def is_complete(self) -> bool:
        """Return True if queue is empty (all fragments delivered)."""
        return len(self._heap) == 0

    def add_result(self, result: FragmentResult) -> bool:
        """Add a processed fragment result to the queue.

        Fragments are buffered and will be emitted in sequence order.
        Duplicate sequence numbers are ignored.

        Args:
            result: Processed fragment result

        Returns:
            True if added, False if duplicate
        """
        seq = result.sequence_number

        # Check for duplicate
        if seq in self._seen_sequences:
            return False

        # Add to heap and track
        heapq.heappush(self._heap, (seq, result))
        self._seen_sequences.add(seq)

        # Signal that a new result is available
        self._new_result_event.set()

        return True

    async def get_next_in_order(self) -> FragmentResult:
        """Get the next fragment in sequence order.

        Blocks until the expected sequence number is available.
        Updates next_expected_sequence after returning.

        Returns:
            FragmentResult with the next expected sequence number
        """
        while True:
            # Check if next expected is available
            result = self.try_get_next()
            if result is not None:
                return result

            # Wait for new results
            self._new_result_event.clear()
            await self._new_result_event.wait()

    def try_get_next(self) -> FragmentResult | None:
        """Try to get the next fragment in sequence order.

        Non-blocking version that returns None if the expected
        sequence is not yet available.

        Returns:
            FragmentResult if available, None otherwise
        """
        if not self._heap:
            return None

        # Peek at the smallest sequence number
        next_seq, _ = self._heap[0]

        if next_seq != self._next_expected_sequence:
            return None

        # Pop and return
        _, result = heapq.heappop(self._heap)
        self._next_expected_sequence += 1

        return result

    def clear(self) -> None:
        """Clear all pending fragments and reset state."""
        self._heap.clear()
        self._seen_sequences.clear()
        self._next_expected_sequence = 0
        self._new_result_event.clear()

    def peek_next_available(self) -> int | None:
        """Peek at the next available sequence number.

        Returns:
            Smallest sequence number in queue, or None if empty
        """
        if not self._heap:
            return None
        return self._heap[0][0]

    def get_gap_info(self) -> dict:
        """Get information about gaps in the sequence.

        Returns:
            Dict with gap analysis:
            - expected: next expected sequence
            - available: list of available sequences
            - missing: list of missing sequences between expected and max
        """
        if not self._heap:
            return {
                "expected": self._next_expected_sequence,
                "available": [],
                "missing": [],
            }

        available = sorted(seq for seq, _ in self._heap)
        max_seq = max(available)
        all_needed = set(range(self._next_expected_sequence, max_seq + 1))
        missing = sorted(all_needed - set(available))

        return {
            "expected": self._next_expected_sequence,
            "available": available,
            "missing": missing,
        }
