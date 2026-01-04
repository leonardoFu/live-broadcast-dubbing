"""
Worker runner for stream dubbing pipeline orchestration.

Coordinates all components:
- Input pipeline (RTSP -> appsink)
- Segment buffer (accumulate to 6s segments)
- STS client (Socket.IO communication)
- A/V sync (pair video with dubbed audio)
- Output pipeline (appsrc -> RTMP)

Per spec 003:
- Full dubbing pipeline orchestration
- Lifecycle management (start/stop/cleanup)
- Error recovery with circuit breaker
- Metrics integration
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from media_service.audio.segment_writer import AudioSegmentWriter
from media_service.buffer.segment_buffer import SegmentBuffer
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
        segment_duration_ns: Segment duration in nanoseconds
    """

    stream_id: str
    rtmp_input_url: str  # Changed from rtsp_url per spec 020-rtmp-stream-pull
    rtmp_url: str
    sts_url: str
    segment_dir: Path
    source_language: str = "en"
    target_language: str = "es"
    voice_profile: str = "default"
    segment_duration_ns: int = 6_000_000_000  # 6 seconds


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

        # Initialize components
        self._init_components()

    def _init_components(self) -> None:
        """Initialize all pipeline components."""

        # Segment buffer
        self.segment_buffer = SegmentBuffer(
            stream_id=self.config.stream_id,
            segment_dir=self.config.segment_dir,
            segment_duration_ns=self.config.segment_duration_ns,
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
            skip_sts = os.getenv("SKIP_STS_CONNECTION", "false").lower() == "true"
            if skip_sts:
                logger.warning(
                    "Skipping STS connection (SKIP_STS_CONNECTION=true) - "
                    "worker will not process audio segments"
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
        self.input_pipeline = InputPipeline(
            rtmp_url=self.config.rtmp_input_url,
            on_video_buffer=self._on_video_buffer,
            on_audio_buffer=self._on_audio_buffer,
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

        Accumulates data and emits segments when ready.

        Note: Duration should be calculated in input pipeline from caps.
        This is a final fallback if duration is still missing.
        """
        if duration_ns == 0:
            logger.warning(
                f"Audio buffer received with duration_ns=0 (size={len(data)}). "
                "This should be calculated from caps in input pipeline."
            )

        logger.debug(f"Audio buffer: size={len(data)}, pts_ns={pts_ns}, duration_ns={duration_ns}")
        segment, segment_data = self.segment_buffer.push_audio(data, pts_ns, duration_ns)

        if segment is not None:
            # Thread-safe queue operation
            try:
                self._audio_queue.put_nowait((segment, segment_data))
                logger.info(f"Audio segment queued: batch={segment.batch_number}")
            except asyncio.QueueFull:
                logger.warning(f"Audio queue full, dropping segment {segment.batch_number}")

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

        Writes to disk and sends to STS for dubbing.
        """
        try:
            # Write original segment to disk
            segment = await self.audio_writer.write(segment, data)

            self.metrics.record_segment_processed("audio", segment.file_size)

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

        if payload.is_success and payload.dubbed_audio:
            # Write dubbed audio
            dubbed_data = payload.dubbed_audio.decode_audio()
            segment = inflight.segment
            segment = await self.audio_writer.write_dubbed(segment, dubbed_data)

            # Push to A/V sync
            pair = await self.av_sync.push_audio(segment, dubbed_data)
            if pair:
                await self._output_pair(pair)

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
        """Output synchronized video/audio pair.

        Uses in-memory data directly from SyncPair instead of reading from files.
        This eliminates unnecessary disk I/O in the output path (T033 simplification).

        Args:
            pair: SyncPair to output (contains video_data and audio_data bytes)
        """
        if self.output_pipeline is None:
            logger.warning("⚠️ Output pipeline is None, skipping pair output")
            return

        logger.info(
            f"🎬 OUTPUTTING PAIR: batch={pair.video_segment.batch_number}, "
            f"pts={pair.pts_ns / 1e9:.2f}s, "
            f"video_size={len(pair.video_data)}, audio_size={len(pair.audio_data)}"
        )

        try:
            # Push video/audio data directly from SyncPair (no file I/O needed)
            # T033: Use in-memory buffers instead of push_segment_files()

            # Video is already in H.264 byte-stream format from input pipeline
            video_ok = self.output_pipeline.push_video(
                pair.video_data,
                pair.pts_ns,
                pair.video_segment.duration_ns,
            )

            # Audio is already in raw AAC format (from aacparse in input pipeline).
            # The segment writer saves raw AAC bytes to .m4a files (not proper container),
            # so the data is already in a format the output pipeline's aacparse can handle.
            # No conversion needed.
            audio_ok = self.output_pipeline.push_audio(
                pair.audio_data,
                pair.pts_ns,
                pair.audio_segment.duration_ns,
            )
            success = video_ok and audio_ok

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

        logger.info("Worker cleaned up")

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
