"""
Unit tests for GStreamer element builders.

Tests T021 from tasks.md - validating GStreamer element construction.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_gst_module():
    """Create a comprehensive mock for GStreamer module.

    This fixture properly mocks the GStreamer module and patches
    the elements module to use it.
    """
    mock_gst = MagicMock()

    # Mock common GStreamer types and constants
    mock_gst.is_initialized = MagicMock(return_value=True)
    mock_gst.init = MagicMock()

    # Mock element factory
    mock_element = MagicMock()
    mock_gst.ElementFactory.make = MagicMock(return_value=mock_element)

    # Mock Caps
    mock_caps = MagicMock()
    mock_gst.Caps.from_string = MagicMock(return_value=mock_caps)

    return mock_gst, mock_element


class TestBuildRtspsrcElement:
    """Tests for build_rtspsrc_element function."""

    def test_build_rtspsrc_returns_element(self, mock_gst_module) -> None:
        """Test that build_rtspsrc_element returns a configured element."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            element = elements.build_rtspsrc_element("rtsp://localhost:8554/live/test/in")

            assert element is not None

    def test_build_rtspsrc_sets_location(self, mock_gst_module) -> None:
        """Test that rtspsrc location property is set correctly."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            url = "rtsp://mediamtx:8554/live/stream1/in"
            elements.build_rtspsrc_element(url)

            # Verify set_property was called with location
            mock_element.set_property.assert_any_call("location", url)

    def test_build_rtspsrc_uses_tcp_protocol(self, mock_gst_module) -> None:
        """Test that rtspsrc uses TCP protocol (protocols=tcp)."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_rtspsrc_element("rtsp://localhost:8554/test")

            # protocols=tcp corresponds to value 4 in GStreamer
            mock_element.set_property.assert_any_call("protocols", "tcp")

    def test_build_rtspsrc_default_latency(self, mock_gst_module) -> None:
        """Test that rtspsrc has default latency of 200ms."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_rtspsrc_element("rtsp://localhost:8554/test")

            mock_element.set_property.assert_any_call("latency", 200)

    def test_build_rtspsrc_custom_latency(self, mock_gst_module) -> None:
        """Test that rtspsrc respects custom latency parameter."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_rtspsrc_element("rtsp://localhost:8554/test", latency=500)

            mock_element.set_property.assert_any_call("latency", 500)


class TestBuildAppsinkElement:
    """Tests for build_appsink_element function."""

    def test_build_appsink_returns_element(self, mock_gst_module) -> None:
        """Test that build_appsink_element returns a configured element."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            element = elements.build_appsink_element("video_sink", "video/x-h264")

            assert element is not None

    def test_build_appsink_sets_name(self, mock_gst_module) -> None:
        """Test that appsink name is set correctly."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_appsink_element("my_sink", "video/x-h264")

            mock_element.set_property.assert_any_call("name", "my_sink")

    def test_build_appsink_sets_caps_video_h264(self, mock_gst_module) -> None:
        """Test that appsink sets correct caps for H.264 video."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_appsink_element("video_sink", "video/x-h264")

            # Verify caps were set
            assert mock_gst.Caps.from_string.called
            mock_gst.Caps.from_string.assert_called_with("video/x-h264")

    def test_build_appsink_sets_caps_audio_aac(self, mock_gst_module) -> None:
        """Test that appsink sets correct caps for AAC audio."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_appsink_element("audio_sink", "audio/mpeg")

            mock_gst.Caps.from_string.assert_called_with("audio/mpeg")

    def test_build_appsink_emit_signals(self, mock_gst_module) -> None:
        """Test that appsink has emit-signals enabled."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_appsink_element("sink", "video/x-h264")

            mock_element.set_property.assert_any_call("emit-signals", True)

    def test_build_appsink_sync_false(self, mock_gst_module) -> None:
        """Test that appsink has sync=false for live streams."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_appsink_element("sink", "video/x-h264")

            mock_element.set_property.assert_any_call("sync", False)


class TestBuildAppsrcElement:
    """Tests for build_appsrc_element function."""

    def test_build_appsrc_returns_element(self, mock_gst_module) -> None:
        """Test that build_appsrc_element returns a configured element."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            element = elements.build_appsrc_element("video_src", "video/x-h264")

            assert element is not None

    def test_build_appsrc_is_live_true(self, mock_gst_module) -> None:
        """Test that appsrc has is-live=true."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_appsrc_element("src", "video/x-h264")

            mock_element.set_property.assert_any_call("is-live", True)

    def test_build_appsrc_format_time(self, mock_gst_module) -> None:
        """Test that appsrc has format=time."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_appsrc_element("src", "video/x-h264")

            # Format.TIME = 3 in GStreamer
            mock_element.set_property.assert_any_call("format", 3)

    def test_build_appsrc_sets_name(self, mock_gst_module) -> None:
        """Test that appsrc name is set correctly."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_appsrc_element("my_source", "audio/mpeg")

            mock_element.set_property.assert_any_call("name", "my_source")

    def test_build_appsrc_sets_caps(self, mock_gst_module) -> None:
        """Test that appsrc sets caps correctly."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_appsrc_element("src", "video/x-h264")

            mock_gst.Caps.from_string.assert_called_with("video/x-h264")


class TestBuildFlvmuxElement:
    """Tests for build_flvmux_element function."""

    def test_build_flvmux_returns_element(self, mock_gst_module) -> None:
        """Test that build_flvmux_element returns a configured element."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            element = elements.build_flvmux_element()

            assert element is not None

    def test_build_flvmux_streamable_true(self, mock_gst_module) -> None:
        """Test that flvmux has streamable=true for RTMP."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_flvmux_element()

            mock_element.set_property.assert_any_call("streamable", True)


class TestBuildRtmpsinkElement:
    """Tests for build_rtmpsink_element function."""

    def test_build_rtmpsink_returns_element(self, mock_gst_module) -> None:
        """Test that build_rtmpsink_element returns a configured element."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            element = elements.build_rtmpsink_element("rtmp://localhost:1935/live/test/out")

            assert element is not None

    def test_build_rtmpsink_sets_location(self, mock_gst_module) -> None:
        """Test that rtmpsink location is set correctly."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            url = "rtmp://mediamtx:1935/live/stream1/out"
            elements.build_rtmpsink_element(url)

            mock_element.set_property.assert_any_call("location", url)


class TestBuildFlvdemuxElement:
    """Tests for build_flvdemux_element function."""

    def test_build_flvdemux_returns_element(self, mock_gst_module) -> None:
        """Test that build_flvdemux_element returns an element."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            element = elements.build_flvdemux_element()

            assert element is not None

    def test_build_flvdemux_creates_correct_element(self, mock_gst_module) -> None:
        """Test that flvdemux element is created with correct name."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_flvdemux_element()

            mock_gst.ElementFactory.make.assert_called_with("flvdemux", "flvdemux0")


class TestBuildQueueElement:
    """Tests for build_queue_element function."""

    def test_build_queue_returns_element(self, mock_gst_module) -> None:
        """Test that build_queue_element returns an element."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            element = elements.build_queue_element("video_queue")

            assert element is not None

    def test_build_queue_sets_max_buffers_default(self, mock_gst_module) -> None:
        """Test that queue uses default max buffers of 200."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_queue_element("queue1")

            mock_element.set_property.assert_any_call("max-size-buffers", 200)

    def test_build_queue_sets_custom_max_buffers(self, mock_gst_module) -> None:
        """Test that queue respects custom max buffers."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_queue_element("queue1", max_buffers=500)

            mock_element.set_property.assert_any_call("max-size-buffers", 500)

    def test_build_queue_sets_unlimited_bytes_and_time(self, mock_gst_module) -> None:
        """Test that queue has unlimited bytes and time."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_queue_element("queue1")

            mock_element.set_property.assert_any_call("max-size-bytes", 0)
            mock_element.set_property.assert_any_call("max-size-time", 0)


class TestBuildH264parseElement:
    """Tests for build_h264parse_element function."""

    def test_build_h264parse_returns_element(self, mock_gst_module) -> None:
        """Test that build_h264parse_element returns an element."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            element = elements.build_h264parse_element()

            assert element is not None

    def test_build_h264parse_creates_correct_element(self, mock_gst_module) -> None:
        """Test that h264parse element is created with correct name."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_h264parse_element()

            mock_gst.ElementFactory.make.assert_called_with("h264parse", "h264parse0")


class TestBuildAacparseElement:
    """Tests for build_aacparse_element function."""

    def test_build_aacparse_returns_element(self, mock_gst_module) -> None:
        """Test that build_aacparse_element returns an element."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            element = elements.build_aacparse_element()

            assert element is not None

    def test_build_aacparse_creates_correct_element(self, mock_gst_module) -> None:
        """Test that aacparse element is created with correct name."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_aacparse_element()

            mock_gst.ElementFactory.make.assert_called_with("aacparse", "aacparse0")


class TestBuildMp4muxElement:
    """Tests for build_mp4mux_element function."""

    def test_build_mp4mux_returns_element(self, mock_gst_module) -> None:
        """Test that build_mp4mux_element returns an element."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            element = elements.build_mp4mux_element()

            assert element is not None

    def test_build_mp4mux_creates_correct_element(self, mock_gst_module) -> None:
        """Test that mp4mux element is created with correct name."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_mp4mux_element()

            mock_gst.ElementFactory.make.assert_called_with("mp4mux", "mp4mux0")

    def test_build_mp4mux_with_fragment_duration(self, mock_gst_module) -> None:
        """Test that mp4mux respects fragment duration."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_mp4mux_element(fragment_duration=6_000_000_000)

            mock_element.set_property.assert_any_call("fragment-duration", 6_000_000_000)

    def test_build_mp4mux_zero_fragment_duration_no_property(self, mock_gst_module) -> None:
        """Test that mp4mux doesn't set fragment-duration when zero."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            elements.build_mp4mux_element(fragment_duration=0)

            # Should not have called set_property with fragment-duration
            calls = [call for call in mock_element.set_property.call_args_list
                    if call[0][0] == "fragment-duration"]
            assert len(calls) == 0


class TestBuildFilesinkElement:
    """Tests for build_filesink_element function."""

    def test_build_filesink_returns_element(self, mock_gst_module) -> None:
        """Test that build_filesink_element returns an element."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            element = elements.build_filesink_element("/tmp/test.mp4")

            assert element is not None

    def test_build_filesink_sets_location(self, mock_gst_module) -> None:
        """Test that filesink location is set correctly."""
        mock_gst, mock_element = mock_gst_module

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            path = "/segments/stream1/000000_video.mp4"
            elements.build_filesink_element(path)

            mock_element.set_property.assert_any_call("location", path)


class TestGstNotAvailable:
    """Tests for when GStreamer is not available."""

    def test_build_rtspsrc_raises_when_gst_unavailable(self) -> None:
        """Test that build_rtspsrc_element raises when GStreamer unavailable."""
        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": None, "GST_AVAILABLE": False}):
            from media_service.pipeline import elements
            elements.Gst = None
            elements.GST_AVAILABLE = False

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_rtspsrc_element("rtsp://localhost:8554/test")

            assert "GStreamer not available" in str(exc_info.value)

    def test_build_appsink_raises_when_gst_unavailable(self) -> None:
        """Test that build_appsink_element raises when GStreamer unavailable."""
        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": None, "GST_AVAILABLE": False}):
            from media_service.pipeline import elements
            elements.Gst = None
            elements.GST_AVAILABLE = False

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_appsink_element("sink", "video/x-h264")

            assert "GStreamer not available" in str(exc_info.value)

    def test_build_appsrc_raises_when_gst_unavailable(self) -> None:
        """Test that build_appsrc_element raises when GStreamer unavailable."""
        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": None, "GST_AVAILABLE": False}):
            from media_service.pipeline import elements
            elements.Gst = None
            elements.GST_AVAILABLE = False

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_appsrc_element("src", "video/x-h264")

            assert "GStreamer not available" in str(exc_info.value)

    def test_build_flvmux_raises_when_gst_unavailable(self) -> None:
        """Test that build_flvmux_element raises when GStreamer unavailable."""
        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": None, "GST_AVAILABLE": False}):
            from media_service.pipeline import elements
            elements.Gst = None
            elements.GST_AVAILABLE = False

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_flvmux_element()

            assert "GStreamer not available" in str(exc_info.value)

    def test_build_rtmpsink_raises_when_gst_unavailable(self) -> None:
        """Test that build_rtmpsink_element raises when GStreamer unavailable."""
        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": None, "GST_AVAILABLE": False}):
            from media_service.pipeline import elements
            elements.Gst = None
            elements.GST_AVAILABLE = False

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_rtmpsink_element("rtmp://localhost:1935/test")

            assert "GStreamer not available" in str(exc_info.value)

    def test_build_flvdemux_raises_when_gst_unavailable(self) -> None:
        """Test that build_flvdemux_element raises when GStreamer unavailable."""
        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": None, "GST_AVAILABLE": False}):
            from media_service.pipeline import elements
            elements.Gst = None
            elements.GST_AVAILABLE = False

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_flvdemux_element()

            assert "GStreamer not available" in str(exc_info.value)

    def test_build_queue_raises_when_gst_unavailable(self) -> None:
        """Test that build_queue_element raises when GStreamer unavailable."""
        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": None, "GST_AVAILABLE": False}):
            from media_service.pipeline import elements
            elements.Gst = None
            elements.GST_AVAILABLE = False

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_queue_element("queue")

            assert "GStreamer not available" in str(exc_info.value)

    def test_build_h264parse_raises_when_gst_unavailable(self) -> None:
        """Test that build_h264parse_element raises when GStreamer unavailable."""
        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": None, "GST_AVAILABLE": False}):
            from media_service.pipeline import elements
            elements.Gst = None
            elements.GST_AVAILABLE = False

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_h264parse_element()

            assert "GStreamer not available" in str(exc_info.value)

    def test_build_aacparse_raises_when_gst_unavailable(self) -> None:
        """Test that build_aacparse_element raises when GStreamer unavailable."""
        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": None, "GST_AVAILABLE": False}):
            from media_service.pipeline import elements
            elements.Gst = None
            elements.GST_AVAILABLE = False

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_aacparse_element()

            assert "GStreamer not available" in str(exc_info.value)

    def test_build_mp4mux_raises_when_gst_unavailable(self) -> None:
        """Test that build_mp4mux_element raises when GStreamer unavailable."""
        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": None, "GST_AVAILABLE": False}):
            from media_service.pipeline import elements
            elements.Gst = None
            elements.GST_AVAILABLE = False

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_mp4mux_element()

            assert "GStreamer not available" in str(exc_info.value)

    def test_build_filesink_raises_when_gst_unavailable(self) -> None:
        """Test that build_filesink_element raises when GStreamer unavailable."""
        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": None, "GST_AVAILABLE": False}):
            from media_service.pipeline import elements
            elements.Gst = None
            elements.GST_AVAILABLE = False

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_filesink_element("/tmp/test.mp4")

            assert "GStreamer not available" in str(exc_info.value)


class TestElementCreationFailure:
    """Tests for element creation failure scenarios."""

    def test_build_rtspsrc_raises_when_factory_returns_none(self, mock_gst_module) -> None:
        """Test that build_rtspsrc raises when factory returns None."""
        mock_gst, _ = mock_gst_module
        mock_gst.ElementFactory.make.return_value = None

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_rtspsrc_element("rtsp://localhost:8554/test")

            assert "Failed to create rtspsrc element" in str(exc_info.value)

    def test_build_appsink_raises_when_factory_returns_none(self, mock_gst_module) -> None:
        """Test that build_appsink raises when factory returns None."""
        mock_gst, _ = mock_gst_module
        mock_gst.ElementFactory.make.return_value = None

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_appsink_element("sink", "video/x-h264")

            assert "Failed to create appsink element" in str(exc_info.value)

    def test_build_appsrc_raises_when_factory_returns_none(self, mock_gst_module) -> None:
        """Test that build_appsrc raises when factory returns None."""
        mock_gst, _ = mock_gst_module
        mock_gst.ElementFactory.make.return_value = None

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_appsrc_element("src", "video/x-h264")

            assert "Failed to create appsrc element" in str(exc_info.value)

    def test_build_flvmux_raises_when_factory_returns_none(self, mock_gst_module) -> None:
        """Test that build_flvmux raises when factory returns None."""
        mock_gst, _ = mock_gst_module
        mock_gst.ElementFactory.make.return_value = None

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_flvmux_element()

            assert "Failed to create flvmux element" in str(exc_info.value)

    def test_build_rtmpsink_raises_when_factory_returns_none(self, mock_gst_module) -> None:
        """Test that build_rtmpsink raises when factory returns None."""
        mock_gst, _ = mock_gst_module
        mock_gst.ElementFactory.make.return_value = None

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_rtmpsink_element("rtmp://localhost:1935/test")

            assert "Failed to create rtmpsink element" in str(exc_info.value)

    def test_build_flvdemux_raises_when_factory_returns_none(self, mock_gst_module) -> None:
        """Test that build_flvdemux raises when factory returns None."""
        mock_gst, _ = mock_gst_module
        mock_gst.ElementFactory.make.return_value = None

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_flvdemux_element()

            assert "Failed to create flvdemux element" in str(exc_info.value)

    def test_build_queue_raises_when_factory_returns_none(self, mock_gst_module) -> None:
        """Test that build_queue raises when factory returns None."""
        mock_gst, _ = mock_gst_module
        mock_gst.ElementFactory.make.return_value = None

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_queue_element("queue")

            assert "Failed to create queue element" in str(exc_info.value)

    def test_build_h264parse_raises_when_factory_returns_none(self, mock_gst_module) -> None:
        """Test that build_h264parse raises when factory returns None."""
        mock_gst, _ = mock_gst_module
        mock_gst.ElementFactory.make.return_value = None

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_h264parse_element()

            assert "Failed to create h264parse element" in str(exc_info.value)

    def test_build_aacparse_raises_when_factory_returns_none(self, mock_gst_module) -> None:
        """Test that build_aacparse raises when factory returns None."""
        mock_gst, _ = mock_gst_module
        mock_gst.ElementFactory.make.return_value = None

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_aacparse_element()

            assert "Failed to create aacparse element" in str(exc_info.value)

    def test_build_mp4mux_raises_when_factory_returns_none(self, mock_gst_module) -> None:
        """Test that build_mp4mux raises when factory returns None."""
        mock_gst, _ = mock_gst_module
        mock_gst.ElementFactory.make.return_value = None

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_mp4mux_element()

            assert "Failed to create mp4mux element" in str(exc_info.value)

    def test_build_filesink_raises_when_factory_returns_none(self, mock_gst_module) -> None:
        """Test that build_filesink raises when factory returns None."""
        mock_gst, _ = mock_gst_module
        mock_gst.ElementFactory.make.return_value = None

        with patch.dict("media_service.pipeline.elements.__dict__",
                       {"Gst": mock_gst, "GST_AVAILABLE": True}):
            from media_service.pipeline import elements
            elements.Gst = mock_gst
            elements.GST_AVAILABLE = True

            with pytest.raises(RuntimeError) as exc_info:
                elements.build_filesink_element("/tmp/test.mp4")

            assert "Failed to create filesink element" in str(exc_info.value)
