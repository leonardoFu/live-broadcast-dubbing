"""
Speaker label detection for Translation component.

Detects and removes speaker labels from text before translation.
"""

import re


class SpeakerLabelDetector:
    """Detects and removes speaker labels from text.

    Speaker labels like "Alice: Hello" or ">> Bob: Hi" are detected
    and removed before translation to prevent the label from being
    translated or spoken by TTS.
    """

    DEFAULT_PATTERNS = [
        r"^([A-Z][a-z]+): ",  # "Name: ..." (Titlecase name)
        r"^>> ([A-Z][a-z]+): ",  # ">> Name: ..." (chevron prefix)
    ]

    # Words that look like speaker names but are common words
    # These will be excluded from speaker detection
    _FALSE_POSITIVE_WORDS = {
        "time",
        "score",
        "note",
        "warning",
        "error",
        "info",
        "debug",
        "update",
        "status",
        "result",
        "total",
        "final",
        "date",
        "type",
        "name",
        "title",
        "url",
        "link",
    }

    def __init__(self, patterns: list[str] | None = None):
        """Initialize with speaker detection patterns.

        Args:
            patterns: List of regex patterns for speaker label detection.
                     Each pattern must have one capture group for the speaker name.
                     Defaults to DEFAULT_PATTERNS if not provided.
        """
        self.patterns = patterns if patterns is not None else self.DEFAULT_PATTERNS
        self._compiled_patterns = [re.compile(p) for p in self.patterns]

    def detect_and_remove(self, text: str) -> tuple[str, str]:
        """Detect and remove speaker label from text.

        Args:
            text: Input text that may contain a speaker label

        Returns:
            Tuple of (speaker_id, cleaned_text)
            If no label detected, returns ("default", original_text)
        """
        if not text:
            return ("default", text)

        for pattern in self._compiled_patterns:
            match = pattern.match(text)
            if match:
                speaker_id = match.group(1)

                # Check for false positives
                if speaker_id.lower() in self._FALSE_POSITIVE_WORDS:
                    continue

                # Remove the speaker label from text
                cleaned_text = pattern.sub("", text)
                return (speaker_id, cleaned_text)

        return ("default", text)
