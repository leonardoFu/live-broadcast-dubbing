"""
Fragment tracker for managing in-flight STS requests.

Tracks fragments that have been sent but not yet processed,
handles timeouts, and provides correlation for responses.

Per spec 003:
- Track in-flight fragments by fragment_id
- Enforce max_inflight limit
- Timeout handling for stalled fragments
- Sequence number management
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

from media_service.models.segments import AudioSegment
from media_service.sts.models import InFlightFragment

logger = logging.getLogger(__name__)

# Type alias for timeout callback
TimeoutCallback = Callable[[str, AudioSegment], Coroutine[Any, Any, None]]


class FragmentTracker:
    """Tracks in-flight STS fragments and manages timeouts.

    Maintains a mapping of fragment_id to InFlightFragment for correlation
    between sent fragments and processed responses.

    Attributes:
        max_inflight: Maximum concurrent in-flight fragments
        timeout_ms: Fragment timeout in milliseconds
        _fragments: Dict of fragment_id to InFlightFragment
        _sequence_counter: Current sequence number
    """

    DEFAULT_TIMEOUT_MS = 60000  # 60 seconds for 30-second fragments

    def __init__(
        self,
        max_inflight: int = 3,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        """Initialize fragment tracker.

        Args:
            max_inflight: Maximum concurrent in-flight fragments
            timeout_ms: Fragment processing timeout in milliseconds
        """
        self.max_inflight = max_inflight
        self.timeout_ms = timeout_ms

        self._fragments: dict[str, InFlightFragment] = {}
        self._sequence_counter = 0
        self._on_timeout: TimeoutCallback | None = None
        self._lock = asyncio.Lock()

    async def track(self, segment: AudioSegment) -> InFlightFragment:
        """Start tracking a fragment.

        Creates an InFlightFragment and starts timeout timer.

        Args:
            segment: AudioSegment being sent to STS

        Returns:
            InFlightFragment for the tracked segment

        Raises:
            RuntimeError: If max_inflight limit reached
        """
        async with self._lock:
            if len(self._fragments) >= self.max_inflight:
                raise RuntimeError(
                    f"Max in-flight limit reached ({self.max_inflight}). "
                    "Wait for fragment to complete before sending more."
                )

            inflight = InFlightFragment(
                fragment_id=segment.fragment_id,
                segment=segment,
                sent_time=time.monotonic(),
                sequence_number=self._sequence_counter,
            )

            # Start timeout task
            inflight.timeout_task = asyncio.create_task(self._timeout_handler(segment.fragment_id))

            self._fragments[segment.fragment_id] = inflight
            self._sequence_counter += 1

            logger.debug(
                f"Tracking fragment: id={segment.fragment_id}, "
                f"seq={inflight.sequence_number}, "
                f"inflight={len(self._fragments)}"
            )

            return inflight

    async def complete(self, fragment_id: str) -> InFlightFragment | None:
        """Mark fragment as complete and stop tracking.

        Cancels timeout and removes from tracked fragments.

        Args:
            fragment_id: Fragment ID to complete

        Returns:
            The InFlightFragment if found, None otherwise
        """
        async with self._lock:
            inflight = self._fragments.pop(fragment_id, None)

            if inflight is None:
                logger.warning(f"Fragment not found for completion: {fragment_id}")
                return None

            # Cancel timeout task
            if inflight.timeout_task and not inflight.timeout_task.done():
                inflight.timeout_task.cancel()
                try:
                    await inflight.timeout_task
                except asyncio.CancelledError:
                    pass

            elapsed = inflight.elapsed_ms
            logger.debug(
                f"Fragment completed: id={fragment_id}, "
                f"elapsed={elapsed}ms, "
                f"remaining_inflight={len(self._fragments)}"
            )

            return inflight

    async def _timeout_handler(self, fragment_id: str) -> None:
        """Handle fragment timeout.

        Called after timeout_ms if fragment not completed.

        Args:
            fragment_id: Fragment ID that timed out
        """
        await asyncio.sleep(self.timeout_ms / 1000.0)

        async with self._lock:
            inflight = self._fragments.get(fragment_id)
            if inflight is None:
                # Already completed
                return

            logger.warning(
                f"Fragment timeout: id={fragment_id}, "
                f"elapsed={inflight.elapsed_ms}ms, "
                f"timeout={self.timeout_ms}ms"
            )

            # Remove from tracking
            self._fragments.pop(fragment_id, None)

        # Call timeout callback outside lock
        if self._on_timeout:
            try:
                await self._on_timeout(fragment_id, inflight.segment)
            except Exception as e:
                logger.error(f"Error in timeout callback: {e}")

    def set_timeout_callback(self, callback: TimeoutCallback) -> None:
        """Set callback for fragment timeouts.

        Args:
            callback: Async function receiving (fragment_id, segment)
        """
        self._on_timeout = callback

    def get(self, fragment_id: str) -> InFlightFragment | None:
        """Get tracked fragment by ID.

        Args:
            fragment_id: Fragment ID to look up

        Returns:
            InFlightFragment if found, None otherwise
        """
        return self._fragments.get(fragment_id)

    def has_capacity(self) -> bool:
        """Check if tracker has capacity for more fragments.

        Returns:
            True if inflight count < max_inflight
        """
        return len(self._fragments) < self.max_inflight

    @property
    def inflight_count(self) -> int:
        """Current number of in-flight fragments."""
        return len(self._fragments)

    @property
    def sequence_number(self) -> int:
        """Current sequence number (next to be assigned)."""
        return self._sequence_counter

    async def clear(self) -> list[InFlightFragment]:
        """Clear all tracked fragments.

        Cancels all timeout tasks and returns the fragments.

        Returns:
            List of cleared InFlightFragment instances
        """
        async with self._lock:
            fragments = list(self._fragments.values())

            # Cancel all timeout tasks
            for inflight in fragments:
                if inflight.timeout_task and not inflight.timeout_task.done():
                    inflight.timeout_task.cancel()

            self._fragments.clear()
            logger.info(f"Cleared {len(fragments)} tracked fragments")

            return fragments

    def reset_sequence(self) -> None:
        """Reset sequence counter to 0.

        Should only be called when tracker is empty.
        """
        if self._fragments:
            logger.warning("Resetting sequence counter with fragments in flight")
        self._sequence_counter = 0

    def get_oldest_inflight(self) -> InFlightFragment | None:
        """Get the oldest in-flight fragment.

        Returns:
            Oldest InFlightFragment by sent_time, or None if empty
        """
        if not self._fragments:
            return None

        return min(self._fragments.values(), key=lambda f: f.sent_time)

    def get_all_inflight(self) -> list[InFlightFragment]:
        """Get all currently in-flight fragments.

        Returns:
            List of all InFlightFragment instances
        """
        return list(self._fragments.values())
