"""
STS (Speech-to-Speech) data models for Socket.IO communication.

Per spec 003 and spec 017 (WebSocket Audio Fragment Protocol), these models
define the data structures for real-time STS communication via Socket.IO.
"""

from __future__ import annotations

import asyncio
import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from media_service.models.segments import AudioSegment


@dataclass
class StreamConfig:
    """Configuration for STS stream processing.

    Sent as part of stream:init event to configure the STS session.

    Attributes:
        source_language: Language code of input audio (e.g., "en", "en-US").
        target_language: Language code for dubbing output (e.g., "es", "es-ES").
        voice_profile: TTS voice profile identifier.
        format: Audio format for transport (always "m4a").
        sample_rate_hz: Audio sample rate in Hz.
        channels: Number of audio channels (1=mono, 2=stereo).
        chunk_duration_ms: Segment duration in milliseconds.
    """

    source_language: str = "en"
    target_language: str = "zh"
    voice_profile: str = "default"
    format: str = "m4a"
    sample_rate_hz: int = 48000
    channels: int = 2
    chunk_duration_ms: int = 6000

    def to_dict(self) -> dict:
        """Convert to dictionary for Socket.IO payload."""
        return {
            "source_language": self.source_language,
            "target_language": self.target_language,
            "voice_profile": self.voice_profile,
            "format": self.format,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": self.channels,
            "chunk_duration_ms": self.chunk_duration_ms,
        }


@dataclass
class InFlightFragment:
    """Tracks a fragment that has been sent but not yet processed.

    Used by FragmentTracker to manage pending fragments and their timeouts.

    Attributes:
        fragment_id: Unique identifier for the fragment (UUID).
        segment: Reference to the original AudioSegment.
        sent_time: Monotonic time when fragment was sent.
        sequence_number: Socket.IO sequence number (0-based).
        timeout_task: Asyncio task for timeout handling.
    """

    fragment_id: str
    segment: AudioSegment
    sent_time: float
    sequence_number: int
    timeout_task: asyncio.Task | None = None

    @property
    def elapsed_ms(self) -> int:
        """Elapsed time since fragment was sent, in milliseconds."""
        return int((time.monotonic() - self.sent_time) * 1000)


@dataclass
class AudioData:
    """Audio data structure for Socket.IO fragment events.

    Used in both fragment:data (sending) and fragment:processed (receiving).

    Attributes:
        format: Audio format (always "m4a").
        sample_rate_hz: Sample rate in Hz.
        channels: Number of channels.
        duration_ms: Duration in milliseconds.
        data_base64: Base64-encoded audio data.
    """

    format: str
    sample_rate_hz: int
    channels: int
    duration_ms: int
    data_base64: str

    @classmethod
    def from_m4a_file(cls, file_path: Path, duration_ms: int) -> AudioData:
        """Create AudioData from an M4A file.

        Args:
            file_path: Path to M4A file.
            duration_ms: Duration in milliseconds.

        Returns:
            AudioData with base64-encoded file contents.
        """
        data = file_path.read_bytes()
        return cls(
            format="m4a",
            sample_rate_hz=48000,
            channels=2,
            duration_ms=duration_ms,
            data_base64=base64.b64encode(data).decode("utf-8"),
        )

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        duration_ms: int,
        sample_rate_hz: int = 48000,
        channels: int = 2,
    ) -> AudioData:
        """Create AudioData from raw bytes.

        Args:
            data: Raw audio data bytes.
            duration_ms: Duration in milliseconds.
            sample_rate_hz: Sample rate.
            channels: Number of channels.

        Returns:
            AudioData with base64-encoded data.
        """
        return cls(
            format="m4a",
            sample_rate_hz=sample_rate_hz,
            channels=channels,
            duration_ms=duration_ms,
            data_base64=base64.b64encode(data).decode("utf-8"),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for Socket.IO payload."""
        return {
            "format": self.format,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": self.channels,
            "duration_ms": self.duration_ms,
            "data_base64": self.data_base64,
        }

    def decode_audio(self) -> bytes:
        """Decode base64 audio data to bytes."""
        return base64.b64decode(self.data_base64)


@dataclass
class FragmentMetadata:
    """Metadata for fragment:data events.

    Optional metadata sent with audio fragments.

    Attributes:
        pts_ns: Presentation timestamp in nanoseconds.
        source_pts_ns: Original source PTS if different.
    """

    pts_ns: int
    source_pts_ns: int | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for Socket.IO payload."""
        result = {"pts_ns": self.pts_ns}
        if self.source_pts_ns is not None:
            result["source_pts_ns"] = self.source_pts_ns
        return result


@dataclass
class FragmentDataPayload:
    """Socket.IO fragment:data event payload.

    Sent when submitting an audio fragment for STS processing.

    Attributes:
        fragment_id: UUID from AudioSegment for correlation.
        stream_id: Stream identifier.
        sequence_number: 0-based monotonic sequence number.
        timestamp: Unix timestamp in milliseconds.
        audio: Audio data object.
        metadata: Optional metadata with PTS information.
    """

    fragment_id: str
    stream_id: str
    sequence_number: int
    timestamp: int
    audio: AudioData
    metadata: FragmentMetadata | None = None

    @classmethod
    def from_segment(
        cls,
        segment: AudioSegment,
        sequence_number: int,
    ) -> FragmentDataPayload:
        """Create FragmentDataPayload from an AudioSegment.

        Args:
            segment: AudioSegment with M4A file.
            sequence_number: Current sequence number.

        Returns:
            FragmentDataPayload ready for Socket.IO emit.
        """
        audio_data = segment.get_m4a_data()
        return cls(
            fragment_id=segment.fragment_id,
            stream_id=segment.stream_id,
            sequence_number=sequence_number,
            timestamp=int(time.time() * 1000),
            audio=AudioData.from_bytes(
                data=audio_data,
                duration_ms=segment.duration_ms,
            ),
            metadata=FragmentMetadata(pts_ns=segment.t0_ns),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for Socket.IO payload."""
        result = {
            "fragment_id": self.fragment_id,
            "stream_id": self.stream_id,
            "sequence_number": self.sequence_number,
            "timestamp": self.timestamp,
            "audio": self.audio.to_dict(),
        }
        if self.metadata:
            result["metadata"] = self.metadata.to_dict()
        return result


@dataclass
class StageTimings:
    """Processing stage timings from STS service.

    Attributes:
        asr_ms: ASR (Automatic Speech Recognition) time.
        translation_ms: Translation processing time.
        tts_ms: TTS (Text-to-Speech) time.
    """

    asr_ms: int = 0
    translation_ms: int = 0
    tts_ms: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> StageTimings:
        """Create from dictionary."""
        return cls(
            asr_ms=data.get("asr_ms", 0),
            translation_ms=data.get("translation_ms", 0),
            tts_ms=data.get("tts_ms", 0),
        )


@dataclass
class ProcessingError:
    """Error information from STS processing.

    Attributes:
        code: Error code (e.g., "TIMEOUT", "MODEL_ERROR").
        message: Human-readable error message.
        retryable: Whether the error is retryable.
    """

    code: str
    message: str
    retryable: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> ProcessingError:
        """Create from dictionary."""
        return cls(
            code=data.get("code", "UNKNOWN"),
            message=data.get("message", "Unknown error"),
            retryable=data.get("retryable", False),
        )


@dataclass
class FragmentProcessedPayload:
    """Socket.IO fragment:processed event payload.

    Received when STS processing completes.

    Attributes:
        fragment_id: Original fragment UUID for correlation.
        stream_id: Stream identifier.
        sequence_number: Original sequence number.
        status: Processing status ("success", "partial", "failed").
        dubbed_audio: Dubbed audio data (if success/partial).
        transcript: ASR transcript (optional).
        translated_text: Translation output (optional).
        processing_time_ms: Total server processing time.
        stage_timings: Breakdown of processing stages.
        error: Error information (if failed).
    """

    fragment_id: str
    stream_id: str
    sequence_number: int
    status: Literal["success", "partial", "failed"]
    dubbed_audio: AudioData | None = None
    transcript: str | None = None
    translated_text: str | None = None
    processing_time_ms: int = 0
    stage_timings: StageTimings | None = None
    error: ProcessingError | None = None

    @classmethod
    def from_dict(cls, data: dict) -> FragmentProcessedPayload:
        """Create from Socket.IO event data dictionary."""
        dubbed_audio = None
        if "dubbed_audio" in data and data["dubbed_audio"]:
            da = data["dubbed_audio"]
            dubbed_audio = AudioData(
                format=da.get("format", "m4a"),
                sample_rate_hz=da.get("sample_rate_hz", 48000),
                channels=da.get("channels", 2),
                duration_ms=da.get("duration_ms", 0),
                data_base64=da.get("data_base64", ""),
            )

        stage_timings = None
        if "stage_timings" in data and data["stage_timings"]:
            stage_timings = StageTimings.from_dict(data["stage_timings"])

        error = None
        if "error" in data and data["error"]:
            error = ProcessingError.from_dict(data["error"])

        return cls(
            fragment_id=data["fragment_id"],
            stream_id=data["stream_id"],
            sequence_number=data["sequence_number"],
            status=data["status"],
            dubbed_audio=dubbed_audio,
            transcript=data.get("transcript"),
            translated_text=data.get("translated_text"),
            processing_time_ms=data.get("processing_time_ms", 0),
            stage_timings=stage_timings,
            error=error,
        )

    @property
    def is_success(self) -> bool:
        """Check if processing was successful."""
        return self.status == "success" and self.dubbed_audio is not None

    @property
    def is_partial(self) -> bool:
        """Check if processing was partial (some audio available)."""
        return self.status == "partial"

    @property
    def is_failed(self) -> bool:
        """Check if processing failed."""
        return self.status == "failed"


@dataclass
class BackpressurePayload:
    """Socket.IO backpressure event payload.

    Received when STS service signals flow control.

    Attributes:
        stream_id: Stream identifier.
        severity: Severity level ("low", "medium", "high").
        current_inflight: Current number of in-flight fragments.
        queue_depth: Server queue depth.
        action: Recommended action ("slow_down", "pause", "none").
        recommended_delay_ms: Recommended delay for slow_down action.
    """

    stream_id: str
    severity: Literal["low", "medium", "high"]
    current_inflight: int
    queue_depth: int
    action: Literal["slow_down", "pause", "none"]
    recommended_delay_ms: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> BackpressurePayload:
        """Create from Socket.IO event data dictionary."""
        return cls(
            stream_id=data["stream_id"],
            severity=data.get("severity", "medium"),
            current_inflight=data.get("current_inflight", 0),
            queue_depth=data.get("queue_depth", 0),
            action=data.get("action", "none"),
            recommended_delay_ms=data.get("recommended_delay_ms", 0),
        )
