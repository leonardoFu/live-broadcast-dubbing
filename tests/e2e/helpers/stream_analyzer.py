"""Stream analyzer for E2E tests.

Analyzes RTMP/RTSP streams using ffprobe to extract
PTS timestamps and calculate A/V sync deltas.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from tests.e2e.config import MediaMTXConfig, TestConfig

logger = logging.getLogger(__name__)


@dataclass
class StreamInfo:
    """Information about a stream."""

    codec_name: str
    codec_type: str  # video or audio
    duration_sec: float
    start_pts: float
    time_base: str
    sample_rate: int | None = None  # audio only
    channels: int | None = None  # audio only
    width: int | None = None  # video only
    height: int | None = None  # video only
    fps: float | None = None  # video only


@dataclass
class PTSFrame:
    """A single frame with PTS timestamp."""

    pts: float
    pts_time: float
    stream_index: int
    media_type: str  # video or audio
    duration: float | None = None


@dataclass
class AVSyncResult:
    """Result of A/V sync analysis."""

    deltas_ms: list[float] = field(default_factory=list)
    avg_delta_ms: float = 0.0
    max_delta_ms: float = 0.0
    min_delta_ms: float = 0.0
    within_threshold_count: int = 0
    total_count: int = 0
    threshold_ms: float = 120.0

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate (samples within threshold)."""
        if self.total_count == 0:
            return 0.0
        return self.within_threshold_count / self.total_count

    @property
    def passes_threshold(self) -> bool:
        """Check if 95% of samples are within threshold."""
        return self.pass_rate >= TestConfig.AV_SYNC_PASS_RATE


class StreamAnalyzer:
    """Analyzes media streams for E2E testing.

    Uses ffprobe to extract stream information and PTS
    timestamps for A/V sync verification.

    Usage:
        analyzer = StreamAnalyzer()
        info = analyzer.get_stream_info("rtmp://localhost:1935/live/test/out")
        sync_result = analyzer.analyze_av_sync("rtmp://localhost:1935/live/test/out")
    """

    def __init__(self, rtmp_base_url: str | None = None) -> None:
        """Initialize stream analyzer.

        Args:
            rtmp_base_url: Base RTMP URL (default: rtmp://localhost:1935)
        """
        self.rtmp_base_url = rtmp_base_url or MediaMTXConfig.RTMP_URL

    def get_stream_info(self, url: str, timeout: int = 10) -> list[StreamInfo]:
        """Get information about streams in URL.

        Args:
            url: Stream URL (RTSP/RTMP)
            timeout: ffprobe timeout in seconds

        Returns:
            List of StreamInfo for each stream

        Raises:
            RuntimeError: If ffprobe fails
        """
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            "-timeout", str(timeout * 1000000),  # microseconds
            url,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")

        data = json.loads(result.stdout)
        streams = []

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type", "unknown")
            info = StreamInfo(
                codec_name=stream.get("codec_name", "unknown"),
                codec_type=codec_type,
                duration_sec=float(stream.get("duration", 0)),
                start_pts=float(stream.get("start_pts", 0)),
                time_base=stream.get("time_base", "1/1000"),
            )

            if codec_type == "audio":
                info.sample_rate = int(stream.get("sample_rate", 0))
                info.channels = int(stream.get("channels", 0))
            elif codec_type == "video":
                info.width = int(stream.get("width", 0))
                info.height = int(stream.get("height", 0))
                # Parse fps from r_frame_rate (e.g., "30/1")
                fps_str = stream.get("r_frame_rate", "0/1")
                try:
                    num, den = map(int, fps_str.split("/"))
                    info.fps = num / den if den != 0 else 0
                except ValueError:
                    info.fps = 0

            streams.append(info)

        return streams

    def extract_pts_frames(
        self,
        url: str,
        duration_sec: float = 10,
        timeout: int = 30,
    ) -> list[PTSFrame]:
        """Extract PTS timestamps from stream.

        Args:
            url: Stream URL
            duration_sec: How long to capture
            timeout: Command timeout

        Returns:
            List of PTSFrame objects

        Raises:
            RuntimeError: If ffprobe fails
        """
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_frames",
            "-select_streams", "v:0,a:0",  # First video and audio streams
            "-read_intervals", f"%+{duration_sec}",
            "-timeout", str(timeout * 1000000),
            url,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")

        data = json.loads(result.stdout)
        frames = []

        for frame in data.get("frames", []):
            pts_time = frame.get("pts_time")
            if pts_time is None:
                continue

            frames.append(PTSFrame(
                pts=float(frame.get("pts", 0)),
                pts_time=float(pts_time),
                stream_index=int(frame.get("stream_index", 0)),
                media_type=frame.get("media_type", "unknown"),
                duration=float(frame.get("duration", 0)) if frame.get("duration") else None,
            ))

        return frames

    def analyze_av_sync(
        self,
        url: str,
        segment_duration_sec: float = 6.0,
        duration_sec: float = 60,
        threshold_ms: float | None = None,
    ) -> AVSyncResult:
        """Analyze A/V sync by comparing PTS timestamps.

        Groups frames into segments and calculates the PTS delta
        between video and audio at segment boundaries.

        Args:
            url: Stream URL
            segment_duration_sec: Segment size for comparison
            duration_sec: How long to analyze
            threshold_ms: Sync threshold in ms (default: 120ms)

        Returns:
            AVSyncResult with analysis
        """
        threshold = threshold_ms or TestConfig.AV_SYNC_THRESHOLD_MS

        # Extract frames
        frames = self.extract_pts_frames(url, duration_sec)

        # Separate video and audio frames
        video_frames = [f for f in frames if f.media_type == "video"]
        audio_frames = [f for f in frames if f.media_type == "audio"]

        if not video_frames or not audio_frames:
            logger.warning("No video or audio frames found")
            return AVSyncResult(threshold_ms=threshold)

        # Calculate deltas at segment boundaries
        deltas_ms = []
        segment_index = 0
        segment_start = 0.0

        while segment_start < duration_sec:
            segment_end = segment_start + segment_duration_sec

            # Find video and audio frames near segment start
            video_pts = self._find_nearest_pts(video_frames, segment_start)
            audio_pts = self._find_nearest_pts(audio_frames, segment_start)

            if video_pts is not None and audio_pts is not None:
                delta_ms = abs(video_pts - audio_pts) * 1000
                deltas_ms.append(delta_ms)

            segment_start = segment_end
            segment_index += 1

        if not deltas_ms:
            return AVSyncResult(threshold_ms=threshold)

        # Calculate statistics
        within_threshold = sum(1 for d in deltas_ms if d <= threshold)

        return AVSyncResult(
            deltas_ms=deltas_ms,
            avg_delta_ms=sum(deltas_ms) / len(deltas_ms),
            max_delta_ms=max(deltas_ms),
            min_delta_ms=min(deltas_ms),
            within_threshold_count=within_threshold,
            total_count=len(deltas_ms),
            threshold_ms=threshold,
        )

    def _find_nearest_pts(
        self,
        frames: list[PTSFrame],
        target_time: float,
    ) -> float | None:
        """Find frame nearest to target time.

        Args:
            frames: List of frames
            target_time: Target time in seconds

        Returns:
            PTS time of nearest frame or None
        """
        if not frames:
            return None

        nearest = min(frames, key=lambda f: abs(f.pts_time - target_time))
        return nearest.pts_time

    def verify_stream_exists(self, stream_path: str, timeout: int = 10) -> bool:
        """Verify stream exists and is readable.

        Args:
            stream_path: Path after base URL (e.g., "live/test/out")
            timeout: Timeout in seconds

        Returns:
            True if stream exists and is readable
        """
        url = f"{self.rtmp_base_url}/{stream_path}"

        try:
            streams = self.get_stream_info(url, timeout)
            return len(streams) > 0
        except (RuntimeError, subprocess.TimeoutExpired):
            return False

    def verify_output_duration(
        self,
        stream_path: str,
        expected_duration_sec: float,
        tolerance_sec: float = 0.5,
    ) -> bool:
        """Verify output stream duration matches expected.

        Args:
            stream_path: Path after base URL
            expected_duration_sec: Expected duration
            tolerance_sec: Acceptable tolerance

        Returns:
            True if duration is within tolerance
        """
        url = f"{self.rtmp_base_url}/{stream_path}"

        try:
            streams = self.get_stream_info(url)
            if not streams:
                return False

            # Use video stream duration
            video_streams = [s for s in streams if s.codec_type == "video"]
            if not video_streams:
                return False

            actual_duration = video_streams[0].duration_sec
            return abs(actual_duration - expected_duration_sec) <= tolerance_sec

        except RuntimeError:
            return False


def analyze_fixture(fixture_path: Path) -> dict:
    """Analyze test fixture properties.

    Args:
        fixture_path: Path to video file

    Returns:
        Dictionary with fixture analysis
    """
    # Get stream info using file path
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(fixture_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)

    analysis = {
        "format": data.get("format", {}).get("format_name", "unknown"),
        "duration_sec": float(data.get("format", {}).get("duration", 0)),
        "streams": [],
    }

    for stream in data.get("streams", []):
        stream_info = {
            "codec_type": stream.get("codec_type"),
            "codec_name": stream.get("codec_name"),
        }
        if stream.get("codec_type") == "video":
            stream_info["width"] = stream.get("width")
            stream_info["height"] = stream.get("height")
            fps_str = stream.get("r_frame_rate", "0/1")
            try:
                num, den = map(int, fps_str.split("/"))
                stream_info["fps"] = num / den if den != 0 else 0
            except ValueError:
                stream_info["fps"] = 0
        elif stream.get("codec_type") == "audio":
            stream_info["sample_rate"] = stream.get("sample_rate")
            stream_info["channels"] = stream.get("channels")

        analysis["streams"].append(stream_info)

    return analysis
