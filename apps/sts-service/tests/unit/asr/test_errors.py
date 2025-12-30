"""
Unit tests for error classification.

TDD: These tests are written BEFORE implementation.
"""

import pytest


class TestClassifyError:
    """Tests for exception to ASRErrorType mapping."""

    def test_classify_error_memory_error(self):
        """Test MemoryError maps to MEMORY_ERROR."""
        from sts_service.asr.errors import classify_error
        from sts_service.asr.models import ASRErrorType

        result = classify_error(MemoryError("OOM"))

        assert result == ASRErrorType.MEMORY_ERROR

    def test_classify_error_timeout_error(self):
        """Test TimeoutError maps to TIMEOUT."""
        from sts_service.asr.errors import classify_error
        from sts_service.asr.models import ASRErrorType

        result = classify_error(TimeoutError("Deadline exceeded"))

        assert result == ASRErrorType.TIMEOUT

    def test_classify_error_file_not_found(self):
        """Test FileNotFoundError maps to MODEL_LOAD_ERROR."""
        from sts_service.asr.errors import classify_error
        from sts_service.asr.models import ASRErrorType

        result = classify_error(FileNotFoundError("Model not found"))

        assert result == ASRErrorType.MODEL_LOAD_ERROR

    def test_classify_error_value_error(self):
        """Test ValueError maps to INVALID_AUDIO."""
        from sts_service.asr.errors import classify_error
        from sts_service.asr.models import ASRErrorType

        result = classify_error(ValueError("Invalid audio format"))

        assert result == ASRErrorType.INVALID_AUDIO

    def test_classify_error_runtime_error(self):
        """Test RuntimeError maps to UNKNOWN."""
        from sts_service.asr.errors import classify_error
        from sts_service.asr.models import ASRErrorType

        result = classify_error(RuntimeError("Something went wrong"))

        assert result == ASRErrorType.UNKNOWN

    def test_classify_error_unknown(self):
        """Test generic Exception maps to UNKNOWN."""
        from sts_service.asr.errors import classify_error
        from sts_service.asr.models import ASRErrorType

        result = classify_error(Exception("Generic error"))

        assert result == ASRErrorType.UNKNOWN


class TestCreateASRError:
    """Tests for creating ASRError from exceptions."""

    def test_create_asr_error_from_exception(self):
        """Test creating ASRError from an exception."""
        from sts_service.asr.errors import create_asr_error
        from sts_service.asr.models import ASRErrorType

        error = create_asr_error(TimeoutError("Processing took too long"))

        assert error.error_type == ASRErrorType.TIMEOUT
        assert "too long" in error.message or "timeout" in error.message.lower()

    def test_asr_error_retryable_for_timeout(self):
        """Test that timeout errors are retryable."""
        from sts_service.asr.errors import create_asr_error

        error = create_asr_error(TimeoutError("timeout"))

        assert error.retryable is True

    def test_asr_error_not_retryable_for_invalid_audio(self):
        """Test that invalid audio errors are not retryable."""
        from sts_service.asr.errors import create_asr_error

        error = create_asr_error(ValueError("Invalid audio"))

        assert error.retryable is False

    def test_asr_error_retryable_for_memory(self):
        """Test that memory errors are retryable."""
        from sts_service.asr.errors import create_asr_error

        error = create_asr_error(MemoryError("OOM"))

        assert error.retryable is True


class TestIsRetryable:
    """Tests for retryable error classification."""

    def test_timeout_is_retryable(self):
        """Test TIMEOUT errors are retryable."""
        from sts_service.asr.errors import is_retryable
        from sts_service.asr.models import ASRErrorType

        assert is_retryable(ASRErrorType.TIMEOUT) is True

    def test_memory_error_is_retryable(self):
        """Test MEMORY_ERROR errors are retryable."""
        from sts_service.asr.errors import is_retryable
        from sts_service.asr.models import ASRErrorType

        assert is_retryable(ASRErrorType.MEMORY_ERROR) is True

    def test_invalid_audio_not_retryable(self):
        """Test INVALID_AUDIO errors are not retryable."""
        from sts_service.asr.errors import is_retryable
        from sts_service.asr.models import ASRErrorType

        assert is_retryable(ASRErrorType.INVALID_AUDIO) is False

    def test_model_load_error_not_retryable(self):
        """Test MODEL_LOAD_ERROR errors are not retryable."""
        from sts_service.asr.errors import is_retryable
        from sts_service.asr.models import ASRErrorType

        assert is_retryable(ASRErrorType.MODEL_LOAD_ERROR) is False

    def test_unknown_not_retryable(self):
        """Test UNKNOWN errors are not retryable."""
        from sts_service.asr.errors import is_retryable
        from sts_service.asr.models import ASRErrorType

        assert is_retryable(ASRErrorType.UNKNOWN) is False
