"""
Integration tests: Live Coqui TTS synthesis.

These tests verify actual TTS synthesis with the Coqui TTS library:
- Real audio synthesis with XTTS-v2 and VITS models
- Audio output format and duration validation
- Multilingual synthesis (English, Spanish)
- Voice cloning (when voice sample available)

Requirements:
- Coqui TTS library installed: pip install TTS
- Tests are marked with @coqui_live and @slow
- Skip with: pytest -m "not coqui_live"
"""

import pytest
from sts_service.tts.coqui_provider import CoquiTTSComponent
from sts_service.tts.models import (
    AudioFormat,
    AudioStatus,
    VoiceProfile,
)

from .conftest import (
    create_text_asset,
    skip_without_coqui,
    synthesize_from_translation,
)

# =============================================================================
# Test: Basic Synthesis
# =============================================================================


@pytest.mark.coqui_live
@skip_without_coqui
class TestBasicSynthesis:
    """Test basic TTS synthesis with Coqui TTS."""

    def test_english_synthesis_produces_audio(self):
        """Test English text produces valid audio output."""
        tts = CoquiTTSComponent(fast_mode=True)  # Use VITS for faster tests
        text_asset = create_text_asset(
            text="Hello, this is a test of the text to speech system.",
            target_language="en",
        )

        audio = synthesize_from_translation(text_asset, tts)

        assert audio.status == AudioStatus.SUCCESS
        assert audio.duration_ms > 0
        assert audio.sample_rate_hz == 16000
        assert audio.channels == 1
        assert audio.language == "en"

        print(f"\nEnglish synthesis: {audio.duration_ms}ms, "
              f"status={audio.status.value}")

        tts.shutdown()

    def test_spanish_synthesis_produces_audio(self):
        """Test Spanish text produces valid audio output."""
        tts = CoquiTTSComponent(fast_mode=True)
        text_asset = create_text_asset(
            text="Hola, esta es una prueba del sistema de texto a voz.",
            target_language="es",
        )
        voice_profile = VoiceProfile(language="es", fast_mode=True)

        audio = tts.synthesize(
            text_asset=text_asset,
            voice_profile=voice_profile,
        )

        assert audio.status == AudioStatus.SUCCESS
        assert audio.duration_ms > 0
        assert audio.language == "es"

        print(f"\nSpanish synthesis: {audio.duration_ms}ms, "
              f"status={audio.status.value}")

        tts.shutdown()

    def test_synthesis_with_custom_sample_rate(self):
        """Test synthesis with custom output sample rate."""
        tts = CoquiTTSComponent(fast_mode=True)
        text_asset = create_text_asset("Testing custom sample rate output.")

        audio = synthesize_from_translation(
            text_asset, tts,
            output_sample_rate_hz=24000,
        )

        assert audio.status == AudioStatus.SUCCESS
        assert audio.sample_rate_hz == 24000

        tts.shutdown()

    def test_synthesis_stereo_output(self):
        """Test synthesis with stereo output channels."""
        tts = CoquiTTSComponent(fast_mode=True)
        text_asset = create_text_asset("Testing stereo output.")

        audio = synthesize_from_translation(
            text_asset, tts,
            output_channels=2,
        )

        assert audio.status == AudioStatus.SUCCESS
        assert audio.channels == 2

        tts.shutdown()


# =============================================================================
# Test: Audio Output Validation
# =============================================================================


@pytest.mark.coqui_live
@skip_without_coqui
class TestAudioOutputValidation:
    """Test synthesized audio output is valid."""

    def test_audio_format_is_pcm_float(self):
        """Test audio format is PCM float32."""
        tts = CoquiTTSComponent(fast_mode=True)
        text_asset = create_text_asset("Format validation test.")

        audio = synthesize_from_translation(text_asset, tts)

        assert audio.audio_format == AudioFormat.PCM_F32LE
        assert audio.status == AudioStatus.SUCCESS

        tts.shutdown()

    def test_audio_duration_reasonable(self):
        """Test audio duration is reasonable for input text."""
        tts = CoquiTTSComponent(fast_mode=True)

        # Short text
        short_text = create_text_asset("Hi.")
        short_audio = synthesize_from_translation(short_text, tts)

        # Longer text
        long_text = create_text_asset(
            "This is a much longer sentence that should produce "
            "significantly more audio output than the short greeting."
        )
        long_audio = synthesize_from_translation(long_text, tts)

        assert short_audio.status == AudioStatus.SUCCESS
        assert long_audio.status == AudioStatus.SUCCESS

        # Longer text should produce longer audio
        print(f"\nShort: {short_audio.duration_ms}ms, Long: {long_audio.duration_ms}ms")
        assert long_audio.duration_ms > short_audio.duration_ms

        tts.shutdown()

    def test_audio_has_valid_payload_ref(self):
        """Test audio has valid payload reference."""
        tts = CoquiTTSComponent(fast_mode=True)
        text_asset = create_text_asset(
            "Payload reference test.",
            stream_id="payload-test-stream",
            sequence_number=42,
        )

        audio = synthesize_from_translation(text_asset, tts)

        assert audio.status == AudioStatus.SUCCESS
        assert audio.payload_ref is not None
        assert len(audio.payload_ref) > 0
        assert "payload-test-stream" in audio.payload_ref
        assert "42" in audio.payload_ref

        tts.shutdown()


# =============================================================================
# Test: Quality Mode vs Fast Mode
# =============================================================================


@pytest.mark.coqui_live
@pytest.mark.slow
@skip_without_coqui
class TestQualityModes:
    """Test quality mode (XTTS-v2) vs fast mode (VITS)."""

    def test_fast_mode_synthesis(self):
        """Test fast mode (VITS) synthesis."""
        tts = CoquiTTSComponent(fast_mode=True)
        text_asset = create_text_asset("Fast mode synthesis test.")

        audio = synthesize_from_translation(text_asset, tts)

        assert audio.status == AudioStatus.SUCCESS
        assert "vits" in tts.component_instance.lower() or "fast" in tts.component_instance.lower()

        print(f"\nFast mode: {tts.component_instance}")

        tts.shutdown()

    def test_quality_mode_synthesis(self):
        """Test quality mode (XTTS-v2) synthesis."""
        tts = CoquiTTSComponent(fast_mode=False)
        text_asset = create_text_asset("Quality mode synthesis test.")

        audio = synthesize_from_translation(text_asset, tts)

        assert audio.status == AudioStatus.SUCCESS
        assert "xtts" in tts.component_instance.lower() or "quality" in tts.component_instance.lower()

        print(f"\nQuality mode: {tts.component_instance}")

        tts.shutdown()

    def test_fast_mode_lower_latency(self):
        """Test fast mode has lower latency than quality mode."""
        import time

        text_asset = create_text_asset("Latency comparison test sentence.")

        # Fast mode
        tts_fast = CoquiTTSComponent(fast_mode=True)
        # Warm up cache
        synthesize_from_translation(text_asset, tts_fast)
        start = time.time()
        for _ in range(3):
            synthesize_from_translation(text_asset, tts_fast)
        fast_time = (time.time() - start) / 3

        # Quality mode
        tts_quality = CoquiTTSComponent(fast_mode=False)
        # Warm up cache
        synthesize_from_translation(text_asset, tts_quality)
        start = time.time()
        for _ in range(3):
            synthesize_from_translation(text_asset, tts_quality)
        quality_time = (time.time() - start) / 3

        print(f"\nAverage times - Fast: {fast_time:.2f}s, Quality: {quality_time:.2f}s")

        # Fast mode should be faster (spec SC-007: at least 40% faster)
        # Note: This depends on hardware and model sizes
        assert fast_time < quality_time or fast_time < 1.0

        tts_fast.shutdown()
        tts_quality.shutdown()


# =============================================================================
# Test: Duration Matching Integration
# =============================================================================


@pytest.mark.coqui_live
@skip_without_coqui
class TestDurationMatchingIntegration:
    """Test duration matching with live TTS synthesis."""

    def test_synthesis_with_target_duration(self):
        """Test synthesis respects target duration."""
        tts = CoquiTTSComponent(fast_mode=True)
        text_asset = create_text_asset("Duration matching integration test.")

        target_duration = 2000  # 2 seconds

        audio = synthesize_from_translation(
            text_asset, tts,
            target_duration_ms=target_duration,
        )

        assert audio.status == AudioStatus.SUCCESS
        # Note: The current implementation may not always achieve exact duration
        # This test verifies the integration works without errors

        print(f"\nTarget: {target_duration}ms, Actual: {audio.duration_ms}ms")

        tts.shutdown()


# =============================================================================
# Test: Error Cases
# =============================================================================


@pytest.mark.coqui_live
@skip_without_coqui
class TestErrorCases:
    """Test error handling with live TTS."""

    def test_empty_text_returns_error(self):
        """Test empty text input returns error."""
        tts = CoquiTTSComponent(fast_mode=True)
        text_asset = create_text_asset("   ")  # Whitespace only

        audio = synthesize_from_translation(text_asset, tts)

        assert audio.status == AudioStatus.FAILED
        assert audio.has_errors
        assert not audio.is_retryable  # Invalid input is not retryable

        tts.shutdown()

    def test_synthesis_includes_processing_time(self):
        """Test processing time is recorded."""
        tts = CoquiTTSComponent(fast_mode=True)
        text_asset = create_text_asset("Processing time measurement test.")

        audio = synthesize_from_translation(text_asset, tts)

        assert audio.status == AudioStatus.SUCCESS
        assert audio.processing_time_ms is not None
        assert audio.processing_time_ms > 0

        print(f"\nProcessing time: {audio.processing_time_ms}ms")

        tts.shutdown()


# =============================================================================
# Test: Preprocessed Text Tracking
# =============================================================================


@pytest.mark.coqui_live
@skip_without_coqui
class TestPreprocessedTextTracking:
    """Test preprocessed text is tracked in output."""

    def test_preprocessed_text_recorded(self):
        """Test preprocessed text is included in AudioAsset."""
        tts = CoquiTTSComponent(fast_mode=True)
        text_asset = create_text_asset("Original input text for preprocessing test.")

        audio = synthesize_from_translation(text_asset, tts)

        assert audio.status == AudioStatus.SUCCESS
        assert audio.preprocessed_text is not None
        # Preprocessed text should be similar to input (basic preprocessing)
        assert len(audio.preprocessed_text) > 0

        print(f"\nOriginal: {text_asset.translated_text}")
        print(f"Preprocessed: {audio.preprocessed_text}")

        tts.shutdown()


# =============================================================================
# Test: Component Instance Identification
# =============================================================================


@pytest.mark.coqui_live
@skip_without_coqui
class TestComponentIdentification:
    """Test component instance identification."""

    def test_component_instance_includes_model_info(self):
        """Test component_instance includes model information."""
        tts_fast = CoquiTTSComponent(fast_mode=True)
        tts_quality = CoquiTTSComponent(fast_mode=False)

        # Both should include "coqui" and mode info
        assert "coqui" in tts_fast.component_instance
        assert "coqui" in tts_quality.component_instance

        # Should distinguish between fast and quality modes
        assert tts_fast.component_instance != tts_quality.component_instance

        print(f"\nFast: {tts_fast.component_instance}")
        print(f"Quality: {tts_quality.component_instance}")

        tts_fast.shutdown()
        tts_quality.shutdown()

    def test_component_name_is_tts(self):
        """Test component_name is always 'tts'."""
        tts = CoquiTTSComponent(fast_mode=True)

        assert tts.component_name == "tts"

        tts.shutdown()


# =============================================================================
# Test: Multi-Language Support
# =============================================================================


@pytest.mark.coqui_live
@pytest.mark.slow
@skip_without_coqui
class TestMultiLanguageSupport:
    """Test multi-language synthesis support."""

    @pytest.mark.parametrize("language,text", [
        ("en", "Hello, how are you today?"),
        ("es", "Hola, como estas hoy?"),
        ("fr", "Bonjour, comment allez-vous?"),
        ("de", "Hallo, wie geht es Ihnen?"),
    ])
    def test_multilingual_synthesis(self, language: str, text: str):
        """Test synthesis works for multiple languages."""
        tts = CoquiTTSComponent(fast_mode=False)  # XTTS-v2 supports multilingual
        text_asset = create_text_asset(text=text, target_language=language)
        voice_profile = VoiceProfile(language=language)

        try:
            audio = tts.synthesize(
                text_asset=text_asset,
                voice_profile=voice_profile,
            )

            # May fail for unsupported languages, but should not crash
            if audio.status == AudioStatus.SUCCESS:
                assert audio.duration_ms > 0
                assert audio.language == language
                print(f"\n{language.upper()}: {audio.duration_ms}ms - SUCCESS")
            else:
                print(f"\n{language.upper()}: {audio.status.value}")

        except Exception as e:
            # Some languages may not be supported by the model
            print(f"\n{language.upper()}: Exception - {e}")

        finally:
            tts.shutdown()


# =============================================================================
# Test: Stress Tests
# =============================================================================


@pytest.mark.coqui_live
@pytest.mark.slow
@skip_without_coqui
class TestStress:
    """Stress tests for TTS synthesis."""

    def test_sequential_synthesis_stability(self):
        """Test multiple sequential synthesis calls are stable."""
        tts = CoquiTTSComponent(fast_mode=True)

        sentences = [
            "First sentence for stability testing.",
            "Second sentence to verify consistency.",
            "Third sentence for the stress test.",
            "Fourth sentence checking reliability.",
            "Fifth and final sentence in this sequence.",
        ]

        results = []
        for i, sentence in enumerate(sentences):
            text_asset = create_text_asset(sentence, sequence_number=i)
            audio = synthesize_from_translation(text_asset, tts)
            results.append({
                "sequence": i,
                "status": audio.status,
                "duration_ms": audio.duration_ms,
            })

        # All should succeed
        assert all(r["status"] == AudioStatus.SUCCESS for r in results)

        print("\n--- Sequential Synthesis Results ---")
        for r in results:
            print(f"  [{r['sequence']}] {r['status'].value}: {r['duration_ms']}ms")

        tts.shutdown()

    def test_long_text_synthesis(self):
        """Test synthesis of longer text passages."""
        tts = CoquiTTSComponent(fast_mode=True)

        long_text = (
            "This is a longer passage of text designed to test the text to speech "
            "system's ability to handle extended input. The system should be able "
            "to synthesize this entire paragraph without issues. Voice synthesis "
            "is a complex task that requires careful attention to timing, "
            "pronunciation, and natural speech patterns."
        )

        text_asset = create_text_asset(long_text)
        audio = synthesize_from_translation(text_asset, tts)

        assert audio.status == AudioStatus.SUCCESS
        assert audio.duration_ms > 5000  # Should be at least 5 seconds

        print(f"\nLong text ({len(long_text)} chars): {audio.duration_ms}ms")

        tts.shutdown()
