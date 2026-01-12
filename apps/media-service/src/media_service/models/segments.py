"""
Segment data models for video and audio segments.

Per spec 003, segments are stored as:
- Video: MP4 files (H.264 codec-copy)
- Audio: M4A files (AAC codec-copy)

Updated for spec 021-fragment-length-30s:
- Each segment represents ~30 seconds of media (increased from 6s)
- DEFAULT_SEGMENT_DURATION_NS changed from 6_000_000_000 to 30_000_000_000
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
from uuid import uuid4


@dataclass
class VideoSegment:
    """Video segment metadata for disk-based storage.

    Video is stored as MP4 file with H.264 codec-copied from source.
    No transcoding occurs - original video quality preserved.

    Attributes:
        fragment_id: Unique identifier for this segment (UUID v4).
        stream_id: Identifier of the source stream.
        batch_number: Sequential number within the stream (0-indexed).
        t0_ns: PTS of the first frame in nanoseconds (GStreamer clock).
        duration_ns: Duration of the segment in nanoseconds.
        file_path: Path to MP4 file on disk.
        file_size: Size of MP4 file in bytes.

    Invariants:
        - duration_ns should be ~30_000_000_000 (30 seconds) +/- 100ms (spec 021)
        - file_path points to valid MP4 with H.264 video track
    """

    fragment_id: str
    stream_id: str
    batch_number: int
    t0_ns: int
    duration_ns: int
    file_path: Path
    file_size: int = 0

    # Constants (spec 021: increased from 6s to 30s)
    DEFAULT_SEGMENT_DURATION_NS: ClassVar[int] = 30_000_000_000  # 30 seconds (spec 021)
    MIN_SEGMENT_DURATION_NS: ClassVar[int] = 1_000_000_000  # 1 second minimum for partial
    TOLERANCE_NS: ClassVar[int] = 100_000_000  # 100ms tolerance

    @classmethod
    def create(
        cls,
        stream_id: str,
        batch_number: int,
        t0_ns: int,
        duration_ns: int,
        segment_dir: Path,
    ) -> VideoSegment:
        """Factory method to create a VideoSegment with auto-generated fragment_id.

        Args:
            stream_id: Stream identifier.
            batch_number: Sequential batch number (0-indexed).
            t0_ns: PTS of first frame in nanoseconds.
            duration_ns: Duration in nanoseconds.
            segment_dir: Base directory for segment storage.

        Returns:
            New VideoSegment with generated fragment_id and file_path.
        """
        fragment_id = str(uuid4())
        file_path = segment_dir / stream_id / f"{batch_number:06d}_video.mp4"
        return cls(
            fragment_id=fragment_id,
            stream_id=stream_id,
            batch_number=batch_number,
            t0_ns=t0_ns,
            duration_ns=duration_ns,
            file_path=file_path,
        )

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        return self.duration_ns / 1_000_000_000

    @property
    def duration_ms(self) -> int:
        """Duration in milliseconds."""
        return self.duration_ns // 1_000_000

    @property
    def exists(self) -> bool:
        """Check if segment file exists on disk."""
        return self.file_path.exists()

    def is_valid_duration(self, allow_partial: bool = False) -> bool:
        """Check if segment duration is within expected range.

        Args:
            allow_partial: If True, accept segments >= 1s (for EOS).

        Returns:
            True if duration is valid.
        """
        if allow_partial:
            return self.duration_ns >= self.MIN_SEGMENT_DURATION_NS

        # Full segment: 30s +/- 100ms (spec 021)
        min_ns = self.DEFAULT_SEGMENT_DURATION_NS - self.TOLERANCE_NS
        max_ns = self.DEFAULT_SEGMENT_DURATION_NS + self.TOLERANCE_NS
        return min_ns <= self.duration_ns <= max_ns


@dataclass
class AudioSegment:
    """Audio segment metadata for disk-based storage and STS transport.

    Audio is stored as M4A file (AAC in MP4 container) codec-copied from source.
    No PCM conversion - AAC preserved for efficient STS transport.

    Attributes:
        fragment_id: Unique identifier for this segment (UUID v4).
        stream_id: Identifier of the source stream.
        batch_number: Sequential number within the stream (0-indexed).
        t0_ns: PTS of the first sample in nanoseconds (GStreamer clock).
        duration_ns: Duration of the segment in nanoseconds.
        file_path: Path to M4A file on disk.
        file_size: Size of M4A file in bytes.
        dubbed_file_path: Path to dubbed M4A file (after STS processing).
        is_dubbed: Whether STS processing completed successfully.

    Invariants:
        - duration_ns should be ~30_000_000_000 (30 seconds) +/- 100ms (spec 021)
        - file_path points to valid M4A with AAC audio track
    """

    fragment_id: str
    stream_id: str
    batch_number: int
    t0_ns: int
    duration_ns: int
    file_path: Path
    file_size: int = 0
    dubbed_file_path: Path | None = None
    is_dubbed: bool = False

    # Constants (same as VideoSegment for consistency) - spec 021: increased from 6s to 30s
    DEFAULT_SEGMENT_DURATION_NS: ClassVar[int] = 30_000_000_000  # 30 seconds (spec 021)
    MIN_SEGMENT_DURATION_NS: ClassVar[int] = 1_000_000_000  # 1 second minimum for partial
    TOLERANCE_NS: ClassVar[int] = 100_000_000  # 100ms tolerance

    @classmethod
    def create(
        cls,
        stream_id: str,
        batch_number: int,
        t0_ns: int,
        duration_ns: int,
        segment_dir: Path,
    ) -> AudioSegment:
        """Factory method to create an AudioSegment with auto-generated fragment_id.

        Args:
            stream_id: Stream identifier.
            batch_number: Sequential batch number (0-indexed).
            t0_ns: PTS of first sample in nanoseconds.
            duration_ns: Duration in nanoseconds.
            segment_dir: Base directory for segment storage.

        Returns:
            New AudioSegment with generated fragment_id and file_path.
        """
        fragment_id = str(uuid4())
        file_path = segment_dir / stream_id / f"{batch_number:06d}_audio.m4a"
        return cls(
            fragment_id=fragment_id,
            stream_id=stream_id,
            batch_number=batch_number,
            t0_ns=t0_ns,
            duration_ns=duration_ns,
            file_path=file_path,
        )

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        return self.duration_ns / 1_000_000_000

    @property
    def duration_ms(self) -> int:
        """Duration in milliseconds."""
        return self.duration_ns // 1_000_000

    @property
    def exists(self) -> bool:
        """Check if segment file exists on disk."""
        return self.file_path.exists()

    def get_m4a_data(self) -> bytes:
        """Read M4A data from file for STS transport.

        Returns:
            M4A file contents as bytes, or empty bytes if file doesn't exist.
        """
        if not self.exists:
            return b""
        return self.file_path.read_bytes()

    def set_dubbed(self, dubbed_path: Path) -> None:
        """Mark segment as dubbed with path to dubbed file.

        Args:
            dubbed_path: Path to the dubbed M4A file.
        """
        self.dubbed_file_path = dubbed_path
        self.is_dubbed = True

    @property
    def output_file_path(self) -> Path:
        """Get file path to use for output (dubbed or original).

        Returns:
            Path to dubbed file if available, otherwise original file.
        """
        if self.is_dubbed and self.dubbed_file_path:
            return self.dubbed_file_path
        return self.file_path

    def is_valid_duration(self, allow_partial: bool = False) -> bool:
        """Check if segment duration is within expected range.

        Args:
            allow_partial: If True, accept segments >= 1s (for EOS).

        Returns:
            True if duration is valid.
        """
        if allow_partial:
            return self.duration_ns >= self.MIN_SEGMENT_DURATION_NS

        # Full segment: 30s +/- 100ms (spec 021)
        min_ns = self.DEFAULT_SEGMENT_DURATION_NS - self.TOLERANCE_NS
        max_ns = self.DEFAULT_SEGMENT_DURATION_NS + self.TOLERANCE_NS
        return min_ns <= self.duration_ns <= max_ns
