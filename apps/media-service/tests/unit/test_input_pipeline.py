"""
Unit tests for InputPipeline class.

Tests T022 and T024 from tasks.md - validating input pipeline construction.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_gst_module():
    """Create a comprehensive mock for GStreamer module."""
    mock_gst = MagicMock()

    # Mock common GStreamer types and constants
    mock_gst.is_initialized = MagicMock(return_value=True)
    mock_gst.init = MagicMock()

    # Mock element factory
    mock_element = MagicMock()
    mock_gst.ElementFactory.make = MagicMock(return_value=mock_element)

    # Mock Pipeline
    mock_pipeline = MagicMock()
    mock_gst.Pipeline.new = MagicMock(return_value=mock_pipeline)
    mock_pipeline.add = MagicMock()
    mock_pipeline.set_state = MagicMock(return_value=1)  # SUCCESS

    # Mock Caps
    mock_caps = MagicMock()
    mock_gst.Caps.from_string = MagicMock(return_value=mock_caps)

    # State constants
    mock_gst.State.NULL = 0
    mock_gst.State.READY = 1
    mock_gst.State.PAUSED = 2
    mock_gst.State.PLAYING = 3
    mock_gst.StateChangeReturn.SUCCESS = 1
    mock_gst.StateChangeReturn.ASYNC = 2

    return mock_gst, mock_pipeline, mock_element


class TestInputPipelineBuild:
    """Tests for InputPipeline.build() method."""

    def test_input_pipeline_creates_valid_pipeline(self, mock_gst_module) -> None:
        """Test that InputPipeline.build() constructs a valid pipeline."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtsp_url="rtsp://mediamtx:8554/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )

        pipeline.build()

        # Verify pipeline was created
        assert pipeline._pipeline is not None

    def test_input_pipeline_registers_video_callback(self, mock_gst_module) -> None:
        """Test that video appsink callback is registered."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        video_callback = MagicMock()
        pipeline = InputPipeline(
            rtsp_url="rtsp://localhost:8554/test",
            on_video_buffer=video_callback,
            on_audio_buffer=MagicMock(),
        )

        pipeline.build()

        # Verify callback is stored
        assert pipeline._on_video_buffer == video_callback

    def test_input_pipeline_registers_audio_callback(self, mock_gst_module) -> None:
        """Test that audio appsink callback is registered."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        audio_callback = MagicMock()
        pipeline = InputPipeline(
            rtsp_url="rtsp://localhost:8554/test",
            on_video_buffer=MagicMock(),
            on_audio_buffer=audio_callback,
        )

        pipeline.build()

        assert pipeline._on_audio_buffer == audio_callback


class TestInputPipelineStateTransitions:
    """Tests for InputPipeline state transitions."""

    def test_pipeline_starts_in_null_state(self, mock_gst: MagicMock) -> None:
        """Test that pipeline starts in NULL state."""
        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtsp_url="rtsp://localhost:8554/test",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )

        assert pipeline.get_state() == "NULL"

    def test_pipeline_transitions_to_playing(self, mock_gst_module) -> None:
        """Test that pipeline can transition to PLAYING state."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtsp_url="rtsp://localhost:8554/test",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()
        pipeline.start()

        # Verify set_state was called with PLAYING
        pipeline._pipeline.set_state.assert_called()

    def test_pipeline_stop_transitions_to_null(self, mock_gst_module) -> None:
        """Test that stop() transitions pipeline to NULL state."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtsp_url="rtsp://localhost:8554/test",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()
        pipeline.start()
        pipeline.stop()

        # Verify set_state was called
        assert pipeline._pipeline.set_state.called


class TestInputPipelineErrorHandling:
    """Tests for InputPipeline error handling."""

    def test_invalid_rtsp_url_raises_error(self, mock_gst: MagicMock) -> None:
        """Test that invalid RTSP URL raises ValueError."""
        from media_service.pipeline.input import InputPipeline

        with pytest.raises(ValueError, match="Invalid RTSP URL"):
            InputPipeline(
                rtsp_url="http://invalid.url",  # Not RTSP
                on_video_buffer=MagicMock(),
                on_audio_buffer=MagicMock(),
            )

    def test_empty_url_raises_error(self, mock_gst: MagicMock) -> None:
        """Test that empty URL raises ValueError."""
        from media_service.pipeline.input import InputPipeline

        with pytest.raises(ValueError, match="RTSP URL cannot be empty"):
            InputPipeline(
                rtsp_url="",
                on_video_buffer=MagicMock(),
                on_audio_buffer=MagicMock(),
            )


class TestRtspInputUrlFormat:
    """Contract tests for RTSP input URL format (T024)."""

    def test_rtsp_url_matches_mediamtx_format(self, mock_gst: MagicMock) -> None:
        """Test URL matches MediaMTX expectations: rtsp://host:port/path."""
        from media_service.pipeline.input import InputPipeline

        # Valid MediaMTX URL format
        pipeline = InputPipeline(
            rtsp_url="rtsp://mediamtx:8554/live/stream123/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )

        assert pipeline._rtsp_url == "rtsp://mediamtx:8554/live/stream123/in"

    def test_rtsp_url_with_localhost(self, mock_gst: MagicMock) -> None:
        """Test URL with localhost is valid."""
        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtsp_url="rtsp://localhost:8554/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )

        assert "localhost" in pipeline._rtsp_url

    def test_rtsp_url_with_ip_address(self, mock_gst: MagicMock) -> None:
        """Test URL with IP address is valid."""
        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtsp_url="rtsp://192.168.1.100:8554/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )

        assert "192.168.1.100" in pipeline._rtsp_url

    def test_rtsp_url_must_start_with_rtsp(self, mock_gst: MagicMock) -> None:
        """Test URL must start with rtsp://."""
        from media_service.pipeline.input import InputPipeline

        with pytest.raises(ValueError):
            InputPipeline(
                rtsp_url="rtsps://secure.url:8554/test",  # rtsps not rtsp
                on_video_buffer=MagicMock(),
                on_audio_buffer=MagicMock(),
            )
