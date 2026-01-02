"""Stream publisher helper for E2E tests.

Publishes video files to MediaMTX RTMP server using ffmpeg subprocess.
Provides controlled stream injection for deterministic E2E testing.
"""

from __future__ import annotations

import contextlib
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tests.e2e.config import MediaMTXConfig, TestFixtureConfig, TimeoutConfig

if TYPE_CHECKING:
    from subprocess import Popen

logger = logging.getLogger(__name__)


@dataclass
class PublishStats:
    """Statistics from stream publishing."""

    duration_sec: float
    frames_published: int
    bytes_published: int
    errors: list[str]


class StreamPublisher:
    """Publishes video streams to MediaMTX for E2E testing.

    Uses ffmpeg to push video files to RTSP endpoint,
    simulating a real stream source.

    Usage:
        publisher = StreamPublisher()
        publisher.start("live/test/in")
        # ... run tests ...
        publisher.stop()
    """

    def __init__(
        self,
        fixture_path: Path | None = None,
        rtmp_base_url: str | None = None,
    ) -> None:
        """Initialize stream publisher.

        Args:
            fixture_path: Path to video fixture (default: 1-min-nfl.mp4)
            rtmp_base_url: RTMP server URL (default: rtmp://localhost:1935)
        """
        self.fixture_path = fixture_path or TestFixtureConfig.FIXTURE_PATH
        self.rtmp_base_url = rtmp_base_url or MediaMTXConfig.RTMP_URL
        self._process: Popen | None = None
        self._stream_path: str | None = None

    def start(
        self,
        stream_path: str = "live/test/in",
        loop: bool = False,
        realtime: bool = True,
    ) -> None:
        """Start publishing stream to RTMP.

        Args:
            stream_path: RTMP path (e.g., "live/test/in")
            loop: Whether to loop the video (for longer tests)
            realtime: Whether to publish at realtime speed

        Raises:
            FileNotFoundError: If fixture file doesn't exist
            RuntimeError: If ffmpeg fails to start
        """
        if self._process is not None:
            logger.warning("Publisher already running, stopping first")
            self.stop()

        if not self.fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found: {self.fixture_path}")

        rtmp_url = f"{self.rtmp_base_url}/{stream_path}"
        self._stream_path = stream_path

        # Build ffmpeg command
        cmd = self._build_ffmpeg_command(rtmp_url, loop, realtime)

        logger.info(f"Starting stream publisher: {stream_path}")
        logger.debug(f"ffmpeg command: {' '.join(cmd)}")
        logger.debug(f"Publishing to: {rtmp_url}")

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Give ffmpeg time to connect
        time.sleep(1)

        # Verify process is running
        if self._process.poll() is not None:
            _, stderr = self._process.communicate()
            raise RuntimeError(f"ffmpeg failed to start: {stderr.decode()}")

        logger.info(f"Stream publisher started: {rtmp_url}")

    def _build_ffmpeg_command(
        self,
        rtmp_url: str,
        loop: bool,
        realtime: bool,
    ) -> list[str]:
        """Build ffmpeg command for RTMP publishing.

        Args:
            rtmp_url: Target RTMP URL
            loop: Whether to loop input
            realtime: Whether to publish at realtime

        Returns:
            ffmpeg command as list of strings
        """
        cmd = ["ffmpeg", "-hide_banner"]

        # Input options
        if loop:
            cmd.extend(["-stream_loop", "-1"])  # Infinite loop

        if realtime:
            cmd.extend(["-re"])  # Realtime playback speed

        cmd.extend(["-i", str(self.fixture_path)])

        # Output options - copy codecs (no re-encoding)
        cmd.extend([
            "-c:v", "copy",
            "-c:a", "copy",
            "-f", "flv",
            rtmp_url,
        ])

        return cmd

    def stop(self) -> PublishStats | None:
        """Stop publishing stream.

        Returns:
            Publishing statistics if available
        """
        if self._process is None:
            return None

        logger.info("Stopping stream publisher")

        # Terminate gracefully
        self._process.terminate()

        try:
            stdout, stderr = self._process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg didn't terminate, killing")
            self._process.kill()
            stdout, stderr = self._process.communicate()

        stats = self._parse_ffmpeg_output(stderr.decode())

        self._process = None
        self._stream_path = None

        logger.info("Stream publisher stopped")
        return stats

    def _parse_ffmpeg_output(self, output: str) -> PublishStats:
        """Parse ffmpeg stderr output for statistics.

        Args:
            output: ffmpeg stderr output

        Returns:
            Parsed statistics
        """
        # Simple parsing - could be enhanced
        frames = 0
        size_bytes = 0
        duration = 0.0
        errors = []

        for line in output.split("\n"):
            if "frame=" in line:
                # Parse progress line
                parts = line.split()
                for part in parts:
                    if part.startswith("frame="):
                        with contextlib.suppress(ValueError):
                            frames = int(part.split("=")[1])
                    elif part.startswith("size="):
                        with contextlib.suppress(ValueError):
                            size_str = part.split("=")[1]
                            if size_str.endswith("kB"):
                                size_bytes = int(size_str[:-2]) * 1024
                    elif part.startswith("time="):
                        with contextlib.suppress(ValueError):
                            time_str = part.split("=")[1]
                            parts_time = time_str.split(":")
                            if len(parts_time) == 3:
                                h, m, s = parts_time
                                duration = int(h) * 3600 + int(m) * 60 + float(s)

            if "error" in line.lower():
                errors.append(line.strip())

        return PublishStats(
            duration_sec=duration,
            frames_published=frames,
            bytes_published=size_bytes,
            errors=errors,
        )

    def is_running(self) -> bool:
        """Check if publisher is running.

        Returns:
            True if publishing
        """
        if self._process is None:
            return False
        return self._process.poll() is None

    def wait_for_completion(self, timeout: int | None = None) -> PublishStats | None:
        """Wait for stream to complete (for non-looped streams).

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            Publishing statistics
        """
        if self._process is None:
            return None

        timeout = timeout or TimeoutConfig.PIPELINE_COMPLETION

        try:
            stdout, stderr = self._process.communicate(timeout=timeout)
            stats = self._parse_ffmpeg_output(stderr.decode())
            self._process = None
            return stats
        except subprocess.TimeoutExpired:
            logger.warning("Stream didn't complete within timeout")
            return self.stop()

    @property
    def stream_url(self) -> str | None:
        """Get the current RTMP stream URL.

        Returns:
            RTMP URL if publishing, None otherwise
        """
        if self._stream_path:
            return f"{self.rtmp_base_url}/{self._stream_path}"
        return None


def verify_fixture(fixture_path: Path | None = None) -> dict:
    """Verify test fixture properties using ffprobe.

    Args:
        fixture_path: Path to video file

    Returns:
        Dictionary with fixture properties

    Raises:
        FileNotFoundError: If fixture doesn't exist
        RuntimeError: If ffprobe fails
    """
    import json as json_module

    path = fixture_path or TestFixtureConfig.FIXTURE_PATH

    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    return json_module.loads(result.stdout)
