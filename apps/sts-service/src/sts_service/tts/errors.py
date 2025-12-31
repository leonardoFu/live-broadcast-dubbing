"""
TTS Error Types and Classification.

This module defines error types and classification logic for the TTS component.
Errors are classified as retryable or non-retryable to enable orchestrator-level
retry and fallback decisions.

Based on specs/008-tts-module/data-model.md.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TTSErrorType(str, Enum):
    """Classification of TTS errors for orchestration policies.

    Each error type has a default retryability that can be overridden
    in specific cases.
    """

    # Retryable errors (transient failures)
    MODEL_LOAD_FAILED = "model_load_failed"  # Model file unavailable or corrupt
    ALIGNMENT_FAILED = "alignment_failed"  # Time-stretch operation failed
    TIMEOUT = "timeout"  # Processing exceeded deadline
    UNKNOWN = "unknown"  # Unclassified failure (safe default: retryable)

    # Non-retryable errors (permanent failures)
    SYNTHESIS_FAILED = "synthesis_failed"  # Synthesis engine crashed/invalid output
    INVALID_INPUT = "invalid_input"  # Input validation failed (empty text, etc.)
    VOICE_SAMPLE_INVALID = "voice_sample_invalid"  # Voice cloning sample corrupt


# Default retryability mapping
_DEFAULT_RETRYABLE: dict[TTSErrorType, bool] = {
    TTSErrorType.MODEL_LOAD_FAILED: True,
    TTSErrorType.ALIGNMENT_FAILED: True,
    TTSErrorType.TIMEOUT: True,
    TTSErrorType.UNKNOWN: True,  # Safe default: retry unknown errors
    TTSErrorType.SYNTHESIS_FAILED: False,
    TTSErrorType.INVALID_INPUT: False,
    TTSErrorType.VOICE_SAMPLE_INVALID: False,
}


class TTSError(BaseModel):
    """Structured error information for failed or partial synthesis.

    Enables retry and fallback decisions by the orchestrator.
    """

    error_type: TTSErrorType = Field(..., description="Error classification")
    message: str = Field(
        ..., min_length=1, description="Human-readable error message (safe for logs)"
    )
    retryable: bool = Field(..., description="Whether this error warrants a retry")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional error context (debug info)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "error_type": "model_load_failed",
                "message": "Failed to load XTTS-v2 model for language 'es': File not found",
                "retryable": True,
                "details": {
                    "model_path": "/models/xtts_v2_es",
                    "exception": "FileNotFoundError",
                },
            }
        }
    }


def classify_error(
    error_type: TTSErrorType,
    message: str,
    details: dict[str, Any] | None = None,
    retryable_override: bool | None = None,
) -> TTSError:
    """Create a TTSError with proper classification.

    Uses default retryability for the error type unless explicitly overridden.

    Args:
        error_type: The type of error that occurred
        message: Human-readable error message (must be non-empty)
        details: Optional additional context (stack traces, config values, etc.)
        retryable_override: Optional override for default retryability

    Returns:
        TTSError with proper classification

    Raises:
        ValueError: If message is empty
    """
    if not message or not message.strip():
        raise ValueError("Error message must be non-empty")

    retryable = (
        retryable_override
        if retryable_override is not None
        else _DEFAULT_RETRYABLE.get(error_type, True)
    )

    return TTSError(
        error_type=error_type,
        message=message,
        retryable=retryable,
        details=details,
    )


def is_retryable_error_type(error_type: TTSErrorType) -> bool:
    """Check if an error type is retryable by default.

    Args:
        error_type: The error type to check

    Returns:
        True if the error type is retryable by default
    """
    return _DEFAULT_RETRYABLE.get(error_type, True)
