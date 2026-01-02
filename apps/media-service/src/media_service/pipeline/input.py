"""
Input pipeline for RTMP stream consumption.

Pulls RTMP stream from MediaMTX, demuxes FLV container into
video (H.264) and audio (AAC) tracks via appsinks.

Per spec 020-rtmp-stream-pull:
- Uses rtmpsrc + flvdemux for simplified RTMP pull (no RTP depayloading)
- Video and audio are codec-copied (no re-encode)
- Appsink callbacks for buffer processing
- Pipeline state management (NULL -> READY -> PAUSED -> PLAYING)
- Audio track validation (rejects video-only streams)
"""

from __future__ import annotations

import logging
import time
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
    """RTMP input pipeline with video and audio appsinks.

    Constructs a GStreamer pipeline that:
    1. Pulls RTMP stream from MediaMTX via rtmpsrc
    2. Demuxes FLV container into video (H.264) and audio (AAC) via flvdemux
    3. Routes streams to appsinks for callback-based processing

    The pipeline preserves original codecs (no re-encoding).

    Attributes:
        _rtmp_url: RTMP source URL
        _on_video_buffer: Callback for video buffer processing
        _on_audio_buffer: Callback for audio buffer processing
        _pipeline: GStreamer pipeline (after build)
        _state: Current pipeline state string
        has_video_pad: Whether video pad has been linked
        has_audio_pad: Whether audio pad has been linked
    """

    def __init__(
        self,
        rtmp_url: str,
        on_video_buffer: BufferCallback,
        on_audio_buffer: BufferCallback,
        max_buffers: int = 10,
    ) -> None:
        """Initialize input pipeline.

        Args:
            rtmp_url: RTMP URL (e.g., "rtmp://mediamtx:1935/live/stream/in")
            on_video_buffer: Callback for video buffers (data, pts_ns, duration_ns)
            on_audio_buffer: Callback for audio buffers (data, pts_ns, duration_ns)
            max_buffers: Maximum buffers for flvdemux queue (default 10)

        Raises:
            ValueError: If RTMP URL is empty or invalid format
        """
        if not rtmp_url:
            raise ValueError("RTMP URL cannot be empty")

        if not rtmp_url.startswith("rtmp://"):
            raise ValueError(f"Invalid RTMP URL: must start with 'rtmp://' - got '{rtmp_url}'")

        self._rtmp_url = rtmp_url
        self._on_video_buffer = on_video_buffer
        self._on_audio_buffer = on_audio_buffer
        self._max_buffers = max_buffers
        self._pipeline: Gst.Pipeline | None = None
        self._state = "NULL"
        self._bus: Gst.Bus | None = None
        self._video_appsink: Gst.Element | None = None
        self._audio_appsink: Gst.Element | None = None

        # Pad detection flags for audio validation
        self.has_video_pad = False
        self.has_audio_pad = False

    def build(self) -> None:
        """Build the GStreamer pipeline.

        Creates pipeline structure:
        rtmpsrc -> flvdemux -> video: h264parse -> queue -> appsink
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

        # Create RTMP source elements
        rtmpsrc = Gst.ElementFactory.make("rtmpsrc", "rtmpsrc")
        if rtmpsrc is None:
            raise RuntimeError("Failed to create rtmpsrc element")

        rtmpsrc.set_property("location", self._rtmp_url)

        # Create FLV demuxer
        flvdemux = Gst.ElementFactory.make("flvdemux", "flvdemux")
        if flvdemux is None:
            raise RuntimeError("Failed to create flvdemux element")

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

        # Configure video appsink
        self._video_appsink.set_property("emit-signals", True)
        self._video_appsink.set_property("sync", False)
        video_caps = Gst.Caps.from_string("video/x-h264")
        self._video_appsink.set_property("caps", video_caps)

        # Configure audio appsink
        self._audio_appsink.set_property("emit-signals", True)
        self._audio_appsink.set_property("sync", False)
        self._audio_appsink.set_property("async", False)
        self._audio_appsink.set_property("max-buffers", 0)  # Unlimited buffering
        self._audio_appsink.set_property("drop", False)
        audio_caps = Gst.Caps.from_string("audio/mpeg")
        self._audio_appsink.set_property("caps", audio_caps)

        # Connect appsink signals
        self._video_appsink.connect("new-sample", self._on_video_sample)
        self._audio_appsink.connect("new-sample", self._on_audio_sample)

        # Add elements to pipeline
        self._pipeline.add(rtmpsrc)
        self._pipeline.add(flvdemux)
        self._pipeline.add(h264parse)
        self._pipeline.add(video_queue)
        self._pipeline.add(self._video_appsink)
        self._pipeline.add(aacparse)
        self._pipeline.add(audio_queue)
        self._pipeline.add(self._audio_appsink)

        # Link static source elements: rtmpsrc -> flvdemux
        if not rtmpsrc.link(flvdemux):
            raise RuntimeError("Failed to link rtmpsrc -> flvdemux")

        # Link static video elements: h264parse -> queue -> sink
        if not h264parse.link(video_queue):
            raise RuntimeError("Failed to link h264parse -> video_queue")
        if not video_queue.link(self._video_appsink):
            raise RuntimeError("Failed to link video_queue -> video_sink")

        # Link static audio elements: aacparse -> queue -> sink
        if not aacparse.link(audio_queue):
            raise RuntimeError("Failed to link aacparse -> audio_queue")
        if not audio_queue.link(self._audio_appsink):
            raise RuntimeError("Failed to link audio_queue -> audio_sink")

        # Store references for dynamic pad linking
        self._h264parse = h264parse
        self._aacparse = aacparse
        self._flvdemux = flvdemux

        # Connect flvdemux pad-added signal for dynamic linking
        flvdemux.connect("pad-added", self._on_pad_added)

        # Set up bus message handling
        self._bus = self._pipeline.get_bus()
        if self._bus:
            self._bus.add_signal_watch()
            self._bus.connect("message", self._on_bus_message)

        self._state = "READY"
        logger.info(f"Input pipeline built for {self._rtmp_url}")

    def _on_pad_added(
        self, element: Gst.Element, pad: Gst.Pad
    ) -> None:
        """Handle dynamic pad creation from flvdemux.

        Links newly created pads to appropriate parsers based on media type.
        FLV demuxer outputs raw video/x-h264 and audio/mpeg caps directly
        (no RTP wrapping, so no depayloading needed).

        Args:
            element: Source element (flvdemux)
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

        # Handle FLV demuxed pads (direct codec formats, not RTP)
        if media_type.startswith("video/x-h264"):
            # Link to h264parse
            sink_pad = self._h264parse.get_static_pad("sink")
            if sink_pad and not sink_pad.is_linked():
                result = pad.link(sink_pad)
                if result == Gst.PadLinkReturn.OK:
                    self.has_video_pad = True
                    logger.info("Linked flvdemux video pad to h264parse")
                else:
                    logger.error(f"Failed to link video pad: {result}")

        elif media_type.startswith("audio/mpeg"):
            # Link to aacparse
            sink_pad = self._aacparse.get_static_pad("sink")
            if sink_pad and not sink_pad.is_linked():
                result = pad.link(sink_pad)
                if result == Gst.PadLinkReturn.OK:
                    self.has_audio_pad = True
                    logger.info("Linked flvdemux audio pad to aacparse")
                else:
                    logger.error(f"Failed to link audio pad: {result}")

    def _validate_audio_track(self, timeout_ms: int = 2000) -> None:
        """Validate audio track presence in the stream.

        Waits for both video and audio pads to be detected within the timeout.
        Raises RuntimeError if audio track is missing (video-only stream).

        Args:
            timeout_ms: Maximum wait time in milliseconds (default 2000ms)

        Raises:
            RuntimeError: If audio track is missing after timeout
        """
        start = time.time()
        timeout_sec = timeout_ms / 1000.0

        while (time.time() - start) < timeout_sec:
            if self.has_audio_pad and self.has_video_pad:
                logger.info("Audio track validation passed: both video and audio detected")
                return
            time.sleep(0.1)

        # Timeout reached - check what's missing
        if not self.has_audio_pad:
            raise RuntimeError(
                "Audio track required for dubbing pipeline - stream rejected. "
                "Video-only streams are not supported."
            )

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
        self.has_video_pad = False
        self.has_audio_pad = False
        logger.info("Pipeline cleaned up")
