"""
Unit tests for FFmpeg output pipeline.

Tests RTMP output pipeline with mocked subprocess and OS operations.
"""

from __future__ import annotations

from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock, mock_open, patch

import pytest

from media_service.pipeline.ffmpeg_output import FFmpegOutputPipeline


class TestFFmpegOutputPipelineInit:
    """Tests for FFmpegOutputPipeline initialization."""

    def test_init_sets_rtmp_url(self) -> None:
        """Test that RTMP URL is set correctly."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        assert pipeline._rtmp_url == "rtmp://localhost:1935/live/test"

    def test_init_empty_url_raises_error(self) -> None:
        """Test that empty URL raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            FFmpegOutputPipeline("")

        assert "cannot be empty" in str(exc_info.value)

    def test_init_invalid_url_raises_error(self) -> None:
        """Test that non-RTMP URL raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            FFmpegOutputPipeline("http://localhost:1935/live/test")

        assert "must start with 'rtmp://'" in str(exc_info.value)

    def test_init_state_null(self) -> None:
        """Test initial state is NULL."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        assert pipeline.get_state() == "NULL"

    def test_init_no_process_yet(self) -> None:
        """Test process is None before start."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        assert pipeline._process is None

    def test_init_queue_created(self) -> None:
        """Test segment queue is initialized."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        assert isinstance(pipeline._segment_queue, Queue)


class TestFFmpegOutputPipelineBuild:
    """Tests for pipeline build functionality."""

    def test_build_creates_temp_dir(self) -> None:
        """Test build creates temporary directory."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        with patch("tempfile.TemporaryDirectory") as mock_temp:
            mock_temp.return_value.name = "/tmp/test_dir"

            pipeline.build()

            mock_temp.assert_called_once()

        assert pipeline._state == "READY"

    def test_build_handles_error(self) -> None:
        """Test build handles temp directory creation error."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        with patch("tempfile.TemporaryDirectory", side_effect=OSError("Permission denied")):
            with pytest.raises(RuntimeError) as exc_info:
                pipeline.build()

            assert "Failed to build pipeline" in str(exc_info.value)


class TestFFmpegOutputPipelineGetState:
    """Tests for get_state functionality."""

    def test_get_state_returns_null_initially(self) -> None:
        """Test get_state returns NULL initially."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        assert pipeline.get_state() == "NULL"

    def test_get_state_tracks_state_changes(self) -> None:
        """Test get_state reflects state changes."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        pipeline._state = "PLAYING"
        assert pipeline.get_state() == "PLAYING"


class TestFFmpegOutputPipelinePushVideo:
    """Tests for push_video functionality."""

    def test_push_video_returns_false_when_not_playing(self) -> None:
        """Test push_video returns False when pipeline not playing."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        result = pipeline.push_video(b"\x00" * 100, pts_ns=0)

        assert result is False

    def test_push_video_stores_data_when_playing(self) -> None:
        """Test push_video stores data when pipeline is playing."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        pipeline._state = "PLAYING"

        result = pipeline.push_video(b"\x00" * 100, pts_ns=0)

        assert result is True
        assert hasattr(pipeline, "_pending_video")
        assert pipeline._pending_video is not None

    def test_push_video_extracts_sps_pps(self) -> None:
        """Test push_video extracts SPS/PPS from H.264 data."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        pipeline._state = "PLAYING"

        # H.264 data with SPS (NAL type 7) and PPS (NAL type 8)
        sps = b"\x00\x00\x00\x01\x67\x42\x00\x1e"  # SPS
        pps = b"\x00\x00\x00\x01\x68\xce\x3c\x80"  # PPS
        idr = b"\x00\x00\x00\x01\x65\x00\x00\x00"  # IDR frame
        h264_data = sps + pps + idr

        pipeline.push_video(h264_data, pts_ns=0)

        assert pipeline._sps_pps_data is not None


class TestFFmpegOutputPipelinePushAudio:
    """Tests for push_audio functionality."""

    def test_push_audio_returns_false_when_not_playing(self) -> None:
        """Test push_audio returns False when pipeline not playing."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        result = pipeline.push_audio(b"\x00" * 100, pts_ns=0)

        assert result is False

    def test_push_audio_returns_false_when_no_pending_video(self) -> None:
        """Test push_audio returns False when no pending video."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        pipeline._state = "PLAYING"

        result = pipeline.push_audio(b"\x00" * 100, pts_ns=0)

        assert result is False

    @patch("subprocess.run")
    def test_push_audio_muxes_with_pending_video(self, mock_run: MagicMock) -> None:
        """Test push_audio muxes with pending video data."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        pipeline._state = "PLAYING"
        pipeline._temp_dir = MagicMock()
        pipeline._temp_dir.name = "/tmp/test"

        # Store pending video
        pipeline._pending_video = (b"video_data", 0, 1000000000)

        # Mock successful muxing
        mock_run.return_value.returncode = 0

        with patch.object(Path, "write_bytes"):
            with patch.object(Path, "read_bytes", return_value=b"muxed_data"):
                with patch.object(Path, "unlink"):
                    result = pipeline.push_audio(b"audio_data", pts_ns=0)

        assert result is True
        assert pipeline._pending_video is None


class TestFFmpegOutputPipelineStart:
    """Tests for start functionality."""

    def test_start_returns_false_when_not_ready(self) -> None:
        """Test start returns False when pipeline not in READY state."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        result = pipeline.start()

        assert result is False

    @patch("subprocess.Popen")
    def test_start_launches_ffmpeg(self, mock_popen: MagicMock) -> None:
        """Test start launches ffmpeg subprocess."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        pipeline._state = "READY"

        mock_popen.return_value.pid = 12345

        result = pipeline.start()

        assert result is True
        assert pipeline._state == "PLAYING"
        mock_popen.assert_called_once()

        # Verify ffmpeg command includes -re flag
        call_args = mock_popen.call_args
        ffmpeg_cmd = call_args[0][0]
        assert "ffmpeg" in ffmpeg_cmd
        assert "-re" in ffmpeg_cmd
        assert "pipe:0" in ffmpeg_cmd

    @patch("subprocess.Popen", side_effect=FileNotFoundError("ffmpeg not found"))
    def test_start_handles_ffmpeg_not_found(self, mock_popen: MagicMock) -> None:
        """Test start handles missing ffmpeg."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        pipeline._state = "READY"

        result = pipeline.start()

        assert result is False
        assert pipeline._state == "ERROR"


class TestFFmpegOutputPipelineStop:
    """Tests for stop functionality."""

    def test_stop_no_op_when_null(self) -> None:
        """Test stop is no-op when pipeline state is NULL."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        # Should not raise
        pipeline.stop()

        assert pipeline._state == "NULL"

    def test_stop_terminates_ffmpeg(self) -> None:
        """Test stop terminates ffmpeg process."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        pipeline._state = "PLAYING"
        pipeline._publisher_running = False

        mock_process = MagicMock()
        mock_process.stdin = MagicMock()
        pipeline._process = mock_process

        pipeline.stop()

        mock_process.stdin.close.assert_called_once()
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called()


class TestFFmpegOutputPipelineCleanup:
    """Tests for cleanup functionality."""

    def test_cleanup_calls_stop(self) -> None:
        """Test cleanup calls stop."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        with patch.object(pipeline, "stop") as mock_stop:
            pipeline.cleanup()

            mock_stop.assert_called_once()

    def test_cleanup_removes_temp_dir(self) -> None:
        """Test cleanup removes temporary directory."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        mock_temp_dir = MagicMock()
        pipeline._temp_dir = mock_temp_dir

        with patch.object(pipeline, "stop"):
            pipeline.cleanup()

        mock_temp_dir.cleanup.assert_called_once()


class TestFFmpegOutputPipelineConvertM4aToAdts:
    """Tests for M4A to ADTS conversion."""

    @patch("subprocess.run")
    def test_convert_m4a_bytes_to_adts_success(self, mock_run: MagicMock) -> None:
        """Test successful M4A to ADTS conversion."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        mock_run.return_value.returncode = 0

        # Mock file operations
        with patch("builtins.open", mock_open(read_data=b"\xff\xf1\x00")):
            with patch("os.unlink"):
                result = pipeline.convert_m4a_bytes_to_adts(b"m4a_data")

        assert result == b"\xff\xf1\x00"
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_convert_m4a_bytes_to_adts_failure(self, mock_run: MagicMock) -> None:
        """Test M4A to ADTS conversion failure."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = b"conversion error"

        with patch("os.unlink"):
            with pytest.raises(RuntimeError) as exc_info:
                pipeline.convert_m4a_bytes_to_adts(b"m4a_data")

        assert "M4A conversion failed" in str(exc_info.value)


class TestFFmpegOutputPipelineExtractSpsPps:
    """Tests for SPS/PPS extraction."""

    def test_extract_sps_pps_with_4byte_start_codes(self) -> None:
        """Test extraction with 4-byte start codes."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        sps = b"\x00\x00\x00\x01\x67\x42\x00\x1e\x9a\x74"
        pps = b"\x00\x00\x00\x01\x68\xce\x3c\x80"
        idr = b"\x00\x00\x00\x01\x65\x88"
        data = sps + pps + idr

        result = pipeline._extract_sps_pps(data)

        assert result is not None
        assert b"\x67" in result  # SPS NAL type
        assert b"\x68" in result  # PPS NAL type

    def test_extract_sps_pps_with_3byte_start_codes(self) -> None:
        """Test extraction with 3-byte start codes."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        sps = b"\x00\x00\x01\x67\x42\x00\x1e"
        pps = b"\x00\x00\x01\x68\xce\x3c\x80"
        data = sps + pps

        result = pipeline._extract_sps_pps(data)

        assert result is not None
        # Result should have 4-byte start codes
        assert b"\x00\x00\x00\x01\x67" in result

    def test_extract_sps_pps_returns_none_when_missing(self) -> None:
        """Test extraction returns None when SPS/PPS missing."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")

        # Only IDR frame, no SPS/PPS
        data = b"\x00\x00\x00\x01\x65\x88\x84"

        result = pipeline._extract_sps_pps(data)

        assert result is None


class TestFFmpegOutputPipelineMuxSegment:
    """Tests for segment muxing."""

    @patch("subprocess.run")
    def test_mux_segment_success(self, mock_run: MagicMock) -> None:
        """Test successful segment muxing."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        pipeline._temp_dir = MagicMock()
        pipeline._temp_dir.name = "/tmp/test"

        mock_run.return_value.returncode = 0

        with patch.object(Path, "write_bytes"):
            with patch.object(Path, "read_bytes", return_value=b"muxed_flv_data"):
                with patch.object(Path, "unlink"):
                    result = pipeline._mux_segment(
                        video_data=b"h264_data",
                        audio_data=b"aac_data",
                        pts_ns=0,
                        video_duration_ns=1000000000,
                        audio_duration_ns=1000000000,
                    )

        assert result == b"muxed_flv_data"

    @patch("subprocess.run")
    def test_mux_segment_failure(self, mock_run: MagicMock) -> None:
        """Test muxing failure."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        pipeline._temp_dir = MagicMock()
        pipeline._temp_dir.name = "/tmp/test"

        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = b"mux error"

        with patch.object(Path, "write_bytes"):
            with patch.object(Path, "unlink"):
                result = pipeline._mux_segment(
                    video_data=b"h264_data",
                    audio_data=b"aac_data",
                    pts_ns=0,
                    video_duration_ns=1000000000,
                    audio_duration_ns=1000000000,
                )

        assert result is None

    def test_mux_segment_no_temp_dir(self) -> None:
        """Test muxing fails without temp directory."""
        pipeline = FFmpegOutputPipeline("rtmp://localhost:1935/live/test")
        pipeline._temp_dir = None

        result = pipeline._mux_segment(
            video_data=b"h264_data",
            audio_data=b"aac_data",
            pts_ns=0,
            video_duration_ns=1000000000,
            audio_duration_ns=1000000000,
        )

        assert result is None
