"""
Error classification and handling for Translation component.

Maps Python exceptions to Translation error types with retryable classification.
Includes DeepL-specific exception handling.
"""

from .models import TranslationError, TranslationErrorType

# Re-export TranslationErrorType for convenience
__all__ = [
    "TranslationErrorType",
    "classify_error",
    "is_retryable",
    "create_translation_error",
]

# Set of retryable error types
_RETRYABLE_ERRORS = {
    TranslationErrorType.TIMEOUT,
    TranslationErrorType.PROVIDER_ERROR,
}

# DeepL exception types (lazy import to avoid import errors if deepl not installed)
_DEEPL_AUTH_EXCEPTIONS: tuple[type, ...] = ()
_DEEPL_QUOTA_EXCEPTIONS: tuple[type, ...] = ()
_DEEPL_RATE_LIMIT_EXCEPTIONS: tuple[type, ...] = ()
_DEEPL_CONNECTION_EXCEPTIONS: tuple[type, ...] = ()
_DEEPL_BASE_EXCEPTION: type | None = None

try:
    import deepl

    _DEEPL_BASE_EXCEPTION = deepl.DeepLException
    _DEEPL_AUTH_EXCEPTIONS = (deepl.AuthorizationException,)
    _DEEPL_QUOTA_EXCEPTIONS = (deepl.QuotaExceededException,)
    _DEEPL_RATE_LIMIT_EXCEPTIONS = (deepl.TooManyRequestsException,)
    _DEEPL_CONNECTION_EXCEPTIONS = (deepl.ConnectionException,)
except ImportError:
    pass


def classify_error(exception: Exception) -> TranslationErrorType:
    """Classify a Python exception to a TranslationErrorType.

    Handles DeepL-specific exceptions when the deepl library is available.

    Args:
        exception: The exception to classify

    Returns:
        The corresponding TranslationErrorType
    """
    # DeepL-specific exception handling
    if _DEEPL_BASE_EXCEPTION and isinstance(exception, _DEEPL_BASE_EXCEPTION):
        if _DEEPL_AUTH_EXCEPTIONS and isinstance(exception, _DEEPL_AUTH_EXCEPTIONS):
            return TranslationErrorType.PROVIDER_ERROR
        if _DEEPL_QUOTA_EXCEPTIONS and isinstance(exception, _DEEPL_QUOTA_EXCEPTIONS):
            return TranslationErrorType.PROVIDER_ERROR
        if _DEEPL_RATE_LIMIT_EXCEPTIONS and isinstance(exception, _DEEPL_RATE_LIMIT_EXCEPTIONS):
            return TranslationErrorType.TIMEOUT  # Rate limiting is retryable
        if _DEEPL_CONNECTION_EXCEPTIONS and isinstance(exception, _DEEPL_CONNECTION_EXCEPTIONS):
            return TranslationErrorType.PROVIDER_ERROR
        return TranslationErrorType.PROVIDER_ERROR

    # Standard Python exceptions
    if isinstance(exception, TimeoutError):
        return TranslationErrorType.TIMEOUT
    elif isinstance(exception, ValueError):
        return TranslationErrorType.EMPTY_INPUT
    elif isinstance(exception, ConnectionError):
        return TranslationErrorType.PROVIDER_ERROR
    else:
        return TranslationErrorType.UNKNOWN


def is_retryable(error_type: TranslationErrorType, exception: Exception | None = None) -> bool:
    """Determine if an error type is worth retrying.

    Retryable errors are transient and may succeed on retry:
    - TIMEOUT: May succeed with more time
    - PROVIDER_ERROR: May succeed if provider recovers

    Non-retryable errors are permanent:
    - EMPTY_INPUT: Input is invalid
    - UNSUPPORTED_LANGUAGE_PAIR: Configuration issue
    - NORMALIZATION_ERROR: Processing issue
    - UNKNOWN: Cannot determine appropriate action

    Args:
        error_type: The error type to check

    Returns:
        True if the error is retryable
    """
    return error_type in _RETRYABLE_ERRORS


def create_translation_error(exception: Exception) -> TranslationError:
    """Create a TranslationError from a Python exception.

    Args:
        exception: The exception to convert

    Returns:
        TranslationError with appropriate type and retryable flag
    """
    error_type = classify_error(exception)
    message = str(exception) if str(exception) else f"{type(exception).__name__}"

    return TranslationError(
        error_type=error_type,
        message=message,
        retryable=is_retryable(error_type),
        details={"exception_type": type(exception).__name__},
    )
