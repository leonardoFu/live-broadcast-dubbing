"""
Integration tests: Translation -> TTS handoff.

These tests verify the pipeline integration between Translation and TTS modules:
- TextAsset flows correctly to TTS component
- Asset lineage (parent_asset_ids) is properly tracked
- Metadata (stream_id, sequence_number, language) flows through
- Multi-fragment stream processing works correctly

Requirements:
- TTS mock components (no external dependencies)
"""

from sts_service.translation.factory import create_translation_component
from sts_service.translation.models import TextAsset, TranslationStatus
from sts_service.tts.factory import create_tts_component
from sts_service.tts.mock import MockTTSFailOnce, MockTTSFixedTone
from sts_service.tts.models import AudioAsset, AudioStatus

from .conftest import create_text_asset, synthesize_from_translation

# =============================================================================
# Test: Translation -> TTS Handoff (Mock-based)
# =============================================================================


class TestTranslationToTTSHandoff:
    """Integration tests for Translation -> TTS handoff using mock components."""

    def test_text_asset_to_audio_asset_basic(
        self,
        english_greeting_text_asset: TextAsset,
    ):
        """Test basic TextAsset -> AudioAsset conversion."""
        tts = MockTTSFixedTone()

        audio_asset = synthesize_from_translation(
            text_asset=english_greeting_text_asset,
            tts=tts,
        )

        # Verify AudioAsset is valid
        assert isinstance(audio_asset, AudioAsset)
        assert audio_asset.status == AudioStatus.SUCCESS
        assert audio_asset.duration_ms > 0

        # Verify lineage tracking
        assert english_greeting_text_asset.asset_id in audio_asset.parent_asset_ids

        # Verify metadata flow
        assert audio_asset.stream_id == english_greeting_text_asset.stream_id
        assert audio_asset.sequence_number == english_greeting_text_asset.sequence_number
        assert audio_asset.language == english_greeting_text_asset.target_language

    def test_spanish_text_asset_synthesis(
        self,
        spanish_greeting_text_asset: TextAsset,
    ):
        """Test TTS synthesis with Spanish text asset."""
        tts = MockTTSFixedTone()

        audio_asset = synthesize_from_translation(
            text_asset=spanish_greeting_text_asset,
            tts=tts,
        )

        assert audio_asset.status == AudioStatus.SUCCESS
        assert audio_asset.language == "es"
        assert spanish_greeting_text_asset.asset_id in audio_asset.parent_asset_ids

    def test_component_instance_tracking(
        self,
        english_greeting_text_asset: TextAsset,
    ):
        """Test component instance is correctly recorded."""
        tts = MockTTSFixedTone()

        audio_asset = synthesize_from_translation(
            text_asset=english_greeting_text_asset,
            tts=tts,
        )

        # TTS component instance should be recorded
        assert audio_asset.component == "tts"
        assert audio_asset.component_instance == "mock-fixed-tone-v1"

    def test_preprocessed_text_tracking(
        self,
        english_greeting_text_asset: TextAsset,
    ):
        """Test preprocessed text is tracked in AudioAsset."""
        tts = MockTTSFixedTone()

        audio_asset = synthesize_from_translation(
            text_asset=english_greeting_text_asset,
            tts=tts,
        )

        # Preprocessed text should match input (mock does basic preprocessing)
        assert audio_asset.preprocessed_text is not None
        assert audio_asset.preprocessed_text == english_greeting_text_asset.translated_text


# =============================================================================
# Test: Asset Lineage Chain
# =============================================================================


class TestAssetLineageChain:
    """Test asset lineage tracking through the Translation -> TTS pipeline."""

    def test_lineage_chain_integrity(
        self,
        text_asset_factory,
    ):
        """Verify parent_asset_ids correctly chain Translation -> TTS."""
        # Create text asset (simulating Translation output)
        text_asset = text_asset_factory(
            text="This is a test sentence for lineage tracking.",
            stream_id="lineage-test-stream",
            sequence_number=42,
        )

        tts = MockTTSFixedTone()
        audio_asset = synthesize_from_translation(text_asset, tts)

        # Verify lineage chain
        assert text_asset.component == "translate"
        assert audio_asset.component == "tts"
        assert text_asset.asset_id in audio_asset.parent_asset_ids
        assert audio_asset.stream_id == text_asset.stream_id
        assert audio_asset.sequence_number == text_asset.sequence_number

        # Verify unique asset IDs
        assert audio_asset.asset_id != text_asset.asset_id

        print("\n--- Asset Lineage Chain ---")
        print(f"Translation Asset ID: {text_asset.asset_id}")
        print(f"TTS Asset ID: {audio_asset.asset_id}")
        print(f"TTS Parent IDs: {audio_asset.parent_asset_ids}")
        print(f"Lineage correct: {text_asset.asset_id in audio_asset.parent_asset_ids}")

    def test_lineage_preserved_on_retry(
        self,
        text_asset_factory,
    ):
        """Test lineage is preserved even when TTS fails and retries."""
        text_asset = text_asset_factory(
            text="Test sentence for retry scenario.",
            stream_id="retry-test",
            sequence_number=1,
        )

        tts = MockTTSFailOnce()

        # First call - should fail
        first_result = synthesize_from_translation(text_asset, tts)
        assert first_result.status == AudioStatus.FAILED
        # Even failed results should track lineage
        assert text_asset.asset_id in first_result.parent_asset_ids

        # Retry - should succeed
        retry_result = synthesize_from_translation(text_asset, tts)
        assert retry_result.status == AudioStatus.SUCCESS
        assert text_asset.asset_id in retry_result.parent_asset_ids


# =============================================================================
# Test: Multi-Fragment Stream Processing
# =============================================================================


class TestMultiFragmentStreamProcessing:
    """Test processing multiple sequential fragments as a stream."""

    def test_multi_fragment_pipeline(
        self,
        multi_fragment_text_assets: list[TextAsset],
    ):
        """Test multiple fragments are processed with correct lineage."""
        tts = MockTTSFixedTone()
        results = []

        for text_asset in multi_fragment_text_assets:
            audio_asset = synthesize_from_translation(text_asset, tts)
            results.append(
                {
                    "sequence": audio_asset.sequence_number,
                    "text_asset_id": text_asset.asset_id,
                    "audio_asset_id": audio_asset.asset_id,
                    "status": audio_asset.status,
                    "lineage_correct": text_asset.asset_id in audio_asset.parent_asset_ids,
                }
            )

        # Verify all fragments processed
        assert len(results) == len(multi_fragment_text_assets)

        # Verify all lineages are correct
        for result in results:
            assert result["lineage_correct"], f"Fragment {result['sequence']} has incorrect lineage"
            assert result["status"] == AudioStatus.SUCCESS

        # Verify sequence numbers are preserved
        expected_sequences = list(range(len(multi_fragment_text_assets)))
        actual_sequences = [r["sequence"] for r in results]
        assert actual_sequences == expected_sequences

    def test_stream_id_consistency(
        self,
        multi_fragment_text_assets: list[TextAsset],
    ):
        """Test stream_id is consistent across all fragments."""
        tts = MockTTSFixedTone()

        audio_assets = [
            synthesize_from_translation(text_asset, tts)
            for text_asset in multi_fragment_text_assets
        ]

        # All fragments should have same stream_id
        stream_ids = {audio.stream_id for audio in audio_assets}
        assert len(stream_ids) == 1
        assert "integration-test-stream" in stream_ids


# =============================================================================
# Test: Full Pipeline with Real Translation (Mock-based)
# =============================================================================


class TestFullPipelineWithMockTranslation:
    """End-to-end tests using real Translation component with mock TTS."""

    def test_translation_to_tts_pipeline(self):
        """Test full pipeline: source text -> Translation -> TTS."""
        # Step 1: Create mock translator
        translator = create_translation_component(mock=True)

        # Step 2: Translate source text
        text_asset = translator.translate(
            source_text="This is a test of the full pipeline.",
            stream_id="full-pipeline-test",
            sequence_number=0,
            source_language="en",
            target_language="es",
            parent_asset_ids=[],  # Root asset has no parents
        )

        assert text_asset.status == TranslationStatus.SUCCESS

        # Step 3: Synthesize with TTS
        tts = create_tts_component(provider="mock")
        audio_asset = synthesize_from_translation(text_asset, tts)

        # Verify pipeline integrity
        assert audio_asset.status == AudioStatus.SUCCESS
        assert text_asset.asset_id in audio_asset.parent_asset_ids
        assert audio_asset.stream_id == "full-pipeline-test"
        assert audio_asset.sequence_number == 0

        print("\n--- Full Pipeline: Translation -> TTS ---")
        print("Source: This is a test of the full pipeline.")
        print(f"Translated: {text_asset.translated_text}")
        print(f"Audio Duration: {audio_asset.duration_ms}ms")
        print(f"Lineage: {text_asset.asset_id} -> {audio_asset.asset_id}")

    def test_pipeline_with_target_duration(self):
        """Test pipeline with duration matching specified."""
        translator = create_translation_component(mock=True)

        text_asset = translator.translate(
            source_text="Short test sentence.",
            stream_id="duration-test",
            sequence_number=0,
            source_language="en",
            target_language="es",
            parent_asset_ids=[],  # Root asset has no parents
        )

        tts = create_tts_component(provider="mock")

        # Request specific target duration
        target_duration_ms = 2000
        audio_asset = synthesize_from_translation(
            text_asset,
            tts,
            target_duration_ms=target_duration_ms,
        )

        assert audio_asset.status == AudioStatus.SUCCESS
        # Mock should respect target duration
        assert audio_asset.duration_ms == target_duration_ms


# =============================================================================
# Test: Error Handling in Pipeline
# =============================================================================


class TestPipelineErrorHandling:
    """Test error handling in the Translation -> TTS pipeline."""

    def test_empty_text_produces_error(self):
        """Test that empty text produces an error."""
        # Create text asset with empty content
        text_asset = create_text_asset(
            text="   ",  # Whitespace only
            stream_id="error-test",
            sequence_number=0,
        )

        from sts_service.tts.coqui_provider import CoquiTTSComponent

        tts = CoquiTTSComponent()

        audio_asset = synthesize_from_translation(text_asset, tts)

        # Should fail with error
        assert audio_asset.status == AudioStatus.FAILED
        assert audio_asset.has_errors
        assert len(audio_asset.errors) > 0

        # Error should be non-retryable (invalid input)
        assert not audio_asset.is_retryable

    def test_retryable_error_handling(
        self,
        english_greeting_text_asset: TextAsset,
    ):
        """Test retryable error behavior with MockTTSFailOnce."""
        tts = MockTTSFailOnce()

        # First call fails with retryable error
        first_result = synthesize_from_translation(english_greeting_text_asset, tts)
        assert first_result.status == AudioStatus.FAILED
        assert first_result.is_retryable

        # Second call succeeds
        retry_result = synthesize_from_translation(english_greeting_text_asset, tts)
        assert retry_result.status == AudioStatus.SUCCESS


# =============================================================================
# Test: Processing Metadata
# =============================================================================


class TestProcessingMetadata:
    """Test processing metadata is correctly tracked."""

    def test_processing_time_recorded(
        self,
        english_greeting_text_asset: TextAsset,
    ):
        """Test processing time is recorded in AudioAsset."""
        tts = MockTTSFixedTone()

        audio_asset = synthesize_from_translation(english_greeting_text_asset, tts)

        assert audio_asset.processing_time_ms is not None
        assert audio_asset.processing_time_ms >= 0

    def test_voice_cloning_flag(
        self,
        english_greeting_text_asset: TextAsset,
    ):
        """Test voice_cloning_used flag is set correctly."""
        tts = MockTTSFixedTone()

        audio_asset = synthesize_from_translation(english_greeting_text_asset, tts)

        # Mock doesn't use voice cloning
        assert audio_asset.voice_cloning_used is False

    def test_audio_format_metadata(
        self,
        english_greeting_text_asset: TextAsset,
    ):
        """Test audio format metadata is correct."""
        tts = MockTTSFixedTone()

        audio_asset = synthesize_from_translation(
            english_greeting_text_asset,
            tts,
            output_sample_rate_hz=16000,
            output_channels=1,
        )

        assert audio_asset.sample_rate_hz == 16000
        assert audio_asset.channels == 1
        assert audio_asset.audio_format.value == "pcm_f32le"
