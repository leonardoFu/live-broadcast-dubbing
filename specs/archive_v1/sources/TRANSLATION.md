# Translation Text Pipeline (Pre/Post Processing)

This repo’s translation *quality* and *real-time stability* are heavily influenced by lightweight text normalization in `.sts-service-archive/utils/text_processing.py`. The goal is to feed cleaner, more consistent strings into the MT model (M2M100 in the runtime scripts) and produce TTS-friendly output with minimal per-segment latency.

## Where This Fits (Real-Time Path)

Per ASR segment (or per combined utterance) the live scripts effectively do:

1. **(Optional) Speaker label handling**
   - `detect_speaker(text)` extracts a text-based speaker label (e.g., `Referee:`) when present.
   - `clean_speaker_prefix(text, speaker)` removes that prefix so MT/TTS don’t “translate the label”.

2. **Translation-oriented normalization**
   - `preprocess_text_for_translation(text)` standardizes the text specifically to reduce MT errors and cache churn.

3. **MT model inference**
   - Done elsewhere (e.g. `talk_multi_coqui.py`), typically translating EN → target language.

4. **TTS-oriented cleanup (when needed)**
   - `preprocess_text_for_tts(text, convert_numbers=...)` and `clean_punctuation(text)` make the final string easier to pronounce.

## Dependencies (and Why)

- **`re` (stdlib)**: fast regex-based normalization suitable for per-segment real-time processing.
- **`inflect` (optional)**: converts digits → English words when enabled; improves MT behavior in some cases (especially number-heavy sports text). If not installed, there’s a small built-in fallback for basic numbers.

No network calls or heavy NLP libraries are used in this module to keep latency predictable.

## Translation Quality “Tuning” Logic

These are the key heuristics used to make M2M100 (and downstream TTS) behave better:

- **Time/clock phrases**
  - Special-cases scoreboard-style text like `1:54 REMAINING` to keep it readable and consistent (not shouting in ALL CAPS), and to avoid odd tokenization.

- **Hyphen handling**
  - Normalizes hyphenated sports phrases (`TEN-YARD`) into space-separated tokens (`TEN YARD`) so MT is less likely to mistranslate or drop parts of the phrase.

- **Abbreviation and symbol expansion**
  - Expands/rewrites common items so MT and TTS don’t guess:
    - Acronyms like `NFL` → `N F L` (better spoken output; often also reduces MT weirdness).
    - Short forms like `vs.` → `versus`.
    - Symbols like `&`, `%`, `$`, `@` → words.

- **Numeral strategy (two modes)**
  - `preprocess_text_for_translation(...)` intentionally **preserves numerals** in most cases to avoid MT “creative” rewrites.
  - `convert_numbers_to_english_words(...)` exists for cases where converting digits/time → words yields better MT output (can be enabled via `preprocess_text_for_tts(..., convert_numbers=True)` when that’s the chosen strategy).

## TTS-Focused Cleanup (Often Used After MT)

Even though this lives next to translation preprocessing, it’s mainly about producing stable audio:

- `clean_punctuation(text)` normalizes “smart punctuation” to ASCII, reduces excessive punctuation, preserves ellipses as natural pauses, and rewrites score-like patterns (e.g., `15-12` → `15 to 12`) to avoid being read as “minus”.

## Why This Helps Real-Time

- Keeps per-utterance processing **cheap and deterministic** (regex + small lookups).
- Reduces **translation variance** caused by casing/punctuation/formatting noise, which also improves cache hit rate when MT results are cached per normalized string.
- Produces more **TTS-friendly** strings without waiting for heavier post-processing models.

## Reference Code (Python)

This is a copy/paste-friendly reference implementation matching `.sts-service-archive/utils/text_processing.py`.

```python
#!/usr/bin/env python3
"""
Text preprocessing reference for real-time MT + TTS.

Primary goals:
- Improve MT robustness for noisy ASR output (sports/news style text).
- Keep transformations deterministic and low-latency for streaming.
- Produce TTS-friendly strings (pronunciation + punctuation stability).
"""

from __future__ import annotations

import re
from typing import Dict


ABBREVIATIONS: Dict[str, str] = {
    # Common team name edge-cases (kept as-is; placeholder for domain overrides)
    'Eagles': 'Eagles',
    'Hawks': 'Hawks',
    # Sports acronyms -> spoken letters
    'NBA': 'N B A',
    'NFL': 'N F L',
    'MLB': 'M L B',
    'NHL': 'N H L',
    # Common forms
    'vs': 'versus',
    'vs.': 'versus',
    # Symbols -> words (TTS/MT friendliness)
    '&': 'and',
    '%': 'percent',
    '$': 'dollars',
    '#': 'number',
    '@': 'at',
    '+': 'plus',
    '=': 'equals',
    '/': 'slash',
    '\\': 'backslash',
    '*': 'asterisk',
    # Preserve pause markers
    '...': '...',
    '..': '..',
}


PUNCTUATION_REPLACEMENTS: Dict[str, str] = {
    '¡': '',  # inverted exclamation
    '¿': '',  # inverted question
    # Smart quotes -> ASCII
    '“': '"',
    '”': '"',
    '„': '"',
    '‟': '"',
    '‘': "'",
    '’': "'",
    '‚': "'",
    '‛': "'",
    # Dashes/ellipsis -> ASCII-friendly forms
    '–': '-',
    '—': '-',
    '…': '...',
}


def handle_abbreviations(text: str) -> str:
    for abbrev, replacement in ABBREVIATIONS.items():
        text = text.replace(abbrev, replacement)
    return text


def convert_numbers_to_english_words(text: str) -> str:
    """
    Optional strategy: convert numerals to English words.
    This can help MT models that struggle with mixed numeric + domain text.
    """
    try:
        import inflect

        p = inflect.engine()

        # e.g. "1:54 REMAINING" -> "one minute fifty-four seconds remaining"
        time_pattern = r'\b(\d{1,2}):(\d{2})\s+([A-Z\s]+)'

        def replace_time(match: re.Match[str]) -> str:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            following_text = match.group(3).strip().lower()

            if minutes == 0:
                seconds_unit = 'second' if seconds == 1 else 'seconds'
                time_part = f'{p.number_to_words(seconds)} {seconds_unit}'
            elif seconds == 0:
                minutes_unit = 'minute' if minutes == 1 else 'minutes'
                time_part = f'{p.number_to_words(minutes)} {minutes_unit}'
            else:
                minutes_unit = 'minute' if minutes == 1 else 'minutes'
                seconds_unit = 'second' if seconds == 1 else 'seconds'
                time_part = (
                    f'{p.number_to_words(minutes)} {minutes_unit} '
                    f'{p.number_to_words(seconds)} {seconds_unit}'
                )

            return f'{time_part} {following_text}'

        text = re.sub(time_pattern, replace_time, text)

        # Remaining standalone integers -> words
        text = re.sub(r'\b(\d+)\b', lambda m: p.number_to_words(int(m.group(1))), text)
        return text
    except ImportError:
        # Minimal fallback for environments without inflect
        number_words = {
            '0': 'zero',
            '1': 'one',
            '2': 'two',
            '3': 'three',
            '4': 'four',
            '5': 'five',
            '6': 'six',
            '7': 'seven',
            '8': 'eight',
            '9': 'nine',
            '10': 'ten',
            '11': 'eleven',
            '12': 'twelve',
            '13': 'thirteen',
            '14': 'fourteen',
            '15': 'fifteen',
            '16': 'sixteen',
            '17': 'seventeen',
            '18': 'eighteen',
            '19': 'nineteen',
            '20': 'twenty',
        }
        for num, word in number_words.items():
            text = re.sub(r'\b' + num + r'\b', word, text)
        return text


def preprocess_text_for_translation(text: str) -> str:
    """
    MT-focused preprocessing that *preserves numerals*.

    Key ideas:
    - Normalize clock phrases like "1:54 REMAINING" -> "1:54 remaining"
    - Remove hyphens that frequently harm MT tokenization ("TEN-YARD" -> "TEN YARD")
    - Expand common abbreviations/symbols so MT is less likely to guess
    """
    time_pattern = r'\b(\d{1,2}):(\d{2})\s+([A-Z\s]+)'

    def replace_time(match: re.Match[str]) -> str:
        minutes = match.group(1)
        seconds = match.group(2)
        following_text = match.group(3).strip().lower()
        return f'{minutes}:{seconds} {following_text}'

    text = re.sub(time_pattern, replace_time, text)
    text = text.replace('-', ' ')
    text = handle_abbreviations(text)
    return text


def clean_punctuation(text: str) -> str:
    """
    TTS-focused punctuation cleanup:
    - Strip/normalize punctuation that causes odd prosody
    - Preserve ellipses as a natural pause marker
    - Rewrite score-like hyphens ("15-12" -> "15 to 12") so TTS doesn't say "minus"
    """
    for old, new in PUNCTUATION_REPLACEMENTS.items():
        text = text.replace(old, new)

    # Convert double dots that are NOT part of ellipsis into a spaced pause marker.
    text = re.sub(r'(?<!\.)\.\.(?!\.)', ' .. ', text)

    # Score patterns: "15-12" -> "15 to 12"
    text = re.sub(r'(\d+)-(\d+)', r'\1 to \2', text)

    # Collapse excessive punctuation
    text = re.sub(r'[!]{2,}', '!', text)
    text = re.sub(r'[?]{2,}', '?', text)
    text = re.sub(r'[.]{4,}', '...', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def preprocess_text_for_tts(text: str, convert_numbers: bool = True) -> str:
    """
    End-to-end TTS-friendly preprocessing.

    If you're translating first, you typically apply this *after* MT output
    (often with convert_numbers=False for non-English targets).
    """
    if convert_numbers:
        text = convert_numbers_to_english_words(text)
    text = text.replace('-', ' ')
    text = handle_abbreviations(text)
    text = clean_punctuation(text)
    return text


def detect_speaker(text: str) -> str:
    """
    Text-only speaker label detection.
    Examples:
    - "Referee: ..." -> "Referee"
    - ">> Joe: ..." -> "Joe"
    """
    speaker_match = re.match(r'^([A-Z][a-z]+):\s*', text)
    if speaker_match:
        return speaker_match.group(1).strip()

    speaker_match = re.match(r'^>>\s*([A-Z][a-z]+):', text)
    if speaker_match:
        return speaker_match.group(1).strip()

    return 'default'


def clean_speaker_prefix(text: str, speaker: str) -> str:
    """
    Remove a detected speaker label from the front of the string so MT/TTS
    don't translate/speak the label.
    """
    pattern = rf'^{re.escape(speaker)}:?\s*'
    return re.sub(pattern, '', text).strip()
```
