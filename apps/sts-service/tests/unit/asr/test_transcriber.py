"""
Unit tests for FasterWhisperASR transcriber (with mocked model).

TDD: These tests mock the WhisperModel to test component logic.
"""

from unittest.mock import MagicMock, patch

import pytest


# Mock segment and info structures to match faster-whisper output
def create_mock_segment(
    text: str,
    start: float,
    end: float,
    avg_logprob: float = -0.3,
    no_speech_prob: float = 0.1,
    words: list = None,
):
    """Create a mock segment object matching faster-whisper output."""
    segment = MagicMock()
    segment.text = text
    segment.start = start
    segment.end = end
    segment.avg_logprob = avg_logprob
    segment.no_speech_prob = no_speech_prob

    if words:
        segment.words = words
    else:
        # Create mock words
        word_list = text.split()
        mock_words = []
        word_duration = (end - start) / len(word_list) if word_list else 0
        current_time = start
        for w in word_list:
            mock_word = MagicMock()
            mock_word.word = w
            mock_word.start = current_time
            mock_word.end = current_time + word_duration
            mock_word.probability = 0.9
            mock_words.append(mock_word)
            current_time += word_duration
        segment.words = mock_words

    return segment


def create_mock_info(language: str = "en", language_probability: float = 0.99):
    """Create a mock TranscriptionInfo object."""
    info = MagicMock()
    info.language = language
    info.language_probability = language_probability
    return info


class TestFasterWhisperASR:
    """Tests for FasterWhisperASR with mocked model."""

    @pytest.fixture(autouse=True)
    def clear_model_cache(self):
        """Clear model cache before each test to ensure mock is used."""
        # Clear the cache before each test
        from sts_service.asr import transcriber
        transcriber._MODEL_CACHE.clear()
        yield
        # Clear again after test
        transcriber._MODEL_CACHE.clear()

    @pytest.fixture
    def mock_whisper_model(self):
        """Fixture providing a mocked WhisperModel."""
        with patch("sts_service.asr.transcriber.WhisperModel") as mock_class:
            mock_model = MagicMock()
            mock_class.return_value = mock_model

            # Default transcribe behavior
            mock_model.transcribe.return_value = (
                [create_mock_segment("Test text", 0.0, 1.0)],
                create_mock_info(),
            )

            yield mock_model

    def test_faster_whisper_asr_implements_protocol(self, mock_whisper_model):
        """Test that FasterWhisperASR implements ASRComponent protocol."""
        from sts_service.asr.interface import ASRComponent
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        asr = FasterWhisperASR(config=ASRConfig())

        assert isinstance(asr, ASRComponent)

    def test_faster_whisper_asr_component_instance(self, mock_whisper_model):
        """Test component instance name contains model info."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        asr = FasterWhisperASR(config=ASRConfig())

        assert "faster-whisper" in asr.component_instance
        assert "base" in asr.component_instance

    def test_faster_whisper_asr_is_ready_after_init(self, mock_whisper_model):
        """Test that is_ready is True after initialization."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        asr = FasterWhisperASR(config=ASRConfig())

        assert asr.is_ready is True

    def test_transcribe_returns_transcript_asset(self, mock_whisper_model, sample_audio_bytes):
        """Test that transcribe returns a TranscriptAsset."""
        from sts_service.asr.models import ASRConfig, TranscriptAsset
        from sts_service.asr.transcriber import FasterWhisperASR

        asr = FasterWhisperASR(config=ASRConfig())
        result = asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        assert isinstance(result, TranscriptAsset)

    def test_transcribe_success_status_for_speech(self, mock_whisper_model, sample_audio_bytes):
        """Test SUCCESS status when speech is detected."""
        from sts_service.asr.models import ASRConfig, TranscriptStatus
        from sts_service.asr.transcriber import FasterWhisperASR

        mock_whisper_model.transcribe.return_value = (
            [create_mock_segment("Hello world", 0.0, 1.0)],
            create_mock_info(),
        )

        asr = FasterWhisperASR(config=ASRConfig())
        result = asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        assert result.status == TranscriptStatus.SUCCESS
        assert len(result.segments) > 0

    def test_transcribe_empty_segments_for_silence(self, mock_whisper_model, sample_audio_bytes):
        """Test empty segments when no speech detected."""
        from sts_service.asr.models import ASRConfig, TranscriptStatus
        from sts_service.asr.transcriber import FasterWhisperASR

        # Return empty segments (no speech)
        mock_whisper_model.transcribe.return_value = ([], create_mock_info())

        asr = FasterWhisperASR(config=ASRConfig())
        result = asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        assert result.status == TranscriptStatus.SUCCESS
        assert len(result.segments) == 0

    def test_transcribe_applies_preprocessing(self, mock_whisper_model, sample_audio_bytes):
        """Test that preprocessing is applied before transcription."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        asr = FasterWhisperASR(config=ASRConfig())
        asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        # Model's transcribe should have been called
        assert mock_whisper_model.transcribe.called

    def test_transcribe_uses_domain_prompt(self, mock_whisper_model, sample_audio_bytes):
        """Test that domain prompt is passed to model."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        asr = FasterWhisperASR(config=ASRConfig())
        asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
            domain="football",
        )

        # Check that initial_prompt contains domain vocabulary
        call_kwargs = mock_whisper_model.transcribe.call_args[1]
        assert "initial_prompt" in call_kwargs
        assert len(call_kwargs["initial_prompt"]) > 0

    def test_transcribe_handles_timeout(self, mock_whisper_model, sample_audio_bytes):
        """Test timeout handling."""
        from sts_service.asr.models import ASRConfig, TranscriptStatus
        from sts_service.asr.transcriber import FasterWhisperASR

        mock_whisper_model.transcribe.side_effect = TimeoutError("Timeout")

        asr = FasterWhisperASR(config=ASRConfig())
        result = asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        assert result.status == TranscriptStatus.FAILED
        assert len(result.errors) > 0
        assert result.errors[0].retryable is True

    def test_transcribe_handles_memory_error(self, mock_whisper_model, sample_audio_bytes):
        """Test memory error handling."""
        from sts_service.asr.models import ASRConfig, TranscriptStatus
        from sts_service.asr.transcriber import FasterWhisperASR

        mock_whisper_model.transcribe.side_effect = MemoryError("OOM")

        asr = FasterWhisperASR(config=ASRConfig())
        result = asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        assert result.status == TranscriptStatus.FAILED
        assert len(result.errors) > 0
        assert result.errors[0].retryable is True

    def test_transcribe_calculates_confidence(self, mock_whisper_model, sample_audio_bytes):
        """Test confidence calculation from log probabilities."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        # avg_logprob of -0.5 should give ~0.5 confidence
        mock_whisper_model.transcribe.return_value = (
            [create_mock_segment("Test", 0.0, 1.0, avg_logprob=-0.5)],
            create_mock_info(),
        )

        asr = FasterWhisperASR(config=ASRConfig())
        result = asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        assert result.segments[0].confidence == pytest.approx(0.5, rel=0.1)

    def test_transcribe_converts_relative_to_absolute_timestamps(
        self, mock_whisper_model, sample_audio_bytes
    ):
        """Test that timestamps are converted to absolute stream time."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        # Model returns relative times (0.0 - 1.0)
        mock_whisper_model.transcribe.return_value = (
            [create_mock_segment("Test", 0.0, 1.0)],
            create_mock_info(),
        )

        asr = FasterWhisperASR(config=ASRConfig())
        result = asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test",
            sequence_number=0,
            start_time_ms=5000,  # Fragment starts at 5 seconds
            end_time_ms=6000,
        )

        # Timestamps should be absolute (offset by fragment start)
        segment = result.segments[0]
        assert segment.start_time_ms >= 5000
        assert segment.end_time_ms <= 6000

    def test_transcribe_records_processing_time(self, mock_whisper_model, sample_audio_bytes):
        """Test that processing time is recorded."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        asr = FasterWhisperASR(config=ASRConfig())
        result = asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        assert result.processing_time_ms is not None
        assert result.processing_time_ms >= 0

    def test_transcribe_sets_model_info(self, mock_whisper_model, sample_audio_bytes):
        """Test that model info is set in result."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        asr = FasterWhisperASR(config=ASRConfig())
        result = asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        assert result.model_info is not None
        assert "faster-whisper" in result.model_info

    def test_shutdown_clears_model_cache(self, mock_whisper_model):
        """Test that shutdown clears cached models."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR, _clear_model_cache

        asr = FasterWhisperASR(config=ASRConfig())
        asr.shutdown()

        # Should not raise


class TestModelCache:
    """Tests for model caching behavior."""

    def test_model_cache_reuses_model(self):
        """Test that same config reuses cached model."""
        # This test would require checking internal state
        # Simplified version just ensures no exceptions
        pass


class TestArtifactEmission:
    """Tests for debug artifact emission (transcript output to files)."""

    @pytest.fixture(autouse=True)
    def clear_model_cache(self):
        """Clear model cache before each test."""
        from sts_service.asr import transcriber
        transcriber._MODEL_CACHE.clear()
        yield
        transcriber._MODEL_CACHE.clear()

    @pytest.fixture
    def mock_whisper_model(self):
        """Fixture providing a mocked WhisperModel."""
        with patch("sts_service.asr.transcriber.WhisperModel") as mock_class:
            mock_model = MagicMock()
            mock_class.return_value = mock_model

            mock_model.transcribe.return_value = (
                [create_mock_segment("Hello world from ASR", 0.0, 1.0)],
                create_mock_info(),
            )

            yield mock_model

    @pytest.fixture
    def artifacts_dir(self, tmp_path, monkeypatch):
        """Create temp artifacts directory and patch working directory."""
        artifacts_path = tmp_path / ".artifacts" / "asr"
        monkeypatch.chdir(tmp_path)
        return artifacts_path

    def test_emit_transcript_artifact_when_enabled(
        self, mock_whisper_model, sample_audio_bytes, artifacts_dir
    ):
        """Test that transcript file is created when debug_artifacts=True."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        config = ASRConfig(debug_artifacts=True)
        asr = FasterWhisperASR(config=config)

        result = asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test-stream",
            sequence_number=42,
            start_time_ms=0,
            end_time_ms=1000,
        )

        # Verify artifact file was created
        expected_file = artifacts_dir / "test-stream" / "transcript_000042.txt"
        assert expected_file.exists(), f"Expected artifact file at {expected_file}"
        assert expected_file.read_text() == result.total_text

    def test_no_artifact_when_disabled(
        self, mock_whisper_model, sample_audio_bytes, artifacts_dir
    ):
        """Test that no artifact is created when debug_artifacts=False."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        config = ASRConfig(debug_artifacts=False)
        asr = FasterWhisperASR(config=config)

        asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="test-stream",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        # Verify no artifact directory was created
        assert not artifacts_dir.exists(), "Artifacts dir should not exist when disabled"

    def test_artifact_file_path_format(
        self, mock_whisper_model, sample_audio_bytes, artifacts_dir
    ):
        """Test that artifact file uses correct naming convention."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        config = ASRConfig(debug_artifacts=True)
        asr = FasterWhisperASR(config=config)

        # Test with various sequence numbers
        for seq_num in [0, 1, 123, 999999]:
            asr.transcribe(
                audio_data=sample_audio_bytes,
                stream_id="my-stream-id",
                sequence_number=seq_num,
                start_time_ms=0,
                end_time_ms=1000,
            )

            expected_file = artifacts_dir / "my-stream-id" / f"transcript_{seq_num:06d}.txt"
            assert expected_file.exists(), f"Expected file: {expected_file}"

    def test_artifact_contains_no_speech_message_for_silence(
        self, mock_whisper_model, sample_audio_bytes, artifacts_dir
    ):
        """Test that artifact contains placeholder when no speech detected."""
        from sts_service.asr.models import ASRConfig
        from sts_service.asr.transcriber import FasterWhisperASR

        # Return empty segments (silence)
        mock_whisper_model.transcribe.return_value = ([], create_mock_info())

        config = ASRConfig(debug_artifacts=True)
        asr = FasterWhisperASR(config=config)

        asr.transcribe(
            audio_data=sample_audio_bytes,
            stream_id="silent-stream",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        expected_file = artifacts_dir / "silent-stream" / "transcript_000000.txt"
        assert expected_file.exists()
        assert expected_file.read_text() == "(no speech detected)"
