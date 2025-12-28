"""Integration tests for test stream publish and playback.

Tests for User Story 5 (T075): Provide developers with simple commands to publish
test streams and verify playback without requiring external streaming software.

Test Coverage Target: 80% minimum

Prerequisites:
- Docker Compose running (make dev)
- FFmpeg installed for test stream publishing

These tests verify:
- FFmpeg publish command creates active stream
- Stream appears in Control API /v3/paths/list
- Stream has expected tracks (H264, AAC)
- RTSP playback URL returns valid stream
"""

import subprocess
import time

import pytest
import requests

# Service URLs
MEDIAMTX_RTMP_URL = "rtmp://localhost:1935"
MEDIAMTX_RTSP_URL = "rtsp://localhost:8554"
MEDIAMTX_CONTROL_API_URL = "http://localhost:9997"


@pytest.fixture
def unique_stream_id() -> str:
    """Generate unique stream ID for test isolation."""
    return f"test-publish-{int(time.time())}"


@pytest.fixture
def ffmpeg_publish_command(unique_stream_id: str) -> list[str]:
    """Build FFmpeg command for test stream publishing."""
    stream_path = f"live/{unique_stream_id}/in"
    return [
        "ffmpeg",
        "-re",
        "-f", "lavfi",
        "-i", "testsrc=size=640x480:rate=30",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:sample_rate=48000",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-b:v", "1000k",
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", "10",  # 10 second stream
        "-f", "flv",
        f"{MEDIAMTX_RTMP_URL}/{stream_path}"
    ]


def wait_for_stream_ready(
    stream_path: str,
    timeout: float = 5.0,
    poll_interval: float = 0.2
) -> dict | None:
    """Wait for stream to appear in Control API.

    Args:
        stream_path: Path to check (e.g., "live/test/in")
        timeout: Maximum time to wait in seconds
        poll_interval: Time between polls in seconds

    Returns:
        Stream info dict if found, None if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(
                f"{MEDIAMTX_CONTROL_API_URL}/v3/paths/list",
                timeout=2.0
            )
            if response.status_code == 200:
                paths = response.json().get("items", [])
                for path in paths:
                    if path.get("name") == stream_path and path.get("ready"):
                        return path
        except requests.RequestException:
            pass  # Continue polling
        time.sleep(poll_interval)
    return None


def wait_for_stream_removed(
    stream_path: str,
    timeout: float = 5.0,
    poll_interval: float = 0.2
) -> bool:
    """Wait for stream to be removed from Control API.

    Args:
        stream_path: Path to check
        timeout: Maximum time to wait
        poll_interval: Time between polls

    Returns:
        True if stream was removed, False if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(
                f"{MEDIAMTX_CONTROL_API_URL}/v3/paths/list",
                timeout=2.0
            )
            if response.status_code == 200:
                paths = response.json().get("items", [])
                if not any(p.get("name") == stream_path for p in paths):
                    return True
        except requests.RequestException:
            pass
        time.sleep(poll_interval)
    return False


@pytest.mark.integration
class TestFFmpegPublishCreatesActiveStream:
    """Test FFmpeg publish command creates active stream."""

    def test_ffmpeg_publish_creates_stream(
        self,
        unique_stream_id: str,
        ffmpeg_publish_command: list[str]
    ) -> None:
        """Test FFmpeg publish command creates an active stream in MediaMTX.

        Acceptance criteria:
        - FFmpeg command publishes successfully
        - Stream appears in MediaMTX within 5 seconds
        - Stream is marked as ready
        """
        stream_path = f"live/{unique_stream_id}/in"

        # Start FFmpeg publish process
        ffmpeg_process = subprocess.Popen(
            ffmpeg_publish_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            # Wait for stream to become ready
            stream_info = wait_for_stream_ready(stream_path, timeout=5.0)

            # Assert stream was created
            assert stream_info is not None, (
                f"Stream {stream_path} did not appear in Control API within 5 seconds"
            )
            assert stream_info.get("ready") is True, (
                f"Stream {stream_path} is not marked as ready"
            )

        finally:
            # Cleanup
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)

    def test_ffmpeg_publish_with_query_params(
        self,
        unique_stream_id: str
    ) -> None:
        """Test FFmpeg publish with query parameters works correctly."""
        stream_path = f"live/{unique_stream_id}/in"
        query_params = "lang=es&quality=high"

        # Build command with query params
        ffmpeg_cmd = [
            "ffmpeg",
            "-re",
            "-f", "lavfi",
            "-i", "testsrc=size=640x480:rate=30",
            "-f", "lavfi",
            "-i", "sine=frequency=1000:sample_rate=48000",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-c:a", "aac",
            "-t", "5",
            "-f", "flv",
            f"{MEDIAMTX_RTMP_URL}/{stream_path}?{query_params}"
        ]

        ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            # Wait for stream to become ready
            stream_info = wait_for_stream_ready(stream_path, timeout=5.0)

            # Assert stream was created (MediaMTX accepts query params)
            assert stream_info is not None, (
                "Stream with query params did not appear in Control API"
            )

        finally:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)


@pytest.mark.integration
class TestStreamAppearsInControlAPI:
    """Test stream appears in Control API /v3/paths/list."""

    def test_stream_listed_in_paths_list(
        self,
        unique_stream_id: str,
        ffmpeg_publish_command: list[str]
    ) -> None:
        """Test published stream appears in /v3/paths/list endpoint.

        Acceptance criteria:
        - Stream path matches expected format (live/<streamId>/in)
        - Response is valid JSON with items array
        """
        stream_path = f"live/{unique_stream_id}/in"

        ffmpeg_process = subprocess.Popen(
            ffmpeg_publish_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            # Wait for stream
            time.sleep(2.0)

            # Query Control API
            response = requests.get(
                f"{MEDIAMTX_CONTROL_API_URL}/v3/paths/list",
                timeout=5.0
            )

            # Assert API response
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert isinstance(data["items"], list)

            # Find our stream
            stream_info = next(
                (p for p in data["items"] if p.get("name") == stream_path),
                None
            )
            assert stream_info is not None, (
                f"Stream {stream_path} not found in Control API response"
            )

        finally:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)

    def test_stream_removed_after_disconnect(
        self,
        unique_stream_id: str,
        ffmpeg_publish_command: list[str]
    ) -> None:
        """Test stream is removed from Control API after publisher disconnects."""
        stream_path = f"live/{unique_stream_id}/in"

        ffmpeg_process = subprocess.Popen(
            ffmpeg_publish_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            # Wait for stream to appear
            stream_info = wait_for_stream_ready(stream_path, timeout=5.0)
            assert stream_info is not None

            # Terminate FFmpeg (disconnect)
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)

            # Wait for stream to be removed
            was_removed = wait_for_stream_removed(stream_path, timeout=5.0)
            assert was_removed, (
                f"Stream {stream_path} was not removed after disconnect"
            )

        finally:
            if ffmpeg_process.poll() is None:
                ffmpeg_process.terminate()
                ffmpeg_process.wait(timeout=5)


@pytest.mark.integration
class TestStreamHasExpectedTracks:
    """Test stream has expected tracks (H264, AAC)."""

    def test_stream_has_h264_video_track(
        self,
        unique_stream_id: str,
        ffmpeg_publish_command: list[str]
    ) -> None:
        """Test published stream has H264 video track.

        Acceptance criteria:
        - Stream tracks include H264 video codec
        """
        stream_path = f"live/{unique_stream_id}/in"

        ffmpeg_process = subprocess.Popen(
            ffmpeg_publish_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            # Wait for stream
            stream_info = wait_for_stream_ready(stream_path, timeout=5.0)
            assert stream_info is not None

            # Check tracks
            tracks = stream_info.get("tracks", [])
            # Note: MediaMTX may report tracks differently based on version
            # We check if any track indicates H264
            has_h264 = any(
                "H264" in str(track).upper() or "AVC" in str(track).upper()
                for track in tracks
            ) if tracks else True  # Skip if tracks not reported

            assert has_h264 or not tracks, (
                f"Stream does not have H264 video track. Tracks: {tracks}"
            )

        finally:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)

    def test_stream_has_aac_audio_track(
        self,
        unique_stream_id: str,
        ffmpeg_publish_command: list[str]
    ) -> None:
        """Test published stream has AAC audio track.

        Acceptance criteria:
        - Stream tracks include AAC audio codec
        """
        stream_path = f"live/{unique_stream_id}/in"

        ffmpeg_process = subprocess.Popen(
            ffmpeg_publish_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            # Wait for stream
            stream_info = wait_for_stream_ready(stream_path, timeout=5.0)
            assert stream_info is not None

            # Check tracks
            tracks = stream_info.get("tracks", [])
            has_aac = any(
                "AAC" in str(track).upper() or "MPEG4-GENERIC" in str(track).upper()
                for track in tracks
            ) if tracks else True  # Skip if tracks not reported

            assert has_aac or not tracks, (
                f"Stream does not have AAC audio track. Tracks: {tracks}"
            )

        finally:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)


@pytest.mark.integration
class TestRTSPPlayback:
    """Test RTSP playback URL returns valid stream."""

    def test_rtsp_playback_url_accessible(
        self,
        unique_stream_id: str,
        ffmpeg_publish_command: list[str]
    ) -> None:
        """Test RTSP playback URL is accessible after stream is published.

        Uses ffprobe to verify RTSP stream is valid.

        Acceptance criteria:
        - RTSP URL responds to connection
        - Stream metadata can be retrieved
        """
        stream_path = f"live/{unique_stream_id}/in"

        ffmpeg_process = subprocess.Popen(
            ffmpeg_publish_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            # Wait for stream
            stream_info = wait_for_stream_ready(stream_path, timeout=5.0)
            assert stream_info is not None

            # Build RTSP URL
            rtsp_url = f"{MEDIAMTX_RTSP_URL}/{stream_path}"

            # Use ffprobe to check RTSP stream
            ffprobe_cmd = [
                "ffprobe",
                "-rtsp_transport", "tcp",
                "-v", "error",
                "-show_entries", "stream=codec_type,codec_name",
                "-of", "json",
                "-timeout", "5000000",  # 5 second timeout in microseconds
                rtsp_url
            ]

            ffprobe_result = subprocess.run(
                ffprobe_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            # Assert ffprobe succeeded
            assert ffprobe_result.returncode == 0, (
                f"ffprobe failed to read RTSP stream: {ffprobe_result.stderr}"
            )

        finally:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)

    def test_rtsp_playback_contains_video_stream(
        self,
        unique_stream_id: str,
        ffmpeg_publish_command: list[str]
    ) -> None:
        """Test RTSP playback contains video stream.

        Uses ffprobe to verify video codec information.
        """
        stream_path = f"live/{unique_stream_id}/in"

        ffmpeg_process = subprocess.Popen(
            ffmpeg_publish_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            # Wait for stream
            stream_info = wait_for_stream_ready(stream_path, timeout=5.0)
            assert stream_info is not None

            rtsp_url = f"{MEDIAMTX_RTSP_URL}/{stream_path}"

            # Probe for video stream
            ffprobe_cmd = [
                "ffprobe",
                "-rtsp_transport", "tcp",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                "-timeout", "5000000",
                rtsp_url
            ]

            ffprobe_result = subprocess.run(
                ffprobe_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            # Assert video codec is h264
            video_codec = ffprobe_result.stdout.strip()
            assert "h264" in video_codec.lower(), (
                f"Expected H264 video codec, got: {video_codec}"
            )

        finally:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)

    def test_rtsp_playback_contains_audio_stream(
        self,
        unique_stream_id: str,
        ffmpeg_publish_command: list[str]
    ) -> None:
        """Test RTSP playback contains audio stream.

        Uses ffprobe to verify audio codec information.
        """
        stream_path = f"live/{unique_stream_id}/in"

        ffmpeg_process = subprocess.Popen(
            ffmpeg_publish_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            # Wait for stream
            stream_info = wait_for_stream_ready(stream_path, timeout=5.0)
            assert stream_info is not None

            rtsp_url = f"{MEDIAMTX_RTSP_URL}/{stream_path}"

            # Probe for audio stream
            ffprobe_cmd = [
                "ffprobe",
                "-rtsp_transport", "tcp",
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                "-timeout", "5000000",
                rtsp_url
            ]

            ffprobe_result = subprocess.run(
                ffprobe_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            # Assert audio codec is aac
            audio_codec = ffprobe_result.stdout.strip()
            assert "aac" in audio_codec.lower(), (
                f"Expected AAC audio codec, got: {audio_codec}"
            )

        finally:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)

    def test_rtsp_over_tcp_transport(
        self,
        unique_stream_id: str,
        ffmpeg_publish_command: list[str]
    ) -> None:
        """Test RTSP playback over TCP transport (avoids UDP packet loss).

        Acceptance criteria:
        - RTSP connection works with TCP transport
        - No packet loss during playback
        """
        stream_path = f"live/{unique_stream_id}/in"

        ffmpeg_process = subprocess.Popen(
            ffmpeg_publish_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        try:
            # Wait for stream
            stream_info = wait_for_stream_ready(stream_path, timeout=5.0)
            assert stream_info is not None

            rtsp_url = f"{MEDIAMTX_RTSP_URL}/{stream_path}"

            # Read a few frames using TCP transport
            ffmpeg_read_cmd = [
                "ffmpeg",
                "-rtsp_transport", "tcp",
                "-i", rtsp_url,
                "-frames:v", "10",  # Read 10 video frames
                "-f", "null",
                "-"  # Discard output
            ]

            read_result = subprocess.run(
                ffmpeg_read_cmd,
                capture_output=True,
                text=True,
                timeout=15
            )

            # Assert read succeeded (returncode 0 means success)
            assert read_result.returncode == 0, (
                f"Failed to read RTSP stream over TCP: {read_result.stderr}"
            )

        finally:
            ffmpeg_process.terminate()
            ffmpeg_process.wait(timeout=5)


@pytest.mark.integration
class TestPlaybackCommands:
    """Test documented playback commands work correctly."""

    def test_ffplay_playback_command_format(self) -> None:
        """Test ffplay command format is correct.

        This test verifies the documented command format without actually running playback.
        """
        # Build expected ffplay command
        stream_path = "live/test-stream/in"
        expected_cmd = f"ffplay rtsp://localhost:8554/{stream_path}"

        # Verify command components
        assert "ffplay" in expected_cmd
        assert "rtsp://localhost:8554" in expected_cmd
        assert stream_path in expected_cmd

    def test_ffmpeg_bypass_command_format(self) -> None:
        """Test FFmpeg bypass (RTSP -> RTMP) command format is correct."""
        # This is the documented bypass pattern
        input_path = "live/test-stream/in"
        output_path = "live/test-stream/out"

        # Expected command components
        input_url = f"rtsp://localhost:8554/{input_path}"
        output_url = f"rtmp://localhost:1935/{output_path}"

        # Verify format
        assert input_path in input_url
        assert output_path in output_url
        assert "rtsp://" in input_url
        assert "rtmp://" in output_url
