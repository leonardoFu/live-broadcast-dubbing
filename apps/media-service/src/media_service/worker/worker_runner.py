"""
Worker runner for stream dubbing pipeline orchestration.

Coordinates all components:
- Input pipeline (RTSP -> appsink)
- Segment buffer (accumulate to 6s segments for video, VAD-based for audio)
- STS client (Socket.IO communication)
- A/V sync (pair video with dubbed audio)
- Output pipeline (appsrc -> RTMP)

Per spec 003:
- Full dubbing pipeline orchestration
- Lifecycle management (start/stop/cleanup)
- Error recovery with circuit breaker
- Metrics integration

Per spec 023-vad-audio-segmentation:
- VAD-based audio segmentation using GStreamer level element
- Dynamic segment boundaries at natural speech pauses
- Min/max duration constraints (1-15 seconds)
- Fail-fast design (no fallback to fixed segments)
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from media_service.audio.segment_writer import AudioSegmentWriter
from media_service.buffer.segment_buffer import SegmentBuffer
from media_service.config.segmentation_config import SegmentationConfig
from media_service.metrics.prometheus import WorkerMetrics
from media_service.models.segments import AudioSegment, VideoSegment
from media_service.pipeline.input import InputPipeline
from media_service.pipeline.output import OutputPipeline
from media_service.sts.backpressure_handler import BackpressureHandler
from media_service.sts.circuit_breaker import StsCircuitBreaker
from media_service.sts.fragment_tracker import FragmentTracker
from media_service.sts.models import BackpressurePayload, FragmentProcessedPayload, StreamConfig
from media_service.sts.socketio_client import StsSocketIOClient
from media_service.sync.av_sync import AvSyncManager, SyncPair
from media_service.vad.vad_audio_segmenter import VADAudioSegmenter
from media_service.video.segment_writer import VideoSegmentWriter

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """Configuration for worker runner.

    Attributes:
        stream_id: Stream identifier
        rtmp_input_url: Input RTMP URL for pulling stream from MediaMTX
        rtmp_url: Output RTMP URL for publishing dubbed stream
        sts_url: STS Service URL
        segment_dir: Directory for segment storage
        source_language: Source audio language
        target_language: Target dubbing language
        segment_duration_ns: Segment duration in nanoseconds (for video)
        enable_vad: Enable VAD-based audio segmentation (default True per spec 023)
        output_buffer_size: Number of segments to buffer before starting output (for smooth playback)
    """

    stream_id: str
    rtmp_input_url: str  # Changed from rtsp_url per spec 020-rtmp-stream-pull
    rtmp_url: str
    sts_url: str
    segment_dir: Path
    source_language: str = "en"
    target_language: str = "zh"
    voice_profile: str = "default"
    segment_duration_ns: int = 6_000_000_000  # 6 seconds (for video)
    enable_vad: bool = True  # Enable VAD-based audio segmentation
    output_buffer_size: int = 2  # Buffer 2 segments (~12s) before starting output


class WorkerRunner:
    """Orchestrates the stream dubbing pipeline.

    Coordinates all components for end-to-end dubbing:
    1. Input pipeline pulls RTMP stream from MediaMTX (via rtmpsrc + flvdemux)
    2. Segment buffer accumulates 6-second segments
    3. Video segments written to disk
    4. Audio segments sent to STS for dubbing
    5. A/V sync pairs video with dubbed audio
    6. Output pipeline publishes dubbed stream to RTMP

    Per spec 020-rtmp-stream-pull:
    - Uses RTMP for input (not RTSP) for simpler pipeline
    - No RTP depayloading needed (FLV demuxer handles codec extraction)

    Attributes:
        config: Worker configuration
        metrics: Prometheus metrics
        _running: Whether worker is running
    """

    def __init__(self, config: WorkerConfig) -> None:
        """Initialize worker runner.

        Args:
            config: Worker configuration
        """
        self.config = config
        self.metrics = WorkerMetrics(stream_id=config.stream_id)
        self._running = False
        self._task: asyncio.Task | None = None
        self._skip_sts = False  # Set during start() based on SKIP_STS_CONNECTION env

        # Initialize components
        self._init_components()

    def _init_components(self) -> None:
        """Initialize all pipeline components."""

        # Segment buffer (for video; audio uses VAD segmenter if enabled)
        self.segment_buffer = SegmentBuffer(
            stream_id=self.config.stream_id,
            segment_dir=self.config.segment_dir,
            segment_duration_ns=self.config.segment_duration_ns,
        )

        # VAD audio segmenter (spec 023-vad-audio-segmentation)
        self._vad_config = SegmentationConfig()
        self._vad_segmenter: VADAudioSegmenter | None = None
        self._audio_batch_number = 0

        if self.config.enable_vad:
            self._vad_segmenter = VADAudioSegmenter(
                config=self._vad_config,
                on_segment_ready=self._on_vad_segment_ready,
            )
            logger.info(
                f"VAD audio segmentation enabled: "
                f"silence_threshold={self._vad_config.silence_threshold_db}dB, "
                f"min_duration={self._vad_config.min_segment_duration_s}s, "
                f"max_duration={self._vad_config.max_segment_duration_s}s"
            )

        # Segment writers
        self.video_writer = VideoSegmentWriter(self.config.segment_dir)
        self.audio_writer = AudioSegmentWriter(self.config.segment_dir)

        # STS components
        self.sts_client = StsSocketIOClient(
            server_url=self.config.sts_url,
            namespace="/",  # Use default namespace
        )
        self.fragment_tracker = FragmentTracker(max_inflight=3)
        self.backpressure_handler = BackpressureHandler()
        self.circuit_breaker = StsCircuitBreaker()

        # A/V sync
        self.av_sync = AvSyncManager()

        # Pipelines (initialized later)
        self.input_pipeline: InputPipeline | None = None
        self.output_pipeline: OutputPipeline | None = None

        # Pending segments for processing
        self._video_queue: asyncio.Queue[tuple[VideoSegment, bytes]] = asyncio.Queue()
        self._audio_queue: asyncio.Queue[tuple[AudioSegment, bytes]] = asyncio.Queue()
        self._output_queue: asyncio.Queue[SyncPair] = asyncio.Queue()

        # Output buffer for smooth playback
        # Accumulates segments before starting output to prevent player stutter
        self._output_buffer: deque[SyncPair] = deque()
        self._output_buffer_primed = False

    async def start(self) -> None:
        """Start the worker pipeline.

        Initializes all components and starts processing loop.
        """
        if self._running:
            logger.warning("Worker already running")
            return

        logger.info(f"Starting worker for stream: {self.config.stream_id}")

        try:
            # Connect to STS Service (skip if SKIP_STS_CONNECTION is set for integration tests)
            self._skip_sts = os.getenv("SKIP_STS_CONNECTION", "false").lower() == "true"
            if self._skip_sts:
                logger.warning(
                    "Skipping STS connection (SKIP_STS_CONNECTION=true) - "
                    "audio will pass through unchanged (fallback mode)"
                )
            else:
                await self._connect_sts()

            # Build and start pipelines
            self._build_pipelines()

            # Start processing tasks
            self._running = True
            self._task = asyncio.create_task(self._run_loop())

            self.metrics.set_pipeline_state("input", 1)
            self.metrics.set_pipeline_state("output", 1)

            logger.info("Worker started successfully")

        except Exception as e:
            logger.error(f"Failed to start worker: {e}")
            self.metrics.record_error("startup_failure")
            raise

    async def _connect_sts(self) -> None:
        """Connect to STS Service and initialize stream."""
        await self.sts_client.connect()

        # Set up callbacks
        self.sts_client.set_fragment_processed_callback(self._on_fragment_processed)
        self.sts_client.set_backpressure_callback(self._on_backpressure)
        self.sts_client.set_error_callback(self._on_sts_error)

        # Initialize stream
        stream_config = StreamConfig(
            source_language=self.config.source_language,
            target_language=self.config.target_language,
            voice_profile=self.config.voice_profile,
        )

        await self.sts_client.init_stream(
            stream_id=self.config.stream_id,
            config=stream_config,
        )

    def _build_pipelines(self) -> None:
        """Build input and output GStreamer pipelines."""
        # Input pipeline - uses RTMP to pull stream from MediaMTX
        # If VAD enabled, include level callback for RMS measurement
        level_callback = None
        level_interval_ns = 100_000_000  # 100ms default

        if self.config.enable_vad and self._vad_segmenter is not None:
            level_callback = self._on_level_message
            level_interval_ns = self._vad_config.level_interval_ns

        self.input_pipeline = InputPipeline(
            rtmp_url=self.config.rtmp_input_url,
            on_video_buffer=self._on_video_buffer,
            on_audio_buffer=self._on_audio_buffer,
            on_level_message=level_callback,
            level_interval_ns=level_interval_ns,
        )
        self.input_pipeline.build()
        self.input_pipeline.start()

        # Output pipeline - uses RTMP to publish dubbed stream
        self.output_pipeline = OutputPipeline(
            rtmp_url=self.config.rtmp_url,
        )
        self.output_pipeline.build()
        self.output_pipeline.start()

    def _on_video_buffer(
        self,
        data: bytes,
        pts_ns: int,
        duration_ns: int,
    ) -> None:
        """Handle video buffer from input pipeline.

        Accumulates data and emits segments when ready.
        """
        segment, segment_data = self.segment_buffer.push_video(data, pts_ns, duration_ns)

        if segment is not None:
            # Thread-safe queue operation
            try:
                self._video_queue.put_nowait((segment, segment_data))
                logger.debug(f"Video segment queued: batch={segment.batch_number}")
            except asyncio.QueueFull:
                logger.warning(f"Video queue full, dropping segment {segment.batch_number}")

    def _on_audio_buffer(
        self,
        data: bytes,
        pts_ns: int,
        duration_ns: int,
    ) -> None:
        """Handle audio buffer from input pipeline.

        Routes audio to VAD segmenter if enabled, otherwise uses fixed segmentation.

        Note: Duration should be calculated in input pipeline from caps.
        This is a final fallback if duration is still missing.
        """
        if duration_ns == 0:
            logger.warning(
                f"Audio buffer received with duration_ns=0 (size={len(data)}). "
                "This should be calculated from caps in input pipeline."
            )

        # Log audio buffer info periodically (every 50 buffers ~ every few seconds)
        self._audio_buffer_count = getattr(self, '_audio_buffer_count', 0) + 1
        if self._audio_buffer_count % 50 == 1:
            logger.info(
                f"🔊 Audio buffer #{self._audio_buffer_count}: size={len(data)} bytes, "
                f"pts={pts_ns / 1e9:.2f}s, duration={duration_ns / 1e6:.0f}ms"
            )

        logger.debug(f"Audio buffer: size={len(data)}, pts_ns={pts_ns}, duration_ns={duration_ns}")

        # Route to VAD segmenter if enabled
        if self._vad_segmenter is not None:
            # VAD segmenter handles accumulation and emits segments via callback
            self._vad_segmenter.on_audio_buffer(data, pts_ns, duration_ns)

            # Update VAD metrics
            self.metrics.set_vad_accumulator_state(
                self._vad_segmenter.accumulated_duration_ns,
                self._vad_segmenter.accumulated_bytes,
            )
            return

        # Fall through to fixed segmentation if VAD not enabled
        segment, segment_data = self.segment_buffer.push_audio(data, pts_ns, duration_ns)

        if segment is not None:
            # Thread-safe queue operation
            try:
                self._audio_queue.put_nowait((segment, segment_data))
                logger.info(f"Audio segment queued: batch={segment.batch_number}")
            except asyncio.QueueFull:
                logger.warning(f"Audio queue full, dropping segment {segment.batch_number}")

    def _on_level_message(self, rms_db: float, timestamp_ns: int) -> None:
        """Handle level element message from input pipeline.

        Routes RMS data to VAD segmenter for silence detection.

        Args:
            rms_db: Peak RMS across all channels in dB
            timestamp_ns: Running time in nanoseconds
        """
        if self._vad_segmenter is not None:
            try:
                self._vad_segmenter.on_level_message(rms_db, timestamp_ns)
            except RuntimeError as e:
                # VAD fatal error (e.g., 10+ invalid RMS values)
                logger.error(f"VAD fatal error: {e}")
                self.metrics.record_error("vad_fatal")

    def _on_vad_segment_ready(
        self,
        data: bytes,
        t0_ns: int,
        duration_ns: int,
        trigger: str,
    ) -> None:
        """Handle segment emission from VAD segmenter.

        Creates AudioSegment and queues for processing.

        Args:
            data: Accumulated audio data
            t0_ns: Segment start timestamp
            duration_ns: Segment duration
            trigger: Emission trigger type ("silence", "max_duration", "memory_limit", "eos")
        """
        # Create AudioSegment
        segment = AudioSegment.create(
            stream_id=self.config.stream_id,
            batch_number=self._audio_batch_number,
            t0_ns=t0_ns,
            duration_ns=duration_ns,
            segment_dir=self.config.segment_dir,
        )

        logger.info(
            f"VAD audio segment ready: batch={self._audio_batch_number}, "
            f"duration={duration_ns / 1e9:.2f}s, size={len(data)} bytes, trigger={trigger}"
        )

        self._audio_batch_number += 1

        # Record VAD metrics based on trigger type
        self.metrics.record_vad_segment_duration(duration_ns / 1e9)

        if trigger == "silence":
            self.metrics.record_vad_silence_detection()
        elif trigger == "max_duration":
            self.metrics.record_vad_forced_emission()
        elif trigger == "memory_limit":
            self.metrics.record_vad_memory_limit_emission()
        # Note: "eos" trigger doesn't have a separate counter

        # Thread-safe queue operation
        try:
            self._audio_queue.put_nowait((segment, data))
        except asyncio.QueueFull:
            logger.warning(f"Audio queue full, dropping VAD segment {segment.batch_number}")

    async def _process_video_segment(
        self,
        segment: VideoSegment,
        data: bytes,
    ) -> None:
        """Process video segment.

        T033: Skip MP4 file writing - use in-memory data directly for output.
        Video data flows: input pipeline -> segment buffer -> A/V sync -> output pipeline
        No disk I/O needed in this path.
        """
        try:
            # T033: Skip writing to disk - we use in-memory data for output
            # Just update segment metadata with data size for metrics
            segment.file_size = len(data)

            self.metrics.record_segment_processed("video", len(data))

            # Push to A/V sync with in-memory data
            pair = await self.av_sync.push_video(segment, data)
            if pair:
                await self._output_pair(pair)

        except Exception as e:
            logger.error(f"Error processing video segment: {e}")
            self.metrics.record_error("video_processing")

    async def _process_audio_segment(
        self,
        segment: AudioSegment,
        data: bytes,
    ) -> None:
        """Process audio segment.

        Writes to disk and sends to STS for dubbing (or uses fallback if STS is skipped).
        """
        try:
            # Write original segment to disk
            segment = await self.audio_writer.write(segment, data)

            self.metrics.record_segment_processed("audio", segment.file_size)

            # If STS is skipped, use fallback (passthrough) mode
            if self._skip_sts:
                logger.info(
                    f"Using passthrough for audio segment {segment.batch_number} (STS skipped)"
                )
                await self._use_fallback(segment)
                return

            # Send to STS (with circuit breaker protection)
            await self._send_to_sts(segment)

        except Exception as e:
            logger.error(f"Error processing audio segment: {e}")
            self.metrics.record_error("audio_processing")

    async def _send_to_sts(self, segment: AudioSegment) -> None:
        """Send audio segment to STS Service.

        Uses circuit breaker for fault tolerance.
        """
        # Wait for backpressure
        if not await self.backpressure_handler.wait_and_delay():
            logger.warning("Backpressure timeout, using fallback")
            await self._use_fallback(segment)
            return

        # Check circuit breaker
        fragment_id = await self.circuit_breaker.execute_with_fallback(
            segment=segment,
            send_func=self._do_send_fragment,
        )

        if fragment_id is None:
            # Fallback used (circuit open)
            await self._use_fallback(segment)
            self.metrics.record_circuit_breaker_fallback()

    async def _do_send_fragment(self, segment: AudioSegment) -> str:
        """Actually send fragment to STS.

        Args:
            segment: AudioSegment to send

        Returns:
            fragment_id
        """
        # Track fragment
        await self.fragment_tracker.track(segment)

        # Send to STS
        fragment_id = await self.sts_client.send_fragment(segment)

        logger.info(
            f"📤 AUDIO SENT TO STS: batch={segment.batch_number}, "
            f"pts={segment.t0_ns / 1e9:.2f}-{(segment.t0_ns + segment.duration_ns) / 1e9:.2f}s, "
            f"fragment_id={fragment_id}"
        )

        self.metrics.record_sts_fragment_sent()
        self.metrics.set_sts_inflight(self.fragment_tracker.inflight_count)

        return fragment_id

    async def _use_fallback(self, segment: AudioSegment) -> None:
        """Use original audio as fallback.

        Args:
            segment: AudioSegment with original audio
        """
        logger.info(f"Using fallback for segment {segment.batch_number}")

        # Read original audio
        audio_data = segment.get_m4a_data()

        # Push to A/V sync
        pair = await self.av_sync.push_audio(segment, audio_data)
        if pair:
            await self._output_pair(pair)

    async def _on_fragment_processed(
        self,
        payload: FragmentProcessedPayload,
    ) -> None:
        """Handle fragment:processed event from STS.

        Args:
            payload: Processing result
        """
        # Complete tracking
        inflight = await self.fragment_tracker.complete(payload.fragment_id)

        if inflight is None:
            logger.warning(f"Unknown fragment processed: {payload.fragment_id}")
            return

        # Update circuit breaker (result used for potential future logging)
        self.circuit_breaker.handle_response(payload)

        # Record metrics
        latency_seconds = inflight.elapsed_ms / 1000.0
        self.metrics.record_sts_fragment_processed(payload.status, latency_seconds)
        self.metrics.set_sts_inflight(self.fragment_tracker.inflight_count)
        self.metrics.set_circuit_breaker_state(self.circuit_breaker.state_value)

        if (payload.is_success or payload.is_partial) and payload.dubbed_audio:
            # Write dubbed audio
            dubbed_data = payload.dubbed_audio.decode_audio()
            segment = inflight.segment
            logger.info(
                f"📥 DUBBED AUDIO RECEIVED: batch={segment.batch_number}, "
                f"pts={segment.t0_ns / 1e9:.2f}-{(segment.t0_ns + segment.duration_ns) / 1e9:.2f}s, "
                f"size={len(dubbed_data)} bytes, fragment_id={payload.fragment_id}"
            )
            segment = await self.audio_writer.write_dubbed(segment, dubbed_data)

            # Push to A/V sync - returns list of pairs (one-to-many matching)
            pairs = await self.av_sync.push_audio(segment, dubbed_data)
            if pairs:
                logger.info(
                    f"🔗 AUDIO PAIRED WITH {len(pairs)} VIDEO(S): audio_batch={segment.batch_number}, "
                    f"audio_pts={segment.t0_ns / 1e9:.2f}-{(segment.t0_ns + segment.duration_ns) / 1e9:.2f}s"
                )
                for pair in pairs:
                    logger.info(
                        f"  → Video batch={pair.video_segment.batch_number}, "
                        f"pts={pair.video_segment.t0_ns / 1e9:.2f}-{(pair.video_segment.t0_ns + pair.video_segment.duration_ns) / 1e9:.2f}s"
                    )
                    await self._output_pair(pair)
            else:
                logger.info(
                    f"⏳ AUDIO WAITING FOR VIDEO: audio_batch={segment.batch_number}, "
                    f"pts={segment.t0_ns / 1e9:.2f}-{(segment.t0_ns + segment.duration_ns) / 1e9:.2f}s"
                )

        elif payload.is_failed:
            # Use fallback
            await self._use_fallback(inflight.segment)
            self.metrics.record_circuit_breaker_failure()

    async def _on_backpressure(self, payload: BackpressurePayload) -> None:
        """Handle backpressure event from STS.

        Args:
            payload: Backpressure info
        """
        await self.backpressure_handler.handle(payload)
        self.metrics.record_backpressure_event(payload.action)

    async def _on_sts_error(
        self,
        code: str,
        message: str,
        retryable: bool,
    ) -> None:
        """Handle error event from STS.

        Args:
            code: Error code
            message: Error message
            retryable: Whether error is retryable
        """
        logger.error(f"STS error: {code} - {message}")
        self.metrics.record_error(f"sts_{code.lower()}")

    async def _output_pair(self, pair: SyncPair) -> None:
        """Output synchronized video/audio pair with buffering for smooth playback.

        Buffers segments before starting output to ensure smooth playback.
        Once buffer is primed (has output_buffer_size segments), outputs FIFO.

        Args:
            pair: SyncPair to output (contains video_data and audio_data bytes)
        """
        if self.output_pipeline is None:
            logger.warning("⚠️ Output pipeline is None, skipping pair output")
            return

        # Add to output buffer
        self._output_buffer.append(pair)
        logger.info(
            f"📦 BUFFERED PAIR: batch={pair.video_segment.batch_number}, "
            f"pts={pair.pts_ns / 1e9:.2f}s, buffer_size={len(self._output_buffer)}"
        )

        # Check if buffer is primed
        if not self._output_buffer_primed:
            if len(self._output_buffer) >= self.config.output_buffer_size:
                self._output_buffer_primed = True
                logger.info(
                    f"🚀 OUTPUT BUFFER PRIMED: {len(self._output_buffer)} segments buffered, "
                    f"starting playback"
                )
            else:
                logger.info(
                    f"⏳ BUFFERING: {len(self._output_buffer)}/{self.config.output_buffer_size} "
                    f"segments before starting output"
                )
                return

        # Output the oldest segment from buffer (FIFO)
        pair_to_output = self._output_buffer.popleft()
        await self._do_output_pair(pair_to_output)

    async def _do_output_pair(self, pair: SyncPair) -> None:
        """Actually output a SyncPair to the output pipeline.

        Video is always output. Audio is only output if pair.output_audio is True
        (to prevent duplicate audio output when one audio covers multiple videos).

        Args:
            pair: SyncPair to output
        """
        logger.info(
            f"🎬 OUTPUTTING PAIR: video_batch={pair.video_segment.batch_number}, "
            f"video_pts={pair.video_pts_ns / 1e9:.2f}s, "
            f"audio_pts={pair.audio_pts_ns / 1e9:.2f}s, "
            f"output_audio={pair.output_audio}, "
            f"video_size={len(pair.video_data)}, audio_size={len(pair.audio_data)}, "
            f"buffer_remaining={len(self._output_buffer)}"
        )

        try:
            # Push video/audio data directly from SyncPair (no file I/O needed)
            # T033: Use in-memory buffers instead of push_segment_files()

            # Video is always output at video's PTS
            video_ok = self.output_pipeline.push_video(
                pair.video_data,
                pair.video_pts_ns,
                pair.video_segment.duration_ns,
            )

            # Audio is only output if output_audio flag is True
            # This prevents duplicate audio when one audio covers multiple videos
            audio_ok = True
            if pair.output_audio:
                # Prepare audio data for output
                audio_data = pair.audio_data
                if pair.audio_segment.is_dubbed:
                    # Dubbed audio comes from STS in M4A container format.
                    # Convert to raw ADTS AAC for the output pipeline's aacparse.
                    try:
                        audio_data = self.output_pipeline.convert_m4a_bytes_to_adts(audio_data)
                        logger.info(
                            f"🔊 Converted M4A to ADTS: {len(pair.audio_data)} -> {len(audio_data)} bytes"
                        )
                    except Exception as e:
                        logger.error(f"Failed to convert M4A to ADTS: {e}")
                        # Fall back to original audio data
                        audio_data = pair.audio_data
                # Original audio is already in raw AAC/ADTS format from input aacparse

                # Push audio at AUDIO's PTS (not video's PTS)
                audio_ok = self.output_pipeline.push_audio(
                    audio_data,
                    pair.audio_pts_ns,
                    pair.audio_segment.duration_ns,
                )
                logger.info(
                    f"🔊 AUDIO OUTPUT: pts={pair.audio_pts_ns / 1e9:.2f}s, "
                    f"duration={pair.audio_segment.duration_ns / 1e9:.2f}s"
                )
            else:
                logger.info(
                    f"⏭️ AUDIO SKIPPED (already output): audio_pts={pair.audio_pts_ns / 1e9:.2f}s"
                )

            logger.info(f"Push result: video_ok={video_ok}, audio_ok={audio_ok}")

            # Update metrics
            self.metrics.set_av_sync_delta(self.av_sync.sync_delta_ms)
            self.metrics.set_av_buffer_sizes(
                self.av_sync.video_buffer_size,
                self.av_sync.audio_buffer_size,
            )

            if self.av_sync.needs_correction:
                self.metrics.record_av_sync_correction()

        except Exception as e:
            logger.error(f"Error outputting sync pair: {e}", exc_info=True)
            self.metrics.record_error("output")

    async def _flush_output_buffer(self) -> None:
        """Flush all remaining segments from the output buffer.

        Called on stream end to ensure all buffered content is output.
        """
        if not self._output_buffer:
            logger.info("Output buffer empty, nothing to flush")
            return

        logger.info(f"🔄 FLUSHING OUTPUT BUFFER: {len(self._output_buffer)} segments remaining")

        while self._output_buffer:
            pair = self._output_buffer.popleft()
            await self._do_output_pair(pair)

        logger.info("Output buffer flushed")

    async def _run_loop(self) -> None:
        """Main processing loop."""
        logger.info("Worker run loop started")

        try:
            while self._running:
                # Process video segments from queue
                while not self._video_queue.empty():
                    try:
                        video_seg, video_data = self._video_queue.get_nowait()
                        await self._process_video_segment(video_seg, video_data)
                        self._video_queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                    except Exception as e:
                        logger.error(f"Error processing video segment: {e}")

                # Process audio segments from queue
                while not self._audio_queue.empty():
                    try:
                        audio_seg, audio_data = self._audio_queue.get_nowait()
                        await self._process_audio_segment(audio_seg, audio_data)
                        self._audio_queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                    except Exception as e:
                        logger.error(f"Error processing audio segment: {e}")

                # Update metrics periodically
                self.metrics.set_sts_inflight(self.fragment_tracker.inflight_count)
                self.metrics.set_circuit_breaker_state(self.circuit_breaker.state_value)

                # Check for ready pairs
                pairs = await self.av_sync.get_ready_pairs()
                for pair in pairs:
                    await self._output_pair(pair)

                await asyncio.sleep(0.05)  # 50ms tick for faster responsiveness

        except asyncio.CancelledError:
            logger.info("Worker run loop cancelled")
        except Exception as e:
            logger.error(f"Worker run loop error: {e}")
            self.metrics.record_error("run_loop")

    async def stop(self) -> None:
        """Stop the worker pipeline.

        Gracefully shuts down all components.
        """
        if not self._running:
            return

        logger.info("Stopping worker...")
        self._running = False

        # Cancel run loop
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Flush VAD segmenter to emit any remaining audio (EOS handling)
        if self._vad_segmenter is not None:
            logger.info("Flushing VAD segmenter on EOS")
            self._vad_segmenter.flush()

        # Flush output buffer to ensure all buffered segments are output
        await self._flush_output_buffer()

        # Stop pipelines
        if self.input_pipeline:
            self.input_pipeline.stop()
            self.metrics.set_pipeline_state("input", 0)

        if self.output_pipeline:
            self.output_pipeline.stop()
            self.metrics.set_pipeline_state("output", 0)

        # End STS stream
        await self.sts_client.end_stream()
        await self.sts_client.disconnect()

        # Clear fragment tracker
        await self.fragment_tracker.clear()

        logger.info("Worker stopped")

    async def cleanup(self) -> None:
        """Clean up all resources."""
        await self.stop()

        if self.input_pipeline:
            self.input_pipeline.cleanup()
            self.input_pipeline = None

        if self.output_pipeline:
            self.output_pipeline.cleanup()
            self.output_pipeline = None

        self.segment_buffer.reset()
        self.av_sync.reset()
        self.backpressure_handler.reset()
        self.circuit_breaker.reset()

        # Reset output buffer
        self._output_buffer.clear()
        self._output_buffer_primed = False

        logger.info("Worker cleaned up")

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
