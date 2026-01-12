"""
A/V synchronization manager.

Manages synchronization between video and dubbed audio streams.

Per spec 003 (updated by spec 021-fragment-length-30s):
- Buffer-and-wait approach (av_offset_ns removed)
- Video held in buffer until matching dubbed audio ready
- Output PTS reset to 0 (re-encoded, not original stream PTS)
- Drift correction code removed (FR-013)
- 30-second segments (increased from 6s)
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from media_service.models.segments import AudioSegment, VideoSegment
from media_service.models.state import AvSyncState

logger = logging.getLogger(__name__)


@dataclass
class SyncPair:
    """Paired video and audio segments for output (spec 021).

    Attributes:
        video_segment: VideoSegment with video data
        video_data: Raw video buffer data
        audio_segment: AudioSegment (dubbed or original)
        audio_data: Audio data for output
        pts_ns: Output PTS in nanoseconds (reset to 0 per spec 021)
        requires_reencode: Whether output needs re-encoding (always True per spec 021)
    """

    video_segment: VideoSegment
    video_data: bytes
    audio_segment: AudioSegment
    audio_data: bytes
    pts_ns: int
    requires_reencode: bool = True  # FR-012: Output is re-encoded


class AvSyncManager:
    """Manages A/V synchronization for dubbing pipeline (buffer-and-wait per spec 021).

    Coordinates video and dubbed audio output timing using buffer-and-wait approach:
    - Buffers video segments until corresponding dubbed audio is ready
    - Output PTS reset to 0 (re-encoded, not original stream PTS)
    - No av_offset_ns (buffer-and-wait instead)
    - No drift correction (FR-013)
    - Supports fallback to original audio when circuit breaker trips

    Attributes:
        state: AvSyncState for sync delta logging
        _video_buffer: Queue of waiting video segments
        _audio_buffer: Dict of batch_number -> (AudioSegment, data)
        _ready_pairs: Queue of ready SyncPairs for output
        _output_pts_counter: Counter for sequential output PTS (starting from 0)
    """

    def __init__(
        self,
        drift_threshold_ns: int = 100_000_000,  # 100ms for logging only (spec 021)
        max_buffer_size: int = 10,
    ) -> None:
        """Initialize A/V sync manager (buffer-and-wait per spec 021).

        Args:
            drift_threshold_ns: Drift threshold for logging warnings (default 100ms)
            max_buffer_size: Maximum segments to buffer
        """
        self.state = AvSyncState(
            drift_threshold_ns=drift_threshold_ns,
        )
        self.max_buffer_size = max_buffer_size

        # Segment buffers: (segment, data)
        self._video_buffer: deque[tuple[VideoSegment, bytes]] = deque()
        self._audio_buffer: dict[int, tuple[AudioSegment, bytes]] = {}
        self._ready_pairs: deque[SyncPair] = deque()
        self._lock = asyncio.Lock()

        # Output PTS counter: starts from 0, increments by segment duration
        self._output_pts_ns = 0

    async def push_video(
        self,
        segment: VideoSegment,
        data: bytes,
    ) -> SyncPair | None:
        """Push video segment and check for ready pair.

        Args:
            segment: VideoSegment metadata
            data: Raw video data

        Returns:
            SyncPair if matching audio available, None otherwise
        """
        async with self._lock:
            # Check if matching audio already available
            if segment.batch_number in self._audio_buffer:
                audio_segment, audio_data = self._audio_buffer.pop(segment.batch_number)
                return self._create_pair(segment, data, audio_segment, audio_data)

            # Buffer video and wait for audio
            if len(self._video_buffer) >= self.max_buffer_size:
                logger.warning(
                    f"Video buffer full ({self.max_buffer_size}), dropping oldest segment"
                )
                self._video_buffer.popleft()

            self._video_buffer.append((segment, data))
            logger.debug(
                f"Video buffered: batch={segment.batch_number}, "
                f"buffer_size={len(self._video_buffer)}"
            )

            return None

    async def push_audio(
        self,
        segment: AudioSegment,
        data: bytes,
    ) -> SyncPair | None:
        """Push audio segment and check for ready pair.

        Args:
            segment: AudioSegment metadata (dubbed or original)
            data: Audio data (from file or dubbed bytes)

        Returns:
            SyncPair if matching video available, None otherwise
        """
        async with self._lock:
            # Find matching video in buffer
            for i, (video_segment, video_data) in enumerate(self._video_buffer):
                if video_segment.batch_number == segment.batch_number:
                    # Remove from buffer and create pair
                    del self._video_buffer[i]
                    return self._create_pair(video_segment, video_data, segment, data)

            # Buffer audio and wait for video
            if len(self._audio_buffer) >= self.max_buffer_size:
                logger.warning(f"Audio buffer full ({self.max_buffer_size}), dropping oldest entry")
                # Remove oldest by batch_number
                oldest = min(self._audio_buffer.keys())
                del self._audio_buffer[oldest]

            self._audio_buffer[segment.batch_number] = (segment, data)
            logger.debug(
                f"Audio buffered: batch={segment.batch_number}, "
                f"dubbed={segment.is_dubbed}, "
                f"buffer_size={len(self._audio_buffer)}"
            )

            return None

    def _create_pair(
        self,
        video_segment: VideoSegment,
        video_data: bytes,
        audio_segment: AudioSegment,
        audio_data: bytes,
    ) -> SyncPair:
        """Create synchronized pair from video and audio segments (spec 021).

        Buffer-and-wait approach:
        - Output PTS starts from 0 and increments by segment duration
        - No av_offset_ns adjustment (FR-013)
        - No drift correction (FR-013)

        Args:
            video_segment: VideoSegment metadata
            video_data: Video data bytes
            audio_segment: AudioSegment metadata
            audio_data: Audio data bytes

        Returns:
            SyncPair ready for output with pts_ns=0 or sequential
        """
        # FR-012: Output PTS starts from 0 (re-encoded output)
        # Use sequential PTS based on batch number * segment duration
        output_pts_ns = video_segment.batch_number * video_segment.duration_ns

        # Update sync state for logging (no correction, just monitoring)
        self.state.update_sync_state(video_segment.t0_ns, audio_segment.t0_ns)

        # Log sync delta if above threshold (for monitoring only, no correction)
        if self.state.sync_delta_ns > self.state.drift_threshold_ns:
            logger.warning(
                f"Sync delta above threshold: delta={self.state.sync_delta_ms:.1f}ms "
                f"(threshold={self.state.drift_threshold_ns / 1e6:.1f}ms)"
            )

        pair = SyncPair(
            video_segment=video_segment,
            video_data=video_data,
            audio_segment=audio_segment,
            audio_data=audio_data,
            pts_ns=output_pts_ns,  # FR-012: Sequential PTS starting from 0
            requires_reencode=True,  # FR-012: Output is re-encoded
        )

        # Log pair creation at INFO level for visibility during debugging
        logger.info(
            f"A/V PAIR CREATED: batch={video_segment.batch_number}, "
            f"output_pts={output_pts_ns / 1e9:.2f}s, "
            f"v_size={len(video_data)}, a_size={len(audio_data)}, "
            f"dubbed={audio_segment.is_dubbed}"
        )

        return pair

    async def get_ready_pairs(self) -> list[SyncPair]:
        """Get all ready pairs from buffers.

        Matches any video segments that have corresponding audio.

        Returns:
            List of SyncPairs ready for output
        """
        pairs: list[SyncPair] = []

        async with self._lock:
            # Find all matches
            matched_indices = []
            for i, (video_segment, video_data) in enumerate(self._video_buffer):
                if video_segment.batch_number in self._audio_buffer:
                    audio_segment, audio_data = self._audio_buffer.pop(video_segment.batch_number)
                    matched_indices.append(i)
                    pairs.append(
                        self._create_pair(video_segment, video_data, audio_segment, audio_data)
                    )

            # Remove matched video segments (reverse order to preserve indices)
            for i in reversed(matched_indices):
                del self._video_buffer[i]

        return pairs

    async def flush_with_fallback(
        self,
        get_original_audio: Callable[[AudioSegment], Awaitable[bytes]],
    ) -> list[SyncPair]:
        """Flush video buffer using original audio as fallback.

        Used when circuit breaker is open or stream ends.

        Args:
            get_original_audio: Async function(AudioSegment) -> bytes
                to get original audio data

        Returns:
            List of SyncPairs using original audio
        """
        pairs: list[SyncPair] = []

        async with self._lock:
            while self._video_buffer:
                video_segment, video_data = self._video_buffer.popleft()

                # Check for buffered audio first
                if video_segment.batch_number in self._audio_buffer:
                    audio_segment, audio_data = self._audio_buffer.pop(video_segment.batch_number)
                else:
                    # Create fallback audio segment
                    audio_segment = AudioSegment(
                        fragment_id=video_segment.fragment_id + "_fallback",
                        stream_id=video_segment.stream_id,
                        batch_number=video_segment.batch_number,
                        t0_ns=video_segment.t0_ns,
                        duration_ns=video_segment.duration_ns,
                        file_path=Path("/tmp/fallback.m4a"),  # Placeholder
                    )
                    audio_data = await get_original_audio(audio_segment)

                pairs.append(
                    self._create_pair(video_segment, video_data, audio_segment, audio_data)
                )

        return pairs

    def reset(self) -> None:
        """Reset sync manager state.

        Clears buffers and resets sync state.
        """
        self._video_buffer.clear()
        self._audio_buffer.clear()
        self._ready_pairs.clear()
        self._output_pts_ns = 0  # Reset output PTS counter
        self.state.reset()
        logger.info("A/V sync manager reset")

    @property
    def video_buffer_size(self) -> int:
        """Number of video segments waiting for audio."""
        return len(self._video_buffer)

    @property
    def audio_buffer_size(self) -> int:
        """Number of audio segments waiting for video."""
        return len(self._audio_buffer)

    @property
    def sync_delta_ms(self) -> float:
        """Current sync delta in milliseconds."""
        return self.state.sync_delta_ms
