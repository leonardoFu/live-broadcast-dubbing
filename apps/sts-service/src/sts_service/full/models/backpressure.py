"""Backpressure models for Full STS Service.

Defines typed models for flow control per spec 021:
- BackpressureState for tracking in-flight fragments
- Severity levels with recommended actions
- Threshold configuration

Matches contracts/backpressure-schema.json.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BackpressureSeverity(str, Enum):
    """Backpressure severity levels.

    Thresholds (default configuration):
    - LOW: 1-3 in-flight fragments (normal operation)
    - MEDIUM: 4-6 in-flight fragments (slow down recommended)
    - HIGH: 7-10 in-flight fragments (pause recommended)
    - CRITICAL: 11+ in-flight fragments (reject new fragments)
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BackpressureAction(str, Enum):
    """Recommended worker actions for backpressure."""

    NONE = "none"  # Continue normally
    SLOW_DOWN = "slow_down"  # Increase delay between fragments
    PAUSE = "pause"  # Stop sending new fragments


# Default threshold configuration from spec
DEFAULT_THRESHOLDS = {
    "low": {"min": 1, "max": 3, "action": BackpressureAction.NONE},
    "medium": {"min": 4, "max": 6, "action": BackpressureAction.SLOW_DOWN},
    "high": {"min": 7, "max": 10, "action": BackpressureAction.PAUSE},
    "critical": {"min": 11, "action": "reject"},
}

# Recommended delays by severity
RECOMMENDED_DELAYS_MS = {
    BackpressureSeverity.LOW: 0,
    BackpressureSeverity.MEDIUM: 500,
    BackpressureSeverity.HIGH: 2000,
}


class BackpressureThresholds(BaseModel):
    """Configurable backpressure thresholds."""

    low_max: int = Field(default=3, ge=1, le=10)
    medium_max: int = Field(default=6, ge=1, le=10)
    high_max: int = Field(default=10, ge=1, le=15)

    def get_severity(self, inflight_count: int) -> BackpressureSeverity:
        """Determine severity based on in-flight count."""
        if inflight_count <= self.low_max:
            return BackpressureSeverity.LOW
        elif inflight_count <= self.medium_max:
            return BackpressureSeverity.MEDIUM
        else:
            return BackpressureSeverity.HIGH

    def get_action(self, severity: BackpressureSeverity) -> BackpressureAction:
        """Get recommended action for severity level."""
        if severity == BackpressureSeverity.LOW:
            return BackpressureAction.NONE
        elif severity == BackpressureSeverity.MEDIUM:
            return BackpressureAction.SLOW_DOWN
        else:
            return BackpressureAction.PAUSE


class BackpressureState(BaseModel):
    """Backpressure state for a stream.

    Tracks in-flight fragments and calculates backpressure metrics.
    Matches spec 021 backpressure-schema.json backpressure definition.
    """

    stream_id: str = Field(min_length=1)
    severity: BackpressureSeverity
    action: BackpressureAction
    current_inflight: int = Field(ge=0)
    max_inflight: int = Field(ge=1, le=10)
    threshold_exceeded: Literal["low", "medium", "high"] | None = None
    recommended_delay_ms: int | None = Field(
        default=None,
        ge=0,
        description="Suggested delay before next fragment submission",
    )

    @classmethod
    def calculate(
        cls,
        stream_id: str,
        current_inflight: int,
        max_inflight: int = 3,
        thresholds: BackpressureThresholds | None = None,
    ) -> "BackpressureState":
        """Calculate backpressure state from current conditions.

        Args:
            stream_id: Stream identifier
            current_inflight: Current number of in-flight fragments
            max_inflight: Configured maximum in-flight limit
            thresholds: Optional custom thresholds

        Returns:
            BackpressureState with calculated severity and recommendations
        """
        if thresholds is None:
            thresholds = BackpressureThresholds()

        severity = thresholds.get_severity(current_inflight)
        action = thresholds.get_action(severity)

        # Determine which threshold was exceeded
        threshold_exceeded: Literal["low", "medium", "high"] | None = None
        if severity == BackpressureSeverity.MEDIUM:
            threshold_exceeded = "low"  # Exceeded low threshold
        elif severity == BackpressureSeverity.HIGH:
            threshold_exceeded = "medium"  # Exceeded medium threshold

        # Get recommended delay
        recommended_delay = RECOMMENDED_DELAYS_MS.get(severity, 0)

        return cls(
            stream_id=stream_id,
            severity=severity,
            action=action,
            current_inflight=current_inflight,
            max_inflight=max_inflight,
            threshold_exceeded=threshold_exceeded,
            recommended_delay_ms=recommended_delay if recommended_delay > 0 else None,
        )

    @property
    def should_reject(self) -> bool:
        """Check if new fragments should be rejected (critical threshold)."""
        return self.current_inflight > 10

    @property
    def is_healthy(self) -> bool:
        """Check if backpressure is at healthy levels."""
        return self.severity == BackpressureSeverity.LOW

    def to_event_payload(self) -> dict:
        """Convert to Socket.IO event payload format."""
        payload = {
            "stream_id": self.stream_id,
            "severity": self.severity.value,
            "action": self.action.value,
            "current_inflight": self.current_inflight,
            "max_inflight": self.max_inflight,
            "threshold_exceeded": self.threshold_exceeded,
        }
        if self.recommended_delay_ms is not None:
            payload["recommended_delay_ms"] = self.recommended_delay_ms
        return payload

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stream_id": "stream-abc-123",
                "severity": "medium",
                "action": "slow_down",
                "current_inflight": 5,
                "max_inflight": 3,
                "threshold_exceeded": "low",
                "recommended_delay_ms": 500,
            }
        }
    )
