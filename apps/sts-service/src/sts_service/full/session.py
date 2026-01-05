"""Session management for Full STS Service.

Provides StreamSession dataclass and SessionStore for managing per-connection state
with pipeline coordination and processing tracking.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sts_service.full.models.stream import StreamState

if TYPE_CHECKING:
    from sts_service.full.models.fragment import FragmentResult
    from sts_service.full.pipeline import PipelineCoordinator


@dataclass
class SessionStatistics:
    """Statistics tracked per session.

    Used to generate stream:complete statistics per spec 021.
    """

    total_fragments: int = 0
    success_count: int = 0
    partial_count: int = 0
    failed_count: int = 0
    total_processing_time_ms: float = 0.0
    processing_times: list[float] = field(default_factory=list)

    @property
    def avg_processing_time_ms(self) -> float:
        """Calculate average processing time."""
        if self.total_fragments == 0:
            return 0.0
        return self.total_processing_time_ms / self.total_fragments

    @property
    def p95_processing_time_ms(self) -> float:
        """Calculate 95th percentile processing time."""
        if not self.processing_times:
            return 0.0
        sorted_times = sorted(self.processing_times)
        idx = int(len(sorted_times) * 0.95)
        return float(sorted_times[min(idx, len(sorted_times) - 1)])

    def record_fragment(
        self,
        status: str,
        processing_time_ms: float,
    ) -> None:
        """Record statistics for a processed fragment.

        Args:
            status: Fragment processing status (success, partial, failed).
            processing_time_ms: Time taken to process the fragment.
        """
        self.total_fragments += 1
        self.total_processing_time_ms += processing_time_ms
        self.processing_times.append(processing_time_ms)

        if status == "success":
            self.success_count += 1
        elif status == "partial":
            self.partial_count += 1
        elif status == "failed":
            self.failed_count += 1


@dataclass
class StreamSession:
    """Per-stream session state managed by the Full STS service.

    Each Socket.IO connection has exactly one StreamSession.
    Extends Echo STS pattern with pipeline coordinator and fragment queue.
    """

    # Identity
    sid: str  # Socket.IO session ID
    stream_id: str  # Client-provided stream ID
    worker_id: str  # Client-provided worker ID
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # State (uses StreamState enum from models.stream)
    state: StreamState = StreamState.INITIALIZING
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Configuration (from stream:init)
    source_language: str = "en"
    target_language: str = "zh"
    voice_profile: str = "default"
    chunk_duration_ms: int = 6000
    sample_rate_hz: int = 48000
    channels: int = 1
    format: str = "m4a"
    max_inflight: int = 3
    timeout_ms: int = 8000
    domain_hints: Optional[list[str]] = None

    # Pipeline coordinator (initialized on stream:init)
    pipeline_coordinator: Optional["PipelineCoordinator"] = None

    # Flow control
    inflight_count: int = 0
    next_sequence_to_emit: int = 0
    pending_fragments: dict[int, "FragmentResult"] = field(default_factory=dict)

    # Statistics
    statistics: SessionStatistics = field(default_factory=SessionStatistics)

    # Lifecycle
    _stream_end_received: bool = field(default=False, repr=False)

    def transition_to(self, new_state: StreamState) -> bool:
        """Transition to a new state if the transition is valid.

        Valid transitions per spec 021:
        - INITIALIZING -> READY (on stream:ready sent)
        - READY -> PAUSED (on stream:pause received)
        - PAUSED -> READY (on stream:resume received)
        - READY -> ENDING (on stream:end received)
        - PAUSED -> ENDING (on stream:end received)
        - ENDING -> COMPLETED (when all in-flight fragments processed)

        Args:
            new_state: The target state.

        Returns:
            True if the transition was successful, False otherwise.
        """
        valid_transitions: dict[StreamState, set[StreamState]] = {
            StreamState.INITIALIZING: {StreamState.READY},
            StreamState.READY: {StreamState.PAUSED, StreamState.ENDING},
            StreamState.PAUSED: {StreamState.READY, StreamState.ENDING},
            StreamState.ENDING: {StreamState.COMPLETED},
            StreamState.COMPLETED: set(),  # Terminal state
        }

        if new_state in valid_transitions.get(self.state, set()):
            self.state = new_state
            return True
        return False

    def can_accept_fragments(self) -> bool:
        """Check if the session can accept new fragments.

        Returns:
            True if fragments can be accepted.
        """
        return self.state == StreamState.READY

    def mark_stream_end(self) -> None:
        """Mark that stream:end was received."""
        self._stream_end_received = True
        if self.state in (StreamState.READY, StreamState.PAUSED):
            self.transition_to(StreamState.ENDING)

    def is_complete(self) -> bool:
        """Check if the stream is complete.

        Returns:
            True if stream:end was received and all in-flight fragments are done.
        """
        return self._stream_end_received and self.inflight_count == 0

    def increment_inflight(self) -> None:
        """Increment the in-flight fragment count."""
        self.inflight_count += 1

    def decrement_inflight(self) -> None:
        """Decrement the in-flight fragment count."""
        self.inflight_count = max(0, self.inflight_count - 1)

    def add_pending_fragment(
        self,
        sequence_number: int,
        result: "FragmentResult",
    ) -> None:
        """Add a processed fragment to the pending buffer.

        Args:
            sequence_number: The sequence number of the fragment.
            result: The processed fragment result.
        """
        self.pending_fragments[sequence_number] = result

    def get_fragments_to_emit(self) -> list["FragmentResult"]:
        """Get fragments that can be emitted in order.

        Returns:
            List of fragments that can be emitted, in sequence order.
        """
        fragments = []
        while self.next_sequence_to_emit in self.pending_fragments:
            result = self.pending_fragments.pop(self.next_sequence_to_emit)
            fragments.append(result)
            self.next_sequence_to_emit += 1
        return fragments

    def duration_ms(self) -> int:
        """Calculate session duration in milliseconds."""
        delta = datetime.utcnow() - self.created_at
        return int(delta.total_seconds() * 1000)


class SessionStore:
    """Thread-safe in-memory session store.

    Manages StreamSession instances indexed by both Socket.IO sid
    and stream_id for efficient lookup.
    """

    def __init__(self) -> None:
        """Initialize the session store."""
        self._sessions: dict[str, StreamSession] = {}  # sid -> session
        self._stream_to_sid: dict[str, str] = {}  # stream_id -> sid
        self._lock = asyncio.Lock()

    async def create(
        self,
        sid: str,
        stream_id: str,
        worker_id: str,
    ) -> StreamSession:
        """Create a new session.

        Args:
            sid: Socket.IO session ID.
            stream_id: Client-provided stream ID.
            worker_id: Client-provided worker ID.

        Returns:
            The newly created StreamSession.
        """
        async with self._lock:
            session = StreamSession(
                sid=sid,
                stream_id=stream_id,
                worker_id=worker_id,
            )
            self._sessions[sid] = session
            self._stream_to_sid[stream_id] = sid
            return session

    async def get_by_sid(self, sid: str) -> StreamSession | None:
        """Get session by Socket.IO session ID.

        Args:
            sid: Socket.IO session ID.

        Returns:
            The session, or None if not found.
        """
        return self._sessions.get(sid)

    async def get_by_stream_id(self, stream_id: str) -> StreamSession | None:
        """Get session by stream ID.

        Args:
            stream_id: Client-provided stream ID.

        Returns:
            The session, or None if not found.
        """
        sid = self._stream_to_sid.get(stream_id)
        return self._sessions.get(sid) if sid else None

    async def delete(self, sid: str) -> StreamSession | None:
        """Delete session by Socket.IO session ID.

        Args:
            sid: Socket.IO session ID.

        Returns:
            The deleted session, or None if not found.
        """
        async with self._lock:
            session = self._sessions.pop(sid, None)
            if session:
                self._stream_to_sid.pop(session.stream_id, None)
            return session

    async def delete_by_stream_id(self, stream_id: str) -> StreamSession | None:
        """Delete session by stream ID.

        Args:
            stream_id: Client-provided stream ID.

        Returns:
            The deleted session, or None if not found.
        """
        sid = self._stream_to_sid.get(stream_id)
        if sid:
            return await self.delete(sid)
        return None

    def count(self) -> int:
        """Return number of active sessions."""
        return len(self._sessions)

    async def get_all(self) -> list[StreamSession]:
        """Get all active sessions.

        Returns:
            List of all active sessions.
        """
        return list(self._sessions.values())
