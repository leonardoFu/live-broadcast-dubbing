"""
Postprocessing functions for ASR output (utterance shaping).

Provides segment merging and splitting for better TTS input.
"""

from .models import TranscriptSegment, UtteranceShapingConfig, WordTiming


def shape_utterances(
    segments: list[TranscriptSegment],
    config: UtteranceShapingConfig,
) -> list[TranscriptSegment]:
    """Apply complete utterance shaping pipeline.

    1. Merge short segments that are too brief for TTS
    2. Split long segments that exceed max duration

    Args:
        segments: Input transcript segments
        config: Shaping configuration

    Returns:
        Shaped transcript segments
    """
    if not segments:
        return []

    # First merge short segments
    merged = improve_sentence_boundaries(
        segments,
        merge_threshold_seconds=config.merge_threshold_seconds,
    )

    # Then split long segments
    shaped = split_long_segments(
        merged,
        max_duration_seconds=config.max_segment_duration_seconds,
    )

    return shaped


def improve_sentence_boundaries(
    segments: list[TranscriptSegment],
    merge_threshold_seconds: float = 1.0,
) -> list[TranscriptSegment]:
    """Merge short segments to improve sentence boundaries.

    Short segments (below threshold) are merged with adjacent segments
    to create more natural utterance boundaries.

    Args:
        segments: Input transcript segments
        merge_threshold_seconds: Merge segments shorter than this (seconds)

    Returns:
        Merged transcript segments
    """
    if not segments:
        return []

    if len(segments) == 1:
        return segments.copy()

    threshold_ms = int(merge_threshold_seconds * 1000)
    result: list[TranscriptSegment] = []
    current: TranscriptSegment | None = None

    for segment in segments:
        if current is None:
            current = segment
            continue

        # Check if current segment is short enough to merge
        current_duration = current.duration_ms

        if current_duration < threshold_ms:
            # Merge current with this segment
            current = _merge_segments(current, segment)
        else:
            # Current is long enough, add it and start new
            result.append(current)
            current = segment

    # Don't forget the last segment
    if current is not None:
        result.append(current)

    return result


def split_long_segments(
    segments: list[TranscriptSegment],
    max_duration_seconds: float = 6.0,
) -> list[TranscriptSegment]:
    """Split segments that exceed maximum duration.

    Attempts to split at sentence boundaries (periods, question marks).
    Falls back to word boundaries if no sentence boundary found.

    Args:
        segments: Input transcript segments
        max_duration_seconds: Maximum segment duration (seconds)

    Returns:
        Split transcript segments
    """
    if not segments:
        return []

    max_duration_ms = int(max_duration_seconds * 1000)
    result: list[TranscriptSegment] = []

    for segment in segments:
        if segment.duration_ms <= max_duration_ms:
            result.append(segment)
            continue

        # Need to split this segment
        split_segments = _split_segment(segment, max_duration_ms)
        result.extend(split_segments)

    return result


def _merge_segments(seg1: TranscriptSegment, seg2: TranscriptSegment) -> TranscriptSegment:
    """Merge two adjacent segments into one.

    Args:
        seg1: First segment
        seg2: Second segment

    Returns:
        Merged segment
    """
    # Combine text
    merged_text = f"{seg1.text} {seg2.text}"

    # Average confidence
    merged_confidence = (seg1.confidence + seg2.confidence) / 2

    # Combine words if present
    merged_words: list[WordTiming] | None = None
    if seg1.words and seg2.words:
        merged_words = list(seg1.words) + list(seg2.words)
    elif seg1.words:
        merged_words = list(seg1.words)
    elif seg2.words:
        merged_words = list(seg2.words)

    return TranscriptSegment(
        start_time_ms=seg1.start_time_ms,
        end_time_ms=seg2.end_time_ms,
        text=merged_text,
        confidence=merged_confidence,
        words=merged_words,
    )


def _split_segment(
    segment: TranscriptSegment,
    max_duration_ms: int,
) -> list[TranscriptSegment]:
    """Split a segment that exceeds max duration.

    Attempts to split at:
    1. Sentence boundaries (period, question mark, exclamation)
    2. Word boundaries
    3. Time-based split as fallback

    Args:
        segment: Segment to split
        max_duration_ms: Maximum duration in milliseconds

    Returns:
        List of split segments
    """
    if segment.words:
        return _split_by_words(segment, max_duration_ms)
    else:
        return _split_by_text(segment, max_duration_ms)


def _split_by_words(
    segment: TranscriptSegment,
    max_duration_ms: int,
) -> list[TranscriptSegment]:
    """Split segment using word-level timestamps.

    Args:
        segment: Segment with word timestamps
        max_duration_ms: Maximum duration per split segment

    Returns:
        List of split segments
    """
    if not segment.words:
        return [segment]

    words = list(segment.words)
    result: list[TranscriptSegment] = []

    current_words: list[WordTiming] = []
    current_start: int | None = None

    for word in words:
        if current_start is None:
            current_start = word.start_time_ms

        current_duration = word.end_time_ms - current_start

        # Check for sentence boundary
        is_sentence_end = word.word.rstrip().endswith((".", "?", "!"))

        if current_duration >= max_duration_ms or (
            is_sentence_end and current_duration >= max_duration_ms * 0.5
        ):
            # End current segment
            current_words.append(word)
            split_seg = _create_segment_from_words(current_words, segment.confidence)
            result.append(split_seg)
            current_words = []
            current_start = None
        else:
            current_words.append(word)

    # Handle remaining words
    if current_words:
        split_seg = _create_segment_from_words(current_words, segment.confidence)
        result.append(split_seg)

    return result if result else [segment]


def _split_by_text(
    segment: TranscriptSegment,
    max_duration_ms: int,
) -> list[TranscriptSegment]:
    """Split segment using text-based heuristics (no word timestamps).

    Args:
        segment: Segment without word timestamps
        max_duration_ms: Maximum duration per split segment

    Returns:
        List of split segments
    """
    # Try to split at sentence boundaries
    text = segment.text
    sentences = _split_text_into_sentences(text)

    if len(sentences) <= 1:
        # Cannot split, return as-is
        return [segment]

    # Distribute time proportionally to text length
    total_chars = sum(len(s) for s in sentences)
    total_duration = segment.duration_ms

    result: list[TranscriptSegment] = []
    current_time = segment.start_time_ms

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # Proportional duration
        duration = int((len(sentence) / total_chars) * total_duration)
        end_time = current_time + duration

        result.append(
            TranscriptSegment(
                start_time_ms=current_time,
                end_time_ms=end_time,
                text=sentence,
                confidence=segment.confidence,
            )
        )

        current_time = end_time

    return result if result else [segment]


def _create_segment_from_words(
    words: list[WordTiming],
    base_confidence: float,
) -> TranscriptSegment:
    """Create a transcript segment from a list of words.

    Args:
        words: List of word timings
        base_confidence: Base confidence to use

    Returns:
        New TranscriptSegment
    """
    text = " ".join(w.word for w in words)

    # Calculate average confidence from words if available
    word_confidences = [w.confidence for w in words if w.confidence is not None]
    if word_confidences:
        confidence = sum(word_confidences) / len(word_confidences)
    else:
        confidence = base_confidence

    return TranscriptSegment(
        start_time_ms=words[0].start_time_ms,
        end_time_ms=words[-1].end_time_ms,
        text=text,
        confidence=confidence,
        words=words,
    )


def _split_text_into_sentences(text: str) -> list[str]:
    """Split text into sentences at common boundaries.

    Args:
        text: Input text

    Returns:
        List of sentences
    """
    import re

    # Split at sentence-ending punctuation followed by space or end
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s for s in sentences if s.strip()]
