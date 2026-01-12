"""
Structured logging configuration for Full STS Service.

Uses structlog for JSON-formatted logs with consistent context binding for
stream_id, fragment_id, and session_id throughout the processing lifecycle.
"""

import logging
import sys

import structlog


def setup_logging(level: str = "INFO") -> None:
    """
    Configure structlog with JSON formatter for production logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structlog logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured BoundLogger instance
    """
    return structlog.get_logger(name)


def bind_stream_context(
    logger: structlog.BoundLogger,
    stream_id: str,
    fragment_id: str | None = None,
    session_id: str | None = None,
) -> structlog.BoundLogger:
    """
    Bind stream processing context to logger.

    Creates a new bound logger with stream_id, fragment_id, and session_id
    automatically included in all subsequent log entries.

    Args:
        logger: Base logger instance
        stream_id: Unique stream identifier
        fragment_id: Fragment identifier (optional)
        session_id: Socket.IO session identifier (optional)

    Returns:
        BoundLogger with context bound

    Example:
        >>> logger = get_logger(__name__)
        >>> logger = bind_stream_context(logger, stream_id="stream-123", fragment_id="frag-456")
        >>> logger.info("processing_started")  # Includes stream_id and fragment_id
    """
    context = {"stream_id": stream_id}
    if fragment_id:
        context["fragment_id"] = fragment_id
    if session_id:
        context["session_id"] = session_id

    return logger.bind(**context)
