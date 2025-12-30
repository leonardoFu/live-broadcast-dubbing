"""
TTS-oriented text cleanup for Translation component.

Applies post-translation cleanup rules for better TTS pronunciation.
"""

import re


class TTSCleanup:
    """Applies TTS-oriented cleanup to translated text.

    Rules:
    1. Smart punctuation: Unicode quotes/dashes -> ASCII equivalents
    2. Score rewriting: "15-12" -> "15 to 12"
    3. Whitespace normalization: multiple spaces/tabs/newlines -> single space
    """

    # Smart punctuation replacements
    _SMART_PUNCTUATION = {
        "\u201c": '"',  # Left double quotation mark
        "\u201d": '"',  # Right double quotation mark
        "\u2018": "'",  # Left single quotation mark
        "\u2019": "'",  # Right single quotation mark
        "\u2014": "-",  # Em dash
        "\u2013": "-",  # En dash
    }

    def cleanup(self, text: str) -> str:
        """Apply TTS-oriented cleanup rules.

        Args:
            text: Translated text to clean up

        Returns:
            Cleaned up text optimized for TTS
        """
        if not text:
            return text

        result = text

        # Step 1: Normalize smart punctuation
        result = self._normalize_smart_punctuation(result)

        # Step 2: Rewrite scores (must be after smart punctuation)
        result = self._normalize_scores(result)

        # Step 3: Normalize whitespace (always last)
        result = self._normalize_whitespace(result)

        return result

    def _normalize_smart_punctuation(self, text: str) -> str:
        """Replace Unicode smart punctuation with ASCII equivalents.

        Smart quotes: " " -> ", ' ' -> '
        Em/en dashes: - - -> -
        """
        result = text
        for smart, simple in self._SMART_PUNCTUATION.items():
            result = result.replace(smart, simple)
        return result

    def _normalize_scores(self, text: str) -> str:
        """Rewrite score patterns: '15-12' -> '15 to 12'.

        Only rewrites digit-hyphen-digit patterns.
        """
        pattern = r"(\d+)-(\d+)"
        return re.sub(pattern, r"\1 to \2", text)

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace: multiple spaces/tabs/newlines -> single space.

        Also strips leading/trailing whitespace.
        """
        return " ".join(text.split())
