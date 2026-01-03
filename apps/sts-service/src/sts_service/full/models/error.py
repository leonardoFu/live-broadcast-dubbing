"""Error handling models for Full STS Service.

Defines typed models for error responses per spec 021:
- ErrorResponse for Socket.IO error events
- ErrorCode enum for standardized error codes
- Error categorization by retryability

Matches contracts/error-schema.json.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorStage(str, Enum):
    """Pipeline stage where error occurred."""

    ASR = "asr"
    TRANSLATION = "translation"
    TTS = "tts"


class ErrorCode(str, Enum):
    """Standardized error codes from spec 021.

    Errors are categorized by type and retryability:
    - Stream errors: Configuration/session issues (not retryable)
    - Processing errors: Transient issues (retryable)
    - Pipeline errors: Stage-specific failures (varies)
    """

    # Stream errors (not retryable)
    STREAM_NOT_FOUND = "STREAM_NOT_FOUND"
    STREAM_PAUSED = "STREAM_PAUSED"
    INVALID_CONFIG = "INVALID_CONFIG"
    INVALID_VOICE_PROFILE = "INVALID_VOICE_PROFILE"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"

    # Processing errors (retryable)
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TRANSLATION_API_UNAVAILABLE = "TRANSLATION_API_UNAVAILABLE"
    BACKPRESSURE_EXCEEDED = "BACKPRESSURE_EXCEEDED"
    GPU_OOM = "GPU_OOM"

    # Pipeline errors (varies)
    ASR_FAILED = "ASR_FAILED"
    TRANSLATION_FAILED = "TRANSLATION_FAILED"
    TTS_SYNTHESIS_FAILED = "TTS_SYNTHESIS_FAILED"
    DURATION_MISMATCH_EXCEEDED = "DURATION_MISMATCH_EXCEEDED"
    INVALID_AUDIO_FORMAT = "INVALID_AUDIO_FORMAT"

    @property
    def is_retryable(self) -> bool:
        """Check if this error code is retryable."""
        return self in RETRYABLE_ERRORS

    @property
    def default_message(self) -> str:
        """Get default human-readable message for this error code."""
        return ERROR_MESSAGES.get(self, f"Error: {self.value}")


# Set of retryable error codes
RETRYABLE_ERRORS: set[ErrorCode] = {
    ErrorCode.TIMEOUT,
    ErrorCode.RATE_LIMIT_EXCEEDED,
    ErrorCode.TRANSLATION_API_UNAVAILABLE,
    ErrorCode.BACKPRESSURE_EXCEEDED,
    ErrorCode.GPU_OOM,
}

# Default messages for each error code
ERROR_MESSAGES: dict[ErrorCode, str] = {
    # Stream errors
    ErrorCode.STREAM_NOT_FOUND: "Stream not found in session store",
    ErrorCode.STREAM_PAUSED: "Stream is currently paused, new fragments rejected",
    ErrorCode.INVALID_CONFIG: "Invalid stream configuration",
    ErrorCode.INVALID_VOICE_PROFILE: "Voice profile not found in voices.json",
    ErrorCode.UNSUPPORTED_LANGUAGE: "Language pair not supported",
    # Processing errors
    ErrorCode.TIMEOUT: "Processing timed out",
    ErrorCode.RATE_LIMIT_EXCEEDED: "API rate limit exceeded",
    ErrorCode.TRANSLATION_API_UNAVAILABLE: "Translation API is unavailable",
    ErrorCode.BACKPRESSURE_EXCEEDED: "Critical backpressure threshold exceeded",
    ErrorCode.GPU_OOM: "GPU out of memory",
    # Pipeline errors
    ErrorCode.ASR_FAILED: "ASR processing failed",
    ErrorCode.TRANSLATION_FAILED: "Translation processing failed",
    ErrorCode.TTS_SYNTHESIS_FAILED: "TTS synthesis failed",
    ErrorCode.DURATION_MISMATCH_EXCEEDED: "Duration variance exceeds 20% threshold",
    ErrorCode.INVALID_AUDIO_FORMAT: "Invalid or unsupported audio format",
}


class ErrorResponse(BaseModel):
    """Error response payload.

    Matches spec 021 error-schema.json error_response definition.
    Used for Socket.IO error events and fragment processing errors.
    """

    code: str = Field(
        description="Error code identifier",
    )
    message: str = Field(
        min_length=1,
        description="Human-readable error description",
    )
    retryable: bool = Field(
        description="Whether the error is transient and retryable",
    )
    stage: ErrorStage | None = Field(
        default=None,
        description="Pipeline stage where error occurred (optional)",
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error details",
    )

    @classmethod
    def from_error_code(
        cls,
        code: ErrorCode,
        message: str | None = None,
        stage: ErrorStage | None = None,
        details: dict[str, Any] | None = None,
    ) -> "ErrorResponse":
        """Create error response from standardized error code.

        Args:
            code: ErrorCode enum value
            message: Optional custom message (defaults to code's default)
            stage: Optional pipeline stage
            details: Optional additional details

        Returns:
            ErrorResponse with appropriate fields set
        """
        return cls(
            code=code.value,
            message=message or code.default_message,
            retryable=code.is_retryable,
            stage=stage,
            details=details,
        )

    @classmethod
    def stream_not_found(cls, stream_id: str) -> "ErrorResponse":
        """Create STREAM_NOT_FOUND error."""
        return cls.from_error_code(
            ErrorCode.STREAM_NOT_FOUND,
            message=f"Stream {stream_id} not found",
        )

    @classmethod
    def stream_paused(cls, stream_id: str) -> "ErrorResponse":
        """Create STREAM_PAUSED error."""
        return cls.from_error_code(
            ErrorCode.STREAM_PAUSED,
            message=f"Stream {stream_id} is currently paused",
        )

    @classmethod
    def invalid_config(cls, reason: str) -> "ErrorResponse":
        """Create INVALID_CONFIG error."""
        return cls.from_error_code(
            ErrorCode.INVALID_CONFIG,
            message=f"Invalid configuration: {reason}",
        )

    @classmethod
    def invalid_voice_profile(cls, profile: str) -> "ErrorResponse":
        """Create INVALID_VOICE_PROFILE error."""
        return cls.from_error_code(
            ErrorCode.INVALID_VOICE_PROFILE,
            message=f"Voice profile '{profile}' not found in voices.json",
        )

    @classmethod
    def timeout(
        cls,
        stage: ErrorStage,
        timeout_ms: int,
    ) -> "ErrorResponse":
        """Create TIMEOUT error."""
        return cls.from_error_code(
            ErrorCode.TIMEOUT,
            message=f"{stage.value.upper()} processing timed out after {timeout_ms}ms",
            stage=stage,
            details={"timeout_ms": timeout_ms},
        )

    @classmethod
    def rate_limit_exceeded(
        cls,
        api_name: str,
        retry_after_seconds: int | None = None,
    ) -> "ErrorResponse":
        """Create RATE_LIMIT_EXCEEDED error."""
        message = f"{api_name} API rate limit exceeded"
        if retry_after_seconds:
            message += f". Retry after {retry_after_seconds}s."

        return cls.from_error_code(
            ErrorCode.RATE_LIMIT_EXCEEDED,
            message=message,
            stage=ErrorStage.TRANSLATION,
            details={"retry_after_seconds": retry_after_seconds} if retry_after_seconds else None,
        )

    @classmethod
    def backpressure_exceeded(
        cls,
        current_inflight: int,
        max_threshold: int,
    ) -> "ErrorResponse":
        """Create BACKPRESSURE_EXCEEDED error."""
        return cls.from_error_code(
            ErrorCode.BACKPRESSURE_EXCEEDED,
            message=f"In-flight count {current_inflight} exceeds critical threshold {max_threshold}",
            details={
                "current_inflight": current_inflight,
                "max_threshold": max_threshold,
            },
        )

    @classmethod
    def asr_failed(cls, reason: str) -> "ErrorResponse":
        """Create ASR_FAILED error."""
        return cls.from_error_code(
            ErrorCode.ASR_FAILED,
            message=f"ASR processing failed: {reason}",
            stage=ErrorStage.ASR,
        )

    @classmethod
    def translation_failed(cls, reason: str) -> "ErrorResponse":
        """Create TRANSLATION_FAILED error."""
        return cls.from_error_code(
            ErrorCode.TRANSLATION_FAILED,
            message=f"Translation failed: {reason}",
            stage=ErrorStage.TRANSLATION,
        )

    @classmethod
    def tts_failed(cls, reason: str) -> "ErrorResponse":
        """Create TTS_SYNTHESIS_FAILED error."""
        return cls.from_error_code(
            ErrorCode.TTS_SYNTHESIS_FAILED,
            message=f"TTS synthesis failed: {reason}",
            stage=ErrorStage.TTS,
        )

    @classmethod
    def duration_mismatch(
        cls,
        variance_percent: float,
        threshold: float = 20.0,
    ) -> "ErrorResponse":
        """Create DURATION_MISMATCH_EXCEEDED error."""
        return cls.from_error_code(
            ErrorCode.DURATION_MISMATCH_EXCEEDED,
            message=f"Duration variance {variance_percent:.1f}% exceeds {threshold}% threshold",
            stage=ErrorStage.TTS,
            details={
                "variance_percent": variance_percent,
                "threshold": threshold,
            },
        )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "STREAM_NOT_FOUND",
                "message": "Stream stream-abc-123 not found",
                "retryable": False,
            }
        }
    )
