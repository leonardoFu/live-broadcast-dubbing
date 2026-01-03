"""Full STS Service package.

Provides the complete speech-to-speech pipeline:
ASR -> Translation -> TTS with Socket.IO integration.
"""

from .models import (
    AudioData,
    BackpressurePayload,
    ErrorResponse,
    FragmentAckPayload,
    FragmentDataPayload,
    FragmentProcessedPayload,
    PipelineStage,
    ProcessingError,
    ProcessingStatus,
    StageTiming,
    StreamCompletePayload,
    StreamConfig,
    StreamEndPayload,
    StreamInitPayload,
    StreamPausePayload,
    StreamReadyPayload,
    StreamResumePayload,
    StreamState,
)

# Phase 2 imports
from .pipeline import PipelineCoordinator
from .fragment_queue import FragmentQueue
from .backpressure_tracker import BackpressureTracker

__all__ = [
    # Fragment models
    "AudioData",
    "FragmentDataPayload",
    "FragmentAckPayload",
    "FragmentProcessedPayload",
    "ProcessingError",
    "StageTiming",
    # Stream models
    "StreamConfig",
    "StreamInitPayload",
    "StreamReadyPayload",
    "StreamPausePayload",
    "StreamResumePayload",
    "StreamEndPayload",
    "StreamCompletePayload",
    "StreamState",
    # Other models
    "BackpressurePayload",
    "ErrorResponse",
    "PipelineStage",
    "ProcessingStatus",
    # Phase 2: Pipeline Coordinator
    "PipelineCoordinator",
    "FragmentQueue",
    "BackpressureTracker",
]
