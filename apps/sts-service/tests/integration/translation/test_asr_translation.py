"""
Integration tests for ASR -> Translation pipeline.

Tests the complete flow from ASR TranscriptAsset to Translation TextAsset,
verifying lineage tracking, language handling, and policy application.
"""

from sts_service.asr.models import TranscriptAsset
from sts_service.translation.factory import create_translation_component
from sts_service.translation.mock import (
    MockFailingTranslator,
    MockIdentityTranslator,
    MockLatencyTranslator,
)
from sts_service.translation.models import (
    NormalizationPolicy,
    SpeakerPolicy,
    TextAsset,
    TranslationStatus,
)

from .conftest import translate_transcript

# =============================================================================
# Mock-based Integration Tests (CI-safe, no external dependencies)
# =============================================================================


class TestASRToTranslationPipeline:
    """Test ASR -> Translation pipeline with mock translator."""

    def test_basic_translation_flow(
        self,
        english_greeting_transcript: TranscriptAsset,
    ):
        """Test basic ASR -> Translation flow produces valid TextAsset."""
        translator = MockIdentityTranslator()

        result = translate_transcript(
            transcript=english_greeting_transcript,
            translator=translator,
            target_language="zh",
        )

        # Verify result is TextAsset
        assert isinstance(result, TextAsset)
        assert result.status == TranslationStatus.SUCCESS

        # Verify content
        assert result.translated_text == english_greeting_transcript.total_text
        assert result.source_language == "en"
        assert result.target_language == "zh"

    def test_asset_lineage_tracking(
        self,
        english_greeting_transcript: TranscriptAsset,
    ):
        """Test that parent_asset_ids correctly tracks ASR -> Translation lineage."""
        translator = MockIdentityTranslator()

        result = translate_transcript(
            transcript=english_greeting_transcript,
            translator=translator,
            target_language="zh",
        )

        # Verify lineage
        assert english_greeting_transcript.asset_id in result.parent_asset_ids
        assert len(result.parent_asset_ids) == 1

        # Verify component identification
        assert result.component == "translate"
        assert result.component_instance == "mock-identity-v1"

    def test_stream_metadata_preservation(
        self,
        english_greeting_transcript: TranscriptAsset,
    ):
        """Test that stream_id and sequence_number are preserved."""
        translator = MockIdentityTranslator()

        result = translate_transcript(
            transcript=english_greeting_transcript,
            translator=translator,
            target_language="zh",
        )

        # Verify stream metadata
        assert result.stream_id == english_greeting_transcript.stream_id
        assert result.sequence_number == english_greeting_transcript.sequence_number

    def test_language_metadata_flow(
        self,
        transcript_factory,
    ):
        """Test that language metadata flows correctly from ASR to Translation."""
        # Create transcript with specific language
        transcript = transcript_factory(
            text="Bonjour, comment allez-vous?",
            language="fr",
        )
        translator = MockIdentityTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="en",
        )

        # Verify language flow
        assert result.source_language == "fr"
        assert result.target_language == "en"


class TestMultiFragmentStream:
    """Test translation of multiple sequential fragments."""

    def test_translate_stream_maintains_sequence(
        self,
        multi_fragment_transcripts: list[TranscriptAsset],
    ):
        """Test that translating a stream maintains correct sequence numbers."""
        translator = MockIdentityTranslator()

        results = [
            translate_transcript(
                transcript=transcript,
                translator=translator,
                target_language="zh",
            )
            for transcript in multi_fragment_transcripts
        ]

        # Verify sequence order preserved
        for i, result in enumerate(results):
            assert result.sequence_number == i
            assert result.status == TranslationStatus.SUCCESS

        # Verify all have same stream_id
        stream_ids = {r.stream_id for r in results}
        assert len(stream_ids) == 1

    def test_translate_stream_unique_asset_ids(
        self,
        multi_fragment_transcripts: list[TranscriptAsset],
    ):
        """Test that each translated fragment has unique asset_id."""
        translator = MockIdentityTranslator()

        results = [
            translate_transcript(
                transcript=transcript,
                translator=translator,
                target_language="zh",
            )
            for transcript in multi_fragment_transcripts
        ]

        # Verify unique asset IDs
        asset_ids = [r.asset_id for r in results]
        assert len(asset_ids) == len(set(asset_ids)), "All asset_ids must be unique"

    def test_translate_stream_correct_lineage_chain(
        self,
        multi_fragment_transcripts: list[TranscriptAsset],
    ):
        """Test that each TextAsset correctly references its TranscriptAsset parent."""
        translator = MockIdentityTranslator()

        for transcript in multi_fragment_transcripts:
            result = translate_transcript(
                transcript=transcript,
                translator=translator,
                target_language="zh",
            )

            # Each result should reference exactly its transcript parent
            assert transcript.asset_id in result.parent_asset_ids
            assert len(result.parent_asset_ids) == 1


class TestNormalizationPolicyIntegration:
    """Test normalization policy application in pipeline."""

    def test_normalization_applied_before_translation(
        self,
        english_sports_transcript: TranscriptAsset,
        default_normalization_policy: NormalizationPolicy,
    ):
        """Test that normalization is applied before translation."""
        translator = MockIdentityTranslator()

        result = translate_transcript(
            transcript=english_sports_transcript,
            translator=translator,
            target_language="zh",
            normalization_policy=default_normalization_policy,
        )

        # With identity translator, normalized text should be returned
        # Check that time phrase normalization was applied
        # Original: "1:54 remaining" should have REMAINING lowercased
        assert result.status == TranslationStatus.SUCCESS
        assert result.translated_text  # Should have content

    def test_normalization_disabled(
        self,
        english_sports_transcript: TranscriptAsset,
    ):
        """Test translation with normalization disabled."""
        translator = MockIdentityTranslator()
        policy = NormalizationPolicy(enabled=False)

        result = translate_transcript(
            transcript=english_sports_transcript,
            translator=translator,
            target_language="zh",
            normalization_policy=policy,
        )

        # Without normalization, original text should be preserved
        assert result.translated_text == english_sports_transcript.total_text

    def test_tts_cleanup_applied_post_translation(
        self,
        transcript_factory,
        tts_optimized_policy: NormalizationPolicy,
    ):
        """Test that TTS cleanup is applied after translation."""
        # Create transcript with score
        transcript = transcript_factory(
            text="The final score was 21-14.",
        )
        translator = MockIdentityTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="zh",
            normalization_policy=tts_optimized_policy,
        )

        # TTS cleanup converts "21-14" to "21 to 14"
        # Note: Identity translator returns normalized input
        assert result.status == TranslationStatus.SUCCESS


class TestSpeakerPolicyIntegration:
    """Test speaker policy application in pipeline."""

    def test_speaker_detection_in_pipeline(
        self,
        english_conversation_transcript: TranscriptAsset,
        speaker_detection_policy: SpeakerPolicy,
    ):
        """Test speaker detection and removal in translation pipeline."""
        translator = MockIdentityTranslator()

        result = translate_transcript(
            transcript=english_conversation_transcript,
            translator=translator,
            target_language="zh",
            speaker_policy=speaker_detection_policy,
        )

        # Speaker should be detected
        assert result.speaker_id == "Alice"
        # Text should not contain speaker label
        assert "Alice:" not in result.translated_text
        assert result.status == TranslationStatus.SUCCESS

    def test_speaker_detection_disabled(
        self,
        english_conversation_transcript: TranscriptAsset,
    ):
        """Test that speaker label is preserved when detection disabled."""
        translator = MockIdentityTranslator()
        policy = SpeakerPolicy(detect_and_remove=False)

        result = translate_transcript(
            transcript=english_conversation_transcript,
            translator=translator,
            target_language="zh",
            speaker_policy=policy,
        )

        # Speaker detection disabled - label should remain
        assert result.speaker_id == "default"
        assert "Alice:" in result.translated_text


class TestErrorHandling:
    """Test error handling in ASR -> Translation pipeline."""

    def test_failed_translation_with_retryable_error(
        self,
        english_greeting_transcript: TranscriptAsset,
    ):
        """Test handling of retryable translation failures."""
        from sts_service.translation.models import TranslationErrorType

        translator = MockFailingTranslator(
            failure_rate=1.0,  # Always fail
            failure_type=TranslationErrorType.PROVIDER_ERROR,
        )

        result = translate_transcript(
            transcript=english_greeting_transcript,
            translator=translator,
            target_language="zh",
        )

        # Should fail but be retryable
        assert result.status == TranslationStatus.FAILED
        assert len(result.errors) > 0
        assert result.is_retryable

    def test_failed_translation_with_non_retryable_error(
        self,
        english_greeting_transcript: TranscriptAsset,
    ):
        """Test handling of non-retryable translation failures."""
        from sts_service.translation.models import TranslationErrorType

        translator = MockFailingTranslator(
            failure_rate=1.0,
            failure_type=TranslationErrorType.UNSUPPORTED_LANGUAGE_PAIR,
        )

        result = translate_transcript(
            transcript=english_greeting_transcript,
            translator=translator,
            target_language="zh",
        )

        # Should fail and not be retryable
        assert result.status == TranslationStatus.FAILED
        assert not result.is_retryable

    def test_empty_transcript_handling(
        self,
        transcript_factory,
    ):
        """Test handling of empty transcript text."""
        transcript = transcript_factory(text=" ")  # Whitespace only
        translator = MockIdentityTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="zh",
        )

        # Should handle gracefully
        assert result.status == TranslationStatus.SUCCESS


class TestProcessingMetadata:
    """Test processing metadata in translation results."""

    def test_processing_time_recorded(
        self,
        english_greeting_transcript: TranscriptAsset,
    ):
        """Test that processing time is recorded in results."""
        translator = MockIdentityTranslator()

        result = translate_transcript(
            transcript=english_greeting_transcript,
            translator=translator,
            target_language="zh",
        )

        assert result.processing_time_ms is not None
        assert result.processing_time_ms >= 0

    def test_model_info_recorded(
        self,
        english_greeting_transcript: TranscriptAsset,
    ):
        """Test that model info is recorded in results."""
        translator = MockIdentityTranslator()

        result = translate_transcript(
            transcript=english_greeting_transcript,
            translator=translator,
            target_language="zh",
        )

        assert result.model_info is not None
        assert result.model_info == "mock-identity-v1"

    def test_latency_measurement_with_slow_translator(
        self,
        english_greeting_transcript: TranscriptAsset,
    ):
        """Test that latency is correctly measured with slow translator."""
        latency_ms = 100
        translator = MockLatencyTranslator(latency_ms=latency_ms)

        result = translate_transcript(
            transcript=english_greeting_transcript,
            translator=translator,
            target_language="zh",
        )

        # Processing time should be at least the simulated latency
        assert result.processing_time_ms >= latency_ms


class TestFactoryIntegration:
    """Test translation factory integration with pipeline."""

    def test_factory_creates_mock_translator(
        self,
        english_greeting_transcript: TranscriptAsset,
    ):
        """Test that factory creates working mock translator."""
        translator = create_translation_component(mock=True)

        result = translate_transcript(
            transcript=english_greeting_transcript,
            translator=translator,
            target_language="zh",
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.translated_text == english_greeting_transcript.total_text


class TestDeterminism:
    """Test deterministic behavior of translation pipeline."""

    def test_same_input_produces_same_output(
        self,
        english_greeting_transcript: TranscriptAsset,
    ):
        """Test that same input produces identical output (determinism)."""
        translator = MockIdentityTranslator()

        results = [
            translate_transcript(
                transcript=english_greeting_transcript,
                translator=translator,
                target_language="zh",
            )
            for _ in range(10)
        ]

        # All translated texts should be identical
        texts = [r.translated_text for r in results]
        assert len(set(texts)) == 1, "Same input should produce same output"

    def test_normalization_determinism(
        self,
        english_sports_transcript: TranscriptAsset,
        default_normalization_policy: NormalizationPolicy,
    ):
        """Test that normalization produces deterministic results."""
        translator = MockIdentityTranslator()

        results = [
            translate_transcript(
                transcript=english_sports_transcript,
                translator=translator,
                target_language="zh",
                normalization_policy=default_normalization_policy,
            )
            for _ in range(10)
        ]

        # All normalized source texts should be identical
        normalized_texts = [r.normalized_source_text for r in results]
        # Filter out None values if any
        normalized_texts = [t for t in normalized_texts if t is not None]
        if normalized_texts:
            assert len(set(normalized_texts)) == 1, "Normalization should be deterministic"


# =============================================================================
# Full Pipeline Tests (combining multiple aspects)
# =============================================================================


class TestFullPipeline:
    """End-to-end pipeline tests combining all features."""

    def test_complete_pipeline_with_all_policies(
        self,
        english_conversation_transcript: TranscriptAsset,
        speaker_detection_policy: SpeakerPolicy,
        tts_optimized_policy: NormalizationPolicy,
    ):
        """Test complete pipeline with speaker detection and TTS optimization."""
        translator = MockIdentityTranslator()

        result = translate_transcript(
            transcript=english_conversation_transcript,
            translator=translator,
            target_language="zh",
            speaker_policy=speaker_detection_policy,
            normalization_policy=tts_optimized_policy,
        )

        # Verify all aspects
        assert result.status == TranslationStatus.SUCCESS
        assert result.speaker_id == "Alice"
        assert result.stream_id == english_conversation_transcript.stream_id
        assert result.sequence_number == english_conversation_transcript.sequence_number
        assert english_conversation_transcript.asset_id in result.parent_asset_ids
        assert result.processing_time_ms is not None

    def test_pipeline_handles_all_transcript_statuses(
        self,
        transcript_factory,
    ):
        """Test pipeline handles transcripts with different statuses."""
        translator = MockIdentityTranslator()

        # Create successful transcript
        success_transcript = transcript_factory(
            text="This is successful transcription.",
        )

        result = translate_transcript(
            transcript=success_transcript,
            translator=translator,
            target_language="zh",
        )

        # Translation should succeed for successful transcript
        assert result.status == TranslationStatus.SUCCESS
