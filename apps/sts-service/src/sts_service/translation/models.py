"""
Pydantic data models for the Translation component.

Defines typed input/output contracts for text translation.
Based on specs/006-translation-component/data-model.md.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# Import AssetIdentifiers from ASR module for lineage tracking
from sts_service.asr.models import AssetIdentifiers

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class TranslationStatus(str, Enum):
    """Status of translation processing."""

    SUCCESS = "success"  # Translation completed successfully
    PARTIAL = "partial"  # Some processing completed, but with errors
    FAILED = "failed"  # Translation completely failed


class TranslationErrorType(str, Enum):
    """Classification of Translation errors for orchestration policies."""

    EMPTY_INPUT = "empty_input"  # Empty source text
    UNSUPPORTED_LANGUAGE_PAIR = "unsupported_language_pair"  # Language pair not supported
    PROVIDER_ERROR = "provider_error"  # Translation provider failure
    TIMEOUT = "timeout"  # Processing exceeded deadline
    NORMALIZATION_ERROR = "normalization_error"  # Preprocessing failure
    UNKNOWN = "unknown"  # Unclassified failure


# -----------------------------------------------------------------------------
# Error Model
# -----------------------------------------------------------------------------


class TranslationError(BaseModel):
    """Structured error information for failed or partial translations."""

    error_type: TranslationErrorType = Field(..., description="Error classification")
    message: str = Field(
        ..., description="Human-readable error message (safe for logs)"
    )
    retryable: bool = Field(..., description="Whether this error is worth retrying")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional error context (debug info)"
    )


# -----------------------------------------------------------------------------
# Policy Models
# -----------------------------------------------------------------------------


class SpeakerPolicy(BaseModel):
    """Controls speaker label detection and removal."""

    detect_and_remove: bool = Field(
        default=False,
        description="If True, detect and remove speaker labels from text",
    )
    allowed_patterns: list[str] = Field(
        default=["^[A-Z][a-z]+: ", "^>> [A-Z][a-z]+: "],
        description="Regex patterns for speaker label detection",
    )


class NormalizationPolicy(BaseModel):
    """Controls translation-oriented text normalization."""

    enabled: bool = Field(default=True, description="Enable normalization")
    normalize_time_phrases: bool = Field(
        default=True,
        description="Normalize time phrases (e.g., '1:54 REMAINING' -> '1:54 remaining')",
    )
    expand_abbreviations: bool = Field(
        default=True,
        description="Expand abbreviations (e.g., 'NFL' -> 'N F L')",
    )
    normalize_hyphens: bool = Field(
        default=True,
        description="Normalize hyphens (e.g., 'TEN-YARD' -> 'TEN YARD')",
    )
    normalize_symbols: bool = Field(
        default=True,
        description="Expand symbols (e.g., '&' -> 'and')",
    )
    tts_cleanup: bool = Field(
        default=False,
        description="Post-translation TTS-oriented cleanup",
    )


# -----------------------------------------------------------------------------
# Configuration Model
# -----------------------------------------------------------------------------


class TranslationConfig(BaseModel):
    """Configuration for Translation component."""

    # Supported language pairs (empty = all pairs allowed)
    supported_language_pairs: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Whitelist of allowed (source, target) pairs. Empty = all allowed.",
    )

    # Default policies
    default_speaker_policy: SpeakerPolicy = Field(default_factory=SpeakerPolicy)
    default_normalization_policy: NormalizationPolicy = Field(
        default_factory=NormalizationPolicy
    )

    # Fallback behavior
    fallback_to_source_on_error: bool = Field(
        default=False,
        description="If True, return source text as translation on failure",
    )

    # Timeout
    timeout_ms: int = Field(
        default=5000,
        ge=1000,
        description="Maximum processing time per fragment (ms)",
    )


# -----------------------------------------------------------------------------
# Output Model
# -----------------------------------------------------------------------------


class TextAsset(AssetIdentifiers):
    """Translated text asset with metadata and lineage.

    Produced by the Translation component per specs/004-sts-pipeline-design.md Section 6.3.
    """

    # Component identification
    component: str = Field(
        default="translate", description="Always 'translate' for this asset type"
    )
    component_instance: str = Field(
        ..., description="Provider identifier (e.g., 'mock-identity-v1')"
    )

    # Language metadata
    source_language: str = Field(..., description="Source language code (e.g., 'en')")
    target_language: str = Field(..., description="Target language code (e.g., 'es')")

    # Text content
    translated_text: str = Field(..., description="Final translated output")
    normalized_source_text: str | None = Field(
        default=None,
        description="Preprocessed source text before translation (for debugging)",
    )

    # Speaker handling
    speaker_id: str = Field(
        default="default",
        description="Speaker identifier extracted from text",
    )

    # Status and errors
    status: TranslationStatus = Field(..., description="Overall translation status")
    errors: list[TranslationError] = Field(
        default_factory=list,
        description="List of errors encountered during processing",
    )

    # Warnings (non-fatal issues)
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal issues (e.g., 'empty input after speaker removal')",
    )

    # Processing metadata
    processing_time_ms: int | None = Field(
        default=None,
        ge=0,
        description="Total processing time in milliseconds",
    )
    model_info: str | None = Field(
        default=None,
        description="Model identifier used (e.g., 'mock-identity-v1')",
    )

    @property
    def is_retryable(self) -> bool:
        """Whether this result should be retried."""
        return self.status == TranslationStatus.FAILED and any(
            e.retryable for e in self.errors
        )


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def validate_language_pair(
    source: str,
    target: str,
    supported_pairs: list[tuple[str, str]],
) -> bool:
    """Validate if language pair is supported.

    Returns True if supported_pairs is empty (all pairs allowed).

    Args:
        source: Source language code
        target: Target language code
        supported_pairs: List of allowed (source, target) pairs

    Returns:
        True if language pair is supported
    """
    if not supported_pairs:
        return True
    return (source, target) in supported_pairs
