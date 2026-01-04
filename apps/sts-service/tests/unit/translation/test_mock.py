"""
Tests for mock translation components (T010-T011).

TDD: These tests are written BEFORE the implementation.
"""


class TestMockIdentityTranslator:
    """Tests for MockIdentityTranslator (T010)."""

    def test_mock_exists(self):
        """Test MockIdentityTranslator can be imported."""
        from sts_service.translation.mock import MockIdentityTranslator

        mock = MockIdentityTranslator()
        assert mock is not None

    def test_component_name_is_translate(self):
        """Test component_name returns 'translate'."""
        from sts_service.translation.mock import MockIdentityTranslator

        mock = MockIdentityTranslator()
        assert mock.component_name == "translate"

    def test_component_instance_is_mock_identity(self):
        """Test component_instance returns 'mock-identity-v1'."""
        from sts_service.translation.mock import MockIdentityTranslator

        mock = MockIdentityTranslator()
        assert mock.component_instance == "mock-identity-v1"

    def test_is_ready_returns_true(self):
        """Test is_ready returns True."""
        from sts_service.translation.mock import MockIdentityTranslator

        mock = MockIdentityTranslator()
        assert mock.is_ready is True

    def test_identity_translation(self):
        """Test translate returns source text unchanged (identity)."""
        from sts_service.translation.mock import MockIdentityTranslator
        from sts_service.translation.models import TranslationStatus

        mock = MockIdentityTranslator()
        result = mock.translate(
            source_text="Hello world",
            stream_id="stream-123",
            sequence_number=42,
            source_language="en",
            target_language="es",
            parent_asset_ids=["parent-abc"],
        )

        assert result.translated_text == "Hello world"
        assert result.status == TranslationStatus.SUCCESS
        assert result.source_language == "en"
        assert result.target_language == "es"
        assert result.parent_asset_ids == ["parent-abc"]

    def test_preserves_stream_metadata(self):
        """Test stream_id and sequence_number are preserved."""
        from sts_service.translation.mock import MockIdentityTranslator

        mock = MockIdentityTranslator()
        result = mock.translate(
            source_text="Test",
            stream_id="my-stream",
            sequence_number=99,
            source_language="en",
            target_language="fr",
            parent_asset_ids=[],
        )

        assert result.stream_id == "my-stream"
        assert result.sequence_number == 99

    def test_generates_asset_id(self):
        """Test each call generates a new asset_id."""
        from sts_service.translation.mock import MockIdentityTranslator

        mock = MockIdentityTranslator()
        result1 = mock.translate(
            source_text="Test",
            stream_id="stream",
            sequence_number=0,
            source_language="en",
            target_language="es",
            parent_asset_ids=[],
        )
        result2 = mock.translate(
            source_text="Test",
            stream_id="stream",
            sequence_number=1,
            source_language="en",
            target_language="es",
            parent_asset_ids=[],
        )

        assert result1.asset_id != result2.asset_id

    def test_applies_speaker_policy(self):
        """Test speaker policy is applied when provided."""
        from sts_service.translation.mock import MockIdentityTranslator
        from sts_service.translation.models import SpeakerPolicy

        mock = MockIdentityTranslator()
        policy = SpeakerPolicy(detect_and_remove=True)

        result = mock.translate(
            source_text="Alice: Hello there",
            stream_id="stream",
            sequence_number=0,
            source_language="en",
            target_language="es",
            parent_asset_ids=[],
            speaker_policy=policy,
        )

        assert result.speaker_id == "Alice"
        assert result.translated_text == "Hello there"

    def test_applies_normalization_policy(self):
        """Test normalization policy is applied when provided."""
        from sts_service.translation.mock import MockIdentityTranslator
        from sts_service.translation.models import NormalizationPolicy

        mock = MockIdentityTranslator()
        policy = NormalizationPolicy(
            enabled=True,
            normalize_time_phrases=True,
            expand_abbreviations=True,
        )

        result = mock.translate(
            source_text="NFL 1:54 REMAINING",
            stream_id="stream",
            sequence_number=0,
            source_language="en",
            target_language="es",
            parent_asset_ids=[],
            normalization_policy=policy,
        )

        # Should be normalized
        assert "N F L" in result.translated_text
        assert "1:54 remaining" in result.translated_text

    def test_empty_input_returns_success_with_empty_text(self):
        """Test empty input returns success with empty text."""
        from sts_service.translation.mock import MockIdentityTranslator
        from sts_service.translation.models import TranslationStatus

        mock = MockIdentityTranslator()
        result = mock.translate(
            source_text="",
            stream_id="stream",
            sequence_number=0,
            source_language="en",
            target_language="es",
            parent_asset_ids=[],
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.translated_text == ""

    def test_satisfies_protocol(self):
        """Test MockIdentityTranslator satisfies TranslationComponent protocol."""
        from sts_service.translation.interface import TranslationComponent
        from sts_service.translation.mock import MockIdentityTranslator

        mock = MockIdentityTranslator()
        assert isinstance(mock, TranslationComponent)


class TestMockLatencyTranslator:
    """Tests for MockLatencyTranslator with configurable delay."""

    def test_mock_latency_exists(self):
        """Test MockLatencyTranslator can be imported."""
        from sts_service.translation.mock import MockLatencyTranslator

        mock = MockLatencyTranslator(latency_ms=10)
        assert mock is not None

    def test_component_instance_includes_latency(self):
        """Test component_instance reflects configured latency."""
        from sts_service.translation.mock import MockLatencyTranslator

        mock = MockLatencyTranslator(latency_ms=50)
        assert "50ms" in mock.component_instance


class TestMockFailingTranslator:
    """Tests for MockFailingTranslator with configurable failures."""

    def test_mock_failing_exists(self):
        """Test MockFailingTranslator can be imported."""
        from sts_service.translation.mock import MockFailingTranslator

        mock = MockFailingTranslator(failure_rate=0.5)
        assert mock is not None

    def test_zero_failure_rate_always_succeeds(self):
        """Test 0% failure rate always produces SUCCESS."""
        from sts_service.translation.mock import MockFailingTranslator
        from sts_service.translation.models import TranslationStatus

        mock = MockFailingTranslator(failure_rate=0.0)

        for _ in range(10):
            result = mock.translate(
                source_text="Test",
                stream_id="stream",
                sequence_number=0,
                source_language="en",
                target_language="es",
                parent_asset_ids=[],
            )
            assert result.status == TranslationStatus.SUCCESS

    def test_full_failure_rate_always_fails(self):
        """Test 100% failure rate always produces FAILED."""
        from sts_service.translation.mock import MockFailingTranslator
        from sts_service.translation.models import TranslationStatus

        mock = MockFailingTranslator(failure_rate=1.0)

        for _ in range(10):
            result = mock.translate(
                source_text="Test",
                stream_id="stream",
                sequence_number=0,
                source_language="en",
                target_language="es",
                parent_asset_ids=[],
            )
            assert result.status == TranslationStatus.FAILED

    def test_configurable_error_type(self):
        """Test failure type can be configured."""
        from sts_service.translation.mock import MockFailingTranslator
        from sts_service.translation.models import TranslationErrorType, TranslationStatus

        mock = MockFailingTranslator(failure_rate=1.0, failure_type=TranslationErrorType.TIMEOUT)

        result = mock.translate(
            source_text="Test",
            stream_id="stream",
            sequence_number=0,
            source_language="en",
            target_language="es",
            parent_asset_ids=[],
        )

        assert result.status == TranslationStatus.FAILED
        assert len(result.errors) > 0
        assert result.errors[0].error_type == TranslationErrorType.TIMEOUT


class TestMockTranslatorConfig:
    """Tests for MockTranslatorConfig dataclass."""

    def test_config_exists(self):
        """Test MockTranslatorConfig can be imported."""
        from sts_service.translation.mock import MockTranslatorConfig

        config = MockTranslatorConfig()
        assert config is not None

    def test_default_values(self):
        """Test default configuration values."""
        from sts_service.translation.mock import MockTranslatorConfig

        config = MockTranslatorConfig()
        assert config.simulate_latency_ms == 0
        assert config.failure_rate == 0.0
        assert config.failure_type is None
