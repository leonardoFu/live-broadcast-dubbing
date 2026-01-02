"""
Unit tests for InputPipeline class.

Tests for RTMP stream pull migration (spec 020-rtmp-stream-pull).
Validates input pipeline construction with RTMP protocol.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_gst():
    """Create a mock GStreamer module for import patching."""
    mock_gst = MagicMock()
    mock_gst.is_initialized = MagicMock(return_value=True)
    mock_gst.init = MagicMock()
    return mock_gst


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
    mock_gst.StateChangeReturn.FAILURE = 0

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
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
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
            rtmp_url="rtmp://localhost:1935/live/test/in",
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
            rtmp_url="rtmp://localhost:1935/live/test/in",
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
            rtmp_url="rtmp://localhost:1935/live/test/in",
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
            rtmp_url="rtmp://localhost:1935/live/test/in",
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
            rtmp_url="rtmp://localhost:1935/live/test/in",
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

    def test_invalid_rtmp_url_raises_error(self, mock_gst: MagicMock) -> None:
        """Test that invalid RTMP URL raises ValueError."""
        from media_service.pipeline.input import InputPipeline

        with pytest.raises(ValueError, match="must start with 'rtmp://'"):
            InputPipeline(
                rtmp_url="http://invalid.url",  # Not RTMP
                on_video_buffer=MagicMock(),
                on_audio_buffer=MagicMock(),
            )

    def test_empty_url_raises_error(self, mock_gst: MagicMock) -> None:
        """Test that empty URL raises ValueError."""
        from media_service.pipeline.input import InputPipeline

        with pytest.raises(ValueError, match="RTMP URL cannot be empty"):
            InputPipeline(
                rtmp_url="",
                on_video_buffer=MagicMock(),
                on_audio_buffer=MagicMock(),
            )


# =============================================================================
# RTMP URL Validation Tests (T004 - TDD - These tests should FAIL initially)
# =============================================================================


class TestRTMPURLValidation:
    """Unit tests for RTMP URL validation in InputPipeline.

    These tests verify that InputPipeline properly validates RTMP URLs
    as part of the RTSP to RTMP migration (spec 020-rtmp-stream-pull).

    Per TDD workflow, these tests are written BEFORE implementation
    and MUST fail initially.
    """

    def test_rtmp_url_validation_happy_path(self, mock_gst: MagicMock) -> None:
        """Test that valid RTMP URLs are accepted.

        Valid RTMP URL format: rtmp://host:port/app/stream
        """
        from media_service.pipeline.input import InputPipeline

        # Valid RTMP URL should be accepted
        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )

        assert pipeline._rtmp_url == "rtmp://mediamtx:1935/live/test/in"

    def test_rtmp_url_validation_with_localhost(self, mock_gst: MagicMock) -> None:
        """Test RTMP URL with localhost is valid."""
        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://localhost:1935/live/stream/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )

        assert "localhost" in pipeline._rtmp_url

    def test_rtmp_url_validation_with_ip_address(self, mock_gst: MagicMock) -> None:
        """Test RTMP URL with IP address is valid."""
        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://192.168.1.100:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )

        assert "192.168.1.100" in pipeline._rtmp_url

    def test_rtmp_url_validation_error_empty(self, mock_gst: MagicMock) -> None:
        """Test that empty RTMP URL raises ValueError with descriptive message."""
        from media_service.pipeline.input import InputPipeline

        with pytest.raises(ValueError, match="RTMP URL cannot be empty"):
            InputPipeline(
                rtmp_url="",
                on_video_buffer=MagicMock(),
                on_audio_buffer=MagicMock(),
            )

    def test_rtmp_url_validation_error_none(self, mock_gst: MagicMock) -> None:
        """Test that None RTMP URL raises ValueError."""
        from media_service.pipeline.input import InputPipeline

        with pytest.raises(ValueError, match="RTMP URL cannot be empty"):
            InputPipeline(
                rtmp_url=None,  # type: ignore
                on_video_buffer=MagicMock(),
                on_audio_buffer=MagicMock(),
            )

    def test_rtmp_url_validation_error_wrong_protocol_http(
        self, mock_gst: MagicMock
    ) -> None:
        """Test that HTTP URL is rejected with descriptive error."""
        from media_service.pipeline.input import InputPipeline

        with pytest.raises(ValueError, match="must start with 'rtmp://'"):
            InputPipeline(
                rtmp_url="http://localhost:8080/stream",
                on_video_buffer=MagicMock(),
                on_audio_buffer=MagicMock(),
            )

    def test_rtmp_url_validation_error_wrong_protocol_rtsp(
        self, mock_gst: MagicMock
    ) -> None:
        """Test that RTSP URL is rejected - RTMP only after migration."""
        from media_service.pipeline.input import InputPipeline

        with pytest.raises(ValueError, match="must start with 'rtmp://'"):
            InputPipeline(
                rtmp_url="rtsp://localhost:8554/live/stream",
                on_video_buffer=MagicMock(),
                on_audio_buffer=MagicMock(),
            )

    def test_rtmp_url_validation_error_wrong_protocol_rtmps(
        self, mock_gst: MagicMock
    ) -> None:
        """Test that RTMPS URL is rejected (not supported)."""
        from media_service.pipeline.input import InputPipeline

        with pytest.raises(ValueError, match="must start with 'rtmp://'"):
            InputPipeline(
                rtmp_url="rtmps://secure.server:443/stream",
                on_video_buffer=MagicMock(),
                on_audio_buffer=MagicMock(),
            )


# =============================================================================
# RTMP Element Creation Tests (T006 - TDD - These tests should FAIL initially)
# =============================================================================


class TestRTMPElementCreation:
    """Unit tests for RTMP GStreamer element creation.

    These tests verify that InputPipeline.build() creates the correct
    RTMP elements (rtmpsrc, flvdemux) instead of RTSP elements.

    Per TDD workflow, these tests are written BEFORE implementation
    and MUST fail initially.
    """

    def test_build_rtmp_elements_happy_path(self, mock_gst_module) -> None:
        """Test that build() creates correct RTMP elements.

        Expected elements: rtmpsrc, flvdemux, h264parse, aacparse, 2 queues, 2 appsinks
        """
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Verify element factory calls
        make_calls = mock_gst.ElementFactory.make.call_args_list
        element_names = [call[0][0] for call in make_calls]

        # MUST create rtmpsrc (RTMP source)
        assert "rtmpsrc" in element_names, "Must create rtmpsrc element"

        # MUST create flvdemux (FLV demuxer)
        assert "flvdemux" in element_names, "Must create flvdemux element"

        # MUST create parsers
        assert "h264parse" in element_names, "Must create h264parse element"
        assert "aacparse" in element_names, "Must create aacparse element"

    def test_build_rtmp_elements_no_rtspsrc(self, mock_gst_module) -> None:
        """Test that build() does NOT create rtspsrc element."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Verify rtspsrc is NOT created
        make_calls = mock_gst.ElementFactory.make.call_args_list
        element_names = [call[0][0] for call in make_calls]

        assert "rtspsrc" not in element_names, "Must NOT create rtspsrc element"

    def test_build_rtmp_elements_no_depayloaders(self, mock_gst_module) -> None:
        """Test that build() does NOT create RTP depayloader elements."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Verify RTP depayloaders are NOT created
        make_calls = mock_gst.ElementFactory.make.call_args_list
        element_names = [call[0][0] for call in make_calls]

        assert "rtph264depay" not in element_names, "Must NOT create rtph264depay"
        assert "rtpmp4gdepay" not in element_names, "Must NOT create rtpmp4gdepay"
        assert "rtpmp4adepay" not in element_names, "Must NOT create rtpmp4adepay"

    def test_rtmpsrc_location_property(self, mock_gst_module) -> None:
        """Test that rtmpsrc.location property is set to RTMP URL."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        rtmp_url = "rtmp://mediamtx:1935/live/test/in"
        pipeline = InputPipeline(
            rtmp_url=rtmp_url,
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Verify set_property was called with "location" and the URL
        set_property_calls = mock_element.set_property.call_args_list
        location_calls = [
            call for call in set_property_calls
            if len(call[0]) >= 2 and call[0][0] == "location"
        ]

        assert len(location_calls) >= 1, "Must set location property"
        assert location_calls[0][0][1] == rtmp_url, "location must be RTMP URL"

    def test_flvdemux_max_buffers_property(self, mock_gst_module) -> None:
        """Test that flvdemux element is created (max-buffers property support)."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
            max_buffers=10,  # New parameter for buffer control
        )
        pipeline.build()

        # Verify flvdemux was created
        make_calls = mock_gst.ElementFactory.make.call_args_list
        element_names = [call[0][0] for call in make_calls]

        assert "flvdemux" in element_names, "Must create flvdemux element"


# =============================================================================
# Audio Track Validation Tests (T008 - TDD - These tests should FAIL initially)
# =============================================================================


class TestAudioTrackValidation:
    """Unit tests for audio track presence validation.

    These tests verify that InputPipeline validates audio track presence
    during pipeline startup and rejects video-only streams.

    Per TDD workflow, these tests are written BEFORE implementation
    and MUST fail initially.
    """

    def test_audio_validation_success(self, mock_gst_module) -> None:
        """Test audio validation succeeds when both video and audio pads present."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Simulate both pads detected
        pipeline.has_video_pad = True
        pipeline.has_audio_pad = True

        # Validation should pass (no exception)
        pipeline._validate_audio_track(timeout_ms=100)

    def test_audio_validation_error_missing_audio(self, mock_gst_module) -> None:
        """Test RuntimeError raised when audio pad is missing."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Simulate only video pad detected (no audio)
        pipeline.has_video_pad = True
        pipeline.has_audio_pad = False

        # Should raise RuntimeError with descriptive message
        with pytest.raises(RuntimeError, match="Audio track required"):
            pipeline._validate_audio_track(timeout_ms=100)

    def test_audio_validation_timeout(self, mock_gst_module) -> None:
        """Test validation times out if pads not detected within limit."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Simulate no pads detected
        pipeline.has_video_pad = False
        pipeline.has_audio_pad = False

        # Should raise RuntimeError after timeout (not TimeoutError for simplicity)
        with pytest.raises(RuntimeError, match="Audio track required"):
            pipeline._validate_audio_track(timeout_ms=100)


# =============================================================================
# Pad Added Tests (T006 Extended) - Test _on_pad_added method
# =============================================================================


class TestOnPadAdded:
    """Unit tests for InputPipeline._on_pad_added dynamic pad handling.

    These tests verify that flvdemux pad-added signals are handled correctly,
    linking video/x-h264 pads to h264parse and audio/mpeg pads to aacparse.
    """

    def test_on_pad_added_video_pad_links_successfully(self, mock_gst_module) -> None:
        """Test that video/x-h264 pad is linked to h264parse successfully."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        # Set up PadLinkReturn before importing InputPipeline
        mock_gst.PadLinkReturn = MagicMock()
        mock_gst.PadLinkReturn.OK = 0

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Create mock pad with video caps
        mock_pad = MagicMock()
        mock_caps = MagicMock()
        mock_structure = MagicMock()
        mock_structure.get_name.return_value = "video/x-h264"
        mock_caps.is_empty.return_value = False
        mock_caps.get_structure.return_value = mock_structure
        mock_pad.get_current_caps.return_value = mock_caps
        mock_pad.get_name.return_value = "video_0"

        # Mock successful linking - return the actual OK value (0)
        mock_sink_pad = MagicMock()
        mock_sink_pad.is_linked.return_value = False
        pipeline._h264parse = MagicMock()
        pipeline._h264parse.get_static_pad.return_value = mock_sink_pad
        mock_pad.link.return_value = 0  # PadLinkReturn.OK

        # Call _on_pad_added
        pipeline._on_pad_added(MagicMock(), mock_pad)

        # Verify video pad flag set
        assert pipeline.has_video_pad is True

    def test_on_pad_added_audio_pad_links_successfully(self, mock_gst_module) -> None:
        """Test that audio/mpeg pad is linked to aacparse successfully."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        # Set up PadLinkReturn before importing InputPipeline
        mock_gst.PadLinkReturn = MagicMock()
        mock_gst.PadLinkReturn.OK = 0

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Create mock pad with audio caps
        mock_pad = MagicMock()
        mock_caps = MagicMock()
        mock_structure = MagicMock()
        mock_structure.get_name.return_value = "audio/mpeg"
        mock_caps.is_empty.return_value = False
        mock_caps.get_structure.return_value = mock_structure
        mock_pad.get_current_caps.return_value = mock_caps
        mock_pad.get_name.return_value = "audio_0"

        # Mock successful linking - return the actual OK value (0)
        mock_sink_pad = MagicMock()
        mock_sink_pad.is_linked.return_value = False
        pipeline._aacparse = MagicMock()
        pipeline._aacparse.get_static_pad.return_value = mock_sink_pad
        mock_pad.link.return_value = 0  # PadLinkReturn.OK

        # Call _on_pad_added
        pipeline._on_pad_added(MagicMock(), mock_pad)

        # Verify audio pad flag set
        assert pipeline.has_audio_pad is True

    def test_on_pad_added_null_caps_returns_early(self, mock_gst_module) -> None:
        """Test that null caps pad is ignored gracefully."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Create mock pad with null caps
        mock_pad = MagicMock()
        mock_pad.get_current_caps.return_value = None
        mock_pad.query_caps.return_value = None

        # Call _on_pad_added - should return early without error
        pipeline._on_pad_added(MagicMock(), mock_pad)

        # Verify no pads were flagged
        assert pipeline.has_video_pad is False
        assert pipeline.has_audio_pad is False

    def test_on_pad_added_empty_caps_returns_early(self, mock_gst_module) -> None:
        """Test that empty caps pad is ignored gracefully."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Create mock pad with empty caps
        mock_pad = MagicMock()
        mock_caps = MagicMock()
        mock_caps.is_empty.return_value = True
        mock_pad.get_current_caps.return_value = mock_caps

        # Call _on_pad_added
        pipeline._on_pad_added(MagicMock(), mock_pad)

        # Verify no pads were flagged
        assert pipeline.has_video_pad is False
        assert pipeline.has_audio_pad is False

    def test_on_pad_added_video_link_failure_logged(self, mock_gst_module) -> None:
        """Test that video pad link failure is logged."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Create mock pad with video caps
        mock_pad = MagicMock()
        mock_caps = MagicMock()
        mock_structure = MagicMock()
        mock_structure.get_name.return_value = "video/x-h264"
        mock_caps.is_empty.return_value = False
        mock_caps.get_structure.return_value = mock_structure
        mock_pad.get_current_caps.return_value = mock_caps
        mock_pad.get_name.return_value = "video_0"

        # Mock failed linking
        mock_sink_pad = MagicMock()
        mock_sink_pad.is_linked.return_value = False
        pipeline._h264parse = MagicMock()
        pipeline._h264parse.get_static_pad.return_value = mock_sink_pad
        mock_gst.PadLinkReturn.OK = 0
        mock_pad.link.return_value = 1  # Not OK

        # Call _on_pad_added
        pipeline._on_pad_added(MagicMock(), mock_pad)

        # Verify video pad flag NOT set due to failure
        assert pipeline.has_video_pad is False

    def test_on_pad_added_audio_link_failure_logged(self, mock_gst_module) -> None:
        """Test that audio pad link failure is logged."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Create mock pad with audio caps
        mock_pad = MagicMock()
        mock_caps = MagicMock()
        mock_structure = MagicMock()
        mock_structure.get_name.return_value = "audio/mpeg"
        mock_caps.is_empty.return_value = False
        mock_caps.get_structure.return_value = mock_structure
        mock_pad.get_current_caps.return_value = mock_caps
        mock_pad.get_name.return_value = "audio_0"

        # Mock failed linking
        mock_sink_pad = MagicMock()
        mock_sink_pad.is_linked.return_value = False
        pipeline._aacparse = MagicMock()
        pipeline._aacparse.get_static_pad.return_value = mock_sink_pad
        mock_gst.PadLinkReturn.OK = 0
        mock_pad.link.return_value = 1  # Not OK

        # Call _on_pad_added
        pipeline._on_pad_added(MagicMock(), mock_pad)

        # Verify audio pad flag NOT set due to failure
        assert pipeline.has_audio_pad is False

    def test_on_pad_added_uses_query_caps_fallback(self, mock_gst_module) -> None:
        """Test that query_caps is used as fallback when get_current_caps returns None."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        # Set up PadLinkReturn before importing InputPipeline
        mock_gst.PadLinkReturn = MagicMock()
        mock_gst.PadLinkReturn.OK = 0

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Create mock pad that uses query_caps fallback
        mock_pad = MagicMock()
        mock_caps = MagicMock()
        mock_structure = MagicMock()
        mock_structure.get_name.return_value = "video/x-h264"
        mock_caps.is_empty.return_value = False
        mock_caps.get_structure.return_value = mock_structure

        mock_pad.get_current_caps.return_value = None
        mock_pad.query_caps.return_value = mock_caps
        mock_pad.get_name.return_value = "video_0"

        # Mock successful linking - return the actual OK value (0)
        mock_sink_pad = MagicMock()
        mock_sink_pad.is_linked.return_value = False
        pipeline._h264parse = MagicMock()
        pipeline._h264parse.get_static_pad.return_value = mock_sink_pad
        mock_pad.link.return_value = 0  # PadLinkReturn.OK

        # Call _on_pad_added
        pipeline._on_pad_added(MagicMock(), mock_pad)

        # Verify query_caps was used
        mock_pad.query_caps.assert_called()
        assert pipeline.has_video_pad is True


# =============================================================================
# Video Sample Tests (T007 Extended) - Test _on_video_sample method
# =============================================================================


class TestOnVideoSample:
    """Unit tests for InputPipeline._on_video_sample buffer handling.

    These tests verify that video samples are correctly extracted from appsink
    and passed to the video buffer callback with proper PTS and duration.
    """

    def test_on_video_sample_calls_callback_with_data(self, mock_gst_module) -> None:
        """Test that video buffer callback is called with correct data."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        # Set up CLOCK_TIME_NONE constant
        mock_gst.CLOCK_TIME_NONE = 18446744073709551615

        from media_service.pipeline.input import InputPipeline

        video_callback = MagicMock()
        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=video_callback,
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        # Create mock appsink with sample
        mock_appsink = MagicMock()
        mock_sample = MagicMock()
        mock_buffer = MagicMock()
        mock_map_info = MagicMock()
        mock_map_info.data = b"test_video_data"

        mock_appsink.emit.return_value = mock_sample
        mock_sample.get_buffer.return_value = mock_buffer
        mock_buffer.map.return_value = (True, mock_map_info)
        mock_buffer.pts = 1000000000  # 1 second
        mock_buffer.duration = 33333333  # ~30fps

        # Mock FlowReturn
        mock_gst.FlowReturn.OK = 0
        mock_gst.MapFlags.READ = 1

        # Call _on_video_sample
        result = pipeline._on_video_sample(mock_appsink)

        # Verify callback was called with extracted data
        video_callback.assert_called_once_with(b"test_video_data", 1000000000, 33333333)
        assert result == 0

    def test_on_video_sample_null_sample_returns_ok(self, mock_gst_module) -> None:
        """Test that null sample returns FlowReturn.OK."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        mock_gst.CLOCK_TIME_NONE = 18446744073709551615

        from media_service.pipeline.input import InputPipeline

        video_callback = MagicMock()
        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=video_callback,
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        mock_appsink = MagicMock()
        mock_appsink.emit.return_value = None

        mock_gst.FlowReturn.OK = 0

        result = pipeline._on_video_sample(mock_appsink)

        video_callback.assert_not_called()
        assert result == 0

    def test_on_video_sample_null_buffer_returns_ok(self, mock_gst_module) -> None:
        """Test that null buffer returns FlowReturn.OK."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        mock_gst.CLOCK_TIME_NONE = 18446744073709551615

        from media_service.pipeline.input import InputPipeline

        video_callback = MagicMock()
        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=video_callback,
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        mock_appsink = MagicMock()
        mock_sample = MagicMock()
        mock_appsink.emit.return_value = mock_sample
        mock_sample.get_buffer.return_value = None

        mock_gst.FlowReturn.OK = 0

        result = pipeline._on_video_sample(mock_appsink)

        video_callback.assert_not_called()
        assert result == 0

    def test_on_video_sample_handles_clock_time_none(self, mock_gst_module) -> None:
        """Test that CLOCK_TIME_NONE values are converted to 0."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        mock_gst.CLOCK_TIME_NONE = 18446744073709551615

        from media_service.pipeline.input import InputPipeline

        video_callback = MagicMock()
        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=video_callback,
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        mock_appsink = MagicMock()
        mock_sample = MagicMock()
        mock_buffer = MagicMock()
        mock_map_info = MagicMock()
        mock_map_info.data = b"data"

        mock_appsink.emit.return_value = mock_sample
        mock_sample.get_buffer.return_value = mock_buffer
        mock_buffer.map.return_value = (True, mock_map_info)
        mock_buffer.pts = mock_gst.CLOCK_TIME_NONE
        mock_buffer.duration = mock_gst.CLOCK_TIME_NONE

        mock_gst.FlowReturn.OK = 0
        mock_gst.MapFlags.READ = 1

        pipeline._on_video_sample(mock_appsink)

        # Verify 0 was passed instead of CLOCK_TIME_NONE
        video_callback.assert_called_once_with(b"data", 0, 0)

    def test_on_video_sample_callback_exception_logged(self, mock_gst_module) -> None:
        """Test that callback exception is caught and logged."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        mock_gst.CLOCK_TIME_NONE = 18446744073709551615

        from media_service.pipeline.input import InputPipeline

        video_callback = MagicMock()
        video_callback.side_effect = RuntimeError("Callback error")
        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=video_callback,
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        mock_appsink = MagicMock()
        mock_sample = MagicMock()
        mock_buffer = MagicMock()
        mock_map_info = MagicMock()
        mock_map_info.data = b"data"

        mock_appsink.emit.return_value = mock_sample
        mock_sample.get_buffer.return_value = mock_buffer
        mock_buffer.map.return_value = (True, mock_map_info)
        mock_buffer.pts = 0
        mock_buffer.duration = 0

        mock_gst.FlowReturn.OK = 0
        mock_gst.MapFlags.READ = 1

        # Should not raise exception
        result = pipeline._on_video_sample(mock_appsink)
        assert result == 0


# =============================================================================
# Audio Sample Tests (T007 Extended) - Test _on_audio_sample method
# =============================================================================


class TestOnAudioSample:
    """Unit tests for InputPipeline._on_audio_sample buffer handling.

    These tests verify that audio samples are correctly extracted from appsink
    and passed to the audio buffer callback with proper PTS and duration.
    """

    def test_on_audio_sample_calls_callback_with_data(self, mock_gst_module) -> None:
        """Test that audio buffer callback is called with correct data."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        mock_gst.CLOCK_TIME_NONE = 18446744073709551615

        from media_service.pipeline.input import InputPipeline

        audio_callback = MagicMock()
        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=audio_callback,
        )
        pipeline.build()

        mock_appsink = MagicMock()
        mock_sample = MagicMock()
        mock_buffer = MagicMock()
        mock_map_info = MagicMock()
        mock_map_info.data = b"test_audio_data"

        mock_appsink.emit.return_value = mock_sample
        mock_sample.get_buffer.return_value = mock_buffer
        mock_buffer.map.return_value = (True, mock_map_info)
        mock_buffer.pts = 2000000000  # 2 seconds
        mock_buffer.duration = 21333333  # ~48kHz frame

        mock_gst.FlowReturn.OK = 0
        mock_gst.MapFlags.READ = 1

        result = pipeline._on_audio_sample(mock_appsink)

        audio_callback.assert_called_once_with(b"test_audio_data", 2000000000, 21333333)
        assert result == 0

    def test_on_audio_sample_null_sample_returns_ok(self, mock_gst_module) -> None:
        """Test that null sample returns FlowReturn.OK."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        mock_gst.CLOCK_TIME_NONE = 18446744073709551615

        from media_service.pipeline.input import InputPipeline

        audio_callback = MagicMock()
        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=audio_callback,
        )
        pipeline.build()

        mock_appsink = MagicMock()
        mock_appsink.emit.return_value = None

        mock_gst.FlowReturn.OK = 0

        result = pipeline._on_audio_sample(mock_appsink)

        audio_callback.assert_not_called()
        assert result == 0

    def test_on_audio_sample_null_buffer_returns_ok(self, mock_gst_module) -> None:
        """Test that null buffer returns FlowReturn.OK."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        mock_gst.CLOCK_TIME_NONE = 18446744073709551615

        from media_service.pipeline.input import InputPipeline

        audio_callback = MagicMock()
        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=audio_callback,
        )
        pipeline.build()

        mock_appsink = MagicMock()
        mock_sample = MagicMock()
        mock_appsink.emit.return_value = mock_sample
        mock_sample.get_buffer.return_value = None

        mock_gst.FlowReturn.OK = 0

        result = pipeline._on_audio_sample(mock_appsink)

        audio_callback.assert_not_called()
        assert result == 0

    def test_on_audio_sample_handles_clock_time_none(self, mock_gst_module) -> None:
        """Test that CLOCK_TIME_NONE values are converted to 0."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        mock_gst.CLOCK_TIME_NONE = 18446744073709551615

        from media_service.pipeline.input import InputPipeline

        audio_callback = MagicMock()
        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=audio_callback,
        )
        pipeline.build()

        mock_appsink = MagicMock()
        mock_sample = MagicMock()
        mock_buffer = MagicMock()
        mock_map_info = MagicMock()
        mock_map_info.data = b"audio"

        mock_appsink.emit.return_value = mock_sample
        mock_sample.get_buffer.return_value = mock_buffer
        mock_buffer.map.return_value = (True, mock_map_info)
        mock_buffer.pts = mock_gst.CLOCK_TIME_NONE
        mock_buffer.duration = mock_gst.CLOCK_TIME_NONE

        mock_gst.FlowReturn.OK = 0
        mock_gst.MapFlags.READ = 1

        pipeline._on_audio_sample(mock_appsink)

        audio_callback.assert_called_once_with(b"audio", 0, 0)

    def test_on_audio_sample_callback_exception_logged(self, mock_gst_module) -> None:
        """Test that callback exception is caught and logged."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        mock_gst.CLOCK_TIME_NONE = 18446744073709551615

        from media_service.pipeline.input import InputPipeline

        audio_callback = MagicMock()
        audio_callback.side_effect = RuntimeError("Audio callback error")
        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=audio_callback,
        )
        pipeline.build()

        mock_appsink = MagicMock()
        mock_sample = MagicMock()
        mock_buffer = MagicMock()
        mock_map_info = MagicMock()
        mock_map_info.data = b"data"

        mock_appsink.emit.return_value = mock_sample
        mock_sample.get_buffer.return_value = mock_buffer
        mock_buffer.map.return_value = (True, mock_map_info)
        mock_buffer.pts = 0
        mock_buffer.duration = 0

        mock_gst.FlowReturn.OK = 0
        mock_gst.MapFlags.READ = 1

        result = pipeline._on_audio_sample(mock_appsink)
        assert result == 0


# =============================================================================
# Bus Message Tests (T008 Extended) - Test _on_bus_message method
# =============================================================================


class TestOnBusMessage:
    """Unit tests for InputPipeline._on_bus_message handling.

    These tests verify that GStreamer bus messages (ERROR, WARNING, EOS,
    STATE_CHANGED) are handled correctly and pipeline state is updated.
    """

    def test_on_bus_message_error_updates_state(self, mock_gst_module) -> None:
        """Test that ERROR message sets state to ERROR."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        # Set up MessageType constants BEFORE using them
        mock_gst.MessageType.ERROR = 1
        mock_gst.MessageType.WARNING = 2
        mock_gst.MessageType.EOS = 4
        mock_gst.MessageType.STATE_CHANGED = 8

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        mock_bus = MagicMock()
        mock_message = MagicMock()
        mock_message.type = 1  # ERROR

        mock_err = MagicMock()
        mock_err.message = "Test error"
        mock_message.parse_error.return_value = (mock_err, "Debug info")

        result = pipeline._on_bus_message(mock_bus, mock_message)

        assert pipeline._state == "ERROR"
        assert result is True

    def test_on_bus_message_warning_logged(self, mock_gst_module) -> None:
        """Test that WARNING message is logged."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        # Set up MessageType constants BEFORE using them
        mock_gst.MessageType.ERROR = 1
        mock_gst.MessageType.WARNING = 2
        mock_gst.MessageType.EOS = 4
        mock_gst.MessageType.STATE_CHANGED = 8

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        mock_bus = MagicMock()
        mock_message = MagicMock()
        mock_message.type = 2  # WARNING

        mock_warn = MagicMock()
        mock_warn.message = "Test warning"
        mock_message.parse_warning.return_value = (mock_warn, "Debug info")

        result = pipeline._on_bus_message(mock_bus, mock_message)

        assert result is True

    def test_on_bus_message_eos_updates_state(self, mock_gst_module) -> None:
        """Test that EOS message sets state to EOS."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        # Set up MessageType constants BEFORE using them
        mock_gst.MessageType.ERROR = 1
        mock_gst.MessageType.WARNING = 2
        mock_gst.MessageType.EOS = 4
        mock_gst.MessageType.STATE_CHANGED = 8

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        mock_bus = MagicMock()
        mock_message = MagicMock()
        mock_message.type = 4  # EOS

        result = pipeline._on_bus_message(mock_bus, mock_message)

        assert pipeline._state == "EOS"
        assert result is True

    def test_on_bus_message_state_changed_updates_state(self, mock_gst_module) -> None:
        """Test that STATE_CHANGED message updates pipeline state."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        # Set up MessageType constants BEFORE using them
        mock_gst.MessageType.ERROR = 1
        mock_gst.MessageType.WARNING = 2
        mock_gst.MessageType.EOS = 4
        mock_gst.MessageType.STATE_CHANGED = 8

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        mock_bus = MagicMock()
        mock_message = MagicMock()
        mock_message.type = 8  # STATE_CHANGED
        mock_message.src = pipeline._pipeline

        mock_old = MagicMock()
        mock_old.value_nick = "ready"
        mock_new = MagicMock()
        mock_new.value_nick = "playing"
        mock_pending = MagicMock()
        mock_message.parse_state_changed.return_value = (mock_old, mock_new, mock_pending)

        result = pipeline._on_bus_message(mock_bus, mock_message)

        assert pipeline._state == "PLAYING"
        assert result is True

    def test_on_bus_message_state_changed_from_other_element_ignored(
        self, mock_gst_module
    ) -> None:
        """Test that STATE_CHANGED from non-pipeline elements is ignored."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        # Set up MessageType constants BEFORE using them
        mock_gst.MessageType.ERROR = 1
        mock_gst.MessageType.WARNING = 2
        mock_gst.MessageType.EOS = 4
        mock_gst.MessageType.STATE_CHANGED = 8

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()
        original_state = pipeline._state

        mock_bus = MagicMock()
        mock_message = MagicMock()
        mock_message.type = 8  # STATE_CHANGED
        mock_message.src = MagicMock()  # Different element, not the pipeline

        result = pipeline._on_bus_message(mock_bus, mock_message)

        # State should not change
        assert pipeline._state == original_state
        assert result is True

    def test_on_bus_message_returns_true_always(self, mock_gst_module) -> None:
        """Test that _on_bus_message always returns True to continue receiving."""
        mock_gst, mock_pipeline, mock_element = mock_gst_module

        from media_service.pipeline import input as input_module
        input_module.Gst = mock_gst
        input_module.GST_AVAILABLE = True

        # Set up MessageType constants BEFORE using them
        mock_gst.MessageType.ERROR = 1
        mock_gst.MessageType.WARNING = 2
        mock_gst.MessageType.EOS = 4
        mock_gst.MessageType.STATE_CHANGED = 8

        from media_service.pipeline.input import InputPipeline

        pipeline = InputPipeline(
            rtmp_url="rtmp://mediamtx:1935/live/test/in",
            on_video_buffer=MagicMock(),
            on_audio_buffer=MagicMock(),
        )
        pipeline.build()

        mock_bus = MagicMock()
        mock_message = MagicMock()
        mock_message.type = 99999  # Unknown message type

        result = pipeline._on_bus_message(mock_bus, mock_message)

        assert result is True
