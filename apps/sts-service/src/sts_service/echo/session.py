"""Session management for Echo STS Service.

Provides StreamSession dataclass and SessionStore for managing
per-connection state.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from sts_service.echo.models.error import ErrorSimulationConfig
    from sts_service.echo.models.fragment import FragmentProcessedPayload

# Session states as defined in data-model.md
SessionState = Literal["initializing", "active", "paused", "ending", "completed"]


@dataclass
class SessionStatistics:
    """Statistics tracked per session.

    Used to generate stream:complete statistics.
    """

    total_fragments: int = 0
    success_count: int = 0
    partial_count: int = 0
    failed_count: int = 0
    total_processing_time_ms: int = 0
    processing_times: list[int] = field(default_factory=list)

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
        processing_time_ms: int,
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
    """Per-stream session state managed by the echo service.

    Each Socket.IO connection has exactly one StreamSession.
    """

    # Identity
    sid: str  # Socket.IO session ID
    stream_id: str  # Client-provided stream ID
    worker_id: str  # Client-provided worker ID
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # State
    state: SessionState = "initializing"
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Configuration (from stream:init)
    source_language: str = "en"
    target_language: str = "es"
    voice_profile: str = "default"
    chunk_duration_ms: int = 1000
    sample_rate_hz: int = 48000
    channels: int = 1
    format: str = "m4a"
    max_inflight: int = 3
    timeout_ms: int = 8000

    # Flow control
    inflight_count: int = 0
    next_sequence_to_emit: int = 0
    pending_fragments: dict[int, "FragmentProcessedPayload"] = field(default_factory=dict)
    fragment_count: int = 0  # Total fragments received (for nth_fragment trigger)

    # Backpressure
    backpressure_enabled: bool = False
    backpressure_threshold: int = 5
    backpressure_active: bool = False

    # Error simulation
    error_simulation: Optional["ErrorSimulationConfig"] = None

    # Processing delay (for testing latency)
    processing_delay_ms: int = 0

    # Statistics
    statistics: SessionStatistics = field(default_factory=SessionStatistics)

    # Lifecycle
    _stream_end_received: bool = field(default=False, repr=False)

    def transition_to(self, new_state: SessionState) -> bool:
        """Transition to a new state if the transition is valid.

        Valid transitions (from data-model.md):
        - initializing -> active (on stream:ready sent)
        - active -> paused (on stream:pause received)
        - paused -> active (on stream:resume received)
        - active -> ending (on stream:end received)
        - paused -> ending (on stream:end received)
        - ending -> completed (when all in-flight fragments processed)

        Args:
            new_state: The target state.

        Returns:
            True if the transition was successful, False otherwise.
        """
        valid_transitions: dict[SessionState, set[SessionState]] = {
            "initializing": {"active"},
            "active": {"paused", "ending"},
            "paused": {"active", "ending"},
            "ending": {"completed"},
            "completed": set(),  # Terminal state
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
        return self.state == "active"

    def mark_stream_end(self) -> None:
        """Mark that stream:end was received."""
        self._stream_end_received = True
        if self.state in ("active", "paused"):
            self.transition_to("ending")

    def is_complete(self) -> bool:
        """Check if the stream is complete.

        Returns:
            True if stream:end was received and all in-flight fragments are done.
        """
        return self._stream_end_received and self.inflight_count == 0

    def increment_inflight(self) -> None:
        """Increment the in-flight fragment count."""
        self.inflight_count += 1
        self.fragment_count += 1

    def decrement_inflight(self) -> None:
        """Decrement the in-flight fragment count."""
        self.inflight_count = max(0, self.inflight_count - 1)

    def add_pending_fragment(
        self,
        sequence_number: int,
        payload: "FragmentProcessedPayload",
    ) -> None:
        """Add a processed fragment to the pending buffer.

        Args:
            sequence_number: The sequence number of the fragment.
            payload: The processed fragment payload.
        """
        self.pending_fragments[sequence_number] = payload

    def get_fragments_to_emit(self) -> list["FragmentProcessedPayload"]:
        """Get fragments that can be emitted in order.

        Returns:
            List of fragments that can be emitted, in sequence order.
        """
        fragments = []
        while self.next_sequence_to_emit in self.pending_fragments:
            payload = self.pending_fragments.pop(self.next_sequence_to_emit)
            fragments.append(payload)
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
