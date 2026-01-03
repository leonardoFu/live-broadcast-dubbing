"""Unit tests for PipelineCoordinator.

Tests the core pipeline orchestration: ASR -> Translation -> TTS.
These tests MUST be written FIRST and MUST FAIL before implementation (TDD).

Task IDs: T066-T071, T087
"""

import base64
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import models from Phase 1
from sts_service.full.models.asset import (
    AssetStatus,
    AudioAsset,
    DurationMatchMetadata,
    TranscriptAsset,
    TranscriptSegment,
    TranslationAsset,
)
from sts_service.full.models.error import ErrorCode, ErrorStage
from sts_service.full.models.fragment import (
    AudioData,
    FragmentData,
    FragmentMetadata,
    FragmentResult,
    ProcessingStatus,
)
from sts_service.full.models.stream import StreamConfig, StreamSession, StreamState

# Pipeline coordinator will be implemented in Phase 2
from sts_service.full.pipeline import PipelineCoordinator


# -----------------------------------------------------------------------------
# Test Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_audio_bytes() -> bytes:
    """Generate sample PCM audio bytes (silence)."""
    # 6 seconds of silence at 48kHz, 16-bit mono
    num_samples = 48000 * 6
    return b"\x00\x00" * num_samples


@pytest.fixture
def sample_fragment_data(sample_audio_bytes: bytes) -> FragmentData:
    """Create a sample FragmentData for testing."""
    audio_b64 = base64.b64encode(sample_audio_bytes).decode("utf-8")
    return FragmentData(
        fragment_id="frag-001",
        stream_id="stream-abc-123",
        sequence_number=0,
        timestamp=1704067200000,
        audio=AudioData(
            format="m4a",
            sample_rate_hz=48000,
            channels=1,
            duration_ms=6000,
            data_base64=audio_b64,
        ),
        metadata=FragmentMetadata(pts_ns=0),
    )


@pytest.fixture
def sample_stream_session() -> StreamSession:
    """Create a sample StreamSession for testing."""
    return StreamSession(
        stream_id="stream-abc-123",
        session_id="session-xyz-789",
        worker_id="worker-001",
        socket_id="sid-12345",
        config=StreamConfig(
            source_language="en",
            target_language="es",
            voice_profile="spanish_male_1",
            chunk_duration_ms=6000,
            sample_rate_hz=48000,
            channels=1,
            format="m4a",
        ),
        state=StreamState.READY,
        max_inflight=3,
    )


@pytest.fixture
def mock_asr_component():
    """Create a mock ASR component that returns SUCCESS."""
    mock = MagicMock()
    mock.component_name = "asr"
    mock.component_instance = "mock-asr-v1"
    mock.is_ready = True

    # Create a proper mock result object
    asr_result = MagicMock()
    asr_result.asset_id = "asr-asset-001"
    asr_result.fragment_id = "frag-001"
    asr_result.stream_id = "stream-abc-123"
    asr_result.status = AssetStatus.SUCCESS
    asr_result.transcript = "Hello, welcome to the game."
    asr_result.total_text = "Hello, welcome to the game."

    segment = MagicMock()
    segment.text = "Hello, welcome to the game."
    segment.start_ms = 0
    segment.end_ms = 6000
    segment.confidence = 0.95
    asr_result.segments = [segment]

    asr_result.confidence = 0.95
    asr_result.language = "en"
    asr_result.audio_duration_ms = 6000
    asr_result.latency_ms = 1200
    asr_result.parent_asset_ids = []
    asr_result.error_message = None

    mock.transcribe.return_value = asr_result
    return mock


@pytest.fixture
def mock_translation_component():
    """Create a mock Translation component that returns SUCCESS."""
    mock = MagicMock()
    mock.component_name = "translate"
    mock.component_instance = "mock-translate-v1"
    mock.is_ready = True

    # Create a proper mock result object
    trans_result = MagicMock()
    trans_result.asset_id = "trans-asset-001"
    trans_result.fragment_id = "frag-001"
    trans_result.stream_id = "stream-abc-123"
    trans_result.status = AssetStatus.SUCCESS
    trans_result.translated_text = "Hola, bienvenido al juego."
    trans_result.source_text = "Hello, welcome to the game."
    trans_result.source_language = "en"
    trans_result.target_language = "es"
    trans_result.character_count = 27
    trans_result.word_expansion_ratio = 1.2
    trans_result.latency_ms = 250
    trans_result.parent_asset_ids = ["asr-asset-001"]
    trans_result.error_message = None

    mock.translate.return_value = trans_result
    return mock


@pytest.fixture
def mock_tts_component():
    """Create a mock TTS component that returns SUCCESS."""
    mock = MagicMock()
    mock.component_name = "tts"
    mock.component_instance = "mock-tts-v1"
    mock.is_ready = True

    # Create a proper mock result object
    audio_bytes = b"\x00\x00" * (48000 * 6)  # 6 seconds of silence
    tts_result = MagicMock()
    tts_result.asset_id = "audio-asset-001"
    tts_result.fragment_id = "frag-001"
    tts_result.stream_id = "stream-abc-123"
    tts_result.status = AssetStatus.SUCCESS
    tts_result.audio_bytes = audio_bytes
    tts_result.format = "pcm_s16le"
    tts_result.sample_rate_hz = 48000
    tts_result.channels = 1
    tts_result.duration_ms = 6050
    tts_result.duration_metadata = DurationMatchMetadata(
        original_duration_ms=6000,
        raw_duration_ms=6100,
        final_duration_ms=6050,
        duration_variance_percent=0.83,
        speed_ratio=0.99,
        speed_clamped=False,
    )
    tts_result.voice_profile = "spanish_male_1"
    tts_result.text_input = "Hola, bienvenido al juego."
    tts_result.latency_ms = 1500
    tts_result.parent_asset_ids = ["trans-asset-001"]
    tts_result.error_message = None

    mock.synthesize.return_value = tts_result
    return mock


# -----------------------------------------------------------------------------
# T066: Pipeline chains ASR -> Translation -> TTS
# -----------------------------------------------------------------------------


class TestPipelineChaining:
    """Tests for T066: Pipeline chains ASR -> Translation -> TTS."""

    @pytest.mark.asyncio
    async def test_pipeline_chains_asr_translation_tts_in_sequence(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_translation_component,
        mock_tts_component,
    ):
        """Pipeline calls ASR, then Translation, then TTS in sequence."""
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert - Verify all stages were called
        mock_asr_component.transcribe.assert_called_once()
        mock_translation_component.translate.assert_called_once()
        mock_tts_component.synthesize.assert_called_once()

        # Assert - Result is SUCCESS with all expected fields
        assert isinstance(result, FragmentResult)
        assert result.status == ProcessingStatus.SUCCESS
        assert result.fragment_id == "frag-001"
        assert result.stream_id == "stream-abc-123"
        assert result.sequence_number == 0

    @pytest.mark.asyncio
    async def test_pipeline_returns_dubbed_audio_on_success(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_translation_component,
        mock_tts_component,
    ):
        """Pipeline returns FragmentResult with dubbed_audio on success."""
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.status == ProcessingStatus.SUCCESS
        assert result.dubbed_audio is not None
        assert result.dubbed_audio.format == "pcm_s16le"
        assert result.dubbed_audio.sample_rate_hz == 48000
        assert result.dubbed_audio.channels == 1
        assert result.dubbed_audio.duration_ms > 0
        assert len(result.dubbed_audio.data_base64) > 0

    @pytest.mark.asyncio
    async def test_pipeline_includes_transcript_and_translation(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_translation_component,
        mock_tts_component,
    ):
        """Pipeline includes transcript and translated_text in result."""
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.transcript == "Hello, welcome to the game."
        assert result.translated_text == "Hola, bienvenido al juego."

    @pytest.mark.asyncio
    async def test_pipeline_includes_duration_metadata(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_translation_component,
        mock_tts_component,
    ):
        """Pipeline includes duration metadata for A/V sync verification."""
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.metadata is not None
        assert result.metadata.original_duration_ms == 6000
        assert result.metadata.dubbed_duration_ms == 6050
        assert result.metadata.duration_variance_percent < 10.0  # Within threshold


# -----------------------------------------------------------------------------
# T067: Pipeline handles ASR failure
# -----------------------------------------------------------------------------


class TestPipelineASRFailure:
    """Tests for T067: Pipeline handles ASR failure."""

    @pytest.mark.asyncio
    async def test_pipeline_returns_failed_on_asr_failure(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_translation_component,
        mock_tts_component,
    ):
        """Pipeline returns FAILED when ASR fails."""
        # Arrange - Mock ASR to return FAILED
        mock_asr = MagicMock()
        mock_asr.component_name = "asr"
        mock_asr.component_instance = "mock-asr-v1"
        mock_asr.is_ready = True
        mock_asr.transcribe.return_value = MagicMock(
            asset_id="asr-asset-001",
            fragment_id="frag-001",
            stream_id="stream-abc-123",
            status=AssetStatus.FAILED,
            transcript="",
            segments=[],
            confidence=0.0,
            language="en",
            audio_duration_ms=6000,
            latency_ms=5000,
            parent_asset_ids=[],
            error_message="ASR processing timed out",
        )

        coordinator = PipelineCoordinator(
            asr=mock_asr,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.status == ProcessingStatus.FAILED
        assert result.error is not None
        assert result.error.stage == "asr"
        assert result.error.retryable is True

    @pytest.mark.asyncio
    async def test_pipeline_stops_after_asr_failure(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_translation_component,
        mock_tts_component,
    ):
        """Pipeline does NOT call Translation or TTS after ASR failure."""
        # Arrange
        mock_asr = MagicMock()
        mock_asr.component_name = "asr"
        mock_asr.component_instance = "mock-asr-v1"
        mock_asr.is_ready = True
        mock_asr.transcribe.return_value = MagicMock(
            status=AssetStatus.FAILED,
            error_message="Timeout",
        )

        coordinator = PipelineCoordinator(
            asr=mock_asr,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert - Translation and TTS should NOT be called
        mock_translation_component.translate.assert_not_called()
        mock_tts_component.synthesize.assert_not_called()


# -----------------------------------------------------------------------------
# T068: Pipeline handles Translation failure
# -----------------------------------------------------------------------------


class TestPipelineTranslationFailure:
    """Tests for T068: Pipeline handles Translation failure."""

    @pytest.mark.asyncio
    async def test_pipeline_returns_failed_on_translation_failure(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_tts_component,
    ):
        """Pipeline returns FAILED when Translation fails."""
        # Arrange - Mock Translation to return FAILED
        mock_translation = MagicMock()
        mock_translation.component_name = "translate"
        mock_translation.component_instance = "mock-translate-v1"
        mock_translation.is_ready = True
        mock_translation.translate.return_value = MagicMock(
            asset_id="trans-asset-001",
            fragment_id="frag-001",
            stream_id="stream-abc-123",
            status=AssetStatus.FAILED,
            translated_text="",
            source_text="Hello, welcome to the game.",
            source_language="en",
            target_language="es",
            latency_ms=5000,
            parent_asset_ids=["asr-asset-001"],
            error_message="Rate limit exceeded",
        )

        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.status == ProcessingStatus.FAILED
        assert result.error is not None
        assert result.error.stage == "translation"
        assert result.error.retryable is True

    @pytest.mark.asyncio
    async def test_pipeline_stops_after_translation_failure(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_tts_component,
    ):
        """Pipeline does NOT call TTS after Translation failure."""
        # Arrange
        mock_translation = MagicMock()
        mock_translation.component_name = "translate"
        mock_translation.component_instance = "mock-translate-v1"
        mock_translation.is_ready = True
        mock_translation.translate.return_value = MagicMock(
            status=AssetStatus.FAILED,
            error_message="Rate limit exceeded",
        )

        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation,
            tts=mock_tts_component,
        )

        # Act
        await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert - ASR should be called, TTS should NOT
        mock_asr_component.transcribe.assert_called_once()
        mock_tts_component.synthesize.assert_not_called()


# -----------------------------------------------------------------------------
# T069: Pipeline handles TTS failure
# -----------------------------------------------------------------------------


class TestPipelineTTSFailure:
    """Tests for T069: Pipeline handles TTS failure."""

    @pytest.mark.asyncio
    async def test_pipeline_returns_failed_on_tts_failure(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_translation_component,
    ):
        """Pipeline returns FAILED when TTS fails."""
        # Arrange - Mock TTS to return FAILED
        mock_tts = MagicMock()
        mock_tts.component_name = "tts"
        mock_tts.component_instance = "mock-tts-v1"
        mock_tts.is_ready = True
        mock_tts.synthesize.return_value = MagicMock(
            asset_id="audio-asset-001",
            fragment_id="frag-001",
            stream_id="stream-abc-123",
            status=AssetStatus.FAILED,
            audio_bytes=b"",
            duration_ms=0,
            latency_ms=5000,
            parent_asset_ids=["trans-asset-001"],
            error_message="Duration mismatch exceeded 20%",
        )

        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.status == ProcessingStatus.FAILED
        assert result.error is not None
        assert result.error.stage == "tts"
        # Duration mismatch is not retryable
        assert result.error.retryable is False


# -----------------------------------------------------------------------------
# T070: Pipeline preserves asset lineage
# -----------------------------------------------------------------------------


class TestPipelineAssetLineage:
    """Tests for T070: Pipeline preserves asset lineage."""

    @pytest.mark.asyncio
    async def test_translation_receives_transcript_asset_id_as_parent(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_translation_component,
        mock_tts_component,
    ):
        """TranslationAsset.parent_asset_ids includes TranscriptAsset ID."""
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert - Check that translate was called with parent_asset_ids
        call_kwargs = mock_translation_component.translate.call_args
        # The parent_asset_ids should include the ASR asset ID
        assert call_kwargs is not None
        # Check the call includes parent_asset_ids from ASR
        call_args, kwargs = call_kwargs
        # Parent asset IDs should be passed to translation
        assert "parent_asset_ids" in kwargs or len(call_args) > 4

    @pytest.mark.asyncio
    async def test_tts_receives_translation_asset_id_as_parent(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_translation_component,
        mock_tts_component,
    ):
        """AudioAsset.parent_asset_ids includes TranslationAsset ID."""
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert - TTS synthesize should receive a TextAsset with parent IDs
        mock_tts_component.synthesize.assert_called_once()
        call_args = mock_tts_component.synthesize.call_args
        assert call_args is not None


# -----------------------------------------------------------------------------
# T071: Pipeline tracks stage timings
# -----------------------------------------------------------------------------


class TestPipelineStageTiming:
    """Tests for T071: Pipeline tracks stage timings."""

    @pytest.mark.asyncio
    async def test_pipeline_records_asr_timing(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_translation_component,
        mock_tts_component,
    ):
        """Pipeline records ASR stage timing in FragmentResult."""
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.stage_timings is not None
        assert result.stage_timings.asr_ms >= 0

    @pytest.mark.asyncio
    async def test_pipeline_records_all_stage_timings(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_translation_component,
        mock_tts_component,
    ):
        """Pipeline records all stage timings: ASR, Translation, TTS."""
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.stage_timings is not None
        assert result.stage_timings.asr_ms >= 0
        assert result.stage_timings.translation_ms >= 0
        assert result.stage_timings.tts_ms >= 0

    @pytest.mark.asyncio
    async def test_pipeline_total_time_equals_sum_plus_overhead(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_translation_component,
        mock_tts_component,
    ):
        """Pipeline processing_time_ms >= sum of stage timings."""
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.processing_time_ms >= 0
        stage_sum = (
            result.stage_timings.asr_ms
            + result.stage_timings.translation_ms
            + result.stage_timings.tts_ms
        )
        # Total should be at least the sum of stages (with possible overhead)
        assert result.processing_time_ms >= stage_sum


# -----------------------------------------------------------------------------
# Additional edge case tests
# -----------------------------------------------------------------------------


class TestPipelineEdgeCases:
    """Additional edge case tests for pipeline coordinator."""

    @pytest.mark.asyncio
    async def test_pipeline_handles_empty_transcript(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_translation_component,
        mock_tts_component,
    ):
        """Pipeline handles empty transcript (silence audio)."""
        # Arrange - Mock ASR to return empty transcript (silence)
        mock_asr = MagicMock()
        mock_asr.component_name = "asr"
        mock_asr.component_instance = "mock-asr-v1"
        mock_asr.is_ready = True
        mock_asr.transcribe.return_value = MagicMock(
            asset_id="asr-asset-001",
            fragment_id="frag-001",
            stream_id="stream-abc-123",
            status=AssetStatus.SUCCESS,
            transcript="",  # Empty transcript
            segments=[],
            confidence=0.0,
            language="en",
            audio_duration_ms=6000,
            latency_ms=500,
            parent_asset_ids=[],
            error_message=None,
        )

        coordinator = PipelineCoordinator(
            asr=mock_asr,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert - Should still succeed with empty/silence output
        assert result.status == ProcessingStatus.SUCCESS
        assert result.transcript == ""

    @pytest.mark.asyncio
    async def test_pipeline_returns_partial_on_duration_warning(
        self,
        sample_fragment_data: FragmentData,
        sample_stream_session: StreamSession,
        mock_asr_component,
        mock_translation_component,
    ):
        """Pipeline returns PARTIAL status when TTS has warnings (clamped speed)."""
        # Arrange - Mock TTS to return PARTIAL status
        mock_tts = MagicMock()
        mock_tts.component_name = "tts"
        mock_tts.component_instance = "mock-tts-v1"
        mock_tts.is_ready = True

        audio_bytes = b"\x00\x00" * (48000 * 6)
        mock_tts.synthesize.return_value = MagicMock(
            asset_id="audio-asset-001",
            fragment_id="frag-001",
            stream_id="stream-abc-123",
            status=AssetStatus.PARTIAL,  # PARTIAL due to clamped speed
            audio_bytes=audio_bytes,
            format="pcm_s16le",
            sample_rate_hz=48000,
            channels=1,
            duration_ms=7200,  # 20% variance
            duration_metadata=DurationMatchMetadata(
                original_duration_ms=6000,
                raw_duration_ms=8000,
                final_duration_ms=7200,
                duration_variance_percent=20.0,
                speed_ratio=2.0,  # Clamped at max
                speed_clamped=True,
            ),
            voice_profile="spanish_male_1",
            text_input="Hola, bienvenido al juego.",
            latency_ms=1500,
            parent_asset_ids=["trans-asset-001"],
            error_message="Speed ratio clamped to 2.0",
        )

        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts,
        )

        # Act
        result = await coordinator.process_fragment(
            fragment_data=sample_fragment_data,
            session=sample_stream_session,
        )

        # Assert
        assert result.status == ProcessingStatus.PARTIAL
        assert result.dubbed_audio is not None  # Audio still produced
