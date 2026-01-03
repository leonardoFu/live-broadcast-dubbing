"""Full STS Service Pydantic models.

This package contains typed input/output contracts for Socket.IO events
and pipeline processing. Organized by domain:

- stream.py: Stream lifecycle models (StreamConfig, StreamSession)
- fragment.py: Fragment processing models (FragmentData, FragmentResult)
- asset.py: Pipeline asset models (TranscriptAsset, TranslationAsset, AudioAsset)
- error.py: Error handling models (ErrorResponse, ErrorCode)
- backpressure.py: Flow control models (BackpressureState)
"""

from sts_service.full.models.asset import (
    AssetStatus,
    AudioAsset,
    BaseAsset,
    TranscriptAsset,
    TranscriptSegment,
    TranslationAsset,
)
from sts_service.full.models.backpressure import (
    BackpressureAction,
    BackpressureSeverity,
    BackpressureState,
)
from sts_service.full.models.error import (
    ErrorCode,
    ErrorResponse,
    ErrorStage,
)
from sts_service.full.models.fragment import (
    AckStatus,
    AudioData,
    DurationMetadata,
    FragmentAck,
    FragmentData,
    FragmentMetadata,
    FragmentResult,
    ProcessingError,
    ProcessingStatus,
    StageTiming,
)
from sts_service.full.models.stream import (
    StreamConfig,
    StreamState,
    StreamStatistics,
)
# StreamSession is defined in session.py, not models/stream.py
from sts_service.full.session import StreamSession

# Backward-compatible aliases for legacy code
# These match the names used in the old models.py
FragmentDataPayload = FragmentData
FragmentAckPayload = FragmentAck
FragmentProcessedPayload = FragmentResult
BackpressurePayload = BackpressureState
PipelineStage = ErrorStage  # Renamed to ErrorStage for clarity

# Stream payload aliases (for Socket.IO event types)
StreamInitPayload = StreamSession  # Session is the full runtime state
StreamReadyPayload = StreamSession
StreamPausePayload = StreamSession
StreamResumePayload = StreamSession
StreamEndPayload = StreamSession
StreamCompletePayload = StreamStatistics

__all__ = [
    # Asset models
    "AssetStatus",
    "BaseAsset",
    "TranscriptAsset",
    "TranscriptSegment",
    "TranslationAsset",
    "AudioAsset",
    # Backpressure models
    "BackpressureSeverity",
    "BackpressureAction",
    "BackpressureState",
    "BackpressurePayload",  # Alias
    # Error models
    "ErrorStage",
    "ErrorCode",
    "ErrorResponse",
    "PipelineStage",  # Alias for backward compat
    # Fragment models
    "AckStatus",
    "AudioData",
    "StageTiming",
    "DurationMetadata",
    "FragmentData",
    "FragmentDataPayload",  # Alias
    "FragmentAck",
    "FragmentAckPayload",  # Alias
    "FragmentMetadata",
    "FragmentResult",
    "FragmentProcessedPayload",  # Alias
    "ProcessingError",
    "ProcessingStatus",
    # Stream models
    "StreamState",
    "StreamConfig",
    "StreamSession",
    "StreamStatistics",
    # Stream payload aliases
    "StreamInitPayload",
    "StreamReadyPayload",
    "StreamPausePayload",
    "StreamResumePayload",
    "StreamEndPayload",
    "StreamCompletePayload",
]
