"""API key authentication for Echo STS Service.

Provides authentication middleware for Socket.IO connections.
"""

from typing import Any

from sts_service.echo.config import get_config


class AuthenticationError(Exception):
    """Raised when authentication fails.

    Attributes:
        message: Human-readable error message.
        error_code: Error code from spec 016 (default: AUTH_FAILED).
    """

    def __init__(
        self,
        message: str,
        error_code: str = "AUTH_FAILED",
    ) -> None:
        """Initialize the authentication error.

        Args:
            message: Human-readable error message.
            error_code: Error code from spec 016.
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code


def validate_api_key(token: str | None) -> bool:
    """Validate an API key token.

    Args:
        token: The API key token to validate.

    Returns:
        True if the token is valid, False otherwise.
    """
    config = get_config()

    # If authentication is disabled, accept any token
    if not config.require_auth:
        return True

    # Reject missing or empty tokens
    if not token:
        return False

    # Compare with configured API key
    return token == config.api_key


def authenticate_connection(auth: dict[str, Any] | None) -> None:
    """Authenticate a Socket.IO connection.

    This function validates the auth payload from a Socket.IO connection
    handshake. It expects the auth dict to contain a "token" field with
    the API key.

    Args:
        auth: The auth payload from Socket.IO connection.
              Expected format: {"token": "api-key-value"}

    Raises:
        AuthenticationError: If authentication fails.
    """
    config = get_config()

    # If authentication is disabled, accept any connection
    if not config.require_auth:
        return

    # Missing auth dict
    if auth is None:
        raise AuthenticationError(
            "Authentication required: missing auth payload",
            "AUTH_FAILED",
        )

    # Extract token
    token = auth.get("token")

    # Validate token
    if not validate_api_key(token):
        raise AuthenticationError(
            "Authentication failed: invalid API key",
            "AUTH_FAILED",
        )


def extract_connection_headers(
    environ: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    """Extract X-Stream-ID and X-Worker-ID from connection headers.

    Args:
        environ: The ASGI/WSGI environ dict from the connection.

    Returns:
        Tuple of (stream_id, worker_id), either may be None if not provided.
    """
    if environ is None:
        return None, None

    # Headers in environ are prefixed with HTTP_
    stream_id = environ.get("HTTP_X_STREAM_ID")
    worker_id = environ.get("HTTP_X_WORKER_ID")

    return stream_id, worker_id
