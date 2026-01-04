"""
Text Preprocessing for TTS Quality.

Provides deterministic text preprocessing rules to improve TTS synthesis quality.
All functions are pure (no side effects) and deterministic (same input = same output).

Features:
- Punctuation normalization (smart quotes to ASCII)
- Abbreviation expansion (NBA -> N B A, Dr. -> Doctor)
- Score pattern rewriting (15-12 -> 15 to 12)
- Whitespace normalization

Based on specs/008-tts-module/plan.md Phase 0 research.
"""

import re

# Punctuation replacement mapping
PUNCTUATION_MAP: dict[str, str] = {
    # Smart quotes
    "\u201c": '"',  # Left double quote
    "\u201d": '"',  # Right double quote
    "\u2018": "'",  # Left single quote
    "\u2019": "'",  # Right single quote
    # Dashes
    "\u2014": "--",  # Em dash
    "\u2013": "-",  # En dash
    # Other
    "\u2026": "...",  # Ellipsis
    "\u00a0": " ",  # Non-breaking space
}

# Abbreviation expansion mapping (case-sensitive)
ABBREVIATION_MAP: dict[str, str] = {
    # Sports abbreviations
    "NBA": "N B A",
    "NFL": "N F L",
    "MLB": "M L B",
    "NHL": "N H L",
    "NCAA": "N C A A",
    "MVP": "M V P",
    "USA": "U S A",
    "UK": "U K",
    # Titles
    "Dr.": "Doctor",
    "Mr.": "Mister",
    "Mrs.": "Missus",
    "Ms.": "Miss",
    "Prof.": "Professor",
    "Jr.": "Junior",
    "Sr.": "Senior",
    # Academic
    "PhD": "P H D",
    "MD": "M D",
    "MBA": "M B A",
    # Technical
    "CPU": "C P U",
    "GPU": "G P U",
    "AI": "A I",
    "API": "A P I",
}

# Score pattern regex (matches patterns like "15-12" but not "well-known")
SCORE_PATTERN = re.compile(r"\b(\d{1,3})-(\d{1,3})\b")


def normalize_punctuation(text: str) -> str:
    """Normalize special punctuation characters to ASCII equivalents.

    Replaces:
    - Smart quotes (" " ' ') with ASCII quotes (" ')
    - Em dash (—) with double hyphen (--)
    - En dash (–) with hyphen (-)
    - Ellipsis (…) with three dots (...)

    Args:
        text: Input text with potential special punctuation

    Returns:
        Text with normalized punctuation
    """
    result = text
    for special, replacement in PUNCTUATION_MAP.items():
        result = result.replace(special, replacement)
    return result


def expand_abbreviations(text: str) -> str:
    """Expand common abbreviations for better TTS pronunciation.

    Expansions:
    - NBA -> N B A (spelled out)
    - Dr. -> Doctor
    - PhD -> P H D

    Args:
        text: Input text with potential abbreviations

    Returns:
        Text with expanded abbreviations
    """
    result = text

    # Process each abbreviation
    for abbrev, expansion in ABBREVIATION_MAP.items():
        # Create a regex pattern for word boundaries
        # Handle abbreviations with periods specially
        if abbrev.endswith("."):
            # For abbreviations with period (Dr., Mr., etc.)
            pattern = re.compile(r"\b" + re.escape(abbrev))
        else:
            # For abbreviations without period (NBA, PhD, etc.)
            pattern = re.compile(r"\b" + re.escape(abbrev) + r"\b")

        result = pattern.sub(expansion, result)

    return result


def rewrite_score_patterns(text: str) -> str:
    """Rewrite score patterns for better TTS pronunciation.

    Converts:
    - "15-12" -> "15 to 12"
    - "3-0" -> "3 to 0"

    Does NOT convert:
    - "well-known" (hyphenated words)
    - "2020-2025" (year ranges - 4+ digits)

    Args:
        text: Input text with potential score patterns

    Returns:
        Text with rewritten score patterns
    """

    def replace_score(match: re.Match[str]) -> str:
        num1 = match.group(1)
        num2 = match.group(2)
        return f"{num1} to {num2}"

    return SCORE_PATTERN.sub(replace_score, text)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text.

    - Replaces multiple spaces with single space
    - Replaces tabs with spaces
    - Replaces newlines with spaces
    - Strips leading and trailing whitespace

    Args:
        text: Input text with potential whitespace issues

    Returns:
        Text with normalized whitespace
    """
    # Replace tabs and newlines with spaces
    result = text.replace("\t", " ").replace("\n", " ").replace("\r", " ")

    # Replace multiple spaces with single space
    result = re.sub(r" +", " ", result)

    # Strip leading and trailing whitespace
    return result.strip()


def preprocess_text_for_tts(text: str) -> str:
    """Complete preprocessing pipeline for TTS input text.

    Applies all preprocessing steps in the correct order:
    1. Normalize punctuation (smart quotes, dashes, etc.)
    2. Expand abbreviations (NBA, Dr., etc.)
    3. Rewrite score patterns (15-12 -> 15 to 12)
    4. Normalize whitespace

    This function is pure (no side effects) and deterministic
    (same input always produces same output).

    Args:
        text: Raw input text for TTS

    Returns:
        Preprocessed text ready for TTS synthesis
    """
    if not text:
        return ""

    # Apply preprocessing steps in order
    result = text

    # 1. Normalize punctuation first
    result = normalize_punctuation(result)

    # 2. Expand abbreviations
    result = expand_abbreviations(result)

    # 3. Rewrite score patterns
    result = rewrite_score_patterns(result)

    # 4. Normalize whitespace last
    result = normalize_whitespace(result)

    return result
