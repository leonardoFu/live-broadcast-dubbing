"""
Output pipeline for RTMP stream publishing.

Publishes remuxed video (H.264) and audio (AAC) to MediaMTX via RTMP.

Per spec 003:
- Video codec-copied (H.264 passthrough)
- Audio AAC for output
- FLV mux with streamable=true for RTMP
- appsrc with is-live=true, format=time
"""

from __future__ import annotations

import logging

# GStreamer imports
try:
    import gi

    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    from gi.repository import Gst, GstApp

    GST_AVAILABLE = True
except (ImportError, ValueError):
    GST_AVAILABLE = False
    Gst = None  # type: ignore
    GstApp = None  # type: ignore


logger = logging.getLogger(__name__)


class OutputPipeline:
    """RTMP output pipeline with video and audio appsrcs.

    Constructs a GStreamer pipeline that:
    1. Receives video and audio buffers via appsrc push
    2. Muxes into FLV container
    3. Publishes to RTMP endpoint

    Attributes:
        _rtmp_url: RTMP destination URL
        _pipeline: GStreamer pipeline (after build)
        _video_appsrc: Video source element
        _audio_appsrc: Audio source element
        _state: Current pipeline state string
    """

    def __init__(self, rtmp_url: str) -> None:
        """Initialize output pipeline.

        Args:
            rtmp_url: RTMP URL (e.g., "rtmp://mediamtx:1935/live/stream/out")

        Raises:
            ValueError: If RTMP URL is empty or invalid format
        """
        if not rtmp_url:
            raise ValueError("RTMP URL cannot be empty")

        if not rtmp_url.startswith("rtmp://"):
            raise ValueError(f"Invalid RTMP URL: must start with 'rtmp://' - got '{rtmp_url}'")

        self._rtmp_url = rtmp_url
        self._pipeline: Gst.Pipeline | None = None
        self._video_appsrc: Gst.Element | None = None
        self._audio_appsrc: Gst.Element | None = None
        self._state = "NULL"
        self._bus: Gst.Bus | None = None

    def build(self) -> None:
        """Build the GStreamer output pipeline.

        Creates pipeline structure:
        video_appsrc -> h264parse -> queue -> flvmux -> rtmpsink
        audio_appsrc -> aacparse -> queue -^

        Raises:
            RuntimeError: If GStreamer not available or element creation fails
        """
        if not GST_AVAILABLE or Gst is None:
            raise RuntimeError("GStreamer not available")

        if not Gst.is_initialized():
            Gst.init(None)

        # Create pipeline
        self._pipeline = Gst.Pipeline.new("output_pipeline")
        if self._pipeline is None:
            raise RuntimeError("Failed to create GStreamer pipeline")

        # Create video path elements
        self._video_appsrc = Gst.ElementFactory.make("appsrc", "video_src")
        h264parse = Gst.ElementFactory.make("h264parse", "h264parse")
        video_queue = Gst.ElementFactory.make("queue", "video_queue")

        # Create audio path elements
        self._audio_appsrc = Gst.ElementFactory.make("appsrc", "audio_src")
        aacparse = Gst.ElementFactory.make("aacparse", "aacparse")
        audio_queue = Gst.ElementFactory.make("queue", "audio_queue")

        # Create muxer and sink
        flvmux = Gst.ElementFactory.make("flvmux", "flvmux")
        rtmpsink = Gst.ElementFactory.make("rtmpsink", "rtmpsink")

        # Verify all elements created
        elements = [
            ("video_src", self._video_appsrc),
            ("h264parse", h264parse),
            ("video_queue", video_queue),
            ("audio_src", self._audio_appsrc),
            ("aacparse", aacparse),
            ("audio_queue", audio_queue),
            ("flvmux", flvmux),
            ("rtmpsink", rtmpsink),
        ]

        for elem_name, elem in elements:
            if elem is None:
                raise RuntimeError(f"Failed to create {elem_name} element")

        # Configure video appsrc
        video_caps = Gst.Caps.from_string(
            "video/x-h264,stream-format=byte-stream,alignment=au"
        )
        self._video_appsrc.set_property("caps", video_caps)
        self._video_appsrc.set_property("is-live", True)
        self._video_appsrc.set_property("format", 3)  # GST_FORMAT_TIME
        self._video_appsrc.set_property("do-timestamp", False)

        # Configure audio appsrc
        audio_caps = Gst.Caps.from_string(
            "audio/mpeg,mpegversion=4,stream-format=raw,channels=2,rate=48000"
        )
        self._audio_appsrc.set_property("caps", audio_caps)
        self._audio_appsrc.set_property("is-live", True)
        self._audio_appsrc.set_property("format", 3)  # GST_FORMAT_TIME
        self._audio_appsrc.set_property("do-timestamp", False)

        # Configure flvmux for streaming
        flvmux.set_property("streamable", True)

        # Configure rtmpsink
        rtmpsink.set_property("location", self._rtmp_url)

        # Add elements to pipeline
        for _, elem in elements:
            self._pipeline.add(elem)

        # Link video path
        if not self._video_appsrc.link(h264parse):
            raise RuntimeError("Failed to link video_src -> h264parse")
        if not h264parse.link(video_queue):
            raise RuntimeError("Failed to link h264parse -> video_queue")

        # Link audio path
        if not self._audio_appsrc.link(aacparse):
            raise RuntimeError("Failed to link audio_src -> aacparse")
        if not aacparse.link(audio_queue):
            raise RuntimeError("Failed to link aacparse -> audio_queue")

        # Link queues to flvmux using request pads
        video_mux_pad = flvmux.get_request_pad("video")
        audio_mux_pad = flvmux.get_request_pad("audio")

        video_queue_src = video_queue.get_static_pad("src")
        audio_queue_src = audio_queue.get_static_pad("src")

        if video_queue_src.link(video_mux_pad) != Gst.PadLinkReturn.OK:
            raise RuntimeError("Failed to link video_queue -> flvmux")
        if audio_queue_src.link(audio_mux_pad) != Gst.PadLinkReturn.OK:
            raise RuntimeError("Failed to link audio_queue -> flvmux")

        # Link muxer to sink
        if not flvmux.link(rtmpsink):
            raise RuntimeError("Failed to link flvmux -> rtmpsink")

        # Set up bus message handling
        self._bus = self._pipeline.get_bus()
        if self._bus:
            self._bus.add_signal_watch()
            self._bus.connect("message", self._on_bus_message)

        self._state = "READY"
        logger.info(f"Output pipeline built for {self._rtmp_url}")

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
            logger.error(f"Output pipeline error: {err.message}")
            logger.debug(f"Debug info: {debug}")
            self._state = "ERROR"

        elif msg_type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logger.warning(f"Output pipeline warning: {warn.message}")

        elif msg_type == Gst.MessageType.EOS:
            logger.info("Output pipeline EOS")
            self._state = "EOS"

        elif msg_type == Gst.MessageType.STATE_CHANGED:
            if message.src == self._pipeline:
                old, new, pending = message.parse_state_changed()
                logger.debug(f"Output pipeline state: {old.value_nick} -> {new.value_nick}")
                self._state = new.value_nick.upper()

        return True

    def push_video(self, data: bytes, pts_ns: int, duration_ns: int = 0) -> bool:
        """Push video buffer to output pipeline.

        Args:
            data: H.264 encoded video data
            pts_ns: Presentation timestamp in nanoseconds
            duration_ns: Buffer duration in nanoseconds (optional)

        Returns:
            True if push succeeded

        Raises:
            RuntimeError: If pipeline not built
        """
        if self._video_appsrc is None:
            raise RuntimeError("Pipeline not built - call build() first")

        buffer = Gst.Buffer.new_allocate(None, len(data), None)
        buffer.fill(0, data)
        buffer.pts = pts_ns
        if duration_ns > 0:
            buffer.duration = duration_ns

        ret = self._video_appsrc.emit("push-buffer", buffer)
        return ret == Gst.FlowReturn.OK

    def push_audio(self, data: bytes, pts_ns: int, duration_ns: int = 0) -> bool:
        """Push audio buffer to output pipeline.

        Args:
            data: AAC encoded audio data
            pts_ns: Presentation timestamp in nanoseconds
            duration_ns: Buffer duration in nanoseconds (optional)

        Returns:
            True if push succeeded

        Raises:
            RuntimeError: If pipeline not built
        """
        if self._audio_appsrc is None:
            raise RuntimeError("Pipeline not built - call build() first")

        buffer = Gst.Buffer.new_allocate(None, len(data), None)
        buffer.fill(0, data)
        buffer.pts = pts_ns
        if duration_ns > 0:
            buffer.duration = duration_ns

        ret = self._audio_appsrc.emit("push-buffer", buffer)
        return ret == Gst.FlowReturn.OK

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
            logger.error("Failed to start output pipeline")
            return False

        logger.info("Output pipeline started")
        return True

    def stop(self) -> None:
        """Stop the pipeline (transition to NULL)."""
        if self._pipeline is None:
            return

        # Send EOS to appsrcs for clean shutdown
        if self._video_appsrc:
            self._video_appsrc.emit("end-of-stream")
        if self._audio_appsrc:
            self._audio_appsrc.emit("end-of-stream")

        self._pipeline.set_state(Gst.State.NULL)
        self._state = "NULL"
        logger.info("Output pipeline stopped")

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
        self._video_appsrc = None
        self._audio_appsrc = None
        logger.info("Output pipeline cleaned up")
