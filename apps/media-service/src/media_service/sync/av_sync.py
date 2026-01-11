"""
A/V synchronization manager with PTS-based segment pairing.

Manages synchronization between video and dubbed audio streams.

Per spec 003 and 024:
- Video held in buffer until matching dubbed audio ready
- PTS-based synchronization using range overlap detection
- Drift detection and gradual slew correction
- 6-second default offset for STS processing latency
- Support for variable-length VAD audio segments (1-15s)
- One-to-many audio pairing (single audio with multiple videos)
"""

from __future__ import annotations

import asyncio
import bisect
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from media_service.models.segments import AudioSegment, VideoSegment
from media_service.models.state import AvSyncState

logger = logging.getLogger(__name__)


@dataclass
class AudioBufferEntry:
    """Wrapper for buffered audio with output tracking.

    Supports one-to-many pairing where a single audio segment
    can pair with multiple video segments that overlap its PTS range.
    Audio is only OUTPUT once, but can "cover" multiple videos.

    Attributes:
        audio_segment: The underlying AudioSegment metadata
        audio_data: Raw audio bytes
        paired_video_pts: Set of video t0_ns values that have paired with this audio
        insertion_time_ns: Wall-clock time when audio was buffered (for debugging)
        audio_output: Whether this audio has been pushed to output pipeline

    Invariants:
        - audio_segment.t0_ns is immutable after creation
        - audio_segment.duration_ns is immutable after creation
        - paired_video_pts only grows (videos are never "unpaired")
        - audio_output transitions from False to True exactly once
    """

    audio_segment: AudioSegment
    audio_data: bytes
    paired_video_pts: set[int] = field(default_factory=set)
    insertion_time_ns: int = 0
    audio_output: bool = False  # Track if audio has been pushed to output

    @property
    def t0_ns(self) -> int:
        """Start PTS in nanoseconds - key for sorting."""
        return self.audio_segment.t0_ns

    @property
    def end_ns(self) -> int:
        """End PTS in nanoseconds - for overlap calculation."""
        return self.audio_segment.t0_ns + self.audio_segment.duration_ns

    @property
    def duration_ns(self) -> int:
        """Duration in nanoseconds."""
        return self.audio_segment.duration_ns

    def should_evict(self, safe_eviction_pts: int) -> bool:
        """Check if audio can be safely evicted.

        Audio is evicted when its end PTS is at or before the safe
        eviction watermark, meaning no future videos can overlap.

        Args:
            safe_eviction_pts: Watermark calculated as
                max_video_pts_seen - (3 * VIDEO_SEGMENT_DURATION_NS)

        Returns:
            True if audio should be evicted
        """
        return self.end_ns <= safe_eviction_pts


@dataclass
class VideoBufferEntry:
    """Wrapper for buffered video with timeout tracking.

    Videos are buffered when they arrive before matching audio.
    Timeout tracking enables fallback to original audio when
    dubbed audio is not available within threshold.

    Attributes:
        video_segment: The underlying VideoSegment metadata
        video_data: Raw video bytes
        insertion_time_ns: Wall-clock time when video was buffered

    Invariants:
        - video_segment.t0_ns is immutable after creation
        - video_segment.duration_ns is immutable after creation
        - insertion_time_ns is wall-clock, NOT PTS
    """

    video_segment: VideoSegment
    video_data: bytes
    insertion_time_ns: int = 0

    @property
    def t0_ns(self) -> int:
        """Video start PTS in nanoseconds."""
        return self.video_segment.t0_ns

    @property
    def end_ns(self) -> int:
        """Video end PTS in nanoseconds."""
        return self.video_segment.t0_ns + self.video_segment.duration_ns

    @property
    def duration_ns(self) -> int:
        """Duration in nanoseconds."""
        return self.video_segment.duration_ns

    def should_fallback(
        self,
        current_time_ns: int,
        timeout_ns: int = 10_000_000_000,
    ) -> bool:
        """Check if video has waited too long for matching audio.

        Args:
            current_time_ns: Current wall-clock time in nanoseconds
            timeout_ns: Maximum wait time (default 10 seconds)

        Returns:
            True if video should use fallback audio
        """
        age_ns = current_time_ns - self.insertion_time_ns
        return age_ns >= timeout_ns


@dataclass
class SyncPair:
    """Paired video and audio segments for output.

    Attributes:
        video_segment: VideoSegment with video data
        video_data: Raw video buffer data
        audio_segment: AudioSegment (dubbed or original)
        audio_data: Audio data for output
        video_pts_ns: Video output PTS in nanoseconds
        audio_pts_ns: Audio output PTS in nanoseconds
        output_audio: Whether to output audio (False if already output by previous pair)
    """

    video_segment: VideoSegment
    video_data: bytes
    audio_segment: AudioSegment
    audio_data: bytes
    video_pts_ns: int
    audio_pts_ns: int
    output_audio: bool = True  # Only output audio once per audio segment

    @property
    def pts_ns(self) -> int:
        """Video PTS for backward compatibility."""
        return self.video_pts_ns


class AvSyncManager:
    """Manages A/V synchronization for dubbing pipeline with PTS-based matching.

    Coordinates video and dubbed audio output timing:
    - Buffers video segments until corresponding audio is ready
    - Uses PTS range overlap detection for segment matching
    - Supports variable-length VAD audio segments (1-15s)
    - One-to-many pairing: single audio can match multiple videos
    - Applies PTS offset to account for STS processing latency
    - Detects and corrects drift between video and audio
    - Supports fallback to original audio when circuit breaker trips

    Attributes:
        state: AvSyncState for PTS calculations
        _video_buffer: List of VideoBufferEntry waiting for audio
        _audio_buffer: Sorted list of AudioBufferEntry by t0_ns
        _ready_pairs: Queue of ready SyncPairs for output
        _max_video_pts_seen: Highest video end PTS seen (for eviction watermark)
    """

    # Constants
    VIDEO_SEGMENT_DURATION_NS: ClassVar[int] = 6_000_000_000  # 6 seconds
    FALLBACK_TIMEOUT_NS: ClassVar[int] = 10_000_000_000  # 10 seconds

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

        # Segment buffers - PTS-based
        self._video_buffer: list[VideoBufferEntry] = []
        self._audio_buffer: list[AudioBufferEntry] = []  # Sorted by t0_ns
        self._ready_pairs: deque[SyncPair] = deque()
        self._lock = asyncio.Lock()

        # Track max video PTS for safe eviction
        self._max_video_pts_seen: int = 0

    def _overlaps(
        self,
        video_t0: int,
        video_end: int,
        audio_t0: int,
        audio_end: int,
    ) -> bool:
        """Check if video and audio PTS ranges overlap.

        Uses strict inequality per spec: segments touching at exact
        boundaries do NOT overlap.

        Args:
            video_t0: Video start PTS in nanoseconds
            video_end: Video end PTS in nanoseconds
            audio_t0: Audio start PTS in nanoseconds
            audio_end: Audio end PTS in nanoseconds

        Returns:
            True if ranges overlap (not just touch)
        """
        return video_t0 < audio_end and audio_t0 < video_end

    def _insert_audio(self, entry: AudioBufferEntry) -> None:
        """Insert audio entry maintaining sorted order by t0_ns.

        Uses bisect for O(n) insertion into sorted list.

        Args:
            entry: AudioBufferEntry to insert
        """
        # Check buffer size limit
        if len(self._audio_buffer) >= self.max_buffer_size:
            logger.warning(
                f"Audio buffer full ({self.max_buffer_size}), dropping oldest entry"
            )
            self._audio_buffer.pop(0)

        # Find insertion point using bisect
        keys = [e.t0_ns for e in self._audio_buffer]
        idx = bisect.bisect_left(keys, entry.t0_ns)
        self._audio_buffer.insert(idx, entry)

    def _find_overlapping_audio(
        self,
        video_entry: VideoBufferEntry,
    ) -> list[AudioBufferEntry]:
        """Find all audio entries that overlap with video PTS range.

        Args:
            video_entry: VideoBufferEntry to match

        Returns:
            List of overlapping AudioBufferEntry objects
        """
        return [
            audio
            for audio in self._audio_buffer
            if self._overlaps(
                video_entry.t0_ns,
                video_entry.end_ns,
                audio.t0_ns,
                audio.end_ns,
            )
        ]

    def _select_best_overlap(
        self,
        video_entry: VideoBufferEntry,
        candidates: list[AudioBufferEntry],
    ) -> AudioBufferEntry | None:
        """Select audio with maximum overlap when multiple candidates exist.

        Args:
            video_entry: VideoBufferEntry to match
            candidates: List of overlapping AudioBufferEntry objects

        Returns:
            AudioBufferEntry with maximum overlap, or None if empty
        """
        if not candidates:
            return None

        def overlap_amount(audio: AudioBufferEntry) -> int:
            overlap_start = max(video_entry.t0_ns, audio.t0_ns)
            overlap_end = min(video_entry.end_ns, audio.end_ns)
            return max(0, overlap_end - overlap_start)

        return max(candidates, key=overlap_amount)

    def _evict_stale_audio(self) -> None:
        """Remove audio that cannot overlap with future videos.

        Uses safe eviction watermark: max_video_pts_seen - (3 * VIDEO_SEGMENT_DURATION_NS)
        This provides 18-second tolerance for out-of-order video arrival.
        """
        safe_eviction_pts = self._max_video_pts_seen - (
            3 * self.VIDEO_SEGMENT_DURATION_NS
        )

        if safe_eviction_pts <= 0:
            return

        # Count evicted entries for logging
        initial_count = len(self._audio_buffer)

        # Remove audio entries that end before watermark
        self._audio_buffer = [
            entry
            for entry in self._audio_buffer
            if not entry.should_evict(safe_eviction_pts)
        ]

        evicted_count = initial_count - len(self._audio_buffer)
        if evicted_count > 0:
            logger.debug(
                f"Evicted {evicted_count} audio entries, "
                f"watermark={safe_eviction_pts / 1e9:.2f}s, "
                f"remaining={len(self._audio_buffer)}"
            )

    async def push_video(
        self,
        segment: VideoSegment,
        data: bytes,
    ) -> SyncPair | None:
        """Push video segment and check for ready pair using PTS matching.

        Args:
            segment: VideoSegment metadata
            data: Raw video data

        Returns:
            SyncPair if matching audio available, None otherwise
        """
        async with self._lock:
            entry = VideoBufferEntry(
                video_segment=segment,
                video_data=data,
                insertion_time_ns=time.time_ns(),
            )

            # Update max video PTS seen for eviction watermark
            self._max_video_pts_seen = max(self._max_video_pts_seen, entry.end_ns)

            # Find overlapping audio using PTS
            candidates = self._find_overlapping_audio(entry)
            best_audio = self._select_best_overlap(entry, candidates)

            if best_audio is not None:
                # Track that this video paired with this audio
                best_audio.paired_video_pts.add(entry.t0_ns)

                # Only output audio if it hasn't been output yet
                should_output_audio = not best_audio.audio_output
                if should_output_audio:
                    best_audio.audio_output = True

                logger.info(
                    f"Video paired via PTS overlap: "
                    f"video={entry.t0_ns / 1e9:.2f}-{entry.end_ns / 1e9:.2f}s, "
                    f"audio={best_audio.t0_ns / 1e9:.2f}-{best_audio.end_ns / 1e9:.2f}s, "
                    f"output_audio={should_output_audio}"
                )

                # Run eviction check
                self._evict_stale_audio()

                return self._create_pair(
                    entry.video_segment,
                    entry.video_data,
                    best_audio.audio_segment,
                    best_audio.audio_data,
                    output_audio=should_output_audio,
                )

            # Buffer video and wait for audio
            if len(self._video_buffer) >= self.max_buffer_size:
                logger.warning(
                    f"Video buffer full ({self.max_buffer_size}), dropping oldest segment"
                )
                self._video_buffer.pop(0)

            self._video_buffer.append(entry)
            logger.debug(
                f"Video buffered: pts={entry.t0_ns / 1e9:.2f}-{entry.end_ns / 1e9:.2f}s, "
                f"buffer_size={len(self._video_buffer)}"
            )

            # Run eviction even when no pair (watermark still advances)
            self._evict_stale_audio()

            return None

    async def push_audio(
        self,
        segment: AudioSegment,
        data: bytes,
    ) -> list[SyncPair] | None:
        """Push audio segment and check for ready pairs using PTS matching.

        Supports one-to-many pairing: a single audio segment can match
        multiple video segments that overlap its PTS range.
        Audio is only OUTPUT once (first pair), subsequent pairs have output_audio=False.

        Args:
            segment: AudioSegment metadata (dubbed or original)
            data: Audio data (from file or dubbed bytes)

        Returns:
            List of SyncPairs if matching videos found, None otherwise
        """
        async with self._lock:
            entry = AudioBufferEntry(
                audio_segment=segment,
                audio_data=data,
                paired_video_pts=set(),
                insertion_time_ns=time.time_ns(),
                audio_output=False,
            )

            pairs: list[SyncPair] = []
            matched_indices: list[int] = []

            # Find all overlapping videos and sort by PTS for deterministic output order
            overlapping_videos: list[tuple[int, VideoBufferEntry]] = []
            for i, video in enumerate(self._video_buffer):
                if self._overlaps(
                    video.t0_ns,
                    video.end_ns,
                    entry.t0_ns,
                    entry.end_ns,
                ):
                    overlapping_videos.append((i, video))

            # Sort by video PTS to ensure audio is output with earliest video
            overlapping_videos.sort(key=lambda x: x[1].t0_ns)

            # Create pairs - only first pair outputs audio
            for i, video in overlapping_videos:
                entry.paired_video_pts.add(video.t0_ns)
                matched_indices.append(i)

                # Only output audio with first (earliest) video
                should_output_audio = not entry.audio_output
                if should_output_audio:
                    entry.audio_output = True

                pairs.append(
                    self._create_pair(
                        video.video_segment,
                        video.video_data,
                        entry.audio_segment,
                        entry.audio_data,
                        output_audio=should_output_audio,
                    )
                )

            # Remove matched videos (reverse order to preserve indices)
            for i in sorted(matched_indices, reverse=True):
                del self._video_buffer[i]

            if pairs:
                logger.info(
                    f"Audio paired with {len(pairs)} videos via PTS overlap: "
                    f"audio={entry.t0_ns / 1e9:.2f}-{entry.end_ns / 1e9:.2f}s, "
                    f"audio_output_with_first_video=True"
                )

            # Buffer audio for future video matching (audio_output state preserved)
            self._insert_audio(entry)
            logger.debug(
                f"Audio buffered: pts={entry.t0_ns / 1e9:.2f}-{entry.end_ns / 1e9:.2f}s, "
                f"dubbed={segment.is_dubbed}, audio_output={entry.audio_output}, "
                f"buffer_size={len(self._audio_buffer)}"
            )

            # Run eviction
            self._evict_stale_audio()

            return pairs if pairs else None

    async def check_timeouts(
        self,
        get_original_audio: Callable[[AudioSegment], Awaitable[bytes]],
        current_time_ns: int | None = None,
    ) -> list[SyncPair]:
        """Check for timed-out videos and create fallback pairs.

        Videos that have waited too long for matching audio will use
        original audio as fallback.

        Args:
            get_original_audio: Async callback to fetch fallback audio data
            current_time_ns: Current time in nanoseconds (for testing)

        Returns:
            List of fallback SyncPairs for timed-out videos
        """
        if current_time_ns is None:
            current_time_ns = time.time_ns()

        pairs: list[SyncPair] = []
        timed_out_indices: list[int] = []

        async with self._lock:
            for i, video in enumerate(self._video_buffer):
                if video.should_fallback(current_time_ns, self.FALLBACK_TIMEOUT_NS):
                    timed_out_indices.append(i)

                    # Create fallback audio segment with matching PTS
                    fallback_segment = AudioSegment(
                        fragment_id=f"{video.video_segment.fragment_id}_fallback",
                        stream_id=video.video_segment.stream_id,
                        batch_number=video.video_segment.batch_number,
                        t0_ns=video.video_segment.t0_ns,
                        duration_ns=video.video_segment.duration_ns,
                        file_path=Path("/tmp/fallback.m4a"),
                    )
                    fallback_data = await get_original_audio(fallback_segment)

                    logger.info(
                        f"Video timeout, using fallback audio: "
                        f"pts={video.t0_ns / 1e9:.2f}-{video.end_ns / 1e9:.2f}s"
                    )

                    pairs.append(
                        self._create_pair(
                            video.video_segment,
                            video.video_data,
                            fallback_segment,
                            fallback_data,
                        )
                    )

            # Remove timed-out videos (reverse order)
            for i in reversed(timed_out_indices):
                del self._video_buffer[i]

        return pairs

    def _create_pair(
        self,
        video_segment: VideoSegment,
        video_data: bytes,
        audio_segment: AudioSegment,
        audio_data: bytes,
        output_audio: bool = True,
    ) -> SyncPair:
        """Create synchronized pair from video and audio segments.

        Args:
            video_segment: VideoSegment metadata
            video_data: Video data bytes
            audio_segment: AudioSegment metadata
            audio_data: Audio data bytes
            output_audio: Whether to output audio (False if already output)

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
            video_pts_ns=video_pts,
            audio_pts_ns=audio_pts,
            output_audio=output_audio,
        )

        # Log pair creation at INFO level for visibility during debugging
        v_start_s = video_segment.t0_ns / 1e9
        v_end_s = (video_segment.t0_ns + video_segment.duration_ns) / 1e9
        a_start_s = audio_segment.t0_ns / 1e9
        a_end_s = (audio_segment.t0_ns + audio_segment.duration_ns) / 1e9
        logger.info(
            f"A/V PAIR CREATED: video_pts={v_start_s:.2f}-{v_end_s:.2f}s, "
            f"audio_pts={a_start_s:.2f}-{a_end_s:.2f}s, dubbed={audio_segment.is_dubbed}, "
            f"output_audio={output_audio}"
        )

        return pair

    async def get_ready_pairs(self) -> list[SyncPair]:
        """Get all ready pairs from buffers.

        Matches any video segments that have corresponding audio using PTS overlap.
        Audio is only output once per audio segment.

        Returns:
            List of SyncPairs ready for output
        """
        pairs: list[SyncPair] = []

        async with self._lock:
            matched_indices: list[int] = []

            for i, video in enumerate(self._video_buffer):
                candidates = self._find_overlapping_audio(video)
                best_audio = self._select_best_overlap(video, candidates)

                if best_audio is not None:
                    best_audio.paired_video_pts.add(video.t0_ns)
                    matched_indices.append(i)

                    # Only output audio if not already output
                    should_output_audio = not best_audio.audio_output
                    if should_output_audio:
                        best_audio.audio_output = True

                    pairs.append(
                        self._create_pair(
                            video.video_segment,
                            video.video_data,
                            best_audio.audio_segment,
                            best_audio.audio_data,
                            output_audio=should_output_audio,
                        )
                    )

            # Remove matched video segments (reverse order to preserve indices)
            for i in reversed(matched_indices):
                del self._video_buffer[i]

            # Run eviction
            self._evict_stale_audio()

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
                video = self._video_buffer.pop(0)

                # Check for overlapping audio first
                candidates = self._find_overlapping_audio(video)
                best_audio = self._select_best_overlap(video, candidates)

                if best_audio is not None:
                    best_audio.paired_video_pts.add(video.t0_ns)
                    audio_segment = best_audio.audio_segment
                    audio_data = best_audio.audio_data

                    # Track audio output state
                    should_output_audio = not best_audio.audio_output
                    if should_output_audio:
                        best_audio.audio_output = True
                else:
                    # Create fallback audio segment - always output
                    audio_segment = AudioSegment(
                        fragment_id=video.video_segment.fragment_id + "_fallback",
                        stream_id=video.video_segment.stream_id,
                        batch_number=video.video_segment.batch_number,
                        t0_ns=video.video_segment.t0_ns,
                        duration_ns=video.video_segment.duration_ns,
                        file_path=Path("/tmp/fallback.m4a"),
                    )
                    audio_data = await get_original_audio(audio_segment)
                    should_output_audio = True  # Fallback audio always output

                pairs.append(
                    self._create_pair(
                        video.video_segment,
                        video.video_data,
                        audio_segment,
                        audio_data,
                        output_audio=should_output_audio,
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
        self._max_video_pts_seen = 0
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
