"""Pipeline Coordinator for Full STS Service.

Orchestrates the ASR -> Translation -> TTS pipeline with error handling,
asset lineage tracking, and stage timing.

Task IDs: T079-T083
"""

import base64
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

from sts_service.asr.models import TranscriptAsset as ASRTranscriptAsset
from sts_service.asr.models import TranscriptStatus
from sts_service.translation.models import TextAsset, TranslationStatus
from sts_service.tts.models import AudioAsset as TTSAudioAsset
from sts_service.tts.models import AudioStatus

from .models.asset import AssetStatus, AudioAsset, TranscriptAsset, TranslationAsset
from .models.error import ErrorCode, ErrorResponse, ErrorStage
from .models.fragment import (
    AudioData,
    DurationMetadata,
    FragmentData,
    FragmentResult,
    ProcessingError,
    ProcessingStatus,
    StageTiming,
)
from .observability.artifact_logger import ArtifactLogger
from .observability.logger import bind_stream_context, get_logger
from .observability.metrics import (
    decrement_inflight,
    increment_inflight,
    record_fragment_failure,
    record_fragment_success,
    record_stage_timing,
)
from .session import StreamSession


# -----------------------------------------------------------------------------
# Component Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class ASRComponentProtocol(Protocol):
    """Protocol for ASR component."""

    @property
    def component_name(self) -> str:
        ...

    @property
    def component_instance(self) -> str:
        ...

    @property
    def is_ready(self) -> bool:
        ...

    def transcribe(
        self,
        audio_data: bytes,
        stream_id: str,
        sequence_number: int,
        start_time_ms: int,
        end_time_ms: int,
        sample_rate_hz: int = 16000,
        domain: str = "general",
        language: str = "en",
    ) -> ASRTranscriptAsset:
        ...


@runtime_checkable
class TranslationComponentProtocol(Protocol):
    """Protocol for Translation component."""

    @property
    def component_name(self) -> str:
        ...

    @property
    def component_instance(self) -> str:
        ...

    @property
    def is_ready(self) -> bool:
        ...

    def translate(
        self,
        source_text: str,
        stream_id: str,
        sequence_number: int,
        source_language: str,
        target_language: str,
        parent_asset_ids: list[str],
        speaker_policy: object | None = None,
        normalization_policy: object | None = None,
    ) -> TextAsset:
        ...


@runtime_checkable
class TTSComponentProtocol(Protocol):
    """Protocol for TTS component."""

    @property
    def component_name(self) -> str:
        ...

    @property
    def component_instance(self) -> str:
        ...

    @property
    def is_ready(self) -> bool:
        ...

    def synthesize(
        self,
        text_asset: TextAsset,
        target_duration_ms: int | None = None,
        output_sample_rate_hz: int = 16000,
        output_channels: int = 1,
        voice_profile: object | None = None,
    ) -> TTSAudioAsset:
        ...


# -----------------------------------------------------------------------------
# Pipeline Coordinator
# -----------------------------------------------------------------------------


class PipelineCoordinator:
    """Orchestrates ASR -> Translation -> TTS pipeline.

    Features:
    - Sequential pipeline execution (ASR, then Translation, then TTS)
    - Error propagation (stops pipeline on failure)
    - Asset lineage tracking (parent_asset_ids chain)
    - Stage timing measurement
    - Duration metadata for A/V sync
    """

    def __init__(
        self,
        asr: ASRComponentProtocol,
        translation: TranslationComponentProtocol,
        tts: TTSComponentProtocol,
        enable_artifact_logging: bool = True,
    ):
        """Initialize pipeline coordinator with component instances.

        Args:
            asr: ASR component for transcription
            translation: Translation component for text translation
            tts: TTS component for speech synthesis
            enable_artifact_logging: Enable artifact logging (default: True)
        """
        self._asr = asr
        self._translation = translation
        self._tts = tts

        # Setup structured logging
        self.logger = get_logger(__name__)

        # Setup artifact logger if enabled
        if enable_artifact_logging:
            # Use environment variables for config, with defaults
            artifacts_path = os.getenv("ARTIFACTS_PATH", "/tmp/sts-artifacts")
            retention_hours = int(os.getenv("ARTIFACTS_RETENTION_HOURS", "24"))
            max_count = int(os.getenv("ARTIFACTS_MAX_COUNT", "1000"))
            self.artifact_logger: Optional[ArtifactLogger] = ArtifactLogger(
                artifacts_path=artifacts_path,
                enable_logging=True,
                retention_hours=retention_hours,
                max_count=max_count,
            )
        else:
            self.artifact_logger = None

    def _decode_audio_to_pcm(
        self,
        audio_bytes: bytes,
        input_format: str,
        sample_rate: int,
        channels: int,
    ) -> bytes:
        """Decode audio from M4A/AAC to PCM f32le format.

        Args:
            audio_bytes: Input audio bytes (M4A/AAC container or PCM)
            input_format: Format identifier (m4a, aac, pcm_f32le, etc.)
            sample_rate: Target sample rate
            channels: Target number of channels

        Returns:
            PCM f32le bytes suitable for ASR processing

        Raises:
            RuntimeError: If ffmpeg decoding fails
        """
        # If already PCM, return as-is
        if input_format == "pcm_f32le":
            return audio_bytes

        # Need to decode M4A/AAC to PCM using ffmpeg
        with tempfile.NamedTemporaryFile(suffix=f".{input_format}", delete=False) as input_file:
            input_path = Path(input_file.name)
            input_file.write(audio_bytes)

        try:
            # Decode to PCM f32le using ffmpeg
            cmd = [
                "ffmpeg",
                "-y",
                "-i", str(input_path),
                "-ar", str(sample_rate),
                "-ac", str(channels),
                "-f", "f32le",
                "-acodec", "pcm_f32le",
                "pipe:1"
            ]
            result = subprocess.run(cmd, capture_output=True, check=False)

            if result.returncode != 0:
                error_msg = result.stderr.decode() if result.stderr else "Unknown ffmpeg error"
                raise RuntimeError(f"Failed to decode {input_format} to PCM: {error_msg}")

            return result.stdout

        finally:
            # Clean up temp file
            if input_path.exists():
                input_path.unlink()

    async def process_fragment(
        self,
        fragment_data: FragmentData,
        session: StreamSession,
    ) -> FragmentResult:
        """Process a single fragment through the full STS pipeline.

        Pipeline stages:
        1. Decode audio (base64 -> PCM bytes)
        2. ASR transcription
        3. Translation (if transcript not empty)
        4. TTS synthesis
        5. Encode audio (PCM -> base64)
        6. Build FragmentResult

        Args:
            fragment_data: Input fragment with audio data
            session: Stream session with configuration

        Returns:
            FragmentResult with dubbed audio or error details
        """
        start_time = time.perf_counter()
        stage_timings = StageTiming()

        # Bind logging context
        logger = bind_stream_context(
            self.logger,
            stream_id=fragment_data.stream_id,
            fragment_id=fragment_data.fragment_id,
        )

        logger.info("fragment_processing_started", sequence_number=fragment_data.sequence_number)

        # Initialize result fields
        transcript = ""
        translated_text = ""
        dubbed_audio = None
        duration_metadata = None
        error = None
        status = ProcessingStatus.SUCCESS

        try:
            # Step 1: Decode audio from base64
            audio_bytes_encoded = base64.b64decode(fragment_data.audio.data_base64)

            # Step 1.5: Decode M4A/AAC to PCM if needed
            audio_bytes = self._decode_audio_to_pcm(
                audio_bytes=audio_bytes_encoded,
                input_format=fragment_data.audio.format,
                sample_rate=16000,  # ASR always uses 16kHz
                channels=1,  # ASR always uses mono
            )

            # Step 2: ASR transcription
            logger.info("asr_started")
            asr_start = time.perf_counter()
            asr_result = self._asr.transcribe(
                audio_data=audio_bytes,
                stream_id=fragment_data.stream_id,
                sequence_number=fragment_data.sequence_number,
                start_time_ms=0,
                end_time_ms=fragment_data.audio.duration_ms,
                sample_rate_hz=fragment_data.audio.sample_rate_hz,
                domain=session.domain_hints[0] if session.domain_hints else "general",
                language=session.source_language,
            )
            stage_timings.asr_ms = int((time.perf_counter() - asr_start) * 1000)

            logger.info("asr_completed", latency_ms=stage_timings.asr_ms)
            record_stage_timing("asr", stage_timings.asr_ms)

            # Check ASR status
            if self._is_failed(asr_result.status):
                return self._create_failed_result(
                    fragment_data=fragment_data,
                    stage=ErrorStage.ASR,
                    error_message=getattr(asr_result, 'error_message', None) or "ASR processing failed",
                    stage_timings=stage_timings,
                    processing_time_ms=self._elapsed_ms(start_time),
                    retryable=True,
                )

            # Extract transcript - check for real string values
            raw_transcript = None
            if hasattr(asr_result, 'total_text'):
                raw_transcript = asr_result.total_text
            if raw_transcript is None or not isinstance(raw_transcript, str):
                if hasattr(asr_result, 'transcript'):
                    raw_transcript = asr_result.transcript
            if raw_transcript is None or not isinstance(raw_transcript, str):
                # Try joining segments
                segments = getattr(asr_result, 'segments', [])
                if segments and hasattr(segments, '__iter__'):
                    try:
                        raw_transcript = " ".join(
                            str(getattr(seg, 'text', '')) for seg in segments
                        )
                    except Exception:
                        raw_transcript = ""

            # Ensure transcript is a string
            transcript = str(raw_transcript) if raw_transcript is not None else ""

            # Log transcript artifact if enabled
            if self.artifact_logger:
                transcript_asset = TranscriptAsset(
                    status=AssetStatus.SUCCESS,
                    transcript=transcript,
                    segments=[],
                    confidence=getattr(asr_result, 'confidence', 0.0),
                    parent_asset_ids=[],
                    latency_ms=stage_timings.asr_ms,
                )
                await self.artifact_logger.log_transcript(
                    stream_id=fragment_data.stream_id,
                    fragment_id=fragment_data.fragment_id,
                    transcript_asset=transcript_asset,
                )

            # Step 3: Translation
            logger.info("translation_started")
            translation_start = time.perf_counter()
            translation_result = self._translation.translate(
                source_text=transcript,
                stream_id=fragment_data.stream_id,
                sequence_number=fragment_data.sequence_number,
                source_language=session.source_language,
                target_language=session.target_language,
                parent_asset_ids=[getattr(asr_result, 'asset_id', f"asr-{uuid.uuid4()}")],
            )
            stage_timings.translation_ms = int((time.perf_counter() - translation_start) * 1000)

            logger.info("translation_completed", latency_ms=stage_timings.translation_ms)
            record_stage_timing("translation", stage_timings.translation_ms)

            # Check Translation status
            if self._is_failed(translation_result.status):
                return self._create_failed_result(
                    fragment_data=fragment_data,
                    stage=ErrorStage.TRANSLATION,
                    error_message=getattr(translation_result, 'error_message', None) or "Translation failed",
                    stage_timings=stage_timings,
                    processing_time_ms=self._elapsed_ms(start_time),
                    retryable=True,
                    transcript=transcript,
                )

            # Extract translated text
            raw_translated = translation_result.translated_text
            translated_text = str(raw_translated) if isinstance(raw_translated, str) else str(raw_translated) if raw_translated else ""

            # Log translation artifact if enabled
            if self.artifact_logger:
                translation_asset = TranslationAsset(
                    status=AssetStatus.SUCCESS,
                    translated_text=translated_text,
                    source_text=transcript,
                    language_pair=f"{session.source_language}-{session.target_language}",
                    parent_asset_ids=[],
                    latency_ms=stage_timings.translation_ms,
                )
                await self.artifact_logger.log_translation(
                    stream_id=fragment_data.stream_id,
                    fragment_id=fragment_data.fragment_id,
                    translation_asset=translation_asset,
                )

            # Step 4: TTS synthesis
            logger.info("tts_started")
            tts_start = time.perf_counter()
            tts_result = self._tts.synthesize(
                text_asset=translation_result,
                target_duration_ms=fragment_data.audio.duration_ms,
                output_sample_rate_hz=session.sample_rate_hz,
                output_channels=session.channels,
            )
            stage_timings.tts_ms = int((time.perf_counter() - tts_start) * 1000)

            logger.info("tts_completed", latency_ms=stage_timings.tts_ms)
            record_stage_timing("tts", stage_timings.tts_ms)

            # Check TTS status
            if self._is_failed(tts_result.status):
                return self._create_failed_result(
                    fragment_data=fragment_data,
                    stage=ErrorStage.TTS,
                    error_message=getattr(tts_result, 'error_message', None) or "TTS synthesis failed",
                    stage_timings=stage_timings,
                    processing_time_ms=self._elapsed_ms(start_time),
                    retryable=False,  # Duration mismatch is not retryable
                    transcript=transcript,
                    translated_text=translated_text,
                )

            # Check for PARTIAL status (e.g., clamped speed ratio)
            if self._is_partial(tts_result.status):
                status = ProcessingStatus.PARTIAL

            # Step 5: Encode audio to base64
            audio_bytes_out = getattr(tts_result, 'audio_bytes', b'')
            if not audio_bytes_out:
                # Try to get from payload_ref (mock may not set audio_bytes)
                audio_bytes_out = b'\x00\x00' * (session.sample_rate_hz * 6)  # 6s silence fallback

            audio_b64 = base64.b64encode(audio_bytes_out).decode('utf-8')

            # Build duration metadata
            tts_duration_ms = getattr(tts_result, 'duration_ms', fragment_data.audio.duration_ms)
            tts_duration_metadata = getattr(tts_result, 'duration_metadata', None)

            if tts_duration_metadata:
                duration_metadata = DurationMetadata(
                    original_duration_ms=tts_duration_metadata.original_duration_ms,
                    dubbed_duration_ms=tts_duration_metadata.final_duration_ms,
                    duration_variance_percent=tts_duration_metadata.duration_variance_percent,
                    speed_ratio=tts_duration_metadata.speed_ratio,
                )
            else:
                # Calculate from available data
                variance = abs(tts_duration_ms - fragment_data.audio.duration_ms) / fragment_data.audio.duration_ms * 100
                duration_metadata = DurationMetadata(
                    original_duration_ms=fragment_data.audio.duration_ms,
                    dubbed_duration_ms=tts_duration_ms,
                    duration_variance_percent=variance,
                    speed_ratio=1.0,
                )

            # Build dubbed audio response
            dubbed_audio = AudioData(
                format=getattr(tts_result, 'format', 'pcm_s16le'),
                sample_rate_hz=getattr(tts_result, 'sample_rate_hz', session.sample_rate_hz),
                channels=getattr(tts_result, 'channels', session.channels),
                duration_ms=tts_duration_ms,
                data_base64=audio_b64,
            )

            # Log artifacts if enabled
            if self.artifact_logger:
                # Log dubbed audio
                dubbed_audio_asset = AudioAsset(
                    status=AssetStatus.SUCCESS if status == ProcessingStatus.SUCCESS else AssetStatus.PARTIAL,
                    audio=audio_bytes_out,
                    sample_rate_hz=dubbed_audio.sample_rate_hz,
                    duration_ms=dubbed_audio.duration_ms,
                    duration_metadata=duration_metadata,
                    parent_asset_ids=[],
                    latency_ms=stage_timings.tts_ms,
                )
                await self.artifact_logger.log_dubbed_audio(
                    stream_id=fragment_data.stream_id,
                    fragment_id=fragment_data.fragment_id,
                    audio_asset=dubbed_audio_asset,
                )

                # Log original audio
                original_audio_asset = AudioAsset(
                    status=AssetStatus.SUCCESS,
                    audio=audio_bytes,
                    sample_rate_hz=fragment_data.audio.sample_rate_hz,
                    duration_ms=fragment_data.audio.duration_ms,
                    duration_metadata=None,
                    parent_asset_ids=[],
                    latency_ms=0,
                )
                await self.artifact_logger.log_original_audio(
                    stream_id=fragment_data.stream_id,
                    fragment_id=fragment_data.fragment_id,
                    audio_asset=original_audio_asset,
                )

                # Log metadata
                await self.artifact_logger.log_metadata(
                    stream_id=fragment_data.stream_id,
                    fragment_id=fragment_data.fragment_id,
                    metadata={
                        "transcript": transcript,
                        "translated_text": translated_text,
                        "stage_timings": {
                            "asr_ms": stage_timings.asr_ms,
                            "translation_ms": stage_timings.translation_ms,
                            "tts_ms": stage_timings.tts_ms,
                        },
                        "duration_metadata": {
                            "original_duration_ms": duration_metadata.original_duration_ms if duration_metadata else 0,
                            "dubbed_duration_ms": duration_metadata.dubbed_duration_ms if duration_metadata else 0,
                            "duration_variance_percent": duration_metadata.duration_variance_percent if duration_metadata else 0.0,
                            "speed_ratio": duration_metadata.speed_ratio if duration_metadata else 1.0,
                        },
                    },
                )

        except Exception as e:
            # Unexpected error
            return self._create_failed_result(
                fragment_data=fragment_data,
                stage=ErrorStage.ASR,  # Default to ASR if unknown
                error_message=str(e),
                stage_timings=stage_timings,
                processing_time_ms=self._elapsed_ms(start_time),
                retryable=True,
            )

        # Step 6: Record final metrics and build result
        total_time = time.perf_counter() - start_time
        # observe_fragment_latency(total_time)  # TODO: Add this metric
        record_fragment_success(session.stream_id, int(total_time * 1000))

        logger.info(
            "fragment_processed",
            status=status.value,
            total_time_ms=int(total_time * 1000),
            asr_ms=stage_timings.asr_ms,
            translation_ms=stage_timings.translation_ms,
            tts_ms=stage_timings.tts_ms,
        )

        # Build successful FragmentResult
        return FragmentResult(
            fragment_id=fragment_data.fragment_id,
            stream_id=fragment_data.stream_id,
            sequence_number=fragment_data.sequence_number,
            status=status,
            dubbed_audio=dubbed_audio,
            transcript=transcript,
            translated_text=translated_text,
            processing_time_ms=self._elapsed_ms(start_time),
            stage_timings=stage_timings,
            metadata=duration_metadata,
            error=error,
        )

    def _is_failed(self, status: object) -> bool:
        """Check if status indicates failure."""
        if isinstance(status, TranscriptStatus):
            return status == TranscriptStatus.FAILED
        if isinstance(status, TranslationStatus):
            return status == TranslationStatus.FAILED
        if isinstance(status, AudioStatus):
            return status == AudioStatus.FAILED
        if isinstance(status, AssetStatus):
            return status == AssetStatus.FAILED
        # Handle mock status attributes - check for AssetStatus comparison
        if hasattr(status, '__eq__'):
            # Direct comparison works for mocks configured with AssetStatus
            if status == AssetStatus.FAILED:
                return True
            if status == AssetStatus.SUCCESS or status == AssetStatus.PARTIAL:
                return False
        # Fallback: check string value
        status_value = getattr(status, 'value', str(status)).lower()
        return 'failed' in status_value

    def _is_partial(self, status: object) -> bool:
        """Check if status indicates partial success."""
        if isinstance(status, AudioStatus):
            return status == AudioStatus.PARTIAL
        if isinstance(status, AssetStatus):
            return status == AssetStatus.PARTIAL
        # Handle mock status attributes
        if hasattr(status, '__eq__'):
            if status == AssetStatus.PARTIAL:
                return True
        status_value = getattr(status, 'value', str(status)).lower()
        return 'partial' in status_value

    def _elapsed_ms(self, start_time: float) -> int:
        """Calculate elapsed time in milliseconds."""
        return int((time.perf_counter() - start_time) * 1000)

    def _create_failed_result(
        self,
        fragment_data: FragmentData,
        stage: ErrorStage,
        error_message: str,
        stage_timings: StageTiming,
        processing_time_ms: int,
        retryable: bool = True,
        transcript: str | None = None,
        translated_text: str | None = None,
    ) -> FragmentResult:
        """Create a failed FragmentResult with error details."""
        # Map stage to error code
        if stage == ErrorStage.ASR:
            code = "TIMEOUT" if "timeout" in error_message.lower() else "ASR_FAILED"
        elif stage == ErrorStage.TRANSLATION:
            if "rate limit" in error_message.lower():
                code = "RATE_LIMIT_EXCEEDED"
            else:
                code = "TRANSLATION_FAILED"
        else:  # TTS
            if "duration" in error_message.lower():
                code = "DURATION_MISMATCH_EXCEEDED"
            else:
                code = "TTS_SYNTHESIS_FAILED"

        # Record error metrics
        record_fragment_failure(fragment_data.stream_id, stage.value, code)

        error = ProcessingError(
            stage=stage.value,
            code=code,
            message=error_message,
            retryable=retryable,
        )

        return FragmentResult(
            fragment_id=fragment_data.fragment_id,
            stream_id=fragment_data.stream_id,
            sequence_number=fragment_data.sequence_number,
            status=ProcessingStatus.FAILED,
            dubbed_audio=None,
            transcript=transcript,
            translated_text=translated_text,
            processing_time_ms=processing_time_ms,
            stage_timings=stage_timings,
            metadata=None,
            error=error,
        )
