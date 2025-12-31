"""
Unit tests for TTS error classification.

Tests for TTSError, TTSErrorType, and error classification functions.
Following TDD: These tests MUST be written FIRST and MUST FAIL before implementation.

Coverage Target: 80% minimum.
"""

import pytest
from sts_service.tts.errors import (
    TTSError,
    TTSErrorType,
    classify_error,
    is_retryable_error_type,
)


class TestTTSErrorType:
    """Tests for TTSErrorType enum values."""

    def test_model_load_failed_classified_as_retryable(self):
        """Test MODEL_LOAD_FAILED is classified as retryable."""
        assert is_retryable_error_type(TTSErrorType.MODEL_LOAD_FAILED) is True

    def test_synthesis_failed_classified_as_non_retryable(self):
        """Test SYNTHESIS_FAILED is classified as non-retryable."""
        assert is_retryable_error_type(TTSErrorType.SYNTHESIS_FAILED) is False

    def test_invalid_input_classified_as_non_retryable(self):
        """Test INVALID_INPUT is classified as non-retryable."""
        assert is_retryable_error_type(TTSErrorType.INVALID_INPUT) is False

    def test_voice_sample_invalid_classified_as_non_retryable(self):
        """Test VOICE_SAMPLE_INVALID is classified as non-retryable."""
        assert is_retryable_error_type(TTSErrorType.VOICE_SAMPLE_INVALID) is False

    def test_alignment_failed_classified_as_retryable(self):
        """Test ALIGNMENT_FAILED is classified as retryable."""
        assert is_retryable_error_type(TTSErrorType.ALIGNMENT_FAILED) is True

    def test_timeout_classified_as_retryable(self):
        """Test TIMEOUT is classified as retryable."""
        assert is_retryable_error_type(TTSErrorType.TIMEOUT) is True

    def test_unknown_classified_as_retryable(self):
        """Test UNKNOWN is classified as retryable (safe default)."""
        assert is_retryable_error_type(TTSErrorType.UNKNOWN) is True


class TestTTSError:
    """Tests for TTSError model."""

    def test_tts_error_creation_with_required_fields(self):
        """Test TTSError creation with error_type, message, retryable."""
        error = TTSError(
            error_type=TTSErrorType.MODEL_LOAD_FAILED,
            message="Failed to load model",
            retryable=True,
        )

        assert error.error_type == TTSErrorType.MODEL_LOAD_FAILED
        assert error.message == "Failed to load model"
        assert error.retryable is True
        assert error.details is None

    def test_tts_error_includes_optional_details(self):
        """Test TTSError includes optional details dict."""
        details = {"model_path": "/models/test", "exception": "FileNotFoundError"}
        error = TTSError(
            error_type=TTSErrorType.MODEL_LOAD_FAILED,
            message="Model not found",
            retryable=True,
            details=details,
        )

        assert error.details is not None
        assert error.details["model_path"] == "/models/test"
        assert error.details["exception"] == "FileNotFoundError"

    def test_tts_error_message_is_non_empty(self):
        """Test message field must be non-empty."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TTSError(
                error_type=TTSErrorType.INVALID_INPUT,
                message="",  # Empty message
                retryable=False,
            )

    def test_tts_error_serialization(self):
        """Test TTSError JSON serialization."""
        error = TTSError(
            error_type=TTSErrorType.TIMEOUT,
            message="Processing exceeded 5000ms deadline",
            retryable=True,
            details={"elapsed_ms": 5234, "deadline_ms": 5000},
        )

        json_data = error.model_dump()
        assert json_data["error_type"] == "timeout"
        assert json_data["message"] == "Processing exceeded 5000ms deadline"
        assert json_data["retryable"] is True
        assert json_data["details"]["elapsed_ms"] == 5234


class TestClassifyError:
    """Tests for classify_error helper function."""

    def test_classify_error_uses_default_retryability(self):
        """Test classify_error uses default retryability for error type."""
        error = classify_error(
            TTSErrorType.MODEL_LOAD_FAILED,
            "Model not available",
        )
        # MODEL_LOAD_FAILED default is retryable=True
        assert error.retryable is True

        error = classify_error(
            TTSErrorType.INVALID_INPUT,
            "Empty text input",
        )
        # INVALID_INPUT default is retryable=False
        assert error.retryable is False

    def test_classify_error_with_details(self):
        """Test classify_error with optional details."""
        error = classify_error(
            TTSErrorType.TIMEOUT,
            "Processing timeout",
            details={"elapsed_ms": 6000},
        )
        assert error.details is not None
        assert error.details["elapsed_ms"] == 6000

    def test_classify_error_retryable_override(self):
        """Test classify_error with retryable override."""
        # Override retryable for normally non-retryable error
        error = classify_error(
            TTSErrorType.SYNTHESIS_FAILED,
            "Synthesis failed",
            retryable_override=True,  # Override default False
        )
        assert error.retryable is True

        # Override retryable for normally retryable error
        error = classify_error(
            TTSErrorType.MODEL_LOAD_FAILED,
            "Model permanently unavailable",
            retryable_override=False,  # Override default True
        )
        assert error.retryable is False

    def test_classify_error_empty_message_raises(self):
        """Test classify_error raises ValueError for empty message."""
        with pytest.raises(ValueError) as exc_info:
            classify_error(
                TTSErrorType.UNKNOWN,
                "",  # Empty message
            )
        assert "non-empty" in str(exc_info.value).lower()

    def test_classify_error_whitespace_message_raises(self):
        """Test classify_error raises ValueError for whitespace-only message."""
        with pytest.raises(ValueError):
            classify_error(
                TTSErrorType.UNKNOWN,
                "   ",  # Whitespace only
            )


class TestErrorTypeRetryability:
    """Complete mapping tests for error type retryability."""

    def test_all_error_types_have_retryability_defined(self):
        """Test all TTSErrorType values have retryability defined."""
        for error_type in TTSErrorType:
            # Should not raise - all types should be defined
            result = is_retryable_error_type(error_type)
            assert isinstance(result, bool)

    def test_retryable_errors_list(self):
        """Test known retryable error types."""
        retryable_types = [
            TTSErrorType.MODEL_LOAD_FAILED,
            TTSErrorType.ALIGNMENT_FAILED,
            TTSErrorType.TIMEOUT,
            TTSErrorType.UNKNOWN,
        ]
        for error_type in retryable_types:
            assert is_retryable_error_type(error_type) is True

    def test_non_retryable_errors_list(self):
        """Test known non-retryable error types."""
        non_retryable_types = [
            TTSErrorType.SYNTHESIS_FAILED,
            TTSErrorType.INVALID_INPUT,
            TTSErrorType.VOICE_SAMPLE_INVALID,
        ]
        for error_type in non_retryable_types:
            assert is_retryable_error_type(error_type) is False
