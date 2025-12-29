"""
Unit tests for ASR Pydantic models.

TDD: These tests are written BEFORE implementation.
All tests should FAIL initially until models.py is implemented.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError


class TestAudioFormat:
    """Tests for AudioFormat enum."""

    def test_audio_format_pcm_f32le(self):
        """Test PCM float32 little-endian format value."""
        from sts_service.asr.models import AudioFormat

        assert AudioFormat.PCM_F32LE.value == "pcm_f32le"

    def test_audio_format_pcm_s16le(self):
        """Test PCM signed 16-bit little-endian format value."""
        from sts_service.asr.models import AudioFormat

        assert AudioFormat.PCM_S16LE.value == "pcm_s16le"


class TestAudioFragment:
    """Tests for AudioFragment model."""

    def test_audio_fragment_valid_creation(self):
        """Test creating a valid AudioFragment."""
        from sts_service.asr.models import AudioFragment

        fragment = AudioFragment(
            stream_id="test-stream",
            sequence_number=1,
            start_time_ms=0,
            end_time_ms=2000,
            payload_ref="mem://test/1",
        )

        assert fragment.stream_id == "test-stream"
        assert fragment.sequence_number == 1
        assert fragment.start_time_ms == 0
        assert fragment.end_time_ms == 2000
        assert fragment.payload_ref == "mem://test/1"

    def test_audio_fragment_duration_property(self):
        """Test duration_ms computed property."""
        from sts_service.asr.models import AudioFragment

        fragment = AudioFragment(
            stream_id="test-stream",
            sequence_number=1,
            start_time_ms=1000,
            end_time_ms=3000,
            payload_ref="mem://test/1",
        )

        assert fragment.duration_ms == 2000

    def test_audio_fragment_sample_rate_bounds(self):
        """Test sample_rate_hz bounds (8000-48000)."""
        from sts_service.asr.models import AudioFragment

        # Valid sample rates
        fragment = AudioFragment(
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
            payload_ref="mem://test/0",
            sample_rate_hz=16000,
        )
        assert fragment.sample_rate_hz == 16000

        # Minimum valid
        fragment_min = AudioFragment(
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
            payload_ref="mem://test/0",
            sample_rate_hz=8000,
        )
        assert fragment_min.sample_rate_hz == 8000

        # Maximum valid
        fragment_max = AudioFragment(
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
            payload_ref="mem://test/0",
            sample_rate_hz=48000,
        )
        assert fragment_max.sample_rate_hz == 48000

    def test_audio_fragment_invalid_sample_rate_too_low(self):
        """Test that sample_rate < 8000 is rejected."""
        from sts_service.asr.models import AudioFragment

        with pytest.raises(ValidationError):
            AudioFragment(
                stream_id="test",
                sequence_number=0,
                start_time_ms=0,
                end_time_ms=1000,
                payload_ref="mem://test/0",
                sample_rate_hz=7999,
            )

    def test_audio_fragment_invalid_sample_rate_too_high(self):
        """Test that sample_rate > 48000 is rejected."""
        from sts_service.asr.models import AudioFragment

        with pytest.raises(ValidationError):
            AudioFragment(
                stream_id="test",
                sequence_number=0,
                start_time_ms=0,
                end_time_ms=1000,
                payload_ref="mem://test/0",
                sample_rate_hz=48001,
            )

    def test_audio_fragment_invalid_negative_sequence(self):
        """Test that negative sequence_number is rejected."""
        from sts_service.asr.models import AudioFragment

        with pytest.raises(ValidationError):
            AudioFragment(
                stream_id="test",
                sequence_number=-1,
                start_time_ms=0,
                end_time_ms=1000,
                payload_ref="mem://test/0",
            )

    def test_audio_fragment_default_values(self):
        """Test default values for optional fields."""
        from sts_service.asr.models import AudioFormat, AudioFragment

        fragment = AudioFragment(
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
            payload_ref="mem://test/0",
        )

        assert fragment.audio_format == AudioFormat.PCM_F32LE
        assert fragment.sample_rate_hz == 16000
        assert fragment.channels == 1
        assert fragment.domain == "general"
        assert fragment.language == "en"


class TestWordTiming:
    """Tests for WordTiming model."""

    def test_word_timing_valid_creation(self):
        """Test creating a valid WordTiming."""
        from sts_service.asr.models import WordTiming

        word = WordTiming(
            start_time_ms=1000,
            end_time_ms=1500,
            word="touchdown",
            confidence=0.95,
        )

        assert word.start_time_ms == 1000
        assert word.end_time_ms == 1500
        assert word.word == "touchdown"
        assert word.confidence == 0.95

    def test_word_timing_confidence_bounds(self):
        """Test confidence score bounds (0.0-1.0)."""
        from sts_service.asr.models import WordTiming

        # Minimum valid
        word_min = WordTiming(
            start_time_ms=0,
            end_time_ms=100,
            word="test",
            confidence=0.0,
        )
        assert word_min.confidence == 0.0

        # Maximum valid
        word_max = WordTiming(
            start_time_ms=0,
            end_time_ms=100,
            word="test",
            confidence=1.0,
        )
        assert word_max.confidence == 1.0

    def test_word_timing_invalid_confidence_negative(self):
        """Test that negative confidence is rejected."""
        from sts_service.asr.models import WordTiming

        with pytest.raises(ValidationError):
            WordTiming(
                start_time_ms=0,
                end_time_ms=100,
                word="test",
                confidence=-0.1,
            )

    def test_word_timing_invalid_confidence_too_high(self):
        """Test that confidence > 1.0 is rejected."""
        from sts_service.asr.models import WordTiming

        with pytest.raises(ValidationError):
            WordTiming(
                start_time_ms=0,
                end_time_ms=100,
                word="test",
                confidence=1.1,
            )

    def test_word_timing_empty_word_rejected(self):
        """Test that empty word is rejected."""
        from sts_service.asr.models import WordTiming

        with pytest.raises(ValidationError):
            WordTiming(
                start_time_ms=0,
                end_time_ms=100,
                word="",
                confidence=0.9,
            )


class TestTranscriptSegment:
    """Tests for TranscriptSegment model."""

    def test_transcript_segment_valid_creation(self):
        """Test creating a valid TranscriptSegment."""
        from sts_service.asr.models import TranscriptSegment

        segment = TranscriptSegment(
            start_time_ms=0,
            end_time_ms=2000,
            text="Hello world",
            confidence=0.92,
        )

        assert segment.start_time_ms == 0
        assert segment.end_time_ms == 2000
        assert segment.text == "Hello world"
        assert segment.confidence == 0.92

    def test_transcript_segment_duration_property(self):
        """Test duration_ms computed property."""
        from sts_service.asr.models import TranscriptSegment

        segment = TranscriptSegment(
            start_time_ms=1000,
            end_time_ms=3500,
            text="Test text",
            confidence=0.9,
        )

        assert segment.duration_ms == 2500

    def test_transcript_segment_with_words(self):
        """Test segment with word-level timestamps."""
        from sts_service.asr.models import TranscriptSegment, WordTiming

        words = [
            WordTiming(start_time_ms=0, end_time_ms=300, word="Hello", confidence=0.95),
            WordTiming(start_time_ms=350, end_time_ms=600, word="world", confidence=0.90),
        ]

        segment = TranscriptSegment(
            start_time_ms=0,
            end_time_ms=600,
            text="Hello world",
            confidence=0.92,
            words=words,
        )

        assert len(segment.words) == 2
        assert segment.words[0].word == "Hello"
        assert segment.words[1].word == "world"

    def test_transcript_segment_empty_text_rejected(self):
        """Test that empty text is rejected."""
        from sts_service.asr.models import TranscriptSegment

        with pytest.raises(ValidationError):
            TranscriptSegment(
                start_time_ms=0,
                end_time_ms=1000,
                text="",
                confidence=0.9,
            )


class TestASRErrorType:
    """Tests for ASRErrorType enum."""

    def test_asr_error_types_enum(self):
        """Test all ASR error type values exist."""
        from sts_service.asr.models import ASRErrorType

        assert ASRErrorType.NO_SPEECH.value == "no_speech"
        assert ASRErrorType.MODEL_LOAD_ERROR.value == "model_load"
        assert ASRErrorType.MEMORY_ERROR.value == "memory_error"
        assert ASRErrorType.INVALID_AUDIO.value == "invalid_audio"
        assert ASRErrorType.TIMEOUT.value == "timeout"
        assert ASRErrorType.PREPROCESSING_ERROR.value == "preprocessing"
        assert ASRErrorType.UNKNOWN.value == "unknown"


class TestASRError:
    """Tests for ASRError model."""

    def test_asr_error_valid_creation(self):
        """Test creating a valid ASRError."""
        from sts_service.asr.models import ASRError, ASRErrorType

        error = ASRError(
            error_type=ASRErrorType.TIMEOUT,
            message="Processing exceeded deadline",
            retryable=True,
        )

        assert error.error_type == ASRErrorType.TIMEOUT
        assert error.message == "Processing exceeded deadline"
        assert error.retryable is True

    def test_asr_error_retryable_flag(self):
        """Test retryable flag for different error types."""
        from sts_service.asr.models import ASRError, ASRErrorType

        # Retryable errors
        timeout_error = ASRError(
            error_type=ASRErrorType.TIMEOUT,
            message="Timeout",
            retryable=True,
        )
        assert timeout_error.retryable is True

        # Non-retryable errors
        invalid_error = ASRError(
            error_type=ASRErrorType.INVALID_AUDIO,
            message="Invalid audio",
            retryable=False,
        )
        assert invalid_error.retryable is False

    def test_asr_error_with_details(self):
        """Test ASRError with additional details."""
        from sts_service.asr.models import ASRError, ASRErrorType

        error = ASRError(
            error_type=ASRErrorType.TIMEOUT,
            message="Timeout exceeded",
            retryable=True,
            details={"elapsed_ms": 5234, "deadline_ms": 5000},
        )

        assert error.details is not None
        assert error.details["elapsed_ms"] == 5234


class TestTranscriptStatus:
    """Tests for TranscriptStatus enum."""

    def test_transcript_status_success_value(self):
        """Test SUCCESS status value."""
        from sts_service.asr.models import TranscriptStatus

        assert TranscriptStatus.SUCCESS.value == "success"

    def test_transcript_status_partial_value(self):
        """Test PARTIAL status value."""
        from sts_service.asr.models import TranscriptStatus

        assert TranscriptStatus.PARTIAL.value == "partial"

    def test_transcript_status_failed_value(self):
        """Test FAILED status value."""
        from sts_service.asr.models import TranscriptStatus

        assert TranscriptStatus.FAILED.value == "failed"


class TestAssetIdentifiers:
    """Tests for AssetIdentifiers base model."""

    def test_asset_identifiers_valid_creation(self):
        """Test creating valid AssetIdentifiers."""
        from sts_service.asr.models import AssetIdentifiers

        identifiers = AssetIdentifiers(
            stream_id="test-stream",
            sequence_number=5,
            component="asr",
            component_instance="faster-whisper-base",
        )

        assert identifiers.stream_id == "test-stream"
        assert identifiers.sequence_number == 5
        assert identifiers.component == "asr"
        assert identifiers.component_instance == "faster-whisper-base"

    def test_asset_identifiers_auto_generated_asset_id(self):
        """Test that asset_id is auto-generated."""
        from sts_service.asr.models import AssetIdentifiers

        identifiers = AssetIdentifiers(
            stream_id="test",
            sequence_number=0,
            component="asr",
            component_instance="test",
        )

        # Asset ID should be a valid UUID string
        assert identifiers.asset_id is not None
        assert len(identifiers.asset_id) == 36  # UUID format

    def test_asset_identifiers_auto_created_at(self):
        """Test that created_at is auto-generated."""
        from sts_service.asr.models import AssetIdentifiers

        before = datetime.utcnow()
        identifiers = AssetIdentifiers(
            stream_id="test",
            sequence_number=0,
            component="asr",
            component_instance="test",
        )
        after = datetime.utcnow()

        assert identifiers.created_at >= before
        assert identifiers.created_at <= after


class TestTranscriptAsset:
    """Tests for TranscriptAsset model."""

    def test_transcript_asset_valid_creation(self):
        """Test creating a valid TranscriptAsset."""
        from sts_service.asr.models import TranscriptAsset, TranscriptSegment, TranscriptStatus

        segment = TranscriptSegment(
            start_time_ms=0,
            end_time_ms=2000,
            text="Hello world",
            confidence=0.92,
        )

        asset = TranscriptAsset(
            stream_id="test-stream",
            sequence_number=1,
            component_instance="faster-whisper-base",
            language="en",
            segments=[segment],
            status=TranscriptStatus.SUCCESS,
        )

        assert asset.stream_id == "test-stream"
        assert asset.language == "en"
        assert len(asset.segments) == 1
        assert asset.status == TranscriptStatus.SUCCESS

    def test_transcript_asset_total_text_property(self):
        """Test total_text computed property."""
        from sts_service.asr.models import TranscriptAsset, TranscriptSegment, TranscriptStatus

        segments = [
            TranscriptSegment(start_time_ms=0, end_time_ms=1000, text="Hello", confidence=0.9),
            TranscriptSegment(start_time_ms=1000, end_time_ms=2000, text="world", confidence=0.9),
        ]

        asset = TranscriptAsset(
            stream_id="test",
            sequence_number=0,
            component_instance="test",
            language="en",
            segments=segments,
            status=TranscriptStatus.SUCCESS,
        )

        assert asset.total_text == "Hello world"

    def test_transcript_asset_average_confidence_empty(self):
        """Test average_confidence with no segments returns 0.0."""
        from sts_service.asr.models import TranscriptAsset, TranscriptStatus

        asset = TranscriptAsset(
            stream_id="test",
            sequence_number=0,
            component_instance="test",
            language="en",
            segments=[],
            status=TranscriptStatus.SUCCESS,
        )

        assert asset.average_confidence == 0.0

    def test_transcript_asset_average_confidence_multiple(self):
        """Test average_confidence calculation with multiple segments."""
        from sts_service.asr.models import TranscriptAsset, TranscriptSegment, TranscriptStatus

        segments = [
            TranscriptSegment(start_time_ms=0, end_time_ms=1000, text="A", confidence=0.8),
            TranscriptSegment(start_time_ms=1000, end_time_ms=2000, text="B", confidence=0.9),
            TranscriptSegment(start_time_ms=2000, end_time_ms=3000, text="C", confidence=1.0),
        ]

        asset = TranscriptAsset(
            stream_id="test",
            sequence_number=0,
            component_instance="test",
            language="en",
            segments=segments,
            status=TranscriptStatus.SUCCESS,
        )

        # (0.8 + 0.9 + 1.0) / 3 = 0.9
        assert asset.average_confidence == pytest.approx(0.9, rel=1e-6)

    def test_transcript_asset_is_retryable_logic(self):
        """Test is_retryable logic."""
        from sts_service.asr.models import ASRError, ASRErrorType, TranscriptAsset, TranscriptStatus

        # Failed with retryable error
        asset_retryable = TranscriptAsset(
            stream_id="test",
            sequence_number=0,
            component_instance="test",
            language="en",
            segments=[],
            status=TranscriptStatus.FAILED,
            errors=[ASRError(error_type=ASRErrorType.TIMEOUT, message="timeout", retryable=True)],
        )
        assert asset_retryable.is_retryable is True

        # Failed with non-retryable error
        asset_not_retryable = TranscriptAsset(
            stream_id="test",
            sequence_number=0,
            component_instance="test",
            language="en",
            segments=[],
            status=TranscriptStatus.FAILED,
            errors=[ASRError(error_type=ASRErrorType.INVALID_AUDIO, message="invalid", retryable=False)],
        )
        assert asset_not_retryable.is_retryable is False

        # Success - not retryable
        asset_success = TranscriptAsset(
            stream_id="test",
            sequence_number=0,
            component_instance="test",
            language="en",
            segments=[],
            status=TranscriptStatus.SUCCESS,
        )
        assert asset_success.is_retryable is False

    def test_transcript_status_success_conditions(self):
        """Test SUCCESS status with valid conditions."""
        from sts_service.asr.models import TranscriptAsset, TranscriptSegment, TranscriptStatus

        # SUCCESS: segments present, no errors
        asset = TranscriptAsset(
            stream_id="test",
            sequence_number=0,
            component_instance="test",
            language="en",
            segments=[
                TranscriptSegment(start_time_ms=0, end_time_ms=1000, text="Test", confidence=0.9)
            ],
            status=TranscriptStatus.SUCCESS,
            errors=[],
        )
        assert asset.status == TranscriptStatus.SUCCESS
        assert len(asset.errors) == 0

    def test_transcript_status_partial_conditions(self):
        """Test PARTIAL status with errors and segments."""
        from sts_service.asr.models import (
            ASRError,
            ASRErrorType,
            TranscriptAsset,
            TranscriptSegment,
            TranscriptStatus,
        )

        # PARTIAL: some segments, some errors
        asset = TranscriptAsset(
            stream_id="test",
            sequence_number=0,
            component_instance="test",
            language="en",
            segments=[
                TranscriptSegment(start_time_ms=0, end_time_ms=1000, text="Partial", confidence=0.8)
            ],
            status=TranscriptStatus.PARTIAL,
            errors=[ASRError(error_type=ASRErrorType.TIMEOUT, message="timeout", retryable=True)],
        )
        assert asset.status == TranscriptStatus.PARTIAL
        assert len(asset.segments) > 0
        assert len(asset.errors) > 0

    def test_transcript_status_failed_conditions(self):
        """Test FAILED status with no segments."""
        from sts_service.asr.models import ASRError, ASRErrorType, TranscriptAsset, TranscriptStatus

        # FAILED: no segments
        asset = TranscriptAsset(
            stream_id="test",
            sequence_number=0,
            component_instance="test",
            language="en",
            segments=[],
            status=TranscriptStatus.FAILED,
            errors=[ASRError(error_type=ASRErrorType.MEMORY_ERROR, message="OOM", retryable=True)],
        )
        assert asset.status == TranscriptStatus.FAILED
        assert len(asset.segments) == 0

    def test_transcript_asset_default_component(self):
        """Test default component value is 'asr'."""
        from sts_service.asr.models import TranscriptAsset, TranscriptStatus

        asset = TranscriptAsset(
            stream_id="test",
            sequence_number=0,
            component_instance="test",
            language="en",
            segments=[],
            status=TranscriptStatus.SUCCESS,
        )
        assert asset.component == "asr"


class TestASRModelConfig:
    """Tests for ASRModelConfig model."""

    def test_asr_model_config_defaults(self):
        """Test default values for ASRModelConfig."""
        from sts_service.asr.models import ASRModelConfig

        config = ASRModelConfig()

        assert config.model_size == "base"
        assert config.device == "cpu"
        assert config.compute_type == "int8"

    def test_asr_model_config_pattern_validation(self):
        """Test model_size pattern validation."""
        from sts_service.asr.models import ASRModelConfig

        # Valid sizes
        for size in ["tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3", "turbo"]:
            config = ASRModelConfig(model_size=size)
            assert config.model_size == size

    def test_asr_model_config_invalid_size(self):
        """Test that invalid model size is rejected."""
        from sts_service.asr.models import ASRModelConfig

        with pytest.raises(ValidationError):
            ASRModelConfig(model_size="invalid")

    def test_asr_model_config_device_pattern(self):
        """Test device pattern validation."""
        from sts_service.asr.models import ASRModelConfig

        # Valid devices
        valid_devices = ["cpu", "cuda", "cuda:0", "cuda:1"]
        for device in valid_devices:
            config = ASRModelConfig(device=device)
            assert config.device == device


class TestVADConfig:
    """Tests for VADConfig model."""

    def test_vad_config_defaults(self):
        """Test default values for VADConfig."""
        from sts_service.asr.models import VADConfig

        config = VADConfig()

        assert config.enabled is True
        assert config.threshold == 0.5
        assert config.min_silence_duration_ms == 300
        assert config.min_speech_duration_ms == 250
        assert config.speech_pad_ms == 400

    def test_vad_config_bounds(self):
        """Test VAD threshold bounds (0.0-1.0)."""
        from sts_service.asr.models import VADConfig

        # Min valid
        config_min = VADConfig(threshold=0.0)
        assert config_min.threshold == 0.0

        # Max valid
        config_max = VADConfig(threshold=1.0)
        assert config_max.threshold == 1.0

    def test_vad_config_invalid_threshold(self):
        """Test that invalid threshold is rejected."""
        from sts_service.asr.models import VADConfig

        with pytest.raises(ValidationError):
            VADConfig(threshold=1.1)

        with pytest.raises(ValidationError):
            VADConfig(threshold=-0.1)


class TestTranscriptionConfig:
    """Tests for TranscriptionConfig model."""

    def test_transcription_config_defaults(self):
        """Test default values for TranscriptionConfig."""
        from sts_service.asr.models import TranscriptionConfig

        config = TranscriptionConfig()

        assert config.language == "en"
        assert config.word_timestamps is True
        assert config.beam_size == 8
        assert config.best_of == 8
        assert config.temperature == [0.0, 0.2, 0.4]
        assert config.no_speech_threshold == 0.6

    def test_transcription_config_beam_size_bounds(self):
        """Test beam_size bounds (1-10)."""
        from sts_service.asr.models import TranscriptionConfig

        config_min = TranscriptionConfig(beam_size=1)
        assert config_min.beam_size == 1

        config_max = TranscriptionConfig(beam_size=10)
        assert config_max.beam_size == 10

    def test_transcription_config_invalid_beam_size(self):
        """Test that invalid beam_size is rejected."""
        from sts_service.asr.models import TranscriptionConfig

        with pytest.raises(ValidationError):
            TranscriptionConfig(beam_size=0)

        with pytest.raises(ValidationError):
            TranscriptionConfig(beam_size=11)


class TestUtteranceShapingConfig:
    """Tests for UtteranceShapingConfig model."""

    def test_utterance_shaping_config_defaults(self):
        """Test default values for UtteranceShapingConfig."""
        from sts_service.asr.models import UtteranceShapingConfig

        config = UtteranceShapingConfig()

        assert config.merge_threshold_seconds == 1.0
        assert config.max_segment_duration_seconds == 6.0


class TestASRConfig:
    """Tests for ASRConfig model."""

    def test_asr_config_defaults(self):
        """Test default values for ASRConfig."""
        from sts_service.asr.models import ASRConfig

        config = ASRConfig()

        assert config.model is not None
        assert config.vad is not None
        assert config.transcription is not None
        assert config.utterance_shaping is not None
        assert config.timeout_ms == 5000
        assert config.debug_artifacts is False

    def test_asr_config_nested_configs(self):
        """Test ASRConfig with nested configuration objects."""
        from sts_service.asr.models import ASRConfig, ASRModelConfig, TranscriptionConfig, VADConfig

        config = ASRConfig(
            model=ASRModelConfig(model_size="small"),
            vad=VADConfig(enabled=False),
            transcription=TranscriptionConfig(language="es"),
        )

        assert config.model.model_size == "small"
        assert config.vad.enabled is False
        assert config.transcription.language == "es"


class TestASRMetrics:
    """Tests for ASRMetrics model."""

    def test_asr_metrics_required_fields(self):
        """Test all required fields for ASRMetrics."""
        from sts_service.asr.models import ASRMetrics

        metrics = ASRMetrics(
            stream_id="test-stream",
            sequence_number=5,
            preprocess_time_ms=10,
            transcription_time_ms=200,
            postprocess_time_ms=5,
            total_time_ms=215,
            segment_count=3,
            total_text_length=50,
            average_confidence=0.92,
        )

        assert metrics.stream_id == "test-stream"
        assert metrics.sequence_number == 5
        assert metrics.preprocess_time_ms == 10
        assert metrics.transcription_time_ms == 200
        assert metrics.postprocess_time_ms == 5
        assert metrics.total_time_ms == 215
        assert metrics.segment_count == 3
        assert metrics.total_text_length == 50
        assert metrics.average_confidence == 0.92
        assert metrics.error_count == 0  # default
        assert metrics.retryable_error_count == 0  # default

    def test_asr_metrics_non_negative_times(self):
        """Test that negative times are rejected."""
        from sts_service.asr.models import ASRMetrics

        with pytest.raises(ValidationError):
            ASRMetrics(
                stream_id="test",
                sequence_number=0,
                preprocess_time_ms=-1,
                transcription_time_ms=200,
                postprocess_time_ms=5,
                total_time_ms=215,
                segment_count=0,
                total_text_length=0,
                average_confidence=0.0,
            )


class TestModelSerialization:
    """Tests for model JSON serialization."""

    def test_transcript_asset_json_schema(self):
        """Test that TranscriptAsset produces valid JSON schema."""
        from sts_service.asr.models import TranscriptAsset

        schema = TranscriptAsset.model_json_schema()
        assert "properties" in schema
        assert "stream_id" in schema["properties"]
        assert "segments" in schema["properties"]

    def test_audio_fragment_json_serialization(self):
        """Test AudioFragment JSON round-trip."""
        from sts_service.asr.models import AudioFragment

        fragment = AudioFragment(
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
            payload_ref="mem://test/0",
        )

        json_str = fragment.model_dump_json()
        reloaded = AudioFragment.model_validate_json(json_str)

        assert reloaded.stream_id == fragment.stream_id
        assert reloaded.sequence_number == fragment.sequence_number
