"""
Live integration tests for DeepL Translation (EN -> ZH).

These tests require a valid DEEPL_AUTH_KEY environment variable.
Run with: pytest -m deepl_live apps/sts-service/tests/integration/translation/test_deepl_live.py
Skip with: pytest -m "not deepl_live"

To run these tests:
    export DEEPL_AUTH_KEY=your-api-key
    pytest apps/sts-service/tests/integration/translation/test_deepl_live.py -v
"""

import os

import pytest
from sts_service.translation.deepl_provider import DeepLTranslator
from sts_service.translation.factory import create_translation_component
from sts_service.translation.models import (
    NormalizationPolicy,
    SpeakerPolicy,
    TranslationStatus,
)

from .conftest import (
    create_transcript_asset,
    skip_without_deepl,
    translate_transcript,
)

# =============================================================================
# DeepL API Availability Check
# =============================================================================


def has_deepl_key() -> bool:
    """Check if DeepL API key is available."""
    return bool(os.environ.get("DEEPL_AUTH_KEY"))


# =============================================================================
# DeepL Live Integration Tests (EN -> ZH)
# =============================================================================


@pytest.mark.deepl_live
@skip_without_deepl
class TestDeepLEnglishToChineseTranslation:
    """Live DeepL API tests for English to Chinese (Simplified) translation."""

    def test_simple_greeting_translation(self):
        """Test simple greeting translation EN -> ZH."""
        transcript = create_transcript_asset(
            text="Hello, how are you today?",
            language="en",
        )

        translator = DeepLTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",  # DeepL uses uppercase for Chinese
        )

        # Verify translation succeeded
        assert result.status == TranslationStatus.SUCCESS
        assert result.translated_text, "Translation should not be empty"

        # Verify language metadata
        assert result.source_language == "en"
        assert result.target_language == "ZH"

        # Verify Chinese characters in output (basic check)
        # Chinese characters are in Unicode range
        has_chinese = any("\u4e00" <= char <= "\u9fff" for char in result.translated_text)
        assert has_chinese, f"Expected Chinese characters in: {result.translated_text}"

        # Print for manual verification
        print(f"\nEN: {transcript.total_text}")
        print(f"ZH: {result.translated_text}")

    def test_longer_sentence_translation(self):
        """Test longer sentence translation EN -> ZH."""
        transcript = create_transcript_asset(
            text="The weather is beautiful today. I am going to the park to enjoy the sunshine.",
            language="en",
        )

        translator = DeepLTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.translated_text
        assert len(result.translated_text) > 0

        print(f"\nEN: {transcript.total_text}")
        print(f"ZH: {result.translated_text}")

    def test_technical_content_translation(self):
        """Test technical content translation EN -> ZH."""
        transcript = create_transcript_asset(
            text="The API returns a JSON response with status code 200 when the request is successful.",
            language="en",
        )

        translator = DeepLTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
        )

        assert result.status == TranslationStatus.SUCCESS
        # Technical terms like API, JSON may be preserved or translated
        assert result.translated_text

        print(f"\nEN: {transcript.total_text}")
        print(f"ZH: {result.translated_text}")

    def test_sports_commentary_translation(self):
        """Test sports commentary translation EN -> ZH."""
        transcript = create_transcript_asset(
            text="Touchdown! The Chiefs score with two minutes remaining in the game.",
            language="en",
        )

        translator = DeepLTranslator()
        normalization_policy = NormalizationPolicy(enabled=False)  # Test without normalization

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
            normalization_policy=normalization_policy,
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.translated_text

        print(f"\nEN: {transcript.total_text}")
        print(f"ZH: {result.translated_text}")

    def test_conversational_text_translation(self):
        """Test conversational text translation EN -> ZH."""
        transcript = create_transcript_asset(
            text="Thank you so much for your help. I really appreciate it!",
            language="en",
        )

        translator = DeepLTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.translated_text

        print(f"\nEN: {transcript.total_text}")
        print(f"ZH: {result.translated_text}")


@pytest.mark.deepl_live
@skip_without_deepl
class TestDeepLPipelineIntegration:
    """Test full ASR -> DeepL Translation pipeline."""

    def test_asset_lineage_with_deepl(self):
        """Test that asset lineage is correctly tracked with DeepL."""
        transcript = create_transcript_asset(
            text="This is a test message.",
            language="en",
            stream_id="deepl-lineage-test",
            sequence_number=42,
        )

        translator = DeepLTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
        )

        # Verify lineage
        assert transcript.asset_id in result.parent_asset_ids
        assert result.stream_id == "deepl-lineage-test"
        assert result.sequence_number == 42
        assert result.component == "translate"
        assert result.component_instance == "deepl-v1"

    def test_multi_fragment_stream_with_deepl(self):
        """Test translating multiple fragments with DeepL."""
        texts = [
            "Hello everyone.",
            "Welcome to the broadcast.",
            "Today we discuss important topics.",
        ]

        transcripts = [
            create_transcript_asset(
                text=text,
                language="en",
                stream_id="deepl-stream-test",
                sequence_number=i,
            )
            for i, text in enumerate(texts)
        ]

        translator = DeepLTranslator()

        results = [
            translate_transcript(
                transcript=transcript,
                translator=translator,
                target_language="ZH",
            )
            for transcript in transcripts
        ]

        # Verify all translations succeeded
        for i, result in enumerate(results):
            assert result.status == TranslationStatus.SUCCESS
            assert result.sequence_number == i
            assert result.stream_id == "deepl-stream-test"
            print(f"\n[{i}] EN: {texts[i]}")
            print(f"[{i}] ZH: {result.translated_text}")

    def test_processing_time_with_deepl(self):
        """Test that processing time is recorded for DeepL translation."""
        transcript = create_transcript_asset(
            text="Quick translation test.",
            language="en",
        )

        translator = DeepLTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
        )

        assert result.processing_time_ms is not None
        assert result.processing_time_ms > 0  # Should take some time for API call

        print(f"\nProcessing time: {result.processing_time_ms}ms")


@pytest.mark.deepl_live
@skip_without_deepl
class TestDeepLNormalizationIntegration:
    """Test normalization policies with DeepL."""

    def test_translation_with_normalization_enabled(self):
        """Test DeepL translation with normalization preprocessing."""
        transcript = create_transcript_asset(
            text="The score is 21-14 in the NFL game.",
            language="en",
        )

        translator = DeepLTranslator()
        policy = NormalizationPolicy(
            enabled=True,
            expand_abbreviations=True,
            normalize_symbols=True,
        )

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
            normalization_policy=policy,
        )

        assert result.status == TranslationStatus.SUCCESS
        # Check that normalized source was recorded
        if result.normalized_source_text:
            print(f"\nOriginal: {transcript.total_text}")
            print(f"Normalized: {result.normalized_source_text}")
        print(f"Translated: {result.translated_text}")

    def test_translation_with_tts_cleanup(self):
        """Test DeepL translation with TTS cleanup post-processing."""
        transcript = create_transcript_asset(
            text="The final result was great!",
            language="en",
        )

        translator = DeepLTranslator()
        policy = NormalizationPolicy(
            enabled=True,
            tts_cleanup=True,
        )

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
            normalization_policy=policy,
        )

        assert result.status == TranslationStatus.SUCCESS
        print(f"\nEN: {transcript.total_text}")
        print(f"ZH: {result.translated_text}")


@pytest.mark.deepl_live
@skip_without_deepl
class TestDeepLSpeakerHandling:
    """Test speaker detection with DeepL translation."""

    def test_speaker_detection_with_deepl(self):
        """Test speaker detection and removal before DeepL translation."""
        transcript = create_transcript_asset(
            text="Alice: Thank you for joining us today.",
            language="en",
        )

        translator = DeepLTranslator()
        speaker_policy = SpeakerPolicy(detect_and_remove=True)

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
            speaker_policy=speaker_policy,
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.speaker_id == "Alice"
        # The translated text should not contain "Alice:"
        assert "Alice:" not in result.translated_text

        print(f"\nOriginal: {transcript.total_text}")
        print(f"Speaker: {result.speaker_id}")
        print(f"Translated: {result.translated_text}")


@pytest.mark.deepl_live
@skip_without_deepl
class TestDeepLFactoryIntegration:
    """Test DeepL creation through factory."""

    def test_factory_creates_deepl_translator(self):
        """Test that factory correctly creates DeepL translator."""
        translator = create_translation_component(mock=False, provider="deepl")

        assert isinstance(translator, DeepLTranslator)
        assert translator.is_ready
        assert translator.component_instance == "deepl-v1"

    def test_factory_translator_works_in_pipeline(self):
        """Test factory-created DeepL translator in full pipeline."""
        transcript = create_transcript_asset(
            text="Factory created translator test.",
            language="en",
        )

        translator = create_translation_component(mock=False, provider="deepl")

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.translated_text

        print(f"\nEN: {transcript.total_text}")
        print(f"ZH: {result.translated_text}")


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.deepl_live
@skip_without_deepl
class TestDeepLErrorHandling:
    """Test error handling with DeepL API."""

    def test_empty_input_handling(self):
        """Test handling of empty input text."""
        transcript = create_transcript_asset(
            text="   ",  # Whitespace only
            language="en",
        )

        translator = DeepLTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
        )

        # Should handle empty input gracefully
        assert result.status == TranslationStatus.SUCCESS
        # May have warning about empty input
        if result.warnings:
            print(f"\nWarnings: {result.warnings}")

    def test_very_long_text_handling(self):
        """Test handling of longer text content."""
        # Create a longer text
        long_text = " ".join([f"This is sentence number {i}." for i in range(20)])

        transcript = create_transcript_asset(
            text=long_text,
            language="en",
        )

        translator = DeepLTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
        )

        assert result.status == TranslationStatus.SUCCESS
        assert result.translated_text
        print(f"\nOriginal length: {len(long_text)}")
        print(f"Translated length: {len(result.translated_text)}")


# =============================================================================
# Benchmarking Tests (Optional)
# =============================================================================


@pytest.mark.deepl_live
@pytest.mark.slow
@skip_without_deepl
class TestDeepLPerformance:
    """Performance benchmarks for DeepL translation."""

    def test_translation_latency(self):
        """Measure translation latency for typical sentences."""
        test_sentences = [
            "Hello, world!",
            "How are you doing today?",
            "The weather is nice.",
            "I love programming.",
            "Thank you very much.",
        ]

        translator = DeepLTranslator()
        latencies = []

        for sentence in test_sentences:
            transcript = create_transcript_asset(text=sentence, language="en")

            result = translate_transcript(
                transcript=transcript,
                translator=translator,
                target_language="ZH",
            )

            assert result.status == TranslationStatus.SUCCESS
            latencies.append(result.processing_time_ms)

        avg_latency = sum(latencies) / len(latencies)
        print("\n--- DeepL Latency Benchmark ---")
        print(f"Sentences tested: {len(test_sentences)}")
        print(f"Individual latencies: {latencies}ms")
        print(f"Average latency: {avg_latency:.1f}ms")
        print(f"Min latency: {min(latencies)}ms")
        print(f"Max latency: {max(latencies)}ms")

    def test_throughput_sequential(self):
        """Measure sequential translation throughput."""
        import time

        sentences = [f"Test sentence number {i}." for i in range(10)]
        translator = DeepLTranslator()

        start_time = time.time()
        for sentence in sentences:
            transcript = create_transcript_asset(text=sentence, language="en")
            result = translate_transcript(
                transcript=transcript,
                translator=translator,
                target_language="ZH",
            )
            assert result.status == TranslationStatus.SUCCESS

        total_time = time.time() - start_time
        throughput = len(sentences) / total_time

        print("\n--- DeepL Throughput Benchmark ---")
        print(f"Sentences: {len(sentences)}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Throughput: {throughput:.2f} sentences/second")
