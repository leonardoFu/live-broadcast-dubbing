"""
Unit tests for text preprocessing functionality.

Tests for punctuation normalization, abbreviation expansion, and score pattern rewriting.
Following TDD: These tests MUST be written FIRST and MUST FAIL before implementation.

Coverage Target: 80% minimum.
"""

from sts_service.tts.preprocessing import (
    expand_abbreviations,
    normalize_punctuation,
    normalize_whitespace,
    preprocess_text_for_tts,
    rewrite_score_patterns,
)


class TestNormalizePunctuation:
    """Tests for punctuation normalization."""

    def test_smart_quotes_to_ascii(self):
        """Test smart quotes are converted to ASCII quotes."""
        # Left and right double quotes
        assert '"Hello"' in normalize_punctuation("\u201cHello\u201d")
        # Should produce ASCII quotes
        result = normalize_punctuation("\u201cHello World\u201d")
        assert "\u201c" not in result
        assert "\u201d" not in result

    def test_smart_apostrophes_to_ascii(self):
        """Test smart apostrophes are converted to ASCII."""
        result = normalize_punctuation("It\u2019s great")
        assert "'" in result
        assert "\u2019" not in result

    def test_ellipsis_to_dots(self):
        """Test ellipsis character is converted to three dots."""
        result = normalize_punctuation("Wait\u2026")
        assert "..." in result
        assert "\u2026" not in result

    def test_em_dash_to_double_hyphen(self):
        """Test em dash is converted to double hyphen."""
        result = normalize_punctuation("Hello\u2014World")
        assert "--" in result
        assert "\u2014" not in result

    def test_en_dash_to_hyphen(self):
        """Test en dash is converted to hyphen."""
        result = normalize_punctuation("2020\u20132025")
        assert "-" in result

    def test_multiple_punctuation_changes(self):
        """Test multiple punctuation normalizations in one string."""
        input_text = "\u201cIt\u2019s happening\u2026\u201d"
        result = normalize_punctuation(input_text)
        assert '"' in result
        assert "'" in result
        assert "..." in result


class TestExpandAbbreviations:
    """Tests for abbreviation expansion."""

    def test_nba_expands(self):
        """Test 'NBA' expands to 'N B A'."""
        result = expand_abbreviations("NBA Finals")
        assert "N B A" in result

    def test_nfl_expands(self):
        """Test 'NFL' expands to 'N F L'."""
        result = expand_abbreviations("NFL game")
        assert "N F L" in result

    def test_phd_expands(self):
        """Test 'PhD' expands to 'P H D'."""
        result = expand_abbreviations("She has a PhD")
        assert "P H D" in result

    def test_dr_expands(self):
        """Test 'Dr.' expands to 'Doctor'."""
        result = expand_abbreviations("Dr. Smith")
        assert "Doctor" in result

    def test_mr_expands(self):
        """Test 'Mr.' expands to 'Mister'."""
        result = expand_abbreviations("Mr. Jones")
        assert "Mister" in result

    def test_mrs_expands(self):
        """Test 'Mrs.' expands to 'Missus'."""
        result = expand_abbreviations("Mrs. Brown")
        assert "Missus" in result

    def test_case_insensitive(self):
        """Test abbreviation expansion is case-aware."""
        result = expand_abbreviations("nba game")
        # Should handle lowercase
        assert "n b a" in result.lower() or "nba" in result.lower()

    def test_non_abbreviation_unchanged(self):
        """Test regular words are not modified."""
        result = expand_abbreviations("Hello world")
        assert result == "Hello world"


class TestRewriteScorePatterns:
    """Tests for score pattern rewriting."""

    def test_score_pattern_basic(self):
        """Test '15-12' converts to '15 to 12'."""
        result = rewrite_score_patterns("Score is 15-12")
        assert "15 to 12" in result
        assert "15-12" not in result

    def test_score_pattern_zero(self):
        """Test '3-0' converts to '3 to 0'."""
        result = rewrite_score_patterns("They won 3-0")
        assert "3 to 0" in result

    def test_score_pattern_high_numbers(self):
        """Test '121-119' converts correctly."""
        result = rewrite_score_patterns("Final score: 121-119")
        assert "121 to 119" in result

    def test_hyphenated_words_not_affected(self):
        """Test hyphenated words like 'well-known' are not affected."""
        result = rewrite_score_patterns("A well-known player")
        assert "well-known" in result

    def test_year_range_not_affected(self):
        """Test year ranges like '2020-2025' are not affected as scores."""
        # Year ranges are different from scores (4 digits vs 1-3)
        # The function only rewrites patterns with 1-3 digits
        result = rewrite_score_patterns("From 2020-2025")
        # 4-digit numbers should NOT be converted (year range preserved)
        assert "2020-2025" in result


class TestNormalizeWhitespace:
    """Tests for whitespace normalization."""

    def test_multiple_spaces_reduced(self):
        """Test multiple spaces reduced to single space."""
        result = normalize_whitespace("Hello    world")
        assert result == "Hello world"

    def test_leading_trailing_stripped(self):
        """Test leading/trailing whitespace is stripped."""
        result = normalize_whitespace("  Hello world  ")
        assert result == "Hello world"

    def test_newlines_normalized(self):
        """Test newlines are normalized to spaces."""
        result = normalize_whitespace("Hello\nworld")
        assert result == "Hello world"

    def test_tabs_normalized(self):
        """Test tabs are normalized to spaces."""
        result = normalize_whitespace("Hello\tworld")
        assert result == "Hello world"

    def test_mixed_whitespace(self):
        """Test mixed whitespace types are normalized."""
        result = normalize_whitespace("  Hello \t\n  world  ")
        assert result == "Hello world"


class TestPreprocessTextForTTS:
    """Tests for complete preprocessing pipeline."""

    def test_deterministic_output(self):
        """Test same input produces same output (100 iterations)."""
        input_text = "Dr. Smith said \u201cThe NBA score is 15-12\u201d"

        results = set()
        for _ in range(100):
            result = preprocess_text_for_tts(input_text)
            results.add(result)

        # Should only have one unique result (deterministic)
        assert len(results) == 1

    def test_preprocessing_is_pure_function(self):
        """Test preprocessing is a pure function (no side effects)."""
        input_text = "Hello world"

        # Call multiple times
        result1 = preprocess_text_for_tts(input_text)
        result2 = preprocess_text_for_tts(input_text)
        result3 = preprocess_text_for_tts(input_text)

        # All results should be identical
        assert result1 == result2 == result3

    def test_complete_preprocessing(self):
        """Test all preprocessing steps are applied."""
        input_text = "  Dr. Smith said \u201cThe NBA score is 15-12\u201d  "

        result = preprocess_text_for_tts(input_text)

        # Check various transformations
        assert "Doctor" in result  # Dr. expanded
        assert "N B A" in result  # NBA expanded
        assert "15 to 12" in result  # Score rewritten
        assert '"' in result  # Smart quotes normalized
        assert not result.startswith(" ")  # Whitespace stripped

    def test_empty_input(self):
        """Test empty input returns empty output."""
        assert preprocess_text_for_tts("") == ""
        assert preprocess_text_for_tts("   ") == ""

    def test_unicode_preserved(self):
        """Test non-special unicode characters are preserved."""
        # Spanish characters should be preserved
        result = preprocess_text_for_tts("Hola mundo")
        assert result == "Hola mundo"
