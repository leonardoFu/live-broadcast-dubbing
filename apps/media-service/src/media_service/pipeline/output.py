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

        # Configure h264parse to insert SPS/PPS before each IDR frame.
        # This is critical for RTMP streaming where the decoder may join mid-stream
        # and needs the codec configuration data to start decoding.
        h264parse.set_property("config-interval", -1)  # -1 = insert before every IDR

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
        # Use flexible caps - aacparse will determine sample rate and channels from ADTS headers.
        # Don't hardcode rate/channels to avoid mismatch with input (which may be 44100 Hz).
        audio_caps = Gst.Caps.from_string(
            "audio/mpeg,mpegversion=4,stream-format=adts"
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

        # Set up bus for polling-based message handling
        # Note: We use polling instead of signals to avoid GLib main loop requirement
        self._bus = self._pipeline.get_bus()

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
            logger.error(f"❌ OUTPUT PIPELINE ERROR: {err.message}")
            logger.error(f"Debug info: {debug}")
            logger.error(f"Error source: {message.src.get_name()}")
            self._state = "ERROR"

        elif msg_type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logger.warning(f"⚠️ OUTPUT WARNING [{message.src.get_name()}]: {warn.message}")
            logger.debug(f"Debug info: {debug}")

        elif msg_type == Gst.MessageType.EOS:
            logger.info("Output pipeline EOS")
            self._state = "EOS"

        elif msg_type == Gst.MessageType.STATE_CHANGED:
            if message.src == self._pipeline:
                old, new, pending = message.parse_state_changed()
                logger.info(f"🔄 OUTPUT PIPELINE STATE: {old.value_nick} -> {new.value_nick}")
                self._state = new.value_nick.upper()
            elif message.src.get_name() == "rtmpsink":
                old, new, pending = message.parse_state_changed()
                logger.info(f"📡 RTMPSINK STATE: {old.value_nick} -> {new.value_nick}")

        elif msg_type == Gst.MessageType.STREAM_START:
            logger.info(f"▶️ OUTPUT STREAM START: {message.src.get_name()}")

        elif msg_type == Gst.MessageType.ASYNC_DONE:
            logger.info(f"✅ OUTPUT ASYNC DONE: {message.src.get_name()}")

        elif msg_type == Gst.MessageType.ELEMENT:
            # Log element-specific messages (useful for rtmpsink connection events)
            structure = message.get_structure()
            if structure:
                logger.info(f"📨 OUTPUT ELEMENT MESSAGE [{message.src.get_name()}]: {structure.to_string()}")

        return True

    def _poll_bus_messages(self) -> None:
        """Poll bus for messages without requiring GLib main loop.

        This method processes pending bus messages using polling instead of
        signal-based callbacks. This allows the pipeline to progress through
        state changes without requiring a separate GLib main loop thread.

        Should be called periodically (e.g., before pushing buffers) to ensure
        pipeline state changes and error messages are processed in a timely manner.
        """
        if not self._bus:
            return

        # Process all pending messages
        while True:
            # Pop message from bus (non-blocking)
            msg = self._bus.pop_filtered(
                Gst.MessageType.ERROR
                | Gst.MessageType.WARNING
                | Gst.MessageType.EOS
                | Gst.MessageType.STATE_CHANGED
                | Gst.MessageType.STREAM_START
                | Gst.MessageType.ASYNC_DONE
                | Gst.MessageType.ELEMENT
            )

            if not msg:
                # No more messages
                break

            # Process message using existing handler
            self._on_bus_message(self._bus, msg)

    def _wait_for_state_change(self, target_state: Gst.State, timeout_ms: int = 5000) -> bool:
        """Wait for pipeline to reach target state by polling bus messages.

        Args:
            target_state: The state to wait for
            timeout_ms: Maximum time to wait in milliseconds

        Returns:
            True if target state reached, False if timeout or error
        """
        import time

        start_time = time.time()
        timeout_s = timeout_ms / 1000.0

        while True:
            # Check if target state reached
            if self._state == target_state.value_nick.upper():
                return True

            # Check for error state
            if self._state == "ERROR":
                logger.error("Pipeline entered ERROR state while waiting")
                return False

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout_s:
                logger.warning(
                    f"Timeout waiting for {target_state.value_nick} state "
                    f"(current: {self._state}, elapsed: {elapsed:.2f}s)"
                )
                return False

            # Poll messages to progress state transitions
            self._poll_bus_messages()

            # Small sleep to avoid busy-waiting
            time.sleep(0.01)

    def _read_mp4_video(self, mp4_path: str) -> bytes:
        """Read H.264 video data from MP4 file in correct format.

        Uses GStreamer to demux MP4 and extract H.264 in byte-stream format.

        Args:
            mp4_path: Path to MP4 video file

        Returns:
            H.264 video data in byte-stream format with start codes
        """
        if not GST_AVAILABLE or Gst is None:
            raise RuntimeError("GStreamer not available")

        logger.debug(f"🎬 _read_mp4_video: {mp4_path}")

        # Create a pipeline to read and convert the video
        # filesrc ! qtdemux ! h264parse config-interval=-1 ! appsink
        pipeline_str = (
            f"filesrc location={mp4_path} ! "
            "qtdemux name=demux demux.video_0 ! "
            "h264parse config-interval=-1 ! "  # Insert SPS/PPS before each IDR
            "video/x-h264,stream-format=byte-stream,alignment=au ! "
            "appsink name=sink emit-signals=true sync=false"
        )
        logger.debug(f"Pipeline: {pipeline_str}")

        pipeline = Gst.parse_launch(pipeline_str)
        appsink = pipeline.get_by_name("sink")

        # Collect all buffers
        video_data = bytearray()

        def on_new_sample(sink):
            sample = sink.emit("pull-sample")
            if sample:
                buffer = sample.get_buffer()
                success, map_info = buffer.map(Gst.MapFlags.READ)
                if success:
                    video_data.extend(map_info.data)
                    buffer.unmap(map_info)
            return Gst.FlowReturn.OK

        appsink.connect("new-sample", on_new_sample)

        # Run pipeline
        pipeline.set_state(Gst.State.PLAYING)
        bus = pipeline.get_bus()
        msg = bus.timed_pop_filtered(
            Gst.CLOCK_TIME_NONE,
            Gst.MessageType.EOS | Gst.MessageType.ERROR
        )

        if msg and msg.type == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            pipeline.set_state(Gst.State.NULL)
            logger.error(f"❌ GStreamer error reading MP4: {err.message}, debug: {debug}")
            raise RuntimeError(f"Error reading MP4: {err.message}")

        pipeline.set_state(Gst.State.NULL)

        logger.debug(f"✅ Read {len(video_data)} bytes of H.264 from {mp4_path}")
        return bytes(video_data)

    def convert_m4a_bytes_to_adts(self, m4a_data: bytes) -> bytes:
        """Convert M4A container bytes to raw ADTS AAC frames.

        Uses GStreamer to demux M4A and extract AAC in ADTS format.
        This is needed when audio data is in M4A format (from STS service)
        but the output pipeline expects raw ADTS frames.

        Args:
            m4a_data: M4A container data (in memory)

        Returns:
            AAC audio data in ADTS format (self-describing)
        """
        if not GST_AVAILABLE or Gst is None:
            raise RuntimeError("GStreamer not available")

        import tempfile
        import os

        # Write M4A to temp file (GStreamer qtdemux requires seekable source)
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
            tmp.write(m4a_data)
            tmp_path = tmp.name

        try:
            logger.debug(f"🔊 Converting M4A bytes ({len(m4a_data)} bytes) to ADTS")

            # Create a pipeline to read and convert the audio
            pipeline_str = (
                f"filesrc location={tmp_path} ! "
                "qtdemux name=demux demux.audio_0 ! "
                "aacparse ! "
                "audio/mpeg,mpegversion=4,stream-format=adts ! "
                "appsink name=sink emit-signals=true sync=false"
            )

            pipeline = Gst.parse_launch(pipeline_str)
            appsink = pipeline.get_by_name("sink")

            # Collect all buffers
            audio_data = bytearray()

            def on_new_sample(sink):
                sample = sink.emit("pull-sample")
                if sample:
                    buffer = sample.get_buffer()
                    success, map_info = buffer.map(Gst.MapFlags.READ)
                    if success:
                        audio_data.extend(map_info.data)
                        buffer.unmap(map_info)
                return Gst.FlowReturn.OK

            appsink.connect("new-sample", on_new_sample)

            # Run pipeline
            pipeline.set_state(Gst.State.PLAYING)
            bus = pipeline.get_bus()
            msg = bus.timed_pop_filtered(
                5 * Gst.SECOND,  # 5 second timeout
                Gst.MessageType.EOS | Gst.MessageType.ERROR
            )

            if msg and msg.type == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                pipeline.set_state(Gst.State.NULL)
                logger.error(f"❌ GStreamer error converting M4A: {err.message}")
                raise RuntimeError(f"Error converting M4A: {err.message}")

            pipeline.set_state(Gst.State.NULL)

            logger.debug(f"✅ Converted M4A to {len(audio_data)} bytes of ADTS")
            return bytes(audio_data)
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _read_m4a_audio(self, m4a_path: str) -> bytes:
        """Read AAC audio data from M4A file in correct format.

        Uses GStreamer to demux M4A and extract AAC in ADTS format.

        Args:
            m4a_path: Path to M4A audio file

        Returns:
            AAC audio data in ADTS format (self-describing)
        """
        if not GST_AVAILABLE or Gst is None:
            raise RuntimeError("GStreamer not available")

        logger.debug(f"🔊 _read_m4a_audio: {m4a_path}")

        # Create a pipeline to read and convert the audio
        # filesrc ! qtdemux ! aacparse ! appsink
        pipeline_str = (
            f"filesrc location={m4a_path} ! "
            "qtdemux name=demux demux.audio_0 ! "
            "aacparse ! "
            "audio/mpeg,mpegversion=4,stream-format=adts ! "
            "appsink name=sink emit-signals=true sync=false"
        )
        logger.debug(f"Pipeline: {pipeline_str}")

        pipeline = Gst.parse_launch(pipeline_str)
        appsink = pipeline.get_by_name("sink")

        # Collect all buffers
        audio_data = bytearray()

        def on_new_sample(sink):
            sample = sink.emit("pull-sample")
            if sample:
                buffer = sample.get_buffer()
                success, map_info = buffer.map(Gst.MapFlags.READ)
                if success:
                    audio_data.extend(map_info.data)
                    buffer.unmap(map_info)
            return Gst.FlowReturn.OK

        appsink.connect("new-sample", on_new_sample)

        # Run pipeline
        pipeline.set_state(Gst.State.PLAYING)
        bus = pipeline.get_bus()
        msg = bus.timed_pop_filtered(
            Gst.CLOCK_TIME_NONE,
            Gst.MessageType.EOS | Gst.MessageType.ERROR
        )

        if msg and msg.type == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            pipeline.set_state(Gst.State.NULL)
            logger.error(f"❌ GStreamer error reading M4A: {err.message}, debug: {debug}")
            raise RuntimeError(f"Error reading M4A: {err.message}")

        pipeline.set_state(Gst.State.NULL)

        logger.debug(f"✅ Read {len(audio_data)} bytes of AAC from {m4a_path}")
        return bytes(audio_data)

    def push_segment_files(
        self,
        video_mp4_path: str,
        audio_m4a_path: str,
        pts_ns: int,
        video_duration_ns: int,
        audio_duration_ns: int,
    ) -> bool:
        """Push video and audio segment files to output pipeline.

        Reads MP4/M4A files, demuxes them to get properly formatted H.264/AAC,
        and pushes to the output pipeline.

        Args:
            video_mp4_path: Path to video MP4 file
            audio_m4a_path: Path to audio M4A file
            pts_ns: Presentation timestamp in nanoseconds
            video_duration_ns: Video duration in nanoseconds
            audio_duration_ns: Audio duration in nanoseconds

        Returns:
            True if both pushes succeeded
        """
        logger.info(
            f"📦 PUSH_SEGMENT_FILES CALLED: "
            f"video={video_mp4_path}, audio={audio_m4a_path}, "
            f"pts={pts_ns / 1e9:.2f}s"
        )

        try:
            # Check if files exist
            import os
            if not os.path.exists(video_mp4_path):
                logger.error(f"❌ Video file not found: {video_mp4_path}")
                return False
            if not os.path.exists(audio_m4a_path):
                logger.error(f"❌ Audio file not found: {audio_m4a_path}")
                return False

            video_size = os.path.getsize(video_mp4_path)
            audio_size = os.path.getsize(audio_m4a_path)
            logger.info(f"📁 File sizes: video={video_size}B, audio={audio_size}B")

            # Read and demux video
            logger.info(f"📖 Reading MP4 video from {video_mp4_path}...")
            video_data = self._read_mp4_video(video_mp4_path)
            logger.info(f"✅ Read {len(video_data)} bytes of H.264 video data")

            # Read and demux audio
            logger.info(f"📖 Reading M4A audio from {audio_m4a_path}...")
            audio_data = self._read_m4a_audio(audio_m4a_path)
            logger.info(f"✅ Read {len(audio_data)} bytes of AAC audio data")

            # Push to pipeline
            logger.info(f"⬆️ Pushing video data to output pipeline...")
            video_ok = self.push_video(video_data, pts_ns, video_duration_ns)
            logger.info(f"⬆️ Pushing audio data to output pipeline...")
            audio_ok = self.push_audio(audio_data, pts_ns, audio_duration_ns)

            result = video_ok and audio_ok
            logger.info(f"{'✅' if result else '❌'} PUSH_SEGMENT_FILES result: {result}")
            return result

        except Exception as e:
            logger.error(f"❌ Error pushing segment files: {e}", exc_info=True)
            return False

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

        # Poll bus messages to process pipeline state changes
        self._poll_bus_messages()

        buffer = Gst.Buffer.new_allocate(None, len(data), None)
        buffer.fill(0, data)
        buffer.pts = pts_ns
        if duration_ns > 0:
            buffer.duration = duration_ns

        ret = self._video_appsrc.emit("push-buffer", buffer)
        success = ret == Gst.FlowReturn.OK

        if not success:
            logger.error(
                f"❌ VIDEO PUSH FAILED: pts={pts_ns / 1e9:.2f}s, "
                f"size={len(data)}, ret={ret.value_nick}"
            )
        else:
            logger.info(
                f"📹 VIDEO PUSHED: pts={pts_ns / 1e9:.2f}s, "
                f"size={len(data)}, duration={duration_ns / 1e9:.3f}s"
            )

        return success

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

        # Poll bus messages to process pipeline state changes
        self._poll_bus_messages()

        buffer = Gst.Buffer.new_allocate(None, len(data), None)
        buffer.fill(0, data)
        buffer.pts = pts_ns
        if duration_ns > 0:
            buffer.duration = duration_ns

        ret = self._audio_appsrc.emit("push-buffer", buffer)
        success = ret == Gst.FlowReturn.OK

        if not success:
            logger.error(
                f"❌ AUDIO PUSH FAILED: pts={pts_ns / 1e9:.2f}s, "
                f"size={len(data)}, ret={ret.value_nick}"
            )
        else:
            logger.info(
                f"🔊 AUDIO PUSHED: pts={pts_ns / 1e9:.2f}s, "
                f"size={len(data)}, duration={duration_ns / 1e9:.3f}s"
            )

        return success

    def start(self) -> bool:
        """Start the pipeline (transition to PLAYING).

        Returns:
            True if state change succeeded

        Raises:
            RuntimeError: If pipeline not built
        """
        if self._pipeline is None:
            raise RuntimeError("Pipeline not built - call build() first")

        logger.info(f"🚀 STARTING OUTPUT PIPELINE -> {self._rtmp_url}")

        ret = self._pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error(f"❌ FAILED TO START OUTPUT PIPELINE -> {self._rtmp_url}")
            return False
        elif ret == Gst.StateChangeReturn.ASYNC:
            logger.info(f"⏳ OUTPUT PIPELINE STARTING (ASYNC) -> {self._rtmp_url}")
            # For appsrc-based pipelines, the transition to PLAYING may not complete
            # until buffers are pushed. Don't wait synchronously - let it transition
            # naturally as data flows.
            logger.info(f"✅ OUTPUT PIPELINE SET TO PLAYING (will complete when data flows) -> {self._rtmp_url}")
        else:
            logger.info(f"✅ OUTPUT PIPELINE STARTED (SYNC) -> {self._rtmp_url}")

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

        # Release bus reference (no signal watch to remove with polling-based approach)
        self._bus = None

        self._pipeline = None
        self._video_appsrc = None
        self._audio_appsrc = None
        logger.info("Output pipeline cleaned up")
