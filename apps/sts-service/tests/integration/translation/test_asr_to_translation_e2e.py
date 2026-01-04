"""
End-to-end integration tests: Audio → ASR → Translation (EN→ZH).

These tests use real NFL audio fixtures, run them through FasterWhisperASR,
and then translate the transcript to Chinese using DeepL.

Requirements:
- NFL audio fixture: tests/fixtures/test-streams/1-min-nfl.m4a
- FasterWhisper model (tiny for fast tests)
- DeepL API key: DEEPL_AUTH_KEY environment variable
- ffmpeg installed for audio extraction
"""

from pathlib import Path

import pytest
from sts_service.asr import (
    ASRConfig,
    ASRModelConfig,
    FasterWhisperASR,
    TranscriptStatus,
    VADConfig,
)
from sts_service.translation.deepl_provider import DeepLTranslator
from sts_service.translation.factory import create_translation_component
from sts_service.translation.models import (
    NormalizationPolicy,
    TranslationStatus,
)

from .conftest import skip_without_deepl, translate_transcript

# =============================================================================
# Fixtures
# =============================================================================


# Path to test fixtures directory (relative to repo root)
FIXTURES_DIR = (
    Path(__file__).parent.parent.parent.parent.parent.parent / "tests" / "fixtures" / "test-streams"
)


@pytest.fixture
def nfl_audio_path() -> Path:
    """Return the path to the NFL audio fixture."""
    path = FIXTURES_DIR / "1-min-nfl.m4a"
    if not path.exists():
        pytest.skip(f"NFL audio fixture not found: {path}")
    return path


@pytest.fixture
def load_audio_fragment():
    """Return a function that loads an audio fragment from a file."""
    import subprocess

    def _load_fragment(
        path: Path,
        start_ms: int,
        duration_ms: int,
        sample_rate: int = 16000,
    ) -> bytes:
        """Extract audio fragment using ffmpeg and return as PCM float32 bytes."""
        start_seconds = start_ms / 1000.0
        duration_seconds = duration_ms / 1000.0

        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start_seconds),
            "-t",
            str(duration_seconds),
            "-i",
            str(path),
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "pipe:1",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg failed: {e.stderr.decode()}") from e
        except FileNotFoundError:
            pytest.skip("ffmpeg not installed")

    return _load_fragment


@pytest.fixture
def asr_component():
    """Create a FasterWhisperASR with tiny model for fast tests."""
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


# =============================================================================
# End-to-End Tests: Audio → ASR → Translation (Mock)
# =============================================================================


class TestASRToTranslationWithMock:
    """End-to-end tests using real ASR output but mock translation."""

    def test_nfl_audio_asr_to_mock_translation(
        self,
        nfl_audio_path: Path,
        load_audio_fragment,
        asr_component: FasterWhisperASR,
    ):
        """Test full pipeline: NFL audio → ASR → Mock Translation."""
        # Step 1: Load real audio
        audio_bytes = load_audio_fragment(nfl_audio_path, start_ms=0, duration_ms=3000)

        # Step 2: Run through ASR
        transcript = asr_component.transcribe(
            audio_data=audio_bytes,
            stream_id="e2e-nfl-test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=3000,
            domain="sports",
        )

        assert transcript.status == TranscriptStatus.SUCCESS
        assert transcript.total_text, "ASR should produce transcription"

        # Step 3: Translate using mock
        translator = create_translation_component(mock=True)

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="zh",
        )

        # Verify pipeline integrity
        assert result.status == TranslationStatus.SUCCESS
        assert result.translated_text == transcript.total_text  # Mock returns identity
        assert transcript.asset_id in result.parent_asset_ids
        assert result.source_language == "en"
        assert result.target_language == "zh"

        print("\n--- E2E Pipeline (Mock) ---")
        print(f"ASR Output: {transcript.total_text}")
        print(f"Translation: {result.translated_text}")

    def test_multi_fragment_asr_to_mock_translation(
        self,
        nfl_audio_path: Path,
        load_audio_fragment,
        asr_component: FasterWhisperASR,
    ):
        """Test multi-fragment pipeline: Multiple audio segments → ASR → Translation."""
        translator = create_translation_component(mock=True)

        # Process 5 sequential 2-second fragments
        fragments = []
        for i in range(5):
            start_ms = i * 2000
            audio_bytes = load_audio_fragment(
                nfl_audio_path,
                start_ms=start_ms,
                duration_ms=2000,
            )

            transcript = asr_component.transcribe(
                audio_data=audio_bytes,
                stream_id="e2e-multi-fragment",
                sequence_number=i,
                start_time_ms=start_ms,
                end_time_ms=start_ms + 2000,
                domain="sports",
            )

            if transcript.status == TranscriptStatus.SUCCESS and transcript.total_text.strip():
                translated = translate_transcript(
                    transcript=transcript,
                    translator=translator,
                    target_language="zh",
                )
                fragments.append(
                    {
                        "sequence": i,
                        "asr_text": transcript.total_text,
                        "translated_text": translated.translated_text,
                        "asr_asset_id": transcript.asset_id,
                        "translation_asset_id": translated.asset_id,
                        "lineage_correct": transcript.asset_id in translated.parent_asset_ids,
                    }
                )

        # Verify we got some fragments
        assert len(fragments) > 0, "Should have at least one successful fragment"

        # Verify lineage is correct for all fragments
        for frag in fragments:
            assert frag["lineage_correct"], f"Fragment {frag['sequence']} has incorrect lineage"

        print("\n--- Multi-Fragment E2E (Mock) ---")
        for frag in fragments:
            print(f"[{frag['sequence']}] ASR: {frag['asr_text'][:50]}...")


# =============================================================================
# End-to-End Tests: Audio → ASR → DeepL Translation (Live)
# =============================================================================


@pytest.mark.deepl_live
@skip_without_deepl
class TestASRToDeepLTranslation:
    """End-to-end tests using real ASR and real DeepL translation (EN→ZH)."""

    def test_nfl_audio_asr_to_deepl_translation(
        self,
        nfl_audio_path: Path,
        load_audio_fragment,
        asr_component: FasterWhisperASR,
    ):
        """Test full pipeline: NFL audio → ASR → DeepL Translation (EN→ZH)."""
        # Step 1: Load real audio (first 3 seconds)
        audio_bytes = load_audio_fragment(nfl_audio_path, start_ms=0, duration_ms=3000)

        # Step 2: Run through ASR
        transcript = asr_component.transcribe(
            audio_data=audio_bytes,
            stream_id="e2e-nfl-deepl",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=3000,
            domain="sports",
        )

        assert transcript.status == TranscriptStatus.SUCCESS
        assert transcript.total_text, "ASR should produce transcription"

        # Step 3: Translate using DeepL
        translator = DeepLTranslator()

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",  # DeepL uses uppercase
        )

        # Verify pipeline integrity
        assert result.status == TranslationStatus.SUCCESS
        assert result.translated_text, "DeepL should produce Chinese translation"
        assert transcript.asset_id in result.parent_asset_ids
        assert result.source_language == "en"
        assert result.target_language == "ZH"

        # Verify Chinese characters in output
        has_chinese = any("\u4e00" <= char <= "\u9fff" for char in result.translated_text)
        assert has_chinese, f"Expected Chinese characters in: {result.translated_text}"

        print("\n--- E2E Pipeline: Audio → ASR → DeepL (EN→ZH) ---")
        print(f"ASR Output (EN): {transcript.total_text}")
        print(f"DeepL Translation (ZH): {result.translated_text}")
        print(f"ASR Processing Time: {transcript.processing_time_ms}ms")
        print(f"Translation Processing Time: {result.processing_time_ms}ms")

    def test_nfl_multi_segment_deepl_translation(
        self,
        nfl_audio_path: Path,
        load_audio_fragment,
        asr_component: FasterWhisperASR,
    ):
        """Test multi-segment pipeline with DeepL translation."""
        translator = DeepLTranslator()

        # Process 3 sequential 3-second fragments
        results = []
        for i in range(3):
            start_ms = i * 3000
            audio_bytes = load_audio_fragment(
                nfl_audio_path,
                start_ms=start_ms,
                duration_ms=3000,
            )

            transcript = asr_component.transcribe(
                audio_data=audio_bytes,
                stream_id="e2e-multi-deepl",
                sequence_number=i,
                start_time_ms=start_ms,
                end_time_ms=start_ms + 3000,
                domain="sports",
            )

            if transcript.status == TranscriptStatus.SUCCESS and transcript.total_text.strip():
                translated = translate_transcript(
                    transcript=transcript,
                    translator=translator,
                    target_language="ZH",
                )

                results.append(
                    {
                        "sequence": i,
                        "start_ms": start_ms,
                        "asr_text": transcript.total_text,
                        "chinese_text": translated.translated_text,
                        "asr_time_ms": transcript.processing_time_ms,
                        "translation_time_ms": translated.processing_time_ms,
                    }
                )

        assert len(results) > 0, "Should have at least one successful segment"

        print("\n--- Multi-Segment E2E: Audio → ASR → DeepL (EN→ZH) ---")
        for r in results:
            print(f"\n[Segment {r['sequence']}] ({r['start_ms']}ms - {r['start_ms'] + 3000}ms)")
            print(f"  EN: {r['asr_text']}")
            print(f"  ZH: {r['chinese_text']}")
            print(f"  Timing: ASR={r['asr_time_ms']}ms, Translation={r['translation_time_ms']}ms")

    def test_nfl_sports_with_normalization(
        self,
        nfl_audio_path: Path,
        load_audio_fragment,
        asr_component: FasterWhisperASR,
    ):
        """Test sports content with normalization enabled."""
        audio_bytes = load_audio_fragment(nfl_audio_path, start_ms=10000, duration_ms=5000)

        transcript = asr_component.transcribe(
            audio_data=audio_bytes,
            stream_id="e2e-sports-norm",
            sequence_number=0,
            start_time_ms=10000,
            end_time_ms=15000,
            domain="sports",
        )

        if transcript.status != TranscriptStatus.SUCCESS or not transcript.total_text.strip():
            pytest.skip("No speech in this segment")

        translator = DeepLTranslator()
        normalization_policy = NormalizationPolicy(
            enabled=True,
            normalize_time_phrases=True,
            expand_abbreviations=True,
            normalize_hyphens=True,
            normalize_symbols=True,
        )

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="ZH",
            normalization_policy=normalization_policy,
        )

        assert result.status == TranslationStatus.SUCCESS

        print("\n--- Sports Content with Normalization ---")
        print(f"Original ASR: {transcript.total_text}")
        if result.normalized_source_text:
            print(f"Normalized: {result.normalized_source_text}")
        print(f"Chinese: {result.translated_text}")


# =============================================================================
# Benchmark Tests
# =============================================================================


@pytest.mark.deepl_live
@pytest.mark.slow
@skip_without_deepl
class TestE2EPipelinePerformance:
    """Performance benchmarks for full pipeline."""

    def test_pipeline_latency_measurement(
        self,
        nfl_audio_path: Path,
        load_audio_fragment,
        asr_component: FasterWhisperASR,
    ):
        """Measure end-to-end latency for ASR + Translation."""
        import time

        translator = DeepLTranslator()
        measurements = []

        # Measure 5 fragments
        for i in range(5):
            start_ms = i * 2000
            audio_bytes = load_audio_fragment(
                nfl_audio_path,
                start_ms=start_ms,
                duration_ms=2000,
            )

            # Measure ASR
            asr_start = time.time()
            transcript = asr_component.transcribe(
                audio_data=audio_bytes,
                stream_id="e2e-benchmark",
                sequence_number=i,
                start_time_ms=start_ms,
                end_time_ms=start_ms + 2000,
                domain="sports",
            )
            asr_time = (time.time() - asr_start) * 1000

            if transcript.status != TranscriptStatus.SUCCESS or not transcript.total_text.strip():
                continue

            # Measure Translation
            trans_start = time.time()
            result = translate_transcript(
                transcript=transcript,
                translator=translator,
                target_language="ZH",
            )
            trans_time = (time.time() - trans_start) * 1000

            measurements.append(
                {
                    "asr_ms": asr_time,
                    "translation_ms": trans_time,
                    "total_ms": asr_time + trans_time,
                    "text_length": len(transcript.total_text),
                }
            )

        if not measurements:
            pytest.skip("No successful transcriptions")

        avg_asr = sum(m["asr_ms"] for m in measurements) / len(measurements)
        avg_trans = sum(m["translation_ms"] for m in measurements) / len(measurements)
        avg_total = sum(m["total_ms"] for m in measurements) / len(measurements)

        print("\n--- E2E Pipeline Latency Benchmark ---")
        print(f"Fragments measured: {len(measurements)}")
        print(f"Average ASR latency: {avg_asr:.1f}ms")
        print(f"Average Translation latency: {avg_trans:.1f}ms")
        print(f"Average Total latency: {avg_total:.1f}ms")
        print(f"Min Total: {min(m['total_ms'] for m in measurements):.1f}ms")
        print(f"Max Total: {max(m['total_ms'] for m in measurements):.1f}ms")


# =============================================================================
# Lineage Verification Tests
# =============================================================================


class TestAssetLineageTracking:
    """Verify asset lineage is correctly tracked through the pipeline."""

    def test_lineage_chain_integrity(
        self,
        nfl_audio_path: Path,
        load_audio_fragment,
        asr_component: FasterWhisperASR,
    ):
        """Verify parent_asset_ids correctly chain ASR → Translation."""
        audio_bytes = load_audio_fragment(nfl_audio_path, start_ms=5000, duration_ms=2000)

        transcript = asr_component.transcribe(
            audio_data=audio_bytes,
            stream_id="lineage-test",
            sequence_number=1,
            start_time_ms=5000,
            end_time_ms=7000,
            domain="sports",
        )

        if transcript.status != TranscriptStatus.SUCCESS:
            pytest.skip("ASR failed")

        translator = create_translation_component(mock=True)

        result = translate_transcript(
            transcript=transcript,
            translator=translator,
            target_language="zh",
        )

        # Verify lineage chain
        assert result.component == "translate"
        assert transcript.component == "asr"
        assert transcript.asset_id in result.parent_asset_ids
        assert result.stream_id == transcript.stream_id
        assert result.sequence_number == transcript.sequence_number

        # Verify unique asset IDs
        assert result.asset_id != transcript.asset_id

        print("\n--- Asset Lineage Verification ---")
        print(f"ASR Asset ID: {transcript.asset_id}")
        print(f"Translation Asset ID: {result.asset_id}")
        print(f"Translation Parent IDs: {result.parent_asset_ids}")
        print(f"Lineage correct: {transcript.asset_id in result.parent_asset_ids}")
