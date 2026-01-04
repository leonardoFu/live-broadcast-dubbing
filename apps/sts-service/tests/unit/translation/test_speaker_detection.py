"""
Tests for speaker label detection (T007).

TDD: These tests are written BEFORE the implementation.
"""


class TestSpeakerLabelDetector:
    """Tests for SpeakerLabelDetector class."""

    def test_detector_exists(self):
        """Test SpeakerLabelDetector can be imported."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        assert detector is not None

    def test_detect_simple_pattern(self):
        """Test pattern matching: 'Alice: text' -> ('Alice', 'text')."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        speaker, text = detector.detect_and_remove("Alice: How are you today?")

        assert speaker == "Alice"
        assert text == "How are you today?"

    def test_detect_chevron_pattern(self):
        """Test pattern matching: '>> Bob: text' -> ('Bob', 'text')."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        speaker, text = detector.detect_and_remove(">> Bob: I'm doing great!")

        assert speaker == "Bob"
        assert text == "I'm doing great!"

    def test_no_match_returns_default(self):
        """Test no match: 'Hello world' -> ('default', 'Hello world')."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        speaker, text = detector.detect_and_remove("Hello world")

        assert speaker == "default"
        assert text == "Hello world"

    def test_false_positive_time_format(self):
        """Test false positive avoidance: 'Time: 1:54' should NOT match."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        speaker, text = detector.detect_and_remove("Time: 1:54 remaining")

        # "Time" starts with uppercase but should not be treated as speaker
        # because it's a common word
        assert speaker == "default"
        assert text == "Time: 1:54 remaining"

    def test_false_positive_score_format(self):
        """Test false positive avoidance: 'Score: 21-14' should NOT match."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        speaker, text = detector.detect_and_remove("Score: 21-14 at halftime")

        assert speaker == "default"
        assert text == "Score: 21-14 at halftime"

    def test_empty_string_handling(self):
        """Test empty string handling."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        speaker, text = detector.detect_and_remove("")

        assert speaker == "default"
        assert text == ""

    def test_whitespace_only_handling(self):
        """Test whitespace-only string handling."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        speaker, text = detector.detect_and_remove("   ")

        assert speaker == "default"
        assert text == "   "

    def test_determinism_100_runs(self):
        """Test determinism: same input 100 times -> same output."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        test_input = "Alice: Hello world"

        first_result = detector.detect_and_remove(test_input)
        for _ in range(100):
            result = detector.detect_and_remove(test_input)
            assert result == first_result

    def test_custom_patterns(self):
        """Test custom patterns can be provided."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        # Custom pattern for SPEAKER_1: format
        detector = SpeakerLabelDetector(patterns=[r"^(SPEAKER_\d+): "])
        speaker, text = detector.detect_and_remove("SPEAKER_1: Hello there")

        assert speaker == "SPEAKER_1"
        assert text == "Hello there"

    def test_multiple_colons_in_text(self):
        """Test text with multiple colons preserves content after first match."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        speaker, text = detector.detect_and_remove("Alice: The time is 3:45 PM")

        assert speaker == "Alice"
        assert text == "The time is 3:45 PM"

    def test_all_uppercase_name_not_matched(self):
        """Test all uppercase names don't match (pattern requires Titlecase)."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        speaker, text = detector.detect_and_remove("BOB: Hello")

        # Pattern is ^[A-Z][a-z]+: which requires at least one lowercase
        assert speaker == "default"
        assert text == "BOB: Hello"

    def test_speaker_with_trailing_whitespace(self):
        """Test speaker detection with various whitespace."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        detector = SpeakerLabelDetector()
        speaker, text = detector.detect_and_remove("Alice:  Hello")

        # Should handle extra space after colon
        assert speaker == "Alice"
        assert text == " Hello"  # Preserves the extra space

    def test_default_patterns_constant(self):
        """Test DEFAULT_PATTERNS is accessible."""
        from sts_service.translation.preprocessing import SpeakerLabelDetector

        assert hasattr(SpeakerLabelDetector, "DEFAULT_PATTERNS")
        assert len(SpeakerLabelDetector.DEFAULT_PATTERNS) >= 2
