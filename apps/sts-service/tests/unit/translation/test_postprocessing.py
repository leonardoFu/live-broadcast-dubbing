"""
Tests for TTS cleanup postprocessing (T009).

TDD: These tests are written BEFORE the implementation.
"""


class TestTTSCleanup:
    """Tests for TTSCleanup class."""

    def test_cleanup_exists(self):
        """Test TTSCleanup can be imported."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        assert cleanup is not None

    def test_normalize_smart_double_quotes(self):
        """Test smart double quotes normalization: quotes -> straight quotes."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("\u201cHello\u201d")  # "Hello"

        assert result == '"Hello"'

    def test_normalize_smart_single_quotes(self):
        """Test smart single quotes normalization."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("\u2018Hi\u2019")  # 'Hi'

        assert result == "'Hi'"

    def test_normalize_em_dash(self):
        """Test em dash normalization: em-dash -> hyphen."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("Hello\u2014world")  # em-dash

        assert result == "Hello-world"

    def test_normalize_en_dash(self):
        """Test en dash normalization: en-dash -> hyphen."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("Hello\u2013world")  # en-dash

        assert result == "Hello-world"

    def test_normalize_scores(self):
        """Test score rewriting: '15-12' -> '15 to 12'."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("The score is 15-12")

        assert result == "The score is 15 to 12"

    def test_normalize_scores_different_numbers(self):
        """Test various score patterns."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()

        assert cleanup.cleanup("21-14") == "21 to 14"
        assert cleanup.cleanup("7-0") == "7 to 0"
        assert cleanup.cleanup("100-99") == "100 to 99"

    def test_normalize_whitespace_multiple_spaces(self):
        """Test multiple spaces normalized to single."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("a  b   c    d")

        assert result == "a b c d"

    def test_normalize_whitespace_tabs(self):
        """Test tabs normalized to spaces."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("a\tb\tc")

        assert result == "a b c"

    def test_normalize_whitespace_newlines(self):
        """Test newlines normalized to spaces."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("a\nb\nc")

        assert result == "a b c"

    def test_normalize_whitespace_leading_trailing(self):
        """Test leading/trailing whitespace removed."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("  hello world  ")

        assert result == "hello world"

    def test_determinism_100_runs(self):
        """Test determinism: same input 100 times -> same output."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        test_input = "\u201cThe score is 21-14\u2014an exciting game!\u201d"

        first_result = cleanup.cleanup(test_input)
        for _ in range(100):
            result = cleanup.cleanup(test_input)
            assert result == first_result

    def test_empty_string(self):
        """Test empty string handling."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("")

        assert result == ""

    def test_combined_cleanup(self):
        """Test all cleanup rules applied together."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("\u201cThe score is 21-14\u2014what   a game!\u201d")

        # Check all rules applied
        assert '"' in result  # smart quotes normalized
        assert "21 to 14" in result  # score rewritten
        assert "-" in result  # em-dash to hyphen
        assert "what a game" in result  # multiple spaces normalized

    def test_mixed_smart_punctuation(self):
        """Test mixed smart punctuation in realistic text."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()
        result = cleanup.cleanup("She said, \u201cI\u2019ll be there\u2014soon!\u201d")

        assert result == 'She said, "I\'ll be there-soon!"'

    def test_preserve_regular_hyphens(self):
        """Test regular hyphens in non-score context are preserved."""
        from sts_service.translation.postprocessing import TTSCleanup

        cleanup = TTSCleanup()

        # Score pattern (numbers) gets rewritten
        assert cleanup.cleanup("15-12") == "15 to 12"

        # Non-score hyphen preserved (this is a word hyphen)
        assert cleanup.cleanup("self-aware") == "self-aware"
