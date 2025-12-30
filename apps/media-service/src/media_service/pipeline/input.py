"""
Input pipeline for RTSP stream consumption.

Pulls RTSP stream from MediaMTX, demuxes FLV container into
video (H.264) and audio (AAC) tracks via appsinks.

Per spec 003:
- Video and audio are codec-copied (no re-encode)
- Appsink callbacks for buffer processing
- Pipeline state management (NULL -> READY -> PAUSED -> PLAYING)
"""

from __future__ import annotations

import logging
from collections.abc import Callable

# GStreamer imports
try:
    import gi

    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    from gi.repository import GLib, Gst, GstApp

    GST_AVAILABLE = True
except (ImportError, ValueError):
    GST_AVAILABLE = False
    Gst = None  # type: ignore
    GstApp = None  # type: ignore
    GLib = None  # type: ignore


logger = logging.getLogger(__name__)

# Type alias for buffer callbacks
BufferCallback = Callable[[bytes, int, int], None]  # (data, pts_ns, duration_ns)


class InputPipeline:
    """RTSP input pipeline with video and audio appsinks.

    Constructs a GStreamer pipeline that:
    1. Pulls RTSP stream from MediaMTX
    2. Demuxes FLV container into video (H.264) and audio (AAC)
    3. Routes streams to appsinks for callback-based processing

    The pipeline preserves original codecs (no re-encoding).

    Attributes:
        _rtsp_url: RTSP source URL
        _on_video_buffer: Callback for video buffer processing
        _on_audio_buffer: Callback for audio buffer processing
        _pipeline: GStreamer pipeline (after build)
        _state: Current pipeline state string
    """

    def __init__(
        self,
        rtsp_url: str,
        on_video_buffer: BufferCallback,
        on_audio_buffer: BufferCallback,
        latency: int = 200,
    ) -> None:
        """Initialize input pipeline.

        Args:
            rtsp_url: RTSP URL (e.g., "rtsp://mediamtx:8554/live/stream/in")
            on_video_buffer: Callback for video buffers (data, pts_ns, duration_ns)
            on_audio_buffer: Callback for audio buffers (data, pts_ns, duration_ns)
            latency: RTSP jitter buffer latency in ms (default 200)

        Raises:
            ValueError: If RTSP URL is empty or invalid format
        """
        if not rtsp_url:
            raise ValueError("RTSP URL cannot be empty")

        if not rtsp_url.startswith("rtsp://"):
            raise ValueError(f"Invalid RTSP URL: must start with 'rtsp://' - got '{rtsp_url}'")

        self._rtsp_url = rtsp_url
        self._on_video_buffer = on_video_buffer
        self._on_audio_buffer = on_audio_buffer
        self._latency = latency
        self._pipeline: Gst.Pipeline | None = None
        self._state = "NULL"
        self._bus: Gst.Bus | None = None
        self._video_appsink: Gst.Element | None = None
        self._audio_appsink: Gst.Element | None = None

    def build(self) -> None:
        """Build the GStreamer pipeline.

        Creates pipeline structure:
        rtspsrc -> flvdemux -> video: h264parse -> queue -> appsink
                            -> audio: aacparse -> queue -> appsink

        Raises:
            RuntimeError: If GStreamer not available or element creation fails
        """
        if not GST_AVAILABLE or Gst is None:
            raise RuntimeError("GStreamer not available")

        if not Gst.is_initialized():
            Gst.init(None)

        # Create pipeline
        self._pipeline = Gst.Pipeline.new("input_pipeline")
        if self._pipeline is None:
            raise RuntimeError("Failed to create GStreamer pipeline")

        # Create elements
        rtspsrc = Gst.ElementFactory.make("rtspsrc", "rtspsrc")
        if rtspsrc is None:
            raise RuntimeError("Failed to create rtspsrc element")

        rtspsrc.set_property("location", self._rtsp_url)
        rtspsrc.set_property("protocols", "tcp")
        rtspsrc.set_property("latency", self._latency)

        # Video path elements
        h264parse = Gst.ElementFactory.make("h264parse", "h264parse")
        video_queue = Gst.ElementFactory.make("queue", "video_queue")
        self._video_appsink = Gst.ElementFactory.make("appsink", "video_sink")

        # Audio path elements
        aacparse = Gst.ElementFactory.make("aacparse", "aacparse")
        audio_queue = Gst.ElementFactory.make("queue", "audio_queue")
        self._audio_appsink = Gst.ElementFactory.make("appsink", "audio_sink")

        # Verify all elements created
        for elem_name, elem in [
            ("h264parse", h264parse),
            ("video_queue", video_queue),
            ("video_sink", self._video_appsink),
            ("aacparse", aacparse),
            ("audio_queue", audio_queue),
            ("audio_sink", self._audio_appsink),
        ]:
            if elem is None:
                raise RuntimeError(f"Failed to create {elem_name} element")

        # Configure appsinks
        for appsink in [self._video_appsink, self._audio_appsink]:
            appsink.set_property("emit-signals", True)
            appsink.set_property("sync", False)

        # Set caps
        video_caps = Gst.Caps.from_string("video/x-h264")
        self._video_appsink.set_property("caps", video_caps)

        audio_caps = Gst.Caps.from_string("audio/mpeg")
        self._audio_appsink.set_property("caps", audio_caps)

        # Connect appsink signals
        self._video_appsink.connect("new-sample", self._on_video_sample)
        self._audio_appsink.connect("new-sample", self._on_audio_sample)

        # Add elements to pipeline
        self._pipeline.add(rtspsrc)
        self._pipeline.add(h264parse)
        self._pipeline.add(video_queue)
        self._pipeline.add(self._video_appsink)
        self._pipeline.add(aacparse)
        self._pipeline.add(audio_queue)
        self._pipeline.add(self._audio_appsink)

        # Link static elements (video path)
        if not h264parse.link(video_queue):
            raise RuntimeError("Failed to link h264parse -> video_queue")
        if not video_queue.link(self._video_appsink):
            raise RuntimeError("Failed to link video_queue -> video_sink")

        # Link static elements (audio path)
        if not aacparse.link(audio_queue):
            raise RuntimeError("Failed to link aacparse -> audio_queue")
        if not audio_queue.link(self._audio_appsink):
            raise RuntimeError("Failed to link audio_queue -> audio_sink")

        # Store references for dynamic pad linking
        self._h264parse = h264parse
        self._aacparse = aacparse

        # Connect rtspsrc pad-added signal for dynamic linking
        rtspsrc.connect("pad-added", self._on_pad_added)

        # Set up bus message handling
        self._bus = self._pipeline.get_bus()
        if self._bus:
            self._bus.add_signal_watch()
            self._bus.connect("message", self._on_bus_message)

        self._state = "READY"
        logger.info(f"Input pipeline built for {self._rtsp_url}")

    def _on_pad_added(
        self, element: Gst.Element, pad: Gst.Pad
    ) -> None:
        """Handle dynamic pad creation from rtspsrc.

        Links newly created pads to appropriate parsers based on media type.

        Args:
            element: Source element (rtspsrc)
            pad: Newly created pad
        """
        caps = pad.get_current_caps()
        if caps is None:
            caps = pad.query_caps(None)

        if caps is None or caps.is_empty():
            return

        structure = caps.get_structure(0)
        media_type = structure.get_name()

        logger.debug(f"Pad added: {pad.get_name()}, media type: {media_type}")

        if media_type.startswith("video"):
            sink_pad = self._h264parse.get_static_pad("sink")
            if sink_pad and not sink_pad.is_linked():
                result = pad.link(sink_pad)
                if result == Gst.PadLinkReturn.OK:
                    logger.info("Linked rtspsrc video pad to h264parse")
                else:
                    logger.error(f"Failed to link video pad: {result}")

        elif media_type.startswith("audio"):
            sink_pad = self._aacparse.get_static_pad("sink")
            if sink_pad and not sink_pad.is_linked():
                result = pad.link(sink_pad)
                if result == Gst.PadLinkReturn.OK:
                    logger.info("Linked rtspsrc audio pad to aacparse")
                else:
                    logger.error(f"Failed to link audio pad: {result}")

    def _on_video_sample(self, appsink: Gst.Element) -> Gst.FlowReturn:
        """Handle new video sample from appsink.

        Args:
            appsink: The video appsink element

        Returns:
            Gst.FlowReturn.OK on success
        """
        sample = appsink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.OK

        buffer = sample.get_buffer()
        if buffer is None:
            return Gst.FlowReturn.OK

        # Extract buffer data
        result, map_info = buffer.map(Gst.MapFlags.READ)
        if result:
            data = bytes(map_info.data)
            buffer.unmap(map_info)

            pts_ns = buffer.pts if buffer.pts != Gst.CLOCK_TIME_NONE else 0
            duration_ns = buffer.duration if buffer.duration != Gst.CLOCK_TIME_NONE else 0

            try:
                self._on_video_buffer(data, pts_ns, duration_ns)
            except Exception as e:
                logger.error(f"Error in video buffer callback: {e}")

        return Gst.FlowReturn.OK

    def _on_audio_sample(self, appsink: Gst.Element) -> Gst.FlowReturn:
        """Handle new audio sample from appsink.

        Args:
            appsink: The audio appsink element

        Returns:
            Gst.FlowReturn.OK on success
        """
        sample = appsink.emit("pull-sample")
        if sample is None:
            return Gst.FlowReturn.OK

        buffer = sample.get_buffer()
        if buffer is None:
            return Gst.FlowReturn.OK

        # Extract buffer data
        result, map_info = buffer.map(Gst.MapFlags.READ)
        if result:
            data = bytes(map_info.data)
            buffer.unmap(map_info)

            pts_ns = buffer.pts if buffer.pts != Gst.CLOCK_TIME_NONE else 0
            duration_ns = buffer.duration if buffer.duration != Gst.CLOCK_TIME_NONE else 0

            try:
                self._on_audio_buffer(data, pts_ns, duration_ns)
            except Exception as e:
                logger.error(f"Error in audio buffer callback: {e}")

        return Gst.FlowReturn.OK

    def _on_bus_message(self, bus: Gst.Bus, message: Gst.Message) -> bool:
        """Handle GStreamer bus messages.

        Args:
            bus: The pipeline bus
            message: The bus message

        Returns:
            True to continue receiving messages
        """
        msg_type = message.type

        if msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"GStreamer error: {err.message}")
            logger.debug(f"Debug info: {debug}")
            self._state = "ERROR"

        elif msg_type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logger.warning(f"GStreamer warning: {warn.message}")

        elif msg_type == Gst.MessageType.EOS:
            logger.info("End of stream received")
            self._state = "EOS"

        elif msg_type == Gst.MessageType.STATE_CHANGED:
            if message.src == self._pipeline:
                old, new, pending = message.parse_state_changed()
                logger.debug(f"Pipeline state: {old.value_nick} -> {new.value_nick}")
                self._state = new.value_nick.upper()

        return True

    def start(self) -> bool:
        """Start the pipeline (transition to PLAYING).

        Returns:
            True if state change succeeded

        Raises:
            RuntimeError: If pipeline not built
        """
        if self._pipeline is None:
            raise RuntimeError("Pipeline not built - call build() first")

        ret = self._pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("Failed to start pipeline")
            return False

        logger.info("Pipeline started")
        return True

    def stop(self) -> None:
        """Stop the pipeline (transition to NULL)."""
        if self._pipeline is None:
            return

        self._pipeline.set_state(Gst.State.NULL)
        self._state = "NULL"
        logger.info("Pipeline stopped")

    def get_state(self) -> str:
        """Get current pipeline state.

        Returns:
            State string: "NULL", "READY", "PAUSED", "PLAYING", "ERROR", or "EOS"
        """
        return self._state

    def cleanup(self) -> None:
        """Clean up pipeline resources."""
        self.stop()

        if self._bus:
            self._bus.remove_signal_watch()
            self._bus = None

        self._pipeline = None
        self._video_appsink = None
        self._audio_appsink = None
        logger.info("Pipeline cleaned up")
