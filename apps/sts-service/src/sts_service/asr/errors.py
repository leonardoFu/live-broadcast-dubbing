"""
Error classification and handling for ASR component.

Maps Python exceptions to ASR error types with retryable classification.
"""

from .models import ASRError, ASRErrorType

# Set of retryable error types
_RETRYABLE_ERRORS = {
    ASRErrorType.TIMEOUT,
    ASRErrorType.MEMORY_ERROR,
}


def classify_error(exception: Exception) -> ASRErrorType:
    """Classify a Python exception to an ASRErrorType.

    Args:
        exception: The exception to classify

    Returns:
        The corresponding ASRErrorType
    """
    if isinstance(exception, MemoryError):
        return ASRErrorType.MEMORY_ERROR
    elif isinstance(exception, TimeoutError):
        return ASRErrorType.TIMEOUT
    elif isinstance(exception, FileNotFoundError):
        return ASRErrorType.MODEL_LOAD_ERROR
    elif isinstance(exception, ValueError):
        return ASRErrorType.INVALID_AUDIO
    else:
        return ASRErrorType.UNKNOWN


def is_retryable(error_type: ASRErrorType) -> bool:
    """Determine if an error type is worth retrying.

    Retryable errors are transient and may succeed on retry:
    - TIMEOUT: May succeed with more time
    - MEMORY_ERROR: May succeed after garbage collection

    Non-retryable errors are permanent:
    - INVALID_AUDIO: Audio is corrupt
    - MODEL_LOAD_ERROR: Model configuration issue
    - UNKNOWN: Cannot determine appropriate action

    Args:
        error_type: The error type to check

    Returns:
        True if the error is retryable
    """
    return error_type in _RETRYABLE_ERRORS


def create_asr_error(exception: Exception) -> ASRError:
    """Create an ASRError from a Python exception.

    Args:
        exception: The exception to convert

    Returns:
        ASRError with appropriate type and retryable flag
    """
    error_type = classify_error(exception)
    message = str(exception) if str(exception) else f"{type(exception).__name__}"

    return ASRError(
        error_type=error_type,
        message=message,
        retryable=is_retryable(error_type),
    )
