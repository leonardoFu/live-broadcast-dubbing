"""
Segment buffer for accumulating video and audio data.

Accumulates incoming buffers until reaching the configured segment duration
(default 6 seconds), then emits complete segments for disk storage.

Per spec 003:
- 6-second segments for both video and audio
- Partial segments on EOS (minimum 1 second)
- Auto-generated fragment_id (UUID)
- Sequential batch_number increments
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from media_service.models.segments import AudioSegment, VideoSegment

logger = logging.getLogger(__name__)


@dataclass
class BufferAccumulator:
    """Accumulates buffer data and tracks timing.

    Attributes:
        data: Accumulated buffer bytes
        t0_ns: PTS of first buffer in segment
        duration_ns: Total accumulated duration
        buffer_count: Number of buffers accumulated
    """

    data: bytearray = field(default_factory=bytearray)
    t0_ns: int = 0
    duration_ns: int = 0
    buffer_count: int = 0

    def reset(self) -> None:
        """Reset accumulator to initial state."""
        self.data = bytearray()
        self.t0_ns = 0
        self.duration_ns = 0
        self.buffer_count = 0

    def is_empty(self) -> bool:
        """Check if accumulator has no data."""
        return len(self.data) == 0


class SegmentBuffer:
    """Accumulates video and audio buffers into 6-second segments.

    Manages separate accumulators for video and audio streams,
    emitting segments when duration threshold is reached.

    Attributes:
        stream_id: Stream identifier
        segment_duration_ns: Target segment duration in nanoseconds
        segment_dir: Directory for segment file storage
        _video_batch_number: Current video batch number
        _audio_batch_number: Current audio batch number
    """

    # Default 6 seconds in nanoseconds
    DEFAULT_SEGMENT_DURATION_NS = 6_000_000_000
    # Minimum 1 second for partial segments
    MIN_PARTIAL_DURATION_NS = 1_000_000_000

    def __init__(
        self,
        stream_id: str,
        segment_dir: Path,
        segment_duration_ns: int = DEFAULT_SEGMENT_DURATION_NS,
    ) -> None:
        """Initialize segment buffer.

        Args:
            stream_id: Stream identifier for segment naming
            segment_dir: Base directory for segment storage
            segment_duration_ns: Target segment duration (default 6 seconds)
        """
        self.stream_id = stream_id
        self.segment_dir = segment_dir
        self.segment_duration_ns = segment_duration_ns

        self._video_accumulator = BufferAccumulator()
        self._audio_accumulator = BufferAccumulator()
        self._video_batch_number = 0
        self._audio_batch_number = 0

        # Ensure segment directory exists
        self.segment_dir.mkdir(parents=True, exist_ok=True)
        stream_dir = self.segment_dir / self.stream_id
        stream_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"SegmentBuffer initialized: stream_id={stream_id}, "
            f"segment_duration={segment_duration_ns / 1e9:.1f}s"
        )

    def push_video(
        self,
        buffer_data: bytes,
        pts_ns: int,
        duration_ns: int,
    ) -> tuple[VideoSegment | None, bytes]:
        """Push video buffer and return segment if ready.

        Args:
            buffer_data: Raw video buffer data (H.264)
            pts_ns: Buffer presentation timestamp in nanoseconds
            duration_ns: Buffer duration in nanoseconds

        Returns:
            Tuple of (VideoSegment, accumulated_data) if segment ready,
            (None, empty bytes) otherwise
        """
        acc = self._video_accumulator

        # Capture t0 from first buffer
        if acc.is_empty():
            acc.t0_ns = pts_ns

        # Accumulate data
        acc.data.extend(buffer_data)
        acc.duration_ns += duration_ns
        acc.buffer_count += 1

        # Check if segment is ready
        if acc.duration_ns >= self.segment_duration_ns:
            return self._emit_video_segment()

        return None, b""

    def push_audio(
        self,
        buffer_data: bytes,
        pts_ns: int,
        duration_ns: int,
    ) -> tuple[AudioSegment | None, bytes]:
        """Push audio buffer and return segment if ready.

        Args:
            buffer_data: Raw audio buffer data (AAC)
            pts_ns: Buffer presentation timestamp in nanoseconds
            duration_ns: Buffer duration in nanoseconds

        Returns:
            Tuple of (AudioSegment, accumulated_data) if segment ready,
            (None, empty bytes) otherwise
        """
        acc = self._audio_accumulator

        # Capture t0 from first buffer
        if acc.is_empty():
            acc.t0_ns = pts_ns

        # Accumulate data
        acc.data.extend(buffer_data)
        acc.duration_ns += duration_ns
        acc.buffer_count += 1

        # Check if segment is ready
        if acc.duration_ns >= self.segment_duration_ns:
            return self._emit_audio_segment()

        return None, b""

    def flush_video(self) -> tuple[VideoSegment | None, bytes]:
        """Flush remaining video data as partial segment.

        Called on EOS to emit any accumulated data as a partial segment.
        Segments shorter than 1 second are discarded.

        Returns:
            Tuple of (VideoSegment, accumulated_data) if valid partial,
            (None, empty bytes) if no data or too short
        """
        acc = self._video_accumulator

        if acc.is_empty():
            return None, b""

        if acc.duration_ns < self.MIN_PARTIAL_DURATION_NS:
            logger.warning(
                f"Discarding video partial segment: duration {acc.duration_ns / 1e6:.1f}ms < 1s"
            )
            acc.reset()
            return None, b""

        logger.info(f"Flushing video partial segment: {acc.duration_ns / 1e9:.2f}s")
        return self._emit_video_segment()

    def flush_audio(self) -> tuple[AudioSegment | None, bytes]:
        """Flush remaining audio data as partial segment.

        Called on EOS to emit any accumulated data as a partial segment.
        Segments shorter than 1 second are discarded.

        Returns:
            Tuple of (AudioSegment, accumulated_data) if valid partial,
            (None, empty bytes) if no data or too short
        """
        acc = self._audio_accumulator

        if acc.is_empty():
            return None, b""

        if acc.duration_ns < self.MIN_PARTIAL_DURATION_NS:
            logger.warning(
                f"Discarding audio partial segment: duration {acc.duration_ns / 1e6:.1f}ms < 1s"
            )
            acc.reset()
            return None, b""

        logger.info(f"Flushing audio partial segment: {acc.duration_ns / 1e9:.2f}s")
        return self._emit_audio_segment()

    def _emit_video_segment(self) -> tuple[VideoSegment, bytes]:
        """Create and return video segment from accumulated data.

        Returns:
            Tuple of (VideoSegment metadata, accumulated data bytes)
        """
        acc = self._video_accumulator
        data = bytes(acc.data)

        segment = VideoSegment.create(
            stream_id=self.stream_id,
            batch_number=self._video_batch_number,
            t0_ns=acc.t0_ns,
            duration_ns=acc.duration_ns,
            segment_dir=self.segment_dir,
        )

        # [DEBUG-SOLVER] Check for SPS/PPS/IDR in ENTIRE segment data
        has_sps = b'\x00\x00\x00\x01\x67' in data or b'\x00\x00\x01\x67' in data
        has_pps = b'\x00\x00\x00\x01\x68' in data or b'\x00\x00\x01\x68' in data
        has_idr = b'\x00\x00\x00\x01\x65' in data or b'\x00\x00\x01\x65' in data
        # Show first 20 bytes as hex
        first_bytes = data[:20].hex() if len(data) >= 20 else data.hex()

        logger.info(
            f"Video segment emitted: batch={self._video_batch_number}, "
            f"duration={acc.duration_ns / 1e9:.2f}s, buffers={acc.buffer_count}, "
            f"size={len(data)}, has_SPS={has_sps}, has_PPS={has_pps}, has_IDR={has_idr}, "
            f"first_bytes={first_bytes}"
        )

        self._video_batch_number += 1
        acc.reset()

        return segment, data

    def _emit_audio_segment(self) -> tuple[AudioSegment, bytes]:
        """Create and return audio segment from accumulated data.

        Returns:
            Tuple of (AudioSegment metadata, accumulated data bytes)
        """
        acc = self._audio_accumulator
        data = bytes(acc.data)

        segment = AudioSegment.create(
            stream_id=self.stream_id,
            batch_number=self._audio_batch_number,
            t0_ns=acc.t0_ns,
            duration_ns=acc.duration_ns,
            segment_dir=self.segment_dir,
        )

        logger.info(
            f"Audio segment emitted: batch={self._audio_batch_number}, "
            f"duration={acc.duration_ns / 1e9:.2f}s, buffers={acc.buffer_count}"
        )

        self._audio_batch_number += 1
        acc.reset()

        return segment, data

    def reset(self) -> None:
        """Reset both accumulators and batch counters."""
        self._video_accumulator.reset()
        self._audio_accumulator.reset()
        self._video_batch_number = 0
        self._audio_batch_number = 0
        logger.info("SegmentBuffer reset")

    @property
    def video_accumulated_duration_ns(self) -> int:
        """Current accumulated video duration in nanoseconds."""
        return self._video_accumulator.duration_ns

    @property
    def audio_accumulated_duration_ns(self) -> int:
        """Current accumulated audio duration in nanoseconds."""
        return self._audio_accumulator.duration_ns

    @property
    def video_batch_number(self) -> int:
        """Current video batch number."""
        return self._video_batch_number

    @property
    def audio_batch_number(self) -> int:
        """Current audio batch number."""
        return self._audio_batch_number
