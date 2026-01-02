"""
Tests for Translation error classification.

TDD: These tests are written BEFORE the implementation.
"""

import pytest


class TestTranslationErrorType:
    """Tests for TranslationErrorType enum."""

    def test_error_type_enum_values(self):
        """Test all expected error types exist."""
        from sts_service.translation.errors import TranslationErrorType

        assert TranslationErrorType.EMPTY_INPUT == "empty_input"
        assert TranslationErrorType.UNSUPPORTED_LANGUAGE_PAIR == "unsupported_language_pair"
        assert TranslationErrorType.PROVIDER_ERROR == "provider_error"
        assert TranslationErrorType.TIMEOUT == "timeout"
        assert TranslationErrorType.NORMALIZATION_ERROR == "normalization_error"
        assert TranslationErrorType.UNKNOWN == "unknown"

    def test_error_type_is_string_enum(self):
        """Test that error types are string enums."""
        from sts_service.translation.errors import TranslationErrorType

        assert isinstance(TranslationErrorType.TIMEOUT.value, str)
        # str(Enum) returns class.name, but .value returns the string
        assert TranslationErrorType.TIMEOUT.value == "timeout"


class TestClassifyError:
    """Tests for classify_error function."""

    def test_classify_timeout_error(self):
        """Test TimeoutError maps to TIMEOUT."""
        from sts_service.translation.errors import TranslationErrorType, classify_error

        result = classify_error(TimeoutError("Operation timed out"))
        assert result == TranslationErrorType.TIMEOUT

    def test_classify_value_error(self):
        """Test ValueError maps to EMPTY_INPUT."""
        from sts_service.translation.errors import TranslationErrorType, classify_error

        result = classify_error(ValueError("Empty string"))
        assert result == TranslationErrorType.EMPTY_INPUT

    def test_classify_unknown_exception(self):
        """Test unknown exceptions map to UNKNOWN."""
        from sts_service.translation.errors import TranslationErrorType, classify_error

        result = classify_error(RuntimeError("Something went wrong"))
        assert result == TranslationErrorType.UNKNOWN

    def test_classify_connection_error(self):
        """Test ConnectionError maps to PROVIDER_ERROR."""
        from sts_service.translation.errors import TranslationErrorType, classify_error

        result = classify_error(ConnectionError("Connection refused"))
        assert result == TranslationErrorType.PROVIDER_ERROR


class TestIsRetryable:
    """Tests for is_retryable function."""

    def test_timeout_is_retryable(self):
        """Test TIMEOUT errors are retryable."""
        from sts_service.translation.errors import TranslationErrorType, is_retryable

        assert is_retryable(TranslationErrorType.TIMEOUT) is True

    def test_provider_error_is_retryable(self):
        """Test PROVIDER_ERROR is retryable."""
        from sts_service.translation.errors import TranslationErrorType, is_retryable

        assert is_retryable(TranslationErrorType.PROVIDER_ERROR) is True

    def test_empty_input_not_retryable(self):
        """Test EMPTY_INPUT is not retryable."""
        from sts_service.translation.errors import TranslationErrorType, is_retryable

        assert is_retryable(TranslationErrorType.EMPTY_INPUT) is False

    def test_unsupported_language_pair_not_retryable(self):
        """Test UNSUPPORTED_LANGUAGE_PAIR is not retryable."""
        from sts_service.translation.errors import TranslationErrorType, is_retryable

        assert is_retryable(TranslationErrorType.UNSUPPORTED_LANGUAGE_PAIR) is False

    def test_normalization_error_not_retryable(self):
        """Test NORMALIZATION_ERROR is not retryable."""
        from sts_service.translation.errors import TranslationErrorType, is_retryable

        assert is_retryable(TranslationErrorType.NORMALIZATION_ERROR) is False

    def test_unknown_not_retryable(self):
        """Test UNKNOWN is not retryable."""
        from sts_service.translation.errors import TranslationErrorType, is_retryable

        assert is_retryable(TranslationErrorType.UNKNOWN) is False


class TestCreateTranslationError:
    """Tests for create_translation_error factory function."""

    def test_create_error_from_timeout(self):
        """Test creating error from TimeoutError."""
        from sts_service.translation.errors import (
            TranslationErrorType,
            create_translation_error,
        )

        exception = TimeoutError("Exceeded deadline")
        error = create_translation_error(exception)

        assert error.error_type == TranslationErrorType.TIMEOUT
        assert error.message == "Exceeded deadline"
        assert error.retryable is True
        assert error.details is not None
        assert error.details["exception_type"] == "TimeoutError"

    def test_create_error_from_value_error(self):
        """Test creating error from ValueError."""
        from sts_service.translation.errors import (
            TranslationErrorType,
            create_translation_error,
        )

        exception = ValueError("Empty input")
        error = create_translation_error(exception)

        assert error.error_type == TranslationErrorType.EMPTY_INPUT
        assert error.message == "Empty input"
        assert error.retryable is False

    def test_create_error_with_empty_message(self):
        """Test creating error when exception has no message."""
        from sts_service.translation.errors import create_translation_error

        exception = ValueError()
        error = create_translation_error(exception)

        # Should use exception class name as fallback
        assert error.message == "ValueError"

    def test_create_error_preserves_exception_type(self):
        """Test that exception type is recorded in details."""
        from sts_service.translation.errors import create_translation_error

        exception = RuntimeError("Test error")
        error = create_translation_error(exception)

        assert error.details["exception_type"] == "RuntimeError"


class TestTranslationErrorModel:
    """Tests for TranslationError Pydantic model."""

    def test_translation_error_creation(self):
        """Test creating a TranslationError model."""
        from sts_service.translation.models import TranslationError, TranslationErrorType

        error = TranslationError(
            error_type=TranslationErrorType.TIMEOUT,
            message="Operation timed out",
            retryable=True,
        )

        assert error.error_type == TranslationErrorType.TIMEOUT
        assert error.message == "Operation timed out"
        assert error.retryable is True
        assert error.details is None

    def test_translation_error_with_details(self):
        """Test TranslationError with details."""
        from sts_service.translation.models import TranslationError, TranslationErrorType

        error = TranslationError(
            error_type=TranslationErrorType.TIMEOUT,
            message="Exceeded deadline",
            retryable=True,
            details={"elapsed_ms": 5234, "deadline_ms": 5000},
        )

        assert error.details is not None
        assert error.details["elapsed_ms"] == 5234
        assert error.details["deadline_ms"] == 5000

    def test_translation_error_json_serialization(self):
        """Test TranslationError can be serialized to JSON."""
        from sts_service.translation.models import TranslationError, TranslationErrorType

        error = TranslationError(
            error_type=TranslationErrorType.PROVIDER_ERROR,
            message="API error",
            retryable=True,
        )

        json_dict = error.model_dump()
        assert json_dict["error_type"] == "provider_error"
        assert json_dict["message"] == "API error"
        assert json_dict["retryable"] is True


# -----------------------------------------------------------------------------
# T005: Data Models Tests
# -----------------------------------------------------------------------------


class TestModels:
    """Tests for Translation data models (T005)."""

    def test_translation_status_enum_values(self):
        """Test TranslationStatus enum values."""
        from sts_service.translation.models import TranslationStatus

        assert TranslationStatus.SUCCESS == "success"
        assert TranslationStatus.PARTIAL == "partial"
        assert TranslationStatus.FAILED == "failed"

    def test_speaker_policy_defaults(self):
        """Test SpeakerPolicy default values."""
        from sts_service.translation.models import SpeakerPolicy

        policy = SpeakerPolicy()
        assert policy.detect_and_remove is False
        assert len(policy.allowed_patterns) == 2
        assert "^[A-Z][a-z]+: " in policy.allowed_patterns

    def test_speaker_policy_custom_values(self):
        """Test SpeakerPolicy with custom values."""
        from sts_service.translation.models import SpeakerPolicy

        policy = SpeakerPolicy(
            detect_and_remove=True,
            allowed_patterns=["^SPEAKER_\\d+: "],
        )
        assert policy.detect_and_remove is True
        assert len(policy.allowed_patterns) == 1

    def test_normalization_policy_defaults(self):
        """Test NormalizationPolicy default values."""
        from sts_service.translation.models import NormalizationPolicy

        policy = NormalizationPolicy()
        assert policy.enabled is True
        assert policy.normalize_time_phrases is True
        assert policy.expand_abbreviations is True
        assert policy.normalize_hyphens is True
        assert policy.normalize_symbols is True
        assert policy.tts_cleanup is False

    def test_normalization_policy_disabled(self):
        """Test NormalizationPolicy can be disabled."""
        from sts_service.translation.models import NormalizationPolicy

        policy = NormalizationPolicy(enabled=False)
        assert policy.enabled is False

    def test_text_asset_extends_asset_identifiers(self):
        """Test TextAsset correctly extends AssetIdentifiers."""
        from sts_service.translation.models import TextAsset, TranslationStatus

        asset = TextAsset(
            stream_id="stream-123",
            sequence_number=42,
            component_instance="mock-identity-v1",
            source_language="en",
            target_language="es",
            translated_text="Hola mundo",
            status=TranslationStatus.SUCCESS,
        )

        # Inherited from AssetIdentifiers
        assert asset.stream_id == "stream-123"
        assert asset.sequence_number == 42
        assert asset.asset_id is not None  # Auto-generated UUID
        assert asset.parent_asset_ids == []
        assert asset.created_at is not None
        assert asset.component == "translate"
        assert asset.component_instance == "mock-identity-v1"

        # TextAsset-specific
        assert asset.source_language == "en"
        assert asset.target_language == "es"
        assert asset.translated_text == "Hola mundo"
        assert asset.status == TranslationStatus.SUCCESS

    def test_text_asset_is_retryable_property(self):
        """Test TextAsset.is_retryable property."""
        from sts_service.translation.models import (
            TextAsset,
            TranslationError,
            TranslationErrorType,
            TranslationStatus,
        )

        # Failed with retryable error
        asset_retryable = TextAsset(
            stream_id="stream-123",
            sequence_number=0,
            component_instance="test",
            source_language="en",
            target_language="es",
            translated_text="",
            status=TranslationStatus.FAILED,
            errors=[
                TranslationError(
                    error_type=TranslationErrorType.TIMEOUT,
                    message="timeout",
                    retryable=True,
                )
            ],
        )
        assert asset_retryable.is_retryable is True

        # Failed with non-retryable error
        asset_non_retryable = TextAsset(
            stream_id="stream-123",
            sequence_number=0,
            component_instance="test",
            source_language="en",
            target_language="es",
            translated_text="",
            status=TranslationStatus.FAILED,
            errors=[
                TranslationError(
                    error_type=TranslationErrorType.EMPTY_INPUT,
                    message="empty",
                    retryable=False,
                )
            ],
        )
        assert asset_non_retryable.is_retryable is False

        # Success status is not retryable
        asset_success = TextAsset(
            stream_id="stream-123",
            sequence_number=0,
            component_instance="test",
            source_language="en",
            target_language="es",
            translated_text="Hello",
            status=TranslationStatus.SUCCESS,
        )
        assert asset_success.is_retryable is False

    def test_text_asset_with_parent_ids(self):
        """Test TextAsset with parent asset IDs for lineage tracking."""
        from sts_service.translation.models import TextAsset, TranslationStatus

        asset = TextAsset(
            stream_id="stream-123",
            sequence_number=42,
            parent_asset_ids=["asr-asset-uuid-abc"],
            component_instance="mock-identity-v1",
            source_language="en",
            target_language="es",
            translated_text="Hola",
            status=TranslationStatus.SUCCESS,
        )

        assert asset.parent_asset_ids == ["asr-asset-uuid-abc"]

    def test_text_asset_optional_fields(self):
        """Test TextAsset optional fields have correct defaults."""
        from sts_service.translation.models import TextAsset, TranslationStatus

        asset = TextAsset(
            stream_id="stream-123",
            sequence_number=0,
            component_instance="test",
            source_language="en",
            target_language="es",
            translated_text="Hello",
            status=TranslationStatus.SUCCESS,
        )

        assert asset.normalized_source_text is None
        assert asset.speaker_id == "default"
        assert asset.errors == []
        assert asset.warnings == []
        assert asset.processing_time_ms is None
        assert asset.model_info is None


class TestTranslationConfig:
    """Tests for TranslationConfig (T014)."""

    def test_translation_config_defaults(self):
        """Test TranslationConfig default values."""
        from sts_service.translation.models import TranslationConfig

        config = TranslationConfig()
        assert config.supported_language_pairs == []
        assert config.default_speaker_policy is not None
        assert config.default_normalization_policy is not None
        assert config.fallback_to_source_on_error is False
        assert config.timeout_ms == 5000

    def test_translation_config_timeout_validation(self):
        """Test TranslationConfig timeout_ms constraint (ge=1000)."""
        from pydantic import ValidationError
        from sts_service.translation.models import TranslationConfig

        # Valid timeout
        config = TranslationConfig(timeout_ms=3000)
        assert config.timeout_ms == 3000

        # Invalid timeout (too small)
        with pytest.raises(ValidationError):
            TranslationConfig(timeout_ms=500)

    def test_translation_config_with_language_pairs(self):
        """Test TranslationConfig with language pairs."""
        from sts_service.translation.models import TranslationConfig

        config = TranslationConfig(
            supported_language_pairs=[("en", "es"), ("en", "fr")],
        )
        assert len(config.supported_language_pairs) == 2
        assert ("en", "es") in config.supported_language_pairs


class TestValidateLanguagePair:
    """Tests for validate_language_pair helper."""

    def test_empty_list_allows_all_pairs(self):
        """Test empty supported_pairs allows all language pairs."""
        from sts_service.translation.models import validate_language_pair

        assert validate_language_pair("en", "es", []) is True
        assert validate_language_pair("zh", "de", []) is True

    def test_valid_pair_in_list(self):
        """Test valid pair in supported list."""
        from sts_service.translation.models import validate_language_pair

        pairs = [("en", "es"), ("en", "fr")]
        assert validate_language_pair("en", "es", pairs) is True

    def test_invalid_pair_not_in_list(self):
        """Test invalid pair not in supported list."""
        from sts_service.translation.models import validate_language_pair

        pairs = [("en", "es"), ("en", "fr")]
        assert validate_language_pair("en", "de", pairs) is False
