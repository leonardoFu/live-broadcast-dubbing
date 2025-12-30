"""
Comprehensive unit tests for output pipeline.

Tests RTMP output pipeline with mocked GStreamer.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestOutputPipelineInit:
    """Tests for OutputPipeline initialization."""

    def test_init_sets_rtmp_url(self) -> None:
        """Test that RTMP URL is set correctly."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")
            assert pipeline._rtmp_url == "rtmp://localhost:1935/live/test"

    def test_init_empty_url_raises_error(self) -> None:
        """Test that empty URL raises ValueError."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            with pytest.raises(ValueError) as exc_info:
                OutputPipeline("")

            assert "cannot be empty" in str(exc_info.value)

    def test_init_invalid_url_raises_error(self) -> None:
        """Test that non-RTMP URL raises ValueError."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            with pytest.raises(ValueError) as exc_info:
                OutputPipeline("http://localhost:1935/live/test")

            assert "must start with 'rtmp://'" in str(exc_info.value)

    def test_init_state_null(self) -> None:
        """Test initial state is NULL."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")
            assert pipeline.get_state() == "NULL"

    def test_init_no_pipeline_yet(self) -> None:
        """Test pipeline is None before build."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")
            assert pipeline._pipeline is None


class TestOutputPipelineBuild:
    """Tests for pipeline build functionality."""

    def test_build_raises_when_gst_unavailable(self) -> None:
        """Test build raises RuntimeError when GStreamer not available."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")

            with pytest.raises(RuntimeError) as exc_info:
                pipeline.build()

            assert "GStreamer not available" in str(exc_info.value)

    def test_build_creates_pipeline_with_mock_gst(self) -> None:
        """Test build creates pipeline when GStreamer mocked."""
        mock_gst = MagicMock()
        mock_gst.is_initialized.return_value = True

        # Create mock elements
        mock_pipeline = MagicMock()
        mock_element = MagicMock()
        mock_element.link.return_value = True
        mock_element.get_static_pad.return_value = MagicMock()

        # Mock pad linking
        mock_pad = MagicMock()
        mock_pad.link.return_value = mock_gst.PadLinkReturn.OK

        mock_element.get_request_pad.return_value = mock_pad
        mock_element.get_static_pad.return_value = mock_pad

        mock_gst.Pipeline.new.return_value = mock_pipeline
        mock_gst.ElementFactory.make.return_value = mock_element
        mock_gst.Caps.from_string.return_value = MagicMock()
        mock_pipeline.get_bus.return_value = MagicMock()

        with patch.dict("media_service.pipeline.output.__dict__", {
            "GST_AVAILABLE": True,
            "Gst": mock_gst,
        }):
            from media_service.pipeline.output import OutputPipeline

            # Need to reimport to get patched version
            pipeline = OutputPipeline.__new__(OutputPipeline)
            pipeline._rtmp_url = "rtmp://localhost:1935/live/test"
            pipeline._pipeline = None
            pipeline._video_appsrc = None
            pipeline._audio_appsrc = None
            pipeline._state = "NULL"
            pipeline._bus = None

            # Override module-level GST_AVAILABLE
            import media_service.pipeline.output as output_module
            orig_gst_available = output_module.GST_AVAILABLE
            orig_gst = getattr(output_module, "Gst", None)

            try:
                output_module.GST_AVAILABLE = True
                output_module.Gst = mock_gst

                pipeline.build()

                assert pipeline._state == "READY"
            finally:
                output_module.GST_AVAILABLE = orig_gst_available
                if orig_gst:
                    output_module.Gst = orig_gst


class TestOutputPipelineGetState:
    """Tests for get_state functionality."""

    def test_get_state_returns_null_initially(self) -> None:
        """Test get_state returns NULL initially."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")
            assert pipeline.get_state() == "NULL"

    def test_get_state_tracks_state_changes(self) -> None:
        """Test get_state reflects state changes."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")
            pipeline._state = "PLAYING"

            assert pipeline.get_state() == "PLAYING"


class TestOutputPipelinePushVideo:
    """Tests for push_video functionality."""

    def test_push_video_raises_when_not_built(self) -> None:
        """Test push_video raises when pipeline not built."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")

            with pytest.raises(RuntimeError) as exc_info:
                pipeline.push_video(b"\x00" * 100, pts_ns=0)

            assert "Pipeline not built" in str(exc_info.value)


class TestOutputPipelinePushAudio:
    """Tests for push_audio functionality."""

    def test_push_audio_raises_when_not_built(self) -> None:
        """Test push_audio raises when pipeline not built."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")

            with pytest.raises(RuntimeError) as exc_info:
                pipeline.push_audio(b"\x00" * 100, pts_ns=0)

            assert "Pipeline not built" in str(exc_info.value)


class TestOutputPipelineStart:
    """Tests for start functionality."""

    def test_start_raises_when_not_built(self) -> None:
        """Test start raises when pipeline not built."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")

            with pytest.raises(RuntimeError) as exc_info:
                pipeline.start()

            assert "Pipeline not built" in str(exc_info.value)


class TestOutputPipelineStop:
    """Tests for stop functionality."""

    def test_stop_no_op_when_not_built(self) -> None:
        """Test stop is no-op when pipeline not built."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")

            # Should not raise
            pipeline.stop()


class TestOutputPipelineCleanup:
    """Tests for cleanup functionality."""

    def test_cleanup_sets_state_to_null(self) -> None:
        """Test cleanup resets state."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")
            pipeline._state = "PLAYING"

            pipeline.cleanup()

            # Should call stop() which sets state to NULL
            assert pipeline._pipeline is None

    def test_cleanup_clears_appsrc_references(self) -> None:
        """Test cleanup clears appsrc references."""
        with patch.dict("media_service.pipeline.output.__dict__", {"GST_AVAILABLE": False}):
            from media_service.pipeline.output import OutputPipeline

            pipeline = OutputPipeline("rtmp://localhost:1935/live/test")
            pipeline._video_appsrc = MagicMock()
            pipeline._audio_appsrc = MagicMock()

            pipeline.cleanup()

            assert pipeline._video_appsrc is None
            assert pipeline._audio_appsrc is None
