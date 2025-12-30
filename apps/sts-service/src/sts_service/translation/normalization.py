"""
Translation-oriented text normalization.

Applies deterministic normalization rules to reduce translation variance.
"""

import re

from .models import NormalizationPolicy


class TranslationNormalizer:
    """Applies deterministic normalization rules for translation.

    Rules:
    1. Time phrases: "1:54 REMAINING" -> "1:54 remaining"
    2. Hyphens: "TEN-YARD" -> "TEN YARD" (preserve score patterns)
    3. Abbreviations: "NFL" -> "N F L", "vs." -> "versus"
    4. Symbols: "&" -> "and", "%" -> "percent", "$" -> "dollars"
    """

    # Abbreviation expansion mappings
    _ABBREVIATIONS = {
        r"\bNFL\b": "N F L",
        r"\bNBA\b": "N B A",
        r"\bMLB\b": "M L B",
        r"\bNHL\b": "N H L",
        r"\bvs\.": "versus",
        r"\bVS\b": "versus",
    }

    # Symbol expansion mappings
    _SYMBOLS = {
        "&": " and ",
        "%": " percent ",
        "$": " dollars ",
        "@": " at ",
    }

    def normalize(self, text: str, policy: NormalizationPolicy) -> str:
        """Apply normalization rules based on policy.

        Args:
            text: Input text to normalize
            policy: Normalization policy controlling which rules to apply

        Returns:
            Normalized text
        """
        if not policy.enabled:
            return text

        if not text:
            return text

        result = text

        if policy.normalize_time_phrases:
            result = self._normalize_time_phrases(result)

        if policy.normalize_hyphens:
            result = self._normalize_hyphens(result)

        if policy.expand_abbreviations:
            result = self._expand_abbreviations(result)

        if policy.normalize_symbols:
            result = self._normalize_symbols(result)

        return result

    def _normalize_time_phrases(self, text: str) -> str:
        """Normalize time phrases: '1:54 REMAINING' -> '1:54 remaining'.

        Lowercases words following time patterns (HH:MM or M:SS format).
        """
        # Match time format followed by uppercase words
        pattern = r"(\d+:\d+)\s+([A-Z]+)"

        def replace_time_phrase(match: re.Match[str]) -> str:
            time_part = match.group(1)
            word_part = match.group(2).lower()
            return f"{time_part} {word_part}"

        return re.sub(pattern, replace_time_phrase, text)

    def _normalize_hyphens(self, text: str) -> str:
        """Normalize hyphens: 'TEN-YARD' -> 'TEN YARD'.

        Preserves score patterns like '15-12' (digit-digit).
        """
        # Only replace hyphens between uppercase letter sequences
        # This pattern matches WORD-WORD but not 15-12
        pattern = r"([A-Z]+)-([A-Z]+)"
        return re.sub(pattern, r"\1 \2", text)

    def _expand_abbreviations(self, text: str) -> str:
        """Expand common abbreviations.

        NFL -> N F L, vs. -> versus, etc.
        """
        result = text
        for pattern, replacement in self._ABBREVIATIONS.items():
            result = re.sub(pattern, replacement, result)
        return result

    def _normalize_symbols(self, text: str) -> str:
        """Expand symbols to words.

        & -> and, % -> percent, $ -> dollars, @ -> at
        """
        result = text
        for symbol, replacement in self._SYMBOLS.items():
            result = result.replace(symbol, replacement)
        return result
