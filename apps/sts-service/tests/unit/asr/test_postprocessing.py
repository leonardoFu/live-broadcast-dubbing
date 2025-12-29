"""
Unit tests for postprocessing (utterance shaping) functions.

TDD: These tests are written BEFORE implementation.
"""

import pytest


class TestImproveSentenceBoundaries:
    """Tests for the segment merging function."""

    def test_improve_sentence_boundaries_merges_short_segments(self):
        """Test that segments shorter than threshold are merged."""
        from sts_service.asr.models import TranscriptSegment
        from sts_service.asr.postprocessing import improve_sentence_boundaries

        segments = [
            TranscriptSegment(start_time_ms=0, end_time_ms=500, text="Hello", confidence=0.9),
            TranscriptSegment(start_time_ms=500, end_time_ms=800, text="there", confidence=0.85),
        ]

        result = improve_sentence_boundaries(segments, merge_threshold_seconds=1.0)

        # Both segments are <1s, should be merged
        assert len(result) == 1
        assert result[0].text == "Hello there"
        assert result[0].start_time_ms == 0
        assert result[0].end_time_ms == 800

    def test_improve_sentence_boundaries_preserves_long_segments(self):
        """Test that segments longer than threshold are preserved."""
        from sts_service.asr.models import TranscriptSegment
        from sts_service.asr.postprocessing import improve_sentence_boundaries

        segments = [
            TranscriptSegment(start_time_ms=0, end_time_ms=2000, text="Hello there", confidence=0.9),
            TranscriptSegment(start_time_ms=2000, end_time_ms=4000, text="How are you", confidence=0.85),
        ]

        result = improve_sentence_boundaries(segments, merge_threshold_seconds=1.0)

        # Both segments are >1s, should NOT be merged
        assert len(result) == 2

    def test_improve_sentence_boundaries_handles_empty_list(self):
        """Test that empty segment list returns empty."""
        from sts_service.asr.postprocessing import improve_sentence_boundaries

        result = improve_sentence_boundaries([], merge_threshold_seconds=1.0)

        assert result == []

    def test_improve_sentence_boundaries_single_segment(self):
        """Test that single segment is returned as-is."""
        from sts_service.asr.models import TranscriptSegment
        from sts_service.asr.postprocessing import improve_sentence_boundaries

        segments = [
            TranscriptSegment(start_time_ms=0, end_time_ms=500, text="Hello", confidence=0.9),
        ]

        result = improve_sentence_boundaries(segments, merge_threshold_seconds=1.0)

        assert len(result) == 1
        assert result[0].text == "Hello"

    def test_improve_sentence_boundaries_updates_timestamps(self):
        """Test that merged segment has correct timestamps."""
        from sts_service.asr.models import TranscriptSegment
        from sts_service.asr.postprocessing import improve_sentence_boundaries

        segments = [
            TranscriptSegment(start_time_ms=100, end_time_ms=400, text="A", confidence=0.9),
            TranscriptSegment(start_time_ms=400, end_time_ms=700, text="B", confidence=0.8),
            TranscriptSegment(start_time_ms=700, end_time_ms=900, text="C", confidence=0.7),
        ]

        result = improve_sentence_boundaries(segments, merge_threshold_seconds=1.0)

        # All merged into one
        assert len(result) == 1
        assert result[0].start_time_ms == 100
        assert result[0].end_time_ms == 900

    def test_improve_sentence_boundaries_recalculates_confidence(self):
        """Test that merged segment has averaged confidence."""
        from sts_service.asr.models import TranscriptSegment
        from sts_service.asr.postprocessing import improve_sentence_boundaries

        segments = [
            TranscriptSegment(start_time_ms=0, end_time_ms=400, text="A", confidence=0.8),
            TranscriptSegment(start_time_ms=400, end_time_ms=800, text="B", confidence=0.6),
        ]

        result = improve_sentence_boundaries(segments, merge_threshold_seconds=1.0)

        assert len(result) == 1
        assert result[0].confidence == pytest.approx(0.7, rel=0.01)  # Average of 0.8 and 0.6


class TestSplitLongSegments:
    """Tests for the segment splitting function."""

    def test_split_long_segments_at_sentence_boundary(self):
        """Test that long segments are split at sentence boundaries."""
        from sts_service.asr.models import TranscriptSegment, WordTiming
        from sts_service.asr.postprocessing import split_long_segments

        # 8 second segment with words
        words = [
            WordTiming(start_time_ms=0, end_time_ms=1000, word="This"),
            WordTiming(start_time_ms=1000, end_time_ms=2000, word="is"),
            WordTiming(start_time_ms=2000, end_time_ms=3000, word="a"),
            WordTiming(start_time_ms=3000, end_time_ms=4000, word="test."),  # Period = sentence end
            WordTiming(start_time_ms=4000, end_time_ms=5000, word="And"),
            WordTiming(start_time_ms=5000, end_time_ms=6000, word="more"),
            WordTiming(start_time_ms=6000, end_time_ms=7000, word="text"),
            WordTiming(start_time_ms=7000, end_time_ms=8000, word="here."),
        ]

        segment = TranscriptSegment(
            start_time_ms=0,
            end_time_ms=8000,
            text="This is a test. And more text here.",
            confidence=0.9,
            words=words,
        )

        result = split_long_segments([segment], max_duration_seconds=6.0)

        # Should be split at sentence boundary
        assert len(result) >= 2

    def test_split_long_segments_at_word_boundary(self):
        """Test that segments without sentence boundaries split at words."""
        from sts_service.asr.models import TranscriptSegment, WordTiming
        from sts_service.asr.postprocessing import split_long_segments

        # 8 second segment without sentence boundaries
        words = [
            WordTiming(start_time_ms=0, end_time_ms=2000, word="One"),
            WordTiming(start_time_ms=2000, end_time_ms=4000, word="two"),
            WordTiming(start_time_ms=4000, end_time_ms=6000, word="three"),
            WordTiming(start_time_ms=6000, end_time_ms=8000, word="four"),
        ]

        segment = TranscriptSegment(
            start_time_ms=0,
            end_time_ms=8000,
            text="One two three four",
            confidence=0.9,
            words=words,
        )

        result = split_long_segments([segment], max_duration_seconds=5.0)

        # Should be split, each part <= 5s
        assert len(result) >= 2
        for seg in result:
            assert seg.duration_ms <= 5000 + 1000  # Allow 1s tolerance

    def test_split_long_segments_preserves_short_segments(self):
        """Test that short segments are not split."""
        from sts_service.asr.models import TranscriptSegment
        from sts_service.asr.postprocessing import split_long_segments

        segment = TranscriptSegment(
            start_time_ms=0,
            end_time_ms=3000,
            text="Short segment",
            confidence=0.9,
        )

        result = split_long_segments([segment], max_duration_seconds=6.0)

        assert len(result) == 1
        assert result[0].text == "Short segment"

    def test_split_long_segments_handles_no_words(self):
        """Test splitting segment without word-level timestamps."""
        from sts_service.asr.models import TranscriptSegment
        from sts_service.asr.postprocessing import split_long_segments

        segment = TranscriptSegment(
            start_time_ms=0,
            end_time_ms=10000,
            text="Long segment without word timestamps",
            confidence=0.9,
            words=None,
        )

        result = split_long_segments([segment], max_duration_seconds=6.0)

        # Without word timestamps, cannot split precisely
        # Should return original or attempt text-based split
        assert len(result) >= 1

    def test_split_long_segments_max_duration_respected(self):
        """Test that resulting segments respect max duration."""
        from sts_service.asr.models import TranscriptSegment, WordTiming
        from sts_service.asr.postprocessing import split_long_segments

        # Create many short words spanning 10 seconds
        words = [
            WordTiming(start_time_ms=i * 500, end_time_ms=(i + 1) * 500, word=f"w{i}")
            for i in range(20)
        ]

        segment = TranscriptSegment(
            start_time_ms=0,
            end_time_ms=10000,
            text=" ".join(f"w{i}" for i in range(20)),
            confidence=0.9,
            words=words,
        )

        result = split_long_segments([segment], max_duration_seconds=3.0)

        # Each resulting segment should be <= 3s (with tolerance)
        for seg in result:
            assert seg.duration_ms <= 4000  # 3s + 1s tolerance


class TestShapeUtterances:
    """Tests for the complete utterance shaping pipeline."""

    def test_shape_utterances_pipeline(self):
        """Test that shaping applies both merge and split."""
        from sts_service.asr.models import TranscriptSegment, UtteranceShapingConfig
        from sts_service.asr.postprocessing import shape_utterances

        # Mix of short and long segments
        segments = [
            TranscriptSegment(start_time_ms=0, end_time_ms=300, text="Hi", confidence=0.9),
            TranscriptSegment(start_time_ms=300, end_time_ms=600, text="there", confidence=0.85),
            # Long gap
            TranscriptSegment(start_time_ms=2000, end_time_ms=4000, text="How are you", confidence=0.8),
        ]

        config = UtteranceShapingConfig(
            merge_threshold_seconds=1.0,
            max_segment_duration_seconds=6.0,
        )

        result = shape_utterances(segments, config)

        # First two should be merged
        assert len(result) >= 1
        # Text content preserved
        all_text = " ".join(s.text for s in result)
        assert "Hi" in all_text
        assert "there" in all_text
        assert "How are you" in all_text
