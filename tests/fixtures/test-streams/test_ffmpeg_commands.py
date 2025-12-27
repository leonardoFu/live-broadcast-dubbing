"""Unit tests for FFmpeg test command generation.

Tests for User Story 5 (T074): Provide developers with simple commands to publish
test streams and verify playback without requiring external streaming software.

Test Coverage Target: 80% minimum

These tests verify:
- FFmpeg command includes correct RTMP URL format
- FFmpeg command includes H.264 + AAC codec configuration
- FFmpeg command includes testsrc video and sine audio sources
- Command generation handles various stream IDs correctly
"""

import shlex

import pytest


class FFmpegTestCommandBuilder:
    """Builder for FFmpeg test stream commands.

    Generates FFmpeg commands for publishing test streams with:
    - testsrc video pattern (color bars / SMPTE)
    - sine wave audio source
    - H.264 + AAC codec configuration
    - RTMP output to MediaMTX
    """

    DEFAULT_VIDEO_SIZE = "1280x720"
    DEFAULT_VIDEO_RATE = 30
    DEFAULT_AUDIO_FREQ = 1000  # 1kHz sine wave
    DEFAULT_AUDIO_RATE = 48000
    DEFAULT_VIDEO_BITRATE = "2000k"
    DEFAULT_AUDIO_BITRATE = "128k"

    def __init__(
        self,
        rtmp_host: str = "localhost",
        rtmp_port: int = 1935,
    ):
        self.rtmp_host = rtmp_host
        self.rtmp_port = rtmp_port

    def build_publish_command(
        self,
        stream_id: str,
        duration: int | None = None,
        video_size: str | None = None,
        video_rate: int | None = None,
        audio_freq: int | None = None,
        video_bitrate: str | None = None,
        audio_bitrate: str | None = None,
        query_params: str | None = None,
    ) -> list[str]:
        """Build FFmpeg command to publish test stream.

        Args:
            stream_id: Unique identifier for the stream (e.g., "test-stream")
            duration: Stream duration in seconds (None for infinite)
            video_size: Video resolution (e.g., "1280x720")
            video_rate: Video frame rate (e.g., 30)
            audio_freq: Audio sine wave frequency in Hz (e.g., 1000)
            video_bitrate: Video bitrate (e.g., "2000k")
            audio_bitrate: Audio bitrate (e.g., "128k")
            query_params: Optional query string (e.g., "lang=es")

        Returns:
            List of command arguments suitable for subprocess

        Raises:
            ValueError: If stream_id is invalid
        """
        # Validate stream_id
        if not stream_id:
            raise ValueError("stream_id cannot be empty")
        if not self._is_valid_stream_id(stream_id):
            raise ValueError(
                f"Invalid stream_id '{stream_id}': must contain only "
                "alphanumeric characters, hyphens, and underscores"
            )

        # Use defaults for optional parameters
        video_size = video_size or self.DEFAULT_VIDEO_SIZE
        video_rate = video_rate or self.DEFAULT_VIDEO_RATE
        audio_freq = audio_freq or self.DEFAULT_AUDIO_FREQ
        video_bitrate = video_bitrate or self.DEFAULT_VIDEO_BITRATE
        audio_bitrate = audio_bitrate or self.DEFAULT_AUDIO_BITRATE

        # Build RTMP URL
        rtmp_url = self._build_rtmp_url(stream_id, query_params)

        # Build command
        cmd = ["ffmpeg", "-re"]

        # Video input (testsrc)
        cmd.extend([
            "-f", "lavfi",
            "-i", f"testsrc=size={video_size}:rate={video_rate}"
        ])

        # Audio input (sine wave)
        cmd.extend([
            "-f", "lavfi",
            "-i", f"sine=frequency={audio_freq}:sample_rate={self.DEFAULT_AUDIO_RATE}"
        ])

        # Video codec (H.264)
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-b:v", video_bitrate
        ])

        # Audio codec (AAC)
        cmd.extend([
            "-c:a", "aac",
            "-b:a", audio_bitrate
        ])

        # Duration (if specified)
        if duration is not None:
            cmd.extend(["-t", str(duration)])

        # Output format and URL
        cmd.extend(["-f", "flv", rtmp_url])

        return cmd

    def build_publish_command_string(
        self,
        stream_id: str,
        **kwargs
    ) -> str:
        """Build FFmpeg command as a shell-escaped string.

        Args:
            stream_id: Unique identifier for the stream
            **kwargs: Additional arguments passed to build_publish_command

        Returns:
            Shell-escaped command string
        """
        cmd = self.build_publish_command(stream_id, **kwargs)
        return " ".join(shlex.quote(arg) for arg in cmd)

    def _build_rtmp_url(
        self,
        stream_id: str,
        query_params: str | None = None
    ) -> str:
        """Build RTMP URL for stream publishing.

        Args:
            stream_id: Stream identifier
            query_params: Optional query string (without leading ?)

        Returns:
            Full RTMP URL (e.g., rtmp://localhost:1935/live/test-stream/in)
        """
        base_url = f"rtmp://{self.rtmp_host}:{self.rtmp_port}/live/{stream_id}/in"
        if query_params:
            return f"{base_url}?{query_params}"
        return base_url

    def _is_valid_stream_id(self, stream_id: str) -> bool:
        """Check if stream ID contains only valid characters.

        Valid characters: alphanumeric, hyphens, underscores
        """
        import re
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', stream_id))


class GStreamerTestCommandBuilder:
    """Builder for GStreamer test stream commands.

    Generates GStreamer pipelines for publishing test streams with:
    - videotestsrc pattern (SMPTE bars)
    - audiotestsrc sine wave
    - H.264 + AAC codec configuration
    - RTMP output to MediaMTX
    """

    DEFAULT_VIDEO_SIZE = (1280, 720)
    DEFAULT_VIDEO_RATE = 30
    DEFAULT_AUDIO_FREQ = 1000
    DEFAULT_AUDIO_RATE = 48000
    DEFAULT_VIDEO_BITRATE = 2000  # kbps
    DEFAULT_AUDIO_BITRATE = 128000  # bps

    def __init__(
        self,
        rtmp_host: str = "localhost",
        rtmp_port: int = 1935,
    ):
        self.rtmp_host = rtmp_host
        self.rtmp_port = rtmp_port

    def build_publish_command(
        self,
        stream_id: str,
        video_pattern: str = "smpte",
        video_size: tuple | None = None,
        video_rate: int | None = None,
        audio_freq: int | None = None,
        video_bitrate: int | None = None,
        audio_bitrate: int | None = None,
        query_params: str | None = None,
    ) -> list[str]:
        """Build GStreamer command to publish test stream.

        Args:
            stream_id: Unique identifier for the stream
            video_pattern: GStreamer videotestsrc pattern (e.g., "smpte", "ball")
            video_size: Video resolution tuple (width, height)
            video_rate: Video frame rate
            audio_freq: Audio sine wave frequency in Hz
            video_bitrate: Video bitrate in kbps
            audio_bitrate: Audio bitrate in bps
            query_params: Optional query string

        Returns:
            List of command arguments suitable for subprocess

        Raises:
            ValueError: If stream_id is invalid
        """
        if not stream_id:
            raise ValueError("stream_id cannot be empty")
        if not self._is_valid_stream_id(stream_id):
            raise ValueError(
                f"Invalid stream_id '{stream_id}': must contain only "
                "alphanumeric characters, hyphens, and underscores"
            )

        # Use defaults
        width, height = video_size or self.DEFAULT_VIDEO_SIZE
        video_rate = video_rate or self.DEFAULT_VIDEO_RATE
        audio_freq = audio_freq or self.DEFAULT_AUDIO_FREQ
        video_bitrate = video_bitrate or self.DEFAULT_VIDEO_BITRATE
        audio_bitrate = audio_bitrate or self.DEFAULT_AUDIO_BITRATE

        # Build RTMP URL
        rtmp_url = self._build_rtmp_url(stream_id, query_params)

        # Build GStreamer pipeline string
        pipeline = self._build_pipeline_string(
            video_pattern=video_pattern,
            width=width,
            height=height,
            video_rate=video_rate,
            audio_freq=audio_freq,
            video_bitrate=video_bitrate,
            audio_bitrate=audio_bitrate,
            rtmp_url=rtmp_url,
        )

        return ["gst-launch-1.0"] + pipeline.split()

    def _build_pipeline_string(
        self,
        video_pattern: str,
        width: int,
        height: int,
        video_rate: int,
        audio_freq: int,
        video_bitrate: int,
        audio_bitrate: int,
        rtmp_url: str,
    ) -> str:
        """Build GStreamer pipeline as a string."""
        return (
            f"videotestsrc pattern={video_pattern} ! "
            f"video/x-raw,width={width},height={height},framerate={video_rate}/1 ! "
            f"x264enc tune=zerolatency bitrate={video_bitrate} ! h264parse ! "
            f"flvmux name=mux ! rtmpsink location=\"{rtmp_url}\" "
            f"audiotestsrc wave=sine freq={audio_freq} ! "
            f"audio/x-raw,rate={self.DEFAULT_AUDIO_RATE},channels=2 ! "
            f"voaacenc bitrate={audio_bitrate} ! aacparse ! mux."
        )

    def _build_rtmp_url(
        self,
        stream_id: str,
        query_params: str | None = None
    ) -> str:
        """Build RTMP URL for stream publishing."""
        base_url = f"rtmp://{self.rtmp_host}:{self.rtmp_port}/live/{stream_id}/in"
        if query_params:
            return f"{base_url}?{query_params}"
        return base_url

    def _is_valid_stream_id(self, stream_id: str) -> bool:
        """Check if stream ID contains only valid characters."""
        import re
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', stream_id))


# =============================================================================
# UNIT TESTS - Test First (TDD)
# =============================================================================


class TestFFmpegCommandBuilderRTMPURL:
    """Test FFmpeg command includes correct RTMP URL format."""

    def test_build_rtmp_url_format_default(self):
        """Test RTMP URL has correct format: rtmp://host:port/live/<streamId>/in"""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        # Find the RTMP URL in command
        rtmp_url = cmd[-1]  # Last argument is the URL

        assert rtmp_url == "rtmp://localhost:1935/live/test-stream/in"

    def test_build_rtmp_url_custom_host_port(self):
        """Test RTMP URL with custom host and port."""
        builder = FFmpegTestCommandBuilder(rtmp_host="mediamtx", rtmp_port=1936)
        cmd = builder.build_publish_command("my-stream")

        rtmp_url = cmd[-1]
        assert rtmp_url == "rtmp://mediamtx:1936/live/my-stream/in"

    def test_build_rtmp_url_with_query_params(self):
        """Test RTMP URL includes query parameters."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream", query_params="lang=es")

        rtmp_url = cmd[-1]
        assert rtmp_url == "rtmp://localhost:1935/live/test-stream/in?lang=es"

    def test_build_rtmp_url_complex_query_params(self):
        """Test RTMP URL with complex query parameters."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command(
            "test-stream",
            query_params="lang=es&bitrate=high&user=test123"
        )

        rtmp_url = cmd[-1]
        assert "?lang=es&bitrate=high&user=test123" in rtmp_url


class TestFFmpegCommandBuilderCodecs:
    """Test FFmpeg command includes H.264 + AAC codec configuration."""

    def test_command_includes_h264_codec(self):
        """Test command includes H.264 video codec (-c:v libx264)."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        assert "-c:v" in cmd
        video_codec_idx = cmd.index("-c:v")
        assert cmd[video_codec_idx + 1] == "libx264"

    def test_command_includes_aac_codec(self):
        """Test command includes AAC audio codec (-c:a aac)."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        assert "-c:a" in cmd
        audio_codec_idx = cmd.index("-c:a")
        assert cmd[audio_codec_idx + 1] == "aac"

    def test_command_includes_zerolatency_tune(self):
        """Test command includes zero-latency tuning for low latency streaming."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        assert "-tune" in cmd
        tune_idx = cmd.index("-tune")
        assert cmd[tune_idx + 1] == "zerolatency"

    def test_command_includes_veryfast_preset(self):
        """Test command includes veryfast preset for real-time encoding."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        assert "-preset" in cmd
        preset_idx = cmd.index("-preset")
        assert cmd[preset_idx + 1] == "veryfast"

    def test_command_includes_flv_output_format(self):
        """Test command uses FLV format for RTMP output."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        assert "-f" in cmd
        # Find the output format (not input format)
        format_indices = [i for i, arg in enumerate(cmd) if arg == "-f"]
        # Last -f is for output
        output_format_idx = format_indices[-1]
        assert cmd[output_format_idx + 1] == "flv"

    def test_command_includes_video_bitrate(self):
        """Test command includes video bitrate setting."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream", video_bitrate="3000k")

        assert "-b:v" in cmd
        bitrate_idx = cmd.index("-b:v")
        assert cmd[bitrate_idx + 1] == "3000k"

    def test_command_includes_audio_bitrate(self):
        """Test command includes audio bitrate setting."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream", audio_bitrate="192k")

        assert "-b:a" in cmd
        bitrate_idx = cmd.index("-b:a")
        assert cmd[bitrate_idx + 1] == "192k"


class TestFFmpegCommandBuilderSources:
    """Test FFmpeg command includes testsrc video and sine audio sources."""

    def test_command_includes_testsrc_video(self):
        """Test command uses lavfi testsrc for video input."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        # Find testsrc input
        cmd_str = " ".join(cmd)
        assert "testsrc=" in cmd_str

    def test_command_includes_sine_audio(self):
        """Test command uses lavfi sine wave for audio input."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        cmd_str = " ".join(cmd)
        assert "sine=" in cmd_str

    def test_command_uses_lavfi_input(self):
        """Test command uses lavfi filter for test sources."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        # Count lavfi inputs (video + audio)
        lavfi_count = cmd.count("lavfi")
        assert lavfi_count == 2  # One for video, one for audio

    def test_command_video_size_configuration(self):
        """Test command includes video size in testsrc."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream", video_size="1920x1080")

        cmd_str = " ".join(cmd)
        assert "size=1920x1080" in cmd_str

    def test_command_video_rate_configuration(self):
        """Test command includes frame rate in testsrc."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream", video_rate=60)

        cmd_str = " ".join(cmd)
        assert "rate=60" in cmd_str

    def test_command_audio_frequency_configuration(self):
        """Test command includes audio frequency in sine source."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream", audio_freq=440)

        cmd_str = " ".join(cmd)
        assert "frequency=440" in cmd_str

    def test_command_default_values(self):
        """Test command uses default values when not specified."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        cmd_str = " ".join(cmd)
        # Default video: 1280x720 at 30fps
        assert "size=1280x720" in cmd_str
        assert "rate=30" in cmd_str
        # Default audio: 1kHz sine
        assert "frequency=1000" in cmd_str
        # Default bitrates
        assert "2000k" in cmd_str  # video bitrate
        assert "128k" in cmd_str   # audio bitrate


class TestFFmpegCommandBuilderDuration:
    """Test FFmpeg command duration handling."""

    def test_command_with_duration(self):
        """Test command includes duration when specified."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream", duration=10)

        assert "-t" in cmd
        duration_idx = cmd.index("-t")
        assert cmd[duration_idx + 1] == "10"

    def test_command_without_duration(self):
        """Test command has no duration when not specified (infinite stream)."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        assert "-t" not in cmd


class TestFFmpegCommandBuilderStreamIdValidation:
    """Test FFmpeg command stream ID validation."""

    def test_valid_stream_id_alphanumeric(self):
        """Test valid stream ID with alphanumeric characters."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test123")

        assert "test123" in cmd[-1]

    def test_valid_stream_id_with_hyphens(self):
        """Test valid stream ID with hyphens."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream-123")

        assert "test-stream-123" in cmd[-1]

    def test_valid_stream_id_with_underscores(self):
        """Test valid stream ID with underscores."""
        builder = FFmpegTestCommandBuilder()
        cmd = builder.build_publish_command("test_stream_123")

        assert "test_stream_123" in cmd[-1]

    def test_invalid_stream_id_empty(self):
        """Test error on empty stream ID."""
        builder = FFmpegTestCommandBuilder()

        with pytest.raises(ValueError, match="cannot be empty"):
            builder.build_publish_command("")

    def test_invalid_stream_id_special_chars(self):
        """Test error on stream ID with special characters."""
        builder = FFmpegTestCommandBuilder()

        with pytest.raises(ValueError, match="Invalid stream_id"):
            builder.build_publish_command("test/stream")

    def test_invalid_stream_id_spaces(self):
        """Test error on stream ID with spaces."""
        builder = FFmpegTestCommandBuilder()

        with pytest.raises(ValueError, match="Invalid stream_id"):
            builder.build_publish_command("test stream")

    def test_invalid_stream_id_unicode(self):
        """Test error on stream ID with unicode characters."""
        builder = FFmpegTestCommandBuilder()

        with pytest.raises(ValueError, match="Invalid stream_id"):
            builder.build_publish_command("test-stream-\u4e2d\u6587")


class TestFFmpegCommandBuilderStringOutput:
    """Test FFmpeg command string output for documentation."""

    def test_build_command_string_is_shell_safe(self):
        """Test command string is properly shell-escaped."""
        builder = FFmpegTestCommandBuilder()
        cmd_str = builder.build_publish_command_string("test-stream")

        # Should be a string
        assert isinstance(cmd_str, str)
        # Should start with ffmpeg
        assert cmd_str.startswith("ffmpeg")
        # Should contain RTMP URL
        assert "rtmp://localhost:1935/live/test-stream/in" in cmd_str

    def test_build_command_string_with_all_options(self):
        """Test command string includes all options."""
        builder = FFmpegTestCommandBuilder()
        cmd_str = builder.build_publish_command_string(
            "test-stream",
            duration=30,
            video_size="1920x1080",
            video_rate=60,
            audio_freq=880,
            query_params="lang=en"
        )

        # Check all options are present
        assert "1920x1080" in cmd_str
        assert "rate=60" in cmd_str
        assert "frequency=880" in cmd_str
        assert "-t" in cmd_str
        assert "lang=en" in cmd_str


class TestGStreamerCommandBuilder:
    """Test GStreamer command builder."""

    def test_build_rtmp_url_format(self):
        """Test GStreamer builds correct RTMP URL."""
        builder = GStreamerTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        cmd_str = " ".join(cmd)
        assert "rtmp://localhost:1935/live/test-stream/in" in cmd_str

    def test_command_includes_videotestsrc(self):
        """Test command uses videotestsrc."""
        builder = GStreamerTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        cmd_str = " ".join(cmd)
        assert "videotestsrc" in cmd_str

    def test_command_includes_audiotestsrc(self):
        """Test command uses audiotestsrc."""
        builder = GStreamerTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        cmd_str = " ".join(cmd)
        assert "audiotestsrc" in cmd_str

    def test_command_includes_x264enc(self):
        """Test command uses x264enc for H.264."""
        builder = GStreamerTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        cmd_str = " ".join(cmd)
        assert "x264enc" in cmd_str

    def test_command_includes_aac_encoder(self):
        """Test command uses voaacenc for AAC."""
        builder = GStreamerTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        cmd_str = " ".join(cmd)
        assert "voaacenc" in cmd_str

    def test_command_includes_flvmux(self):
        """Test command uses flvmux for RTMP output."""
        builder = GStreamerTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        cmd_str = " ".join(cmd)
        assert "flvmux" in cmd_str

    def test_command_includes_rtmpsink(self):
        """Test command uses rtmpsink."""
        builder = GStreamerTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream")

        cmd_str = " ".join(cmd)
        assert "rtmpsink" in cmd_str

    def test_invalid_stream_id_raises_error(self):
        """Test error on invalid stream ID."""
        builder = GStreamerTestCommandBuilder()

        with pytest.raises(ValueError, match="cannot be empty"):
            builder.build_publish_command("")

    def test_video_pattern_configuration(self):
        """Test video pattern can be configured."""
        builder = GStreamerTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream", video_pattern="ball")

        cmd_str = " ".join(cmd)
        assert "pattern=ball" in cmd_str

    def test_query_params_included(self):
        """Test query parameters included in URL."""
        builder = GStreamerTestCommandBuilder()
        cmd = builder.build_publish_command("test-stream", query_params="lang=es")

        cmd_str = " ".join(cmd)
        assert "?lang=es" in cmd_str
