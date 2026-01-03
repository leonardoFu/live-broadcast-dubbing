"""
A/V synchronization manager.

Manages synchronization between video and dubbed audio streams.

Per spec 003:
- Video held in buffer until matching dubbed audio ready
- PTS-based synchronization
- Drift detection and gradual slew correction
- 6-second default offset for STS processing latency
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
    """Paired video and audio segments for output.

    Attributes:
        video_segment: VideoSegment with video data
        video_data: Raw video buffer data
        audio_segment: AudioSegment (dubbed or original)
        audio_data: Audio data for output
        pts_ns: Output PTS in nanoseconds
    """

    video_segment: VideoSegment
    video_data: bytes
    audio_segment: AudioSegment
    audio_data: bytes
    pts_ns: int


class AvSyncManager:
    """Manages A/V synchronization for dubbing pipeline.

    Coordinates video and dubbed audio output timing:
    - Buffers video segments until corresponding audio is ready
    - Applies PTS offset to account for STS processing latency
    - Detects and corrects drift between video and audio
    - Supports fallback to original audio when circuit breaker trips

    Attributes:
        state: AvSyncState for PTS calculations
        _video_buffer: Queue of waiting video segments
        _audio_buffer: Dict of batch_number -> (AudioSegment, data)
        _ready_pairs: Queue of ready SyncPairs for output
    """

    def __init__(
        self,
        av_offset_ns: int = 6_000_000_000,
        drift_threshold_ns: int = 120_000_000,
        max_buffer_size: int = 10,
    ) -> None:
        """Initialize A/V sync manager.

        Args:
            av_offset_ns: Base PTS offset in nanoseconds (default 6s)
            drift_threshold_ns: Drift threshold for correction (default 120ms)
            max_buffer_size: Maximum segments to buffer
        """
        self.state = AvSyncState(
            av_offset_ns=av_offset_ns,
            drift_threshold_ns=drift_threshold_ns,
        )
        self.max_buffer_size = max_buffer_size

        # Segment buffers: (segment, data)
        self._video_buffer: deque[tuple[VideoSegment, bytes]] = deque()
        self._audio_buffer: dict[int, tuple[AudioSegment, bytes]] = {}
        self._ready_pairs: deque[SyncPair] = deque()
        self._lock = asyncio.Lock()

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
                    f"Video buffer full ({self.max_buffer_size}), "
                    "dropping oldest segment"
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
                    return self._create_pair(
                        video_segment, video_data, segment, data
                    )

            # Buffer audio and wait for video
            if len(self._audio_buffer) >= self.max_buffer_size:
                logger.warning(
                    f"Audio buffer full ({self.max_buffer_size}), "
                    "dropping oldest entry"
                )
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
        """Create synchronized pair from video and audio segments.

        Args:
            video_segment: VideoSegment metadata
            video_data: Video data bytes
            audio_segment: AudioSegment metadata
            audio_data: Audio data bytes

        Returns:
            SyncPair ready for output
        """
        # Calculate output PTS with offset
        video_pts = self.state.adjust_video_pts(video_segment.t0_ns)
        audio_pts = self.state.adjust_audio_pts(audio_segment.t0_ns)

        # Update sync state for drift detection
        self.state.update_sync_state(video_pts, audio_pts)

        # Check for drift correction
        if self.state.needs_correction():
            adjustment = self.state.apply_slew_correction()
            logger.info(
                f"Drift correction applied: delta={self.state.sync_delta_ms:.1f}ms, "
                f"adjustment={adjustment / 1e6:.1f}ms"
            )

        pair = SyncPair(
            video_segment=video_segment,
            video_data=video_data,
            audio_segment=audio_segment,
            audio_data=audio_data,
            pts_ns=video_pts,
        )

        # Log pair creation at INFO level for visibility during debugging
        logger.info(
            f"✅ A/V PAIR CREATED: batch={video_segment.batch_number}, "
            f"pts={video_pts / 1e9:.2f}s, "
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
                    audio_segment, audio_data = self._audio_buffer.pop(
                        video_segment.batch_number
                    )
                    matched_indices.append(i)
                    pairs.append(
                        self._create_pair(
                            video_segment, video_data, audio_segment, audio_data
                        )
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
                    audio_segment, audio_data = self._audio_buffer.pop(
                        video_segment.batch_number
                    )
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
                    self._create_pair(
                        video_segment, video_data, audio_segment, audio_data
                    )
                )

        return pairs

    def reset(self) -> None:
        """Reset sync manager state.

        Clears buffers and resets sync state.
        """
        self._video_buffer.clear()
        self._audio_buffer.clear()
        self._ready_pairs.clear()
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

    @property
    def av_offset_ms(self) -> float:
        """Current A/V offset in milliseconds."""
        return self.state.av_offset_ms

    @property
    def needs_correction(self) -> bool:
        """Check if drift correction is needed."""
        return self.state.needs_correction()
