"""
Confidence score mapping for ASR output.

Converts log probabilities from Whisper to 0-1 confidence scores.
"""


def calculate_confidence(avg_logprob: float) -> float:
    """Calculate confidence score from average log probability.

    Uses linear mapping formula:
        confidence = clamp((avg_logprob + 1.0) / 1.0, 0, 1)

    This maps:
        - avg_logprob = 0.0 -> confidence = 1.0 (perfect)
        - avg_logprob = -1.0 -> confidence = 0.0 (poor)
        - avg_logprob = -0.5 -> confidence = 0.5 (medium)

    Args:
        avg_logprob: Average log probability from Whisper segment

    Returns:
        Confidence score between 0.0 and 1.0
    """
    # Linear mapping from log prob to confidence
    confidence = (avg_logprob + 1.0) / 1.0

    # Clamp to [0, 1] range
    return max(0.0, min(1.0, confidence))
