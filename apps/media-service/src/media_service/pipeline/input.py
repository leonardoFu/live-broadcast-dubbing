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

Per spec 023-vad-audio-segmentation:
- Level element in audio path for RMS measurement
- Tee splits audio: decode branch (level) + passthrough branch (appsink)
- Level messages posted to bus for VAD processing
- RuntimeError if level element unavailable (fail-fast, no fallback)
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
LevelCallback = Callable[[float, int], None]  # (rms_db, timestamp_ns)


class InputPipeline:
    """RTMP input pipeline with video and audio appsinks.

    Constructs a GStreamer pipeline that:
    1. Pulls RTMP stream from MediaMTX via rtmpsrc
    2. Demuxes FLV container into video (H.264) and audio (AAC) via flvdemux
    3. Routes streams to appsinks for callback-based processing
    4. (Optional) Measures audio levels via GStreamer level element for VAD

    The pipeline preserves original codecs (no re-encoding).

    Audio path with VAD enabled:
    flvdemux -> aacparse -> tee -> queue -> appsink (AAC ADTS)
                               -> decodebin -> audioconvert -> level -> fakesink

    Attributes:
        _rtmp_url: RTMP source URL
        _on_video_buffer: Callback for video buffer processing
        _on_audio_buffer: Callback for audio buffer processing
        _on_level_message: Callback for level element messages (optional)
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
        on_level_message: LevelCallback | None = None,
        level_interval_ns: int = 100_000_000,  # 100ms default
    ) -> None:
        """Initialize input pipeline.

        Args:
            rtmp_url: RTMP URL (e.g., "rtmp://mediamtx:1935/live/stream/in")
            on_video_buffer: Callback for video buffers (data, pts_ns, duration_ns)
            on_audio_buffer: Callback for audio buffers (data, pts_ns, duration_ns)
            max_buffers: Maximum buffers for flvdemux queue (default 10)
            on_level_message: Callback for level messages (rms_db, timestamp_ns)
                If provided, VAD level element will be created. If creation fails,
                RuntimeError is raised (fail-fast, no fallback to fixed segments).
            level_interval_ns: Interval for level measurements in nanoseconds (default 100ms)

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
        self._on_level_message = on_level_message
        self._level_interval_ns = level_interval_ns
        self._pipeline: Gst.Pipeline | None = None
        self._state = "NULL"
        self._bus: Gst.Bus | None = None
        self._video_appsink: Gst.Element | None = None
        self._audio_appsink: Gst.Element | None = None
        self._level_element: Gst.Element | None = None

        # Pad detection flags for audio validation
        self.has_video_pad = False
        self.has_audio_pad = False

    def build(self) -> None:
        """Build the GStreamer pipeline.

        Creates pipeline structure:
        rtmpsrc -> flvdemux -> video: h264parse -> queue -> appsink
                            -> audio: aacparse -> queue -> appsink

        Note: flvdemux creates pads dynamically, so video/audio paths are
        linked in _on_pad_added callback. Static elements (parser->queue->sink)
        are pre-linked, dynamic linking happens for flvdemux->parser.

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
        rtmpsrc.set_property("timeout", 30)  # 30 second timeout for network operations

        # Create FLV demuxer
        flvdemux = Gst.ElementFactory.make("flvdemux", "flvdemux")
        if flvdemux is None:
            raise RuntimeError("Failed to create flvdemux element")

        # Video path elements
        h264parse = Gst.ElementFactory.make("h264parse", "h264parse")
        video_queue = Gst.ElementFactory.make("queue", "video_queue")
        self._video_appsink = Gst.ElementFactory.make("appsink", "video_sink")

        # Configure h264parse to insert SPS/PPS before every IDR frame.
        # This ensures that each video segment will have codec configuration data
        # at the start, which is critical for the output pipeline to properly
        # parse and mux the video for RTMP streaming.
        h264parse.set_property("config-interval", -1)  # -1 = insert before every IDR

        # Configure video queue for better buffering
        video_queue.set_property("max-size-buffers", 0)  # Unlimited buffers
        video_queue.set_property("max-size-bytes", 0)  # Unlimited bytes
        video_queue.set_property("max-size-time", 5 * Gst.SECOND)  # 5 seconds of data
        video_queue.set_property("leaky", 2)  # Leak downstream (drop old data if full)

        # Audio path elements
        # Add aacparse for robust caps negotiation and timestamp handling
        aacparse = Gst.ElementFactory.make("aacparse", "aacparse")
        audio_queue = Gst.ElementFactory.make("queue", "audio_queue")
        self._audio_appsink = Gst.ElementFactory.make("appsink", "audio_sink")

        # Configure audio queue for better buffering
        audio_queue.set_property("max-size-buffers", 0)  # Unlimited buffers
        audio_queue.set_property("max-size-bytes", 0)  # Unlimited bytes
        audio_queue.set_property("max-size-time", 5 * Gst.SECOND)  # 5 seconds of data
        audio_queue.set_property("leaky", 2)  # Leak downstream (drop old data if full)

        # VAD level element path (optional, for RMS measurement)
        # This creates a parallel branch that decodes audio and measures levels
        audio_tee = None
        level_decodebin = None
        audioconvert = None
        level_queue = None
        fakesink = None

        if self._on_level_message is not None:
            # Create tee to split audio into two branches
            audio_tee = Gst.ElementFactory.make("tee", "audio_tee")
            if audio_tee is None:
                raise RuntimeError("Failed to create tee element for VAD - level element required")

            # Create level measurement branch elements
            level_queue = Gst.ElementFactory.make("queue", "level_queue")
            level_decodebin = Gst.ElementFactory.make("decodebin", "level_decodebin")
            audioconvert = Gst.ElementFactory.make("audioconvert", "audioconvert")
            self._level_element = Gst.ElementFactory.make("level", "audio_level")
            fakesink = Gst.ElementFactory.make("fakesink", "level_fakesink")

            # Verify level element created - fail-fast, no fallback!
            if self._level_element is None:
                raise RuntimeError(
                    "Failed to create level element - GStreamer gst-plugins-good package "
                    "may be missing. VAD-based segmentation requires level element. "
                    "No fallback to fixed 6-second segments."
                )

            # Verify all other level path elements
            for elem_name, elem in [
                ("level_queue", level_queue),
                ("level_decodebin", level_decodebin),
                ("audioconvert", audioconvert),
                ("level_fakesink", fakesink),
            ]:
                if elem is None:
                    raise RuntimeError(f"Failed to create {elem_name} element for VAD")

            # Configure level element
            self._level_element.set_property("interval", self._level_interval_ns)
            self._level_element.set_property("post-messages", True)

            # Configure level queue
            level_queue.set_property("max-size-buffers", 10)
            level_queue.set_property("leaky", 2)  # Drop old if full

            # Configure fakesink (silent, no output)
            fakesink.set_property("sync", False)
            fakesink.set_property("async", False)

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
        # Request byte-stream format with AU alignment
        # This forces h264parse to convert AVC (from flvdemux) to byte-stream
        # with SPS/PPS embedded inline, alignment=au for mp4mux compatibility
        video_caps = Gst.Caps.from_string("video/x-h264,stream-format=byte-stream,alignment=au")
        self._video_appsink.set_property("caps", video_caps)

        # Configure audio appsink
        self._audio_appsink.set_property("emit-signals", True)
        self._audio_appsink.set_property("sync", False)
        # Request ADTS format from aacparse. FLV contains raw AAC frames, but aacparse
        # will convert them to ADTS (self-describing format with headers) for the output.
        # This ensures the data is consistent throughout the pipeline.
        audio_caps = Gst.Caps.from_string("audio/mpeg,mpegversion=4,stream-format=adts")
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

        # Add level measurement branch if VAD enabled
        if self._on_level_message is not None:
            self._pipeline.add(audio_tee)
            self._pipeline.add(level_queue)
            self._pipeline.add(level_decodebin)
            self._pipeline.add(audioconvert)
            self._pipeline.add(self._level_element)
            self._pipeline.add(fakesink)

        # Link static source elements: rtmpsrc -> flvdemux
        if not rtmpsrc.link(flvdemux):
            raise RuntimeError("Failed to link rtmpsrc -> flvdemux")

        # Link static video elements: h264parse -> queue -> sink
        if not h264parse.link(video_queue):
            raise RuntimeError("Failed to link h264parse -> video_queue")
        if not video_queue.link(self._video_appsink):
            raise RuntimeError("Failed to link video_queue -> video_sink")

        # Link static audio elements based on VAD configuration
        # Note: Do NOT pre-link aacparse to queue! This must happen dynamically
        # after flvdemux creates the audio pad, otherwise the sink pad will be
        # occupied and _on_pad_added will fail to link flvdemux -> aacparse
        if self._on_level_message is not None:
            # With VAD: aacparse -> tee -> queue -> sink (passthrough for appsink)
            #                          -> level_queue -> decodebin -> ... (level measurement)
            if not aacparse.link(audio_tee):
                raise RuntimeError("Failed to link aacparse -> audio_tee")

            # Link passthrough branch: tee -> queue -> appsink
            if not audio_tee.link(audio_queue):
                raise RuntimeError("Failed to link audio_tee -> audio_queue")
            if not audio_queue.link(self._audio_appsink):
                raise RuntimeError("Failed to link audio_queue -> audio_sink")

            # Link level measurement branch: tee -> level_queue -> decodebin
            # Note: decodebin -> audioconvert linking happens dynamically via pad-added
            if not audio_tee.link(level_queue):
                raise RuntimeError("Failed to link audio_tee -> level_queue")
            if not level_queue.link(level_decodebin):
                raise RuntimeError("Failed to link level_queue -> level_decodebin")

            # Link post-decode elements: audioconvert -> level -> fakesink
            if not audioconvert.link(self._level_element):
                raise RuntimeError("Failed to link audioconvert -> level")
            if not self._level_element.link(fakesink):
                raise RuntimeError("Failed to link level -> fakesink")

            # Store references for dynamic pad linking from decodebin
            self._audioconvert = audioconvert
            self._level_decodebin = level_decodebin

            # Connect decodebin pad-added signal for dynamic linking
            level_decodebin.connect("pad-added", self._on_level_decodebin_pad_added)
        else:
            # Without VAD: aacparse -> queue -> sink (original path)
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

    def _on_level_decodebin_pad_added(self, element: Gst.Element, pad: Gst.Pad) -> None:
        """Handle dynamic pad creation from decodebin for level measurement.

        Links decoded audio pad to audioconvert for level measurement.

        Args:
            element: Source element (decodebin)
            pad: Newly created pad
        """
        caps = pad.get_current_caps()
        if caps is None:
            caps = pad.query_caps(None)

        if caps is None or caps.is_empty():
            return

        structure = caps.get_structure(0)
        media_type = structure.get_name()

        logger.debug(f"Level decodebin pad added: {pad.get_name()}, media type: {media_type}")

        # Only link audio pads
        if media_type.startswith("audio/"):
            sink_pad = self._audioconvert.get_static_pad("sink")
            if sink_pad and not sink_pad.is_linked():
                result = pad.link(sink_pad)
                if result == Gst.PadLinkReturn.OK:
                    logger.info("Linked decodebin audio pad to audioconvert for level measurement")
                else:
                    logger.error(f"Failed to link level decodebin audio pad: {result}")

    def _on_pad_added(self, element: Gst.Element, pad: Gst.Pad) -> None:
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
            # Link to aacparse for caps negotiation and timestamp handling
            sink_pad = self._aacparse.get_static_pad("sink")
            if sink_pad and not sink_pad.is_linked():
                result = pad.link(sink_pad)
                if result == Gst.PadLinkReturn.OK:
                    self.has_audio_pad = True
                    logger.info("Linked flvdemux audio pad to aacparse")
                else:
                    logger.error(f"Failed to link audio pad: {result}")
            else:
                if sink_pad:
                    logger.error(f"Audio sink pad already linked - this should not happen!")

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

            # If duration is missing, estimate from framerate (caps) or assume 30fps
            if duration_ns == 0:
                caps = sample.get_caps()
                framerate_fps = 30.0  # Default assumption
                if caps and not caps.is_empty():
                    structure = caps.get_structure(0)
                    if structure.has_field("framerate"):
                        # get_fraction returns (success, numerator, denominator)
                        success, num, denom = structure.get_fraction("framerate")
                        if success and num > 0 and denom > 0:
                            framerate_fps = float(num) / float(denom)
                # Duration = 1/fps * 1e9 ns
                duration_ns = int((1.0 / framerate_fps) * 1_000_000_000)
                logger.debug(
                    f"Estimated video buffer duration: fps={framerate_fps}, duration={duration_ns}ns ({duration_ns / 1e6:.2f}ms)"
                )

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

            # If duration is missing, calculate from caps (sample rate)
            if duration_ns == 0:
                caps = sample.get_caps()
                if caps and not caps.is_empty():
                    structure = caps.get_structure(0)
                    sample_rate = (
                        structure.get_int("rate")[1] if structure.has_field("rate") else 44100
                    )
                    # AAC-LC: 1024 samples per frame
                    # Duration = samples_per_frame / sample_rate * 1e9 ns
                    duration_ns = int((1024 / sample_rate) * 1_000_000_000)
                    logger.debug(
                        f"Calculated audio buffer duration from caps: sample_rate={sample_rate}Hz, duration={duration_ns}ns ({duration_ns / 1e6:.2f}ms)"
                    )

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

        elif msg_type == Gst.MessageType.ELEMENT:
            # Handle level element messages for VAD
            self._handle_level_message(message)

        return True

    def _handle_level_message(self, message: Gst.Message) -> None:
        """Handle level element message and extract RMS.

        Args:
            message: GStreamer ELEMENT message
        """
        if self._on_level_message is None:
            return

        structure = message.get_structure()
        if structure is None:
            return

        if structure.get_name() != "level":
            return

        # Extract RMS array (per-channel)
        success, rms_array = structure.get_array("rms")
        if not success or rms_array is None:
            return

        if rms_array.n_values == 0:
            return

        # Get peak RMS across all channels (max = loudest)
        rms_values = []
        for i in range(rms_array.n_values):
            gvalue = rms_array.get_nth(i)
            if gvalue is not None:
                rms_values.append(gvalue.get_double())

        if not rms_values:
            return

        peak_rms_db = max(rms_values)

        # Extract timestamp
        success, timestamp_ns = structure.get_uint64("running-time")
        if not success:
            timestamp_ns = 0

        # Call callback
        try:
            self._on_level_message(peak_rms_db, timestamp_ns)
        except Exception as e:
            logger.error(f"Error in level message callback: {e}")

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
