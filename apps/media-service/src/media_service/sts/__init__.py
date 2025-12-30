"""
STS (Speech-to-Speech) integration module.

This module provides Socket.IO client integration with the STS Service
for real-time audio dubbing using the WebSocket Audio Fragment Protocol.

Components:
- StsSocketIOClient: Socket.IO AsyncClient for STS communication
- FragmentTracker: Tracks in-flight fragments with timeout handling
- BackpressureHandler: Handles backpressure events and flow control
- ReconnectionManager: Manages exponential backoff reconnection
- StsCircuitBreaker: Circuit breaker for STS failure protection

Data Models:
- StreamConfig: Configuration for STS processing
- InFlightFragment: Tracks fragments pending processing
- FragmentDataPayload: Socket.IO fragment:data event payload
"""

from __future__ import annotations

from media_service.sts.backpressure_handler import BackpressureHandler
from media_service.sts.circuit_breaker import StsCircuitBreaker
from media_service.sts.fragment_tracker import FragmentTracker
from media_service.sts.models import (
    AudioData,
    BackpressurePayload,
    FragmentDataPayload,
    FragmentMetadata,
    FragmentProcessedPayload,
    InFlightFragment,
    ProcessingError,
    StageTimings,
    StreamConfig,
)
from media_service.sts.reconnection_manager import ReconnectionManager
from media_service.sts.socketio_client import StsSocketIOClient

__all__ = [
    "StsSocketIOClient",
    "FragmentTracker",
    "BackpressureHandler",
    "ReconnectionManager",
    "StsCircuitBreaker",
    "StreamConfig",
    "InFlightFragment",
    "FragmentDataPayload",
    "FragmentProcessedPayload",
    "FragmentMetadata",
    "AudioData",
    "StageTimings",
    "ProcessingError",
    "BackpressurePayload",
    "StsConnectionError",
]


class StsConnectionError(Exception):
    """Raised when STS connection fails after max reconnection attempts."""

    pass
