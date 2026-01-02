"""
Tests for translation normalization (T008).

TDD: These tests are written BEFORE the implementation.
"""



class TestTranslationNormalizer:
    """Tests for TranslationNormalizer class."""

    def test_normalizer_exists(self):
        """Test TranslationNormalizer can be imported."""
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        assert normalizer is not None

    def test_normalize_time_phrases(self):
        """Test time phrase normalization: '1:54 REMAINING' -> '1:54 remaining'."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(normalize_time_phrases=True)

        result = normalizer.normalize("1:54 REMAINING", policy)
        assert result == "1:54 remaining"

    def test_normalize_time_phrases_complex(self):
        """Test complex time phrase: '2:30 LEFT IN THE QUARTER'."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(normalize_time_phrases=True)

        result = normalizer.normalize("2:30 LEFT IN THE QUARTER", policy)
        assert "2:30 left" in result

    def test_normalize_hyphens_word_compound(self):
        """Test hyphen normalization: 'TEN-YARD' -> 'TEN YARD'."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(normalize_hyphens=True)

        result = normalizer.normalize("TEN-YARD LINE", policy)
        assert result == "TEN YARD LINE"

    def test_preserve_score_hyphens(self):
        """Test score patterns like '15-12' are preserved."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(normalize_hyphens=True)

        result = normalizer.normalize("15-12", policy)
        assert result == "15-12"  # Score preserved

    def test_expand_abbreviation_nfl(self):
        """Test abbreviation expansion: 'NFL' -> 'N F L'."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(expand_abbreviations=True)

        result = normalizer.normalize("NFL GAME", policy)
        assert result == "N F L GAME"

    def test_expand_abbreviation_vs(self):
        """Test abbreviation expansion: 'vs.' -> 'versus'."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(expand_abbreviations=True)

        result = normalizer.normalize("CHIEFS vs. BILLS", policy)
        assert "versus" in result

    def test_expand_abbreviation_vs_uppercase(self):
        """Test abbreviation expansion: 'VS' -> 'versus'."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(expand_abbreviations=True)

        result = normalizer.normalize("CHIEFS VS BILLS", policy)
        assert "versus" in result

    def test_normalize_symbol_ampersand(self):
        """Test symbol normalization: '&' -> 'and'."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(normalize_symbols=True)

        result = normalizer.normalize("M&M", policy)
        assert "and" in result

    def test_normalize_symbol_percent(self):
        """Test symbol normalization: '%' -> 'percent'."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(normalize_symbols=True)

        result = normalizer.normalize("100%", policy)
        assert "percent" in result

    def test_normalize_symbol_dollar(self):
        """Test symbol normalization: '$' -> 'dollars'."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(normalize_symbols=True)

        result = normalizer.normalize("$50", policy)
        assert "dollars" in result

    def test_normalize_symbol_at(self):
        """Test symbol normalization: '@' -> 'at'."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(normalize_symbols=True)

        result = normalizer.normalize("email@test.com", policy)
        assert " at " in result

    def test_policy_disabled_returns_unchanged(self):
        """Test policy enabled=False returns input unchanged."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy(enabled=False)

        test_input = "NFL 1:54 REMAINING & CHIEFS VS BILLS"
        result = normalizer.normalize(test_input, policy)
        assert result == test_input

    def test_individual_rules_disabled(self):
        """Test individual rules can be disabled."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()

        # Only time phrases enabled
        policy = NormalizationPolicy(
            enabled=True,
            normalize_time_phrases=True,
            expand_abbreviations=False,
            normalize_hyphens=False,
            normalize_symbols=False,
        )

        result = normalizer.normalize("NFL 1:54 REMAINING", policy)
        assert "1:54 remaining" in result
        assert "NFL" in result  # NOT expanded

    def test_determinism_100_runs(self):
        """Test determinism: same input 100 times -> same output."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy()
        test_input = "NFL 1:54 REMAINING & CHIEFS VS BILLS"

        first_result = normalizer.normalize(test_input, policy)
        for _ in range(100):
            result = normalizer.normalize(test_input, policy)
            assert result == first_result

    def test_empty_string(self):
        """Test empty string handling."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy()

        result = normalizer.normalize("", policy)
        assert result == ""

    def test_combined_rules(self):
        """Test all normalization rules applied together."""
        from sts_service.translation.models import NormalizationPolicy
        from sts_service.translation.normalization import TranslationNormalizer

        normalizer = TranslationNormalizer()
        policy = NormalizationPolicy()

        result = normalizer.normalize(
            "NFL 1:54 REMAINING & TEN-YARD LINE VS BILLS", policy
        )

        # Check all rules applied
        assert "N F L" in result  # abbreviation expanded
        assert "1:54 remaining" in result  # time phrase normalized
        assert " and " in result  # & expanded
        assert "TEN YARD" in result  # hyphen normalized
        assert "versus" in result  # VS expanded
