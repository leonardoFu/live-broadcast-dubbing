"""
VAD segmentation configuration from environment variables.

Per spec 023-vad-audio-segmentation:
- All parameters are global (not per-stream) for MVP
- Environment variables use VAD_ prefix
- Sensible defaults for broadcast content
- Validation via Pydantic Field constraints
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class SegmentationConfig(BaseSettings):
    """VAD segmentation configuration from environment variables.

    All parameters are global (not per-stream) for MVP.

    Attributes:
        silence_threshold_db: RMS level below which audio is considered silence.
            Default -50 dB works for typical broadcast content.
        silence_duration_s: Duration of silence required to trigger segment boundary.
            Default 1.0 second provides natural speech boundary detection.
        min_segment_duration_s: Minimum segment duration before emission.
            Default 1.0 second prevents fragments too short for translation.
        max_segment_duration_s: Maximum segment duration before forced emission.
            Default 15.0 seconds prevents memory buildup during continuous speech.
        level_interval_ns: Interval for level element RMS measurements.
            Default 100ms (100,000,000 ns) balances responsiveness and CPU.
        memory_limit_bytes: Maximum accumulator memory per stream.
            Default 10MB (~60s of 16kHz PCM) prevents unbounded growth.
    """

    silence_threshold_db: float = Field(
        default=-50.0,
        ge=-100.0,
        le=0.0,
        description="RMS threshold in dB below which audio is silence",
    )
    silence_duration_s: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Duration of silence to trigger segment boundary",
    )
    min_segment_duration_s: float = Field(
        default=1.0,
        ge=0.5,
        le=5.0,
        description="Minimum segment duration before emission",
    )
    max_segment_duration_s: float = Field(
        default=15.0,
        ge=5.0,
        le=60.0,
        description="Maximum segment duration before forced emission",
    )
    level_interval_ns: int = Field(
        default=100_000_000,
        ge=50_000_000,
        le=500_000_000,
        description="Level element measurement interval in nanoseconds",
    )
    memory_limit_bytes: int = Field(
        default=10_485_760,  # 10 MB
        ge=1_048_576,  # 1 MB minimum
        le=104_857_600,  # 100 MB maximum
        description="Maximum audio accumulator memory per stream",
    )

    model_config = {
        "env_prefix": "VAD_",
        "case_sensitive": False,
    }

    @property
    def silence_duration_ns(self) -> int:
        """Silence duration in nanoseconds."""
        return int(self.silence_duration_s * 1_000_000_000)

    @property
    def min_segment_duration_ns(self) -> int:
        """Minimum segment duration in nanoseconds."""
        return int(self.min_segment_duration_s * 1_000_000_000)

    @property
    def max_segment_duration_ns(self) -> int:
        """Maximum segment duration in nanoseconds."""
        return int(self.max_segment_duration_s * 1_000_000_000)
