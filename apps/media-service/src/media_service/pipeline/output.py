"""
Output pipeline for RTMP stream publishing with A/V re-encoding.

Publishes re-encoded video (H.264) and audio (AAC) to MediaMTX via RTMP.
Both streams are re-encoded to ensure synchronized PTS and smooth playback.

Per spec 003 + 024-pts-av-pairing:
- Video: decode H.264 → re-encode with x264enc (zerolatency)
- Audio: decode AAC → re-encode with voaacenc
- Synchronized PTS: both streams share monotonic output PTS
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
    """RTMP output pipeline with video and audio re-encoding.

    Constructs a GStreamer pipeline that:
    1. Receives video and audio buffers via appsrc push
    2. Re-encodes both streams for synchronized timing
    3. Muxes into FLV container with aligned PTS
    4. Publishes to RTMP endpoint

    Pipeline structure:
    Video: appsrc → h264parse → avdec_h264 → videoconvert → x264enc → h264parse → flvmux
    Audio: appsrc → aacparse → avdec_aac → audioconvert → audioresample → voaacenc → flvmux
                                                                                      ↓
                                                                                 rtmpsink

    Attributes:
        _rtmp_url: RTMP destination URL
        _pipeline: GStreamer pipeline (after build)
        _video_appsrc: Video source element
        _audio_appsrc: Audio source element
        _state: Current pipeline state string
        _output_pts_ns: Monotonically increasing output PTS counter
        _first_video_pts_ns: PTS of first video buffer (for offset calculation)
        _first_audio_pts_ns: PTS of first audio buffer (for offset calculation)
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

        # Store SPS/PPS NAL units extracted from first video segment
        self._sps_pps_data: bytes | None = None

        # Synchronized PTS tracking
        # We track the first PTS of each stream and compute output PTS relative to a common base
        self._first_video_pts_ns: int | None = None
        self._first_audio_pts_ns: int | None = None
        self._base_pts_ns: int | None = None  # Common base for both streams
        self._last_video_output_pts_ns: int = 0
        self._last_audio_output_pts_ns: int = 0

        # Track end PTS for A/V sync summary
        self._last_video_end_pts_ns: int = 0
        self._last_audio_end_pts_ns: int = 0
        self._push_count: int = 0

    def build(self) -> None:
        """Build the GStreamer output pipeline with A/V re-encoding.

        Creates pipeline structure:
        Video: appsrc → h264parse → avdec_h264 → videoconvert → x264enc → flvmux
        Audio: appsrc → aacparse → avdec_aac → audioconvert → voaacenc → flvmux → rtmpsink

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

        # ============ VIDEO PATH ============
        # appsrc → h264parse → avdec_h264 → videoconvert → x264enc → h264parse → queue
        self._video_appsrc = Gst.ElementFactory.make("appsrc", "video_src")
        h264parse_in = Gst.ElementFactory.make("h264parse", "h264parse_in")
        avdec_h264 = Gst.ElementFactory.make("avdec_h264", "avdec_h264")
        videoconvert = Gst.ElementFactory.make("videoconvert", "videoconvert")
        x264enc = Gst.ElementFactory.make("x264enc", "x264enc")
        h264parse_out = Gst.ElementFactory.make("h264parse", "h264parse_out")
        video_queue = Gst.ElementFactory.make("queue", "video_queue")

        # Configure input h264parse
        h264parse_in.set_property("config-interval", -1)  # Insert SPS/PPS for decoder

        # Configure x264enc for low-latency streaming
        x264enc.set_property("tune", 0x00000004)  # zerolatency
        x264enc.set_property("key-int-max", 30)  # Keyframe every 1s at 30fps
        x264enc.set_property("bframes", 0)  # No B-frames
        x264enc.set_property("speed-preset", 3)  # veryfast
        x264enc.set_property("bitrate", 2000)  # 2 Mbps

        # Configure output h264parse for AVC output
        h264parse_out.set_property("config-interval", -1)

        # ============ AUDIO PATH ============
        # appsrc → aacparse → avdec_aac → audioconvert → audioresample → voaacenc → aacparse → queue
        self._audio_appsrc = Gst.ElementFactory.make("appsrc", "audio_src")
        aacparse_in = Gst.ElementFactory.make("aacparse", "aacparse_in")
        avdec_aac = Gst.ElementFactory.make("avdec_aac", "avdec_aac")
        audioconvert = Gst.ElementFactory.make("audioconvert", "audioconvert")
        audioresample = Gst.ElementFactory.make("audioresample", "audioresample")

        # Try voaacenc first (commonly available), fallback to avenc_aac
        voaacenc = Gst.ElementFactory.make("voaacenc", "voaacenc")
        if voaacenc is None:
            logger.warning("voaacenc not available, trying avenc_aac")
            voaacenc = Gst.ElementFactory.make("avenc_aac", "avenc_aac")
            if voaacenc is None:
                logger.warning("avenc_aac not available, trying fdkaacenc")
                voaacenc = Gst.ElementFactory.make("fdkaacenc", "fdkaacenc")

        aacparse_out = Gst.ElementFactory.make("aacparse", "aacparse_out")
        audio_queue = Gst.ElementFactory.make("queue", "audio_queue")

        # ============ MUXER AND SINK ============
        flvmux = Gst.ElementFactory.make("flvmux", "flvmux")
        rtmpsink = Gst.ElementFactory.make("rtmpsink", "rtmpsink")

        # Verify all elements created
        elements = [
            ("video_src", self._video_appsrc),
            ("h264parse_in", h264parse_in),
            ("avdec_h264", avdec_h264),
            ("videoconvert", videoconvert),
            ("x264enc", x264enc),
            ("h264parse_out", h264parse_out),
            ("video_queue", video_queue),
            ("audio_src", self._audio_appsrc),
            ("aacparse_in", aacparse_in),
            ("avdec_aac", avdec_aac),
            ("audioconvert", audioconvert),
            ("audioresample", audioresample),
            ("aac_encoder", voaacenc),
            ("aacparse_out", aacparse_out),
            ("audio_queue", audio_queue),
            ("flvmux", flvmux),
            ("rtmpsink", rtmpsink),
        ]

        for elem_name, elem in elements:
            if elem is None:
                raise RuntimeError(f"Failed to create {elem_name} element")

        # ============ CONFIGURE APPSRCS ============
        # Video appsrc - byte-stream H.264
        video_caps = Gst.Caps.from_string("video/x-h264,stream-format=byte-stream,alignment=au")
        self._video_appsrc.set_property("caps", video_caps)
        self._video_appsrc.set_property("is-live", True)
        self._video_appsrc.set_property("format", 3)  # GST_FORMAT_TIME
        self._video_appsrc.set_property("do-timestamp", False)

        # Audio appsrc - ADTS AAC
        audio_caps = Gst.Caps.from_string("audio/mpeg,mpegversion=4,stream-format=adts")
        self._audio_appsrc.set_property("caps", audio_caps)
        self._audio_appsrc.set_property("is-live", True)
        self._audio_appsrc.set_property("format", 3)  # GST_FORMAT_TIME
        self._audio_appsrc.set_property("do-timestamp", False)

        # ============ CONFIGURE FLVMUX ============
        flvmux.set_property("streamable", True)

        # ============ CONFIGURE RTMPSINK ============
        rtmpsink.set_property("location", self._rtmp_url)

        # ============ ADD ELEMENTS TO PIPELINE ============
        for _, elem in elements:
            self._pipeline.add(elem)

        # ============ LINK VIDEO PATH ============
        if not self._video_appsrc.link(h264parse_in):
            raise RuntimeError("Failed to link video_src -> h264parse_in")
        if not h264parse_in.link(avdec_h264):
            raise RuntimeError("Failed to link h264parse_in -> avdec_h264")
        if not avdec_h264.link(videoconvert):
            raise RuntimeError("Failed to link avdec_h264 -> videoconvert")
        if not videoconvert.link(x264enc):
            raise RuntimeError("Failed to link videoconvert -> x264enc")
        if not x264enc.link(h264parse_out):
            raise RuntimeError("Failed to link x264enc -> h264parse_out")
        if not h264parse_out.link(video_queue):
            raise RuntimeError("Failed to link h264parse_out -> video_queue")

        # ============ LINK AUDIO PATH ============
        if not self._audio_appsrc.link(aacparse_in):
            raise RuntimeError("Failed to link audio_src -> aacparse_in")
        if not aacparse_in.link(avdec_aac):
            raise RuntimeError("Failed to link aacparse_in -> avdec_aac")
        if not avdec_aac.link(audioconvert):
            raise RuntimeError("Failed to link avdec_aac -> audioconvert")
        if not audioconvert.link(audioresample):
            raise RuntimeError("Failed to link audioconvert -> audioresample")
        if not audioresample.link(voaacenc):
            raise RuntimeError("Failed to link audioresample -> voaacenc")
        if not voaacenc.link(aacparse_out):
            raise RuntimeError("Failed to link voaacenc -> aacparse_out")
        if not aacparse_out.link(audio_queue):
            raise RuntimeError("Failed to link aacparse_out -> audio_queue")

        # ============ LINK TO FLVMUX ============
        video_mux_pad = flvmux.get_request_pad("video")
        audio_mux_pad = flvmux.get_request_pad("audio")

        video_queue_src = video_queue.get_static_pad("src")
        audio_queue_src = audio_queue.get_static_pad("src")

        if video_queue_src.link(video_mux_pad) != Gst.PadLinkReturn.OK:
            raise RuntimeError("Failed to link video_queue -> flvmux")
        if audio_queue_src.link(audio_mux_pad) != Gst.PadLinkReturn.OK:
            raise RuntimeError("Failed to link audio_queue -> flvmux")

        # ============ LINK TO RTMPSINK ============
        if not flvmux.link(rtmpsink):
            raise RuntimeError("Failed to link flvmux -> rtmpsink")

        # Set up bus for polling-based message handling
        self._bus = self._pipeline.get_bus()

        self._state = "READY"
        encoder_name = voaacenc.get_factory().get_name() if voaacenc else "unknown"
        logger.info(
            f"🎬 Output pipeline built with A/V RE-ENCODING for {self._rtmp_url}"
        )
        logger.info("   Video: appsrc → h264parse → avdec → x264enc → flvmux")
        logger.info(f"   Audio: appsrc → aacparse → avdec → {encoder_name} → flvmux → rtmpsink")

    def _compute_output_pts(self, input_pts_ns: int, is_video: bool) -> int:
        """Compute synchronized output PTS from input PTS.

        Uses the first PTS received (from either stream) as the base.
        All subsequent PTS values are computed relative to this base,
        ensuring both streams are synchronized.

        Args:
            input_pts_ns: Input PTS in nanoseconds
            is_video: True for video, False for audio

        Returns:
            Output PTS in nanoseconds (monotonically increasing)
        """
        # Track first PTS for each stream
        if is_video:
            if self._first_video_pts_ns is None:
                self._first_video_pts_ns = input_pts_ns
                logger.info(f"🎬 First video PTS: {input_pts_ns / 1e9:.3f}s")
        else:
            if self._first_audio_pts_ns is None:
                self._first_audio_pts_ns = input_pts_ns
                logger.info(f"🔊 First audio PTS: {input_pts_ns / 1e9:.3f}s")

        # Set base PTS from the first stream that arrives
        if self._base_pts_ns is None:
            self._base_pts_ns = input_pts_ns
            logger.info(f"📐 Base PTS set: {self._base_pts_ns / 1e9:.3f}s")

        # Compute output PTS relative to base
        output_pts_ns = input_pts_ns - self._base_pts_ns

        # Ensure monotonically increasing (handle out-of-order arrivals)
        if is_video:
            if output_pts_ns < self._last_video_output_pts_ns:
                logger.warning(
                    f"⚠️ Video PTS went backwards: {output_pts_ns / 1e9:.3f}s < "
                    f"{self._last_video_output_pts_ns / 1e9:.3f}s, using last"
                )
                output_pts_ns = self._last_video_output_pts_ns
            self._last_video_output_pts_ns = output_pts_ns
        else:
            if output_pts_ns < self._last_audio_output_pts_ns:
                logger.warning(
                    f"⚠️ Audio PTS went backwards: {output_pts_ns / 1e9:.3f}s < "
                    f"{self._last_audio_output_pts_ns / 1e9:.3f}s, using last"
                )
                output_pts_ns = self._last_audio_output_pts_ns
            self._last_audio_output_pts_ns = output_pts_ns

        return output_pts_ns

    def _on_bus_message(self, bus: Gst.Bus, message: Gst.Message) -> bool:
        """Handle GStreamer bus messages."""
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
            structure = message.get_structure()
            if structure:
                logger.debug(
                    f"📨 OUTPUT ELEMENT MESSAGE [{message.src.get_name()}]: {structure.to_string()}"
                )

        return True

    def _poll_bus_messages(self) -> None:
        """Poll bus for messages without requiring GLib main loop."""
        if not self._bus:
            return

        while True:
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
                break

            self._on_bus_message(self._bus, msg)

    def convert_m4a_bytes_to_adts(self, m4a_data: bytes) -> bytes:
        """Convert M4A container bytes to raw ADTS AAC frames.

        Uses GStreamer to demux M4A and extract AAC in ADTS format.

        Args:
            m4a_data: M4A container data (in memory)

        Returns:
            AAC audio data in ADTS format
        """
        if not GST_AVAILABLE or Gst is None:
            raise RuntimeError("GStreamer not available")

        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
            tmp.write(m4a_data)
            tmp_path = tmp.name

        try:
            logger.debug(f"🔊 Converting M4A bytes ({len(m4a_data)} bytes) to ADTS")

            pipeline_str = (
                f"filesrc location={tmp_path} ! "
                "qtdemux name=demux demux.audio_0 ! "
                "aacparse ! "
                "audio/mpeg,mpegversion=4,stream-format=adts ! "
                "appsink name=sink emit-signals=true sync=false"
            )

            pipeline = Gst.parse_launch(pipeline_str)
            appsink = pipeline.get_by_name("sink")

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

            pipeline.set_state(Gst.State.PLAYING)
            bus = pipeline.get_bus()
            msg = bus.timed_pop_filtered(
                5 * Gst.SECOND,
                Gst.MessageType.EOS | Gst.MessageType.ERROR,
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
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _extract_sps_pps(self, data: bytes) -> bytes | None:
        """Extract SPS and PPS NAL units from H.264 byte-stream data."""
        sps_data = None
        pps_data = None

        i = 0
        while i < len(data) - 4:
            if data[i : i + 4] == b"\x00\x00\x00\x01":
                nal_type = data[i + 4] & 0x1F
                next_start = len(data)
                for j in range(i + 4, min(len(data) - 3, i + 10000)):
                    if data[j : j + 4] == b"\x00\x00\x00\x01" or data[j : j + 3] == b"\x00\x00\x01":
                        next_start = j
                        break

                if nal_type == 7 and sps_data is None:
                    sps_data = data[i:next_start]
                elif nal_type == 8 and pps_data is None:
                    pps_data = data[i:next_start]

                if sps_data and pps_data:
                    break

                i = next_start
            elif data[i : i + 3] == b"\x00\x00\x01":
                nal_type = data[i + 3] & 0x1F
                next_start = len(data)
                for j in range(i + 3, min(len(data) - 3, i + 10000)):
                    if data[j : j + 4] == b"\x00\x00\x00\x01" or data[j : j + 3] == b"\x00\x00\x01":
                        next_start = j
                        break

                if nal_type == 7 and sps_data is None:
                    sps_data = b"\x00\x00\x00\x01" + data[i + 3 : next_start]
                elif nal_type == 8 and pps_data is None:
                    pps_data = b"\x00\x00\x00\x01" + data[i + 3 : next_start]

                if sps_data and pps_data:
                    break

                i = next_start
            else:
                i += 1

        if sps_data and pps_data:
            return sps_data + pps_data
        return None

    def push_video(self, data: bytes, pts_ns: int, duration_ns: int = 0) -> bool:
        """Push video buffer to output pipeline.

        Args:
            data: H.264 encoded video data
            pts_ns: Presentation timestamp in nanoseconds
            duration_ns: Buffer duration in nanoseconds (optional)

        Returns:
            True if push succeeded
        """
        if self._video_appsrc is None:
            raise RuntimeError("Pipeline not built - call build() first")

        # Check for SPS/PPS
        has_sps = b"\x00\x00\x00\x01\x67" in data or b"\x00\x00\x01\x67" in data
        has_pps = b"\x00\x00\x00\x01\x68" in data or b"\x00\x00\x01\x68" in data
        has_sps_at_start = (
            b"\x00\x00\x00\x01\x67" in data[:100] or b"\x00\x00\x01\x67" in data[:100]
        )
        has_pps_at_start = (
            b"\x00\x00\x00\x01\x68" in data[:200] or b"\x00\x00\x01\x68" in data[:200]
        )

        # Extract and store SPS/PPS
        if self._sps_pps_data is None and has_sps and has_pps:
            self._sps_pps_data = self._extract_sps_pps(data)
            if self._sps_pps_data:
                logger.info(f"📼 Extracted SPS/PPS: {len(self._sps_pps_data)} bytes")

        # Prepend SPS/PPS if needed
        if self._sps_pps_data and not (has_sps_at_start and has_pps_at_start):
            data = self._sps_pps_data + data
            logger.debug("📼 Prepended SPS/PPS to video data")

        # Compute synchronized output PTS
        output_pts_ns = self._compute_output_pts(pts_ns, is_video=True)

        # Poll bus messages
        self._poll_bus_messages()

        buffer = Gst.Buffer.new_allocate(None, len(data), None)
        buffer.fill(0, data)
        buffer.pts = output_pts_ns
        if duration_ns > 0:
            buffer.duration = duration_ns
        buffer.set_flags(Gst.BufferFlags.LIVE)

        ret = self._video_appsrc.emit("push-buffer", buffer)
        success = ret == Gst.FlowReturn.OK

        if not success:
            logger.error(
                f"❌ VIDEO PUSH FAILED: input_pts={pts_ns / 1e9:.2f}s, "
                f"output_pts={output_pts_ns / 1e9:.2f}s, ret={ret.value_nick}"
            )
        else:
            in_pts = pts_ns / 1e9
            out_pts = output_pts_ns / 1e9
            dur = duration_ns / 1e9
            end_pts = out_pts + dur
            self._last_video_end_pts_ns = output_pts_ns + duration_ns
            logger.info(
                f"📹 VIDEO PUSHED: in={in_pts:.2f}s → out=[{out_pts:.2f}s - {end_pts:.2f}s] "
                f"dur={dur:.3f}s size={len(data)}"
            )
            self._log_av_sync_summary()

        return success

    def push_audio(self, data: bytes, pts_ns: int, duration_ns: int = 0) -> bool:
        """Push audio buffer to output pipeline.

        Args:
            data: AAC encoded audio data (ADTS format)
            pts_ns: Presentation timestamp in nanoseconds
            duration_ns: Buffer duration in nanoseconds (optional)

        Returns:
            True if push succeeded
        """
        if self._audio_appsrc is None:
            raise RuntimeError("Pipeline not built - call build() first")

        # Compute synchronized output PTS
        output_pts_ns = self._compute_output_pts(pts_ns, is_video=False)

        # Poll bus messages
        self._poll_bus_messages()

        buffer = Gst.Buffer.new_allocate(None, len(data), None)
        buffer.fill(0, data)
        buffer.pts = output_pts_ns
        if duration_ns > 0:
            buffer.duration = duration_ns

        ret = self._audio_appsrc.emit("push-buffer", buffer)
        success = ret == Gst.FlowReturn.OK

        if not success:
            logger.error(
                f"❌ AUDIO PUSH FAILED: input_pts={pts_ns / 1e9:.2f}s, "
                f"output_pts={output_pts_ns / 1e9:.2f}s, ret={ret.value_nick}"
            )
        else:
            in_pts = pts_ns / 1e9
            out_pts = output_pts_ns / 1e9
            dur = duration_ns / 1e9
            end_pts = out_pts + dur
            self._last_audio_end_pts_ns = output_pts_ns + duration_ns
            logger.info(
                f"🔊 AUDIO PUSHED: in={in_pts:.2f}s → out=[{out_pts:.2f}s - {end_pts:.2f}s] "
                f"dur={dur:.3f}s size={len(data)}"
            )
            self._log_av_sync_summary()

        return success

    def _log_av_sync_summary(self) -> None:
        """Log A/V sync summary showing current state of both streams."""
        self._push_count += 1
        # Log summary every push to show timeline alignment
        v_end = self._last_video_end_pts_ns / 1e9
        a_end = self._last_audio_end_pts_ns / 1e9
        delta = (self._last_video_end_pts_ns - self._last_audio_end_pts_ns) / 1e6  # ms

        if self._last_video_end_pts_ns > 0 and self._last_audio_end_pts_ns > 0:
            sync_status = "SYNC" if abs(delta) < 500 else ("V_AHEAD" if delta > 0 else "A_AHEAD")
            logger.info(
                f"⏱️  A/V TIMELINE: video_end={v_end:.2f}s audio_end={a_end:.2f}s "
                f"delta={delta:+.0f}ms [{sync_status}]"
            )

    def start(self) -> bool:
        """Start the pipeline (transition to PLAYING)."""
        if self._pipeline is None:
            raise RuntimeError("Pipeline not built - call build() first")

        logger.info(f"🚀 STARTING OUTPUT PIPELINE -> {self._rtmp_url}")

        ret = self._pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error(f"❌ FAILED TO START OUTPUT PIPELINE -> {self._rtmp_url}")
            return False
        elif ret == Gst.StateChangeReturn.ASYNC:
            logger.info(f"⏳ OUTPUT PIPELINE STARTING (ASYNC) -> {self._rtmp_url}")
            logger.info("✅ OUTPUT PIPELINE SET TO PLAYING (will complete when data flows)")
        else:
            logger.info(f"✅ OUTPUT PIPELINE STARTED (SYNC) -> {self._rtmp_url}")

        return True

    def stop(self) -> None:
        """Stop the pipeline (transition to NULL)."""
        if self._pipeline is None:
            return

        if self._video_appsrc:
            self._video_appsrc.emit("end-of-stream")
        if self._audio_appsrc:
            self._audio_appsrc.emit("end-of-stream")

        self._pipeline.set_state(Gst.State.NULL)
        self._state = "NULL"
        logger.info("Output pipeline stopped")

    def get_state(self) -> str:
        """Get current pipeline state."""
        return self._state

    def cleanup(self) -> None:
        """Clean up pipeline resources."""
        self.stop()
        self._bus = None
        self._pipeline = None
        self._video_appsrc = None
        self._audio_appsrc = None

        # Reset PTS tracking
        self._first_video_pts_ns = None
        self._first_audio_pts_ns = None
        self._base_pts_ns = None
        self._last_video_output_pts_ns = 0
        self._last_audio_output_pts_ns = 0
        self._last_video_end_pts_ns = 0
        self._last_audio_end_pts_ns = 0
        self._push_count = 0

        logger.info("Output pipeline cleaned up")
