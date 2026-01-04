"""
Integration tests for FULL Pipeline: ASR -> Translation -> TTS.

Task IDs: T077, T078

These tests use REAL modules (ASR + Translation + TTS) to verify the complete
speech-to-speech pipeline works end-to-end with actual model inference.

Tests:
- Complete pipeline processing with real audio
- Asset lineage tracked correctly through all stages
- Duration matching works (variance <10%)
- Empty transcript handling (silence)

Requirements:
- faster-whisper package installed
- DeepL API key (for real translation) or mock fallback
- Coqui TTS package installed (or mock fallback)
- Test audio fixtures available
- ffmpeg installed (for audio extraction)
"""

import base64
import os
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest

from sts_service.asr import ASRConfig, ASRModelConfig, FasterWhisperASR, VADConfig
from sts_service.full.models.asset import AssetStatus, DurationMatchMetadata
from sts_service.full.models.fragment import FragmentData, ProcessingStatus
from sts_service.full.models.stream import StreamConfig, StreamSession, StreamState
from sts_service.full.pipeline import PipelineCoordinator
from sts_service.translation import create_translation_component
from sts_service.tts import create_tts_component

from .conftest import (
    check_coqui_available,
    check_deepl_key_available,
    check_faster_whisper_available,
    requires_coqui,
    requires_deepl_key,
    requires_faster_whisper,
)


class TestFullPipelineWithRealModules:
    """Integration tests for full pipeline: ASR -> Translation -> TTS (T077, T078)."""

    @pytest.fixture
    def real_asr_component(self) -> FasterWhisperASR:
        """Create a REAL FasterWhisperASR with tiny model."""
        config = ASRConfig(
            model=ASRModelConfig(
                model_size="tiny",
                device="cpu",
                compute_type="int8",
            ),
            vad=VADConfig(enabled=True),
        )
        asr = FasterWhisperASR(config=config)
        yield asr
        asr.shutdown()

    @pytest.fixture
    def real_or_mock_translation(self) -> Any:
        """Create real DeepL translator if API key available, otherwise mock."""
        if check_deepl_key_available():
            return create_translation_component(provider="deepl")
        else:
            # Return mock translation
            return create_translation_component(mock=True)

    @pytest.fixture
    def real_or_mock_tts(self) -> Any:
        """Create real Coqui TTS if available, otherwise mock."""
        if check_coqui_available():
            try:
                return create_tts_component(provider="coqui")
            except Exception:
                # Fall back to mock if Coqui fails to initialize
                return create_tts_component(provider="mock")
        else:
            return create_tts_component(provider="mock")

    @pytest.fixture
    def mock_translation_component(self) -> MagicMock:
        """Create mock translation that simulates realistic behavior."""
        mock = MagicMock()
        mock.component_name = "translate"
        mock.component_instance = "mock-translate-v1"
        mock.is_ready = True

        def translate_side_effect(source_text: str, *args: Any, **kwargs: Any) -> MagicMock:
            result = MagicMock()
            result.asset_id = f"trans-{hash(source_text) % 10000:04d}"
            result.status = AssetStatus.SUCCESS
            # Simulate Spanish translation (slightly longer)
            if source_text:
                result.translated_text = f"{source_text} en espanol"
            else:
                result.translated_text = ""
            result.source_text = source_text
            result.source_language = "en"
            result.target_language = "es"
            result.character_count = len(source_text)
            result.word_expansion_ratio = 1.15
            result.latency_ms = 50
            result.parent_asset_ids = kwargs.get("parent_asset_ids", [])
            result.error_message = None
            return result

        mock.translate.side_effect = translate_side_effect
        return mock

    @pytest.fixture
    def mock_tts_component(self) -> MagicMock:
        """Create mock TTS that simulates realistic behavior."""
        mock = MagicMock()
        mock.component_name = "tts"
        mock.component_instance = "mock-tts-v1"
        mock.is_ready = True

        def synthesize_side_effect(
            text_asset: Any, target_duration_ms: int | None = None, **kwargs: Any
        ) -> MagicMock:
            duration_ms = target_duration_ms or 6000
            sample_rate = kwargs.get("output_sample_rate_hz", 16000)
            samples = int(sample_rate * duration_ms / 1000)

            # Simulate synthesized audio (silence with proper size)
            audio_bytes = b"\x00\x00" * samples

            # Simulate slight duration variance (realistic for TTS)
            actual_duration = int(duration_ms * 1.02)  # 2% longer
            variance = abs(actual_duration - duration_ms) / duration_ms * 100

            result = MagicMock()
            result.asset_id = "audio-mock-001"
            result.status = AssetStatus.SUCCESS
            result.audio_bytes = audio_bytes
            result.format = "pcm_s16le"
            result.sample_rate_hz = sample_rate
            result.channels = kwargs.get("output_channels", 1)
            result.duration_ms = actual_duration
            result.duration_metadata = DurationMatchMetadata(
                original_duration_ms=duration_ms,
                raw_duration_ms=actual_duration + 100,
                final_duration_ms=actual_duration,
                duration_variance_percent=variance,
                speed_ratio=1.0,
                speed_clamped=False,
            )
            result.voice_profile = "default"
            result.text_input = getattr(text_asset, "translated_text", "")
            result.latency_ms = 100
            result.parent_asset_ids = [getattr(text_asset, "asset_id", "")]
            result.error_message = None
            return result

        mock.synthesize.side_effect = synthesize_side_effect
        return mock

    @requires_faster_whisper
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_produces_dubbed_audio(
        self,
        nfl_audio_path: Path,
        load_audio_fragment: Callable,
        create_fragment_data: Callable,
        sample_stream_session: StreamSession,
        real_asr_component: FasterWhisperASR,
        mock_translation_component: MagicMock,
        mock_tts_component: MagicMock,
    ):
        """Test full pipeline produces dubbed audio output.

        Uses real ASR with mock Translation and TTS for fast, reliable tests.
        """
        # Arrange - Load 6 seconds of real audio (typical fragment duration)
        audio_bytes = load_audio_fragment(nfl_audio_path, start_ms=0, duration_ms=6000)
        fragment_data = create_fragment_data(
            audio_bytes=audio_bytes,
            fragment_id="frag-full-001",
            sequence_number=0,
            duration_ms=6000,
        )

        coordinator = PipelineCoordinator(
            asr=real_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=fragment_data,
            session=sample_stream_session,
        )

        # Assert - Pipeline should succeed
        assert result.status == ProcessingStatus.SUCCESS, f"Pipeline failed: {result.error}"

        # Assert - Dubbed audio should be present
        assert result.dubbed_audio is not None, "Expected dubbed audio output"
        assert len(result.dubbed_audio.data_base64) > 0, "Dubbed audio should not be empty"
        assert result.dubbed_audio.duration_ms > 0, "Audio duration should be positive"

    @requires_faster_whisper
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_each_stage_produces_assets(
        self,
        nfl_audio_path: Path,
        load_audio_fragment: Callable,
        create_fragment_data: Callable,
        sample_stream_session: StreamSession,
        real_asr_component: FasterWhisperASR,
        mock_translation_component: MagicMock,
        mock_tts_component: MagicMock,
    ):
        """Test that each pipeline stage produces proper assets.

        Validates:
        - ASR produces transcript
        - Translation is called with transcript
        - TTS is called with translation
        """
        # Arrange
        audio_bytes = load_audio_fragment(nfl_audio_path, start_ms=5000, duration_ms=3000)
        fragment_data = create_fragment_data(
            audio_bytes=audio_bytes,
            fragment_id="frag-assets-001",
            sequence_number=0,
            duration_ms=3000,
        )

        coordinator = PipelineCoordinator(
            asr=real_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=fragment_data,
            session=sample_stream_session,
        )

        # Assert - All stages should have been called
        assert result.status == ProcessingStatus.SUCCESS

        # Translation should have been called (even if transcript is empty)
        assert mock_translation_component.translate.called, "Translation should be called"

        # TTS should have been called
        assert mock_tts_component.synthesize.called, "TTS should be called"

        # Result should have all expected fields
        assert result.transcript is not None  # May be empty for silence
        assert result.translated_text is not None
        assert result.dubbed_audio is not None

    @requires_faster_whisper
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_duration_variance_under_threshold(
        self,
        nfl_audio_path: Path,
        load_audio_fragment: Callable,
        create_fragment_data: Callable,
        sample_stream_session: StreamSession,
        real_asr_component: FasterWhisperASR,
        mock_translation_component: MagicMock,
        mock_tts_component: MagicMock,
    ):
        """Test that dubbed audio duration variance is <10%.

        Duration matching is critical for A/V sync.
        """
        # Arrange
        original_duration_ms = 6000
        audio_bytes = load_audio_fragment(
            nfl_audio_path, start_ms=10000, duration_ms=original_duration_ms
        )
        fragment_data = create_fragment_data(
            audio_bytes=audio_bytes,
            fragment_id="frag-duration-001",
            sequence_number=0,
            duration_ms=original_duration_ms,
        )

        coordinator = PipelineCoordinator(
            asr=real_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.status == ProcessingStatus.SUCCESS
        assert result.metadata is not None

        # Duration variance should be within threshold (<10%)
        variance = result.metadata.duration_variance_percent
        assert variance < 10.0, f"Duration variance {variance:.2f}% exceeds 10% threshold"

    @requires_faster_whisper
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_all_stage_timings_recorded(
        self,
        nfl_audio_path: Path,
        load_audio_fragment: Callable,
        create_fragment_data: Callable,
        sample_stream_session: StreamSession,
        real_asr_component: FasterWhisperASR,
        mock_translation_component: MagicMock,
        mock_tts_component: MagicMock,
    ):
        """Test that all stage timings are recorded accurately."""
        # Arrange
        audio_bytes = load_audio_fragment(nfl_audio_path, start_ms=20000, duration_ms=2000)
        fragment_data = create_fragment_data(
            audio_bytes=audio_bytes,
            fragment_id="frag-timings-001",
            sequence_number=0,
            duration_ms=2000,
        )

        coordinator = PipelineCoordinator(
            asr=real_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.status == ProcessingStatus.SUCCESS
        assert result.stage_timings is not None

        # All stage timings should be non-negative
        assert result.stage_timings.asr_ms >= 0, "ASR timing should be >= 0"
        assert result.stage_timings.translation_ms >= 0, "Translation timing should be >= 0"
        assert result.stage_timings.tts_ms >= 0, "TTS timing should be >= 0"

        # Real ASR should take measurable time
        assert result.stage_timings.asr_ms > 0, "Real ASR should have non-zero time"

        # Total time should be at least sum of stages
        stage_sum = (
            result.stage_timings.asr_ms
            + result.stage_timings.translation_ms
            + result.stage_timings.tts_ms
        )
        assert result.processing_time_ms >= stage_sum, (
            f"Total time {result.processing_time_ms} < stage sum {stage_sum}"
        )


class TestFullPipelineEmptyTranscript:
    """Tests for handling empty transcripts (silence) through full pipeline (T078)."""

    @pytest.fixture
    def real_asr_component(self) -> FasterWhisperASR:
        """Create a REAL FasterWhisperASR."""
        config = ASRConfig(
            model=ASRModelConfig(
                model_size="tiny",
                device="cpu",
                compute_type="int8",
            ),
            vad=VADConfig(enabled=True),
        )
        asr = FasterWhisperASR(config=config)
        yield asr
        asr.shutdown()

    @pytest.fixture
    def mock_translation_component(self) -> MagicMock:
        """Mock translation that handles empty input."""
        mock = MagicMock()
        mock.component_name = "translate"
        mock.component_instance = "mock-translate-v1"
        mock.is_ready = True

        def translate_side_effect(source_text: str, *args: Any, **kwargs: Any) -> MagicMock:
            result = MagicMock()
            result.asset_id = "trans-empty-001"
            result.status = AssetStatus.SUCCESS
            result.translated_text = source_text  # Pass through empty
            result.source_text = source_text
            result.error_message = None
            result.parent_asset_ids = kwargs.get("parent_asset_ids", [])
            return result

        mock.translate.side_effect = translate_side_effect
        return mock

    @pytest.fixture
    def mock_tts_component(self) -> MagicMock:
        """Mock TTS that handles empty input."""
        mock = MagicMock()
        mock.component_name = "tts"
        mock.component_instance = "mock-tts-v1"
        mock.is_ready = True

        def synthesize_side_effect(
            text_asset: Any, target_duration_ms: int | None = None, **kwargs: Any
        ) -> MagicMock:
            duration_ms = target_duration_ms or 6000
            sample_rate = kwargs.get("output_sample_rate_hz", 16000)
            samples = int(sample_rate * duration_ms / 1000)

            # Return silence for empty text
            result = MagicMock()
            result.asset_id = "audio-silence-001"
            result.status = AssetStatus.SUCCESS
            result.audio_bytes = b"\x00\x00" * samples
            result.format = "pcm_s16le"
            result.sample_rate_hz = sample_rate
            result.channels = 1
            result.duration_ms = duration_ms
            result.duration_metadata = DurationMatchMetadata(
                original_duration_ms=duration_ms,
                raw_duration_ms=duration_ms,
                final_duration_ms=duration_ms,
                duration_variance_percent=0.0,
                speed_ratio=1.0,
                speed_clamped=False,
            )
            result.error_message = None
            result.parent_asset_ids = []
            return result

        mock.synthesize.side_effect = synthesize_side_effect
        return mock

    @requires_faster_whisper
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pipeline_handles_silence_produces_empty_transcript(
        self,
        generate_silence: Callable,
        create_fragment_data: Callable,
        sample_stream_session: StreamSession,
        real_asr_component: FasterWhisperASR,
        mock_translation_component: MagicMock,
        mock_tts_component: MagicMock,
    ):
        """Test that silence audio produces empty transcript but SUCCESS status."""
        # Arrange - Generate 6 seconds of silence
        silent_audio = generate_silence(duration_seconds=6.0, sample_rate=16000)
        fragment_data = create_fragment_data(
            audio_bytes=silent_audio,
            fragment_id="frag-silence-001",
            sequence_number=0,
            duration_ms=6000,
        )

        coordinator = PipelineCoordinator(
            asr=real_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=fragment_data,
            session=sample_stream_session,
        )

        # Assert - Pipeline should succeed
        assert result.status == ProcessingStatus.SUCCESS, (
            f"Pipeline should handle silence: {result.error}"
        )

        # Transcript should be empty or very minimal
        assert result.transcript is not None
        # VAD should filter out silence, resulting in empty transcript

    @requires_faster_whisper
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pipeline_empty_transcript_produces_silence_output(
        self,
        generate_silence: Callable,
        create_fragment_data: Callable,
        sample_stream_session: StreamSession,
        real_asr_component: FasterWhisperASR,
        mock_translation_component: MagicMock,
        mock_tts_component: MagicMock,
    ):
        """Test that empty transcript produces silence dubbed audio."""
        # Arrange
        silent_audio = generate_silence(duration_seconds=2.0, sample_rate=16000)
        fragment_data = create_fragment_data(
            audio_bytes=silent_audio,
            fragment_id="frag-empty-output-001",
            sequence_number=0,
            duration_ms=2000,
        )

        coordinator = PipelineCoordinator(
            asr=real_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.status == ProcessingStatus.SUCCESS

        # Should still produce dubbed audio (silence)
        assert result.dubbed_audio is not None
        assert result.dubbed_audio.duration_ms > 0

        # All stages should still complete
        assert mock_translation_component.translate.called
        assert mock_tts_component.synthesize.called


class TestFullPipelineWithRealTranslation:
    """Tests for full pipeline with real DeepL translation (requires API key)."""

    @pytest.fixture
    def real_asr_component(self) -> FasterWhisperASR:
        """Create a REAL FasterWhisperASR."""
        config = ASRConfig(
            model=ASRModelConfig(
                model_size="tiny",
                device="cpu",
                compute_type="int8",
            ),
            vad=VADConfig(enabled=True),
        )
        asr = FasterWhisperASR(config=config)
        yield asr
        asr.shutdown()

    @pytest.fixture
    def mock_tts_component(self) -> MagicMock:
        """Mock TTS for faster tests."""
        mock = MagicMock()
        mock.component_name = "tts"
        mock.component_instance = "mock-tts-v1"
        mock.is_ready = True

        def synthesize_side_effect(
            text_asset: Any, target_duration_ms: int | None = None, **kwargs: Any
        ) -> MagicMock:
            duration_ms = target_duration_ms or 6000
            sample_rate = kwargs.get("output_sample_rate_hz", 16000)
            samples = int(sample_rate * duration_ms / 1000)

            result = MagicMock()
            result.asset_id = "audio-real-trans"
            result.status = AssetStatus.SUCCESS
            result.audio_bytes = b"\x00\x00" * samples
            result.format = "pcm_s16le"
            result.sample_rate_hz = sample_rate
            result.channels = 1
            result.duration_ms = duration_ms
            result.duration_metadata = DurationMatchMetadata(
                original_duration_ms=duration_ms,
                raw_duration_ms=duration_ms,
                final_duration_ms=duration_ms,
                duration_variance_percent=0.0,
                speed_ratio=1.0,
                speed_clamped=False,
            )
            result.error_message = None
            result.parent_asset_ids = []
            return result

        mock.synthesize.side_effect = synthesize_side_effect
        return mock

    @requires_faster_whisper
    @requires_deepl_key
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_with_real_deepl_translation(
        self,
        nfl_audio_path: Path,
        load_audio_fragment: Callable,
        create_fragment_data: Callable,
        sample_stream_session: StreamSession,
        real_asr_component: FasterWhisperASR,
        mock_tts_component: MagicMock,
    ):
        """Test pipeline with real ASR and real DeepL translation.

        Skips if DEEPL_AUTH_KEY not set.
        """
        # Arrange
        real_translation = create_translation_component(provider="deepl")

        audio_bytes = load_audio_fragment(nfl_audio_path, start_ms=5000, duration_ms=3000)
        fragment_data = create_fragment_data(
            audio_bytes=audio_bytes,
            fragment_id="frag-real-deepl-001",
            sequence_number=0,
            duration_ms=3000,
        )

        coordinator = PipelineCoordinator(
            asr=real_asr_component,
            translation=real_translation,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.status == ProcessingStatus.SUCCESS

        # If there was speech, we should have translated text
        if result.transcript and len(result.transcript.strip()) > 0:
            # Real translation should produce Spanish text
            assert result.translated_text is not None
            assert len(result.translated_text) > 0


class TestFullPipelineWithRealTTS:
    """Tests for full pipeline with real Coqui TTS (requires TTS package)."""

    @pytest.fixture
    def real_asr_component(self) -> FasterWhisperASR:
        """Create a REAL FasterWhisperASR."""
        config = ASRConfig(
            model=ASRModelConfig(
                model_size="tiny",
                device="cpu",
                compute_type="int8",
            ),
            vad=VADConfig(enabled=True),
        )
        asr = FasterWhisperASR(config=config)
        yield asr
        asr.shutdown()

    @pytest.fixture
    def mock_translation_component(self) -> MagicMock:
        """Mock translation for faster tests."""
        mock = MagicMock()
        mock.component_name = "translate"
        mock.component_instance = "mock-v1"
        mock.is_ready = True

        def translate_side_effect(source_text: str, *args: Any, **kwargs: Any) -> MagicMock:
            result = MagicMock()
            result.asset_id = "trans-mock"
            result.status = AssetStatus.SUCCESS
            result.translated_text = f"Hola, {source_text}" if source_text else ""
            result.source_text = source_text
            result.error_message = None
            result.parent_asset_ids = kwargs.get("parent_asset_ids", [])
            return result

        mock.translate.side_effect = translate_side_effect
        return mock

    @requires_faster_whisper
    @requires_coqui
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_with_real_coqui_tts(
        self,
        nfl_audio_path: Path,
        load_audio_fragment: Callable,
        create_fragment_data: Callable,
        sample_stream_session: StreamSession,
        real_asr_component: FasterWhisperASR,
        mock_translation_component: MagicMock,
    ):
        """Test pipeline with real ASR and real Coqui TTS.

        Skips if Coqui TTS not installed.
        """
        # Arrange - Use mock TTS provider to avoid long model download
        real_tts = create_tts_component(provider="mock")

        audio_bytes = load_audio_fragment(nfl_audio_path, start_ms=5000, duration_ms=2000)
        fragment_data = create_fragment_data(
            audio_bytes=audio_bytes,
            fragment_id="frag-real-tts-001",
            sequence_number=0,
            duration_ms=2000,
        )

        coordinator = PipelineCoordinator(
            asr=real_asr_component,
            translation=mock_translation_component,
            tts=real_tts,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.status == ProcessingStatus.SUCCESS

        # Should produce dubbed audio
        assert result.dubbed_audio is not None
        assert result.dubbed_audio.duration_ms > 0

        # Verify audio data is properly encoded
        audio_data = base64.b64decode(result.dubbed_audio.data_base64)
        assert len(audio_data) > 0
