"""Pydantic models for Echo STS Service.

All models match the WebSocket Audio Fragment Protocol (spec 016)
for full protocol compliance.

Models are organized by category:
- stream: Connection lifecycle payloads
- fragment: Audio fragment payloads
- error: Error and error simulation payloads
"""

__all__ = [
    # Stream models
    "StreamInitPayload",
    "StreamConfigPayload",
    "StreamReadyPayload",
    "StreamCompletePayload",
    "StreamStatistics",
    "ServerCapabilities",
    # Fragment models
    "AudioData",
    "FragmentMetadata",
    "FragmentDataPayload",
    "FragmentProcessedPayload",
    "FragmentAckPayload",
    "StageTimings",
    "ProcessingMetadata",
    "BackpressurePayload",
    # Error models
    "ErrorPayload",
    "ProcessingError",
    "ErrorSimulationConfig",
    "ErrorSimulationRule",
]


def __getattr__(name: str):
    """Lazy import of models."""
    stream_models = {
        "StreamInitPayload",
        "StreamConfigPayload",
        "StreamReadyPayload",
        "StreamCompletePayload",
        "StreamStatistics",
        "ServerCapabilities",
    }
    fragment_models = {
        "AudioData",
        "FragmentMetadata",
        "FragmentDataPayload",
        "FragmentProcessedPayload",
        "FragmentAckPayload",
        "StageTimings",
        "ProcessingMetadata",
        "BackpressurePayload",
    }
    error_models = {
        "ErrorPayload",
        "ProcessingError",
        "ErrorSimulationConfig",
        "ErrorSimulationRule",
    }

    if name in stream_models:
        from sts_service.echo.models import stream

        return getattr(stream, name)
    elif name in fragment_models:
        from sts_service.echo.models import fragment

        return getattr(fragment, name)
    elif name in error_models:
        from sts_service.echo.models import error

        return getattr(error, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
