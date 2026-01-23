"""Environment-based configuration for Full STS Service.

All configuration is loaded from environment variables with sensible defaults.
Missing required variables will cause startup to fail fast.
"""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServerConfig:
    """Server configuration for Full STS Service."""

    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    # Connection limits
    max_connections: int = field(default_factory=lambda: int(os.getenv("WS_MAX_CONNECTIONS", "10")))
    max_buffer_size: int = field(
        default_factory=lambda: int(os.getenv("WS_MAX_BUFFER_SIZE", str(50 * 1024 * 1024)))
    )  # 50MB default

    # Timeouts (in seconds)
    ping_interval: int = field(default_factory=lambda: int(os.getenv("WS_PING_INTERVAL", "25")))
    # Increased from 10s to 60s - TTS processing can take 15+ seconds
    # which may block the event loop and delay ping responses
    ping_timeout: int = field(default_factory=lambda: int(os.getenv("WS_PING_TIMEOUT", "60")))

    # Auto-disconnect after stream:complete (in seconds)
    auto_disconnect_delay: int = field(
        default_factory=lambda: int(os.getenv("AUTO_DISCONNECT_DELAY", "5"))
    )


@dataclass(frozen=True)
class ObservabilityConfig:
    """Observability configuration for logging and metrics."""

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Artifact logging
    enable_artifact_logging: bool = field(
        default_factory=lambda: os.getenv("ENABLE_ARTIFACT_LOGGING", "true").lower() == "true"
    )
    artifacts_path: str = field(
        default_factory=lambda: os.getenv("ARTIFACTS_PATH", "/tmp/sts-artifacts")
    )
    artifact_retention_hours: int = field(
        default_factory=lambda: int(os.getenv("ARTIFACT_RETENTION_HOURS", "24"))
    )
    artifact_max_count: int = field(
        default_factory=lambda: int(os.getenv("ARTIFACT_MAX_COUNT", "1000"))
    )

    # GPU monitoring interval (seconds)
    gpu_monitoring_interval: int = field(
        default_factory=lambda: int(os.getenv("GPU_MONITORING_INTERVAL", "5"))
    )


@dataclass(frozen=True)
class PipelineConfig:
    """Pipeline configuration for ASR, Translation, and TTS."""

    # DeepL API (required for translation)
    deepl_auth_key: str | None = field(default_factory=lambda: os.getenv("DEEPL_AUTH_KEY"))

    # ASR Configuration
    asr_model_size: str = field(default_factory=lambda: os.getenv("ASR_MODEL_SIZE", "medium"))
    asr_device: str = field(
        default_factory=lambda: os.getenv("ASR_DEVICE", "cuda" if _is_cuda_available() else "cpu")
    )
    asr_timeout_ms: int = field(default_factory=lambda: int(os.getenv("ASR_TIMEOUT_MS", "5000")))

    # Translation Configuration
    translation_timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("TRANSLATION_TIMEOUT_MS", "5000"))
    )

    # TTS Configuration
    tts_device: str = field(
        default_factory=lambda: os.getenv("TTS_DEVICE", "cuda" if _is_cuda_available() else "cpu")
    )
    tts_timeout_ms: int = field(default_factory=lambda: int(os.getenv("TTS_TIMEOUT_MS", "10000")))

    # Duration matching thresholds
    duration_variance_success_max: float = field(
        default_factory=lambda: float(os.getenv("DURATION_VARIANCE_SUCCESS_MAX", "0.10"))
    )
    duration_variance_partial_max: float = field(
        default_factory=lambda: float(os.getenv("DURATION_VARIANCE_PARTIAL_MAX", "0.20"))
    )

    # Backpressure thresholds (in-flight fragment counts)
    backpressure_threshold_low: int = field(
        default_factory=lambda: int(os.getenv("BACKPRESSURE_THRESHOLD_LOW", "3"))
    )
    backpressure_threshold_medium: int = field(
        default_factory=lambda: int(os.getenv("BACKPRESSURE_THRESHOLD_MEDIUM", "6"))
    )
    backpressure_threshold_high: int = field(
        default_factory=lambda: int(os.getenv("BACKPRESSURE_THRESHOLD_HIGH", "10"))
    )
    backpressure_threshold_critical: int = field(
        default_factory=lambda: int(os.getenv("BACKPRESSURE_THRESHOLD_CRITICAL", "10"))
    )

    # Model paths (optional - defaults to cache)
    asr_model_path: str | None = field(default_factory=lambda: os.getenv("ASR_MODEL_PATH"))
    tts_model_path: str | None = field(default_factory=lambda: os.getenv("TTS_MODEL_PATH"))
    voice_profiles_path: str = field(
        default_factory=lambda: os.getenv("VOICE_PROFILES_PATH", "/config/voices.json")
    )

    def validate(self) -> None:
        """Validate required configuration values.

        Raises:
            ValueError: If required configuration is missing or invalid.
        """
        if not self.deepl_auth_key:
            raise ValueError(
                "DEEPL_AUTH_KEY environment variable is required for translation. "
                "Get your API key from https://www.deepl.com/pro-api"
            )

        # Validate duration thresholds
        if not 0 <= self.duration_variance_success_max <= 1:
            raise ValueError(
                f"DURATION_VARIANCE_SUCCESS_MAX must be between 0 and 1, got {self.duration_variance_success_max}"
            )
        if not 0 <= self.duration_variance_partial_max <= 1:
            raise ValueError(
                f"DURATION_VARIANCE_PARTIAL_MAX must be between 0 and 1, got {self.duration_variance_partial_max}"
            )
        if self.duration_variance_success_max >= self.duration_variance_partial_max:
            raise ValueError(
                "DURATION_VARIANCE_SUCCESS_MAX must be less than DURATION_VARIANCE_PARTIAL_MAX"
            )

        # Validate backpressure thresholds
        if not (
            self.backpressure_threshold_low
            <= self.backpressure_threshold_medium
            <= self.backpressure_threshold_high
            <= self.backpressure_threshold_critical
        ):
            raise ValueError(
                "Backpressure thresholds must be in ascending order: "
                f"low({self.backpressure_threshold_low}) <= "
                f"medium({self.backpressure_threshold_medium}) <= "
                f"high({self.backpressure_threshold_high}) <= "
                f"critical({self.backpressure_threshold_critical})"
            )


@dataclass(frozen=True)
class FullSTSConfig:
    """Complete configuration for Full STS Service.

    Combines all configuration sections with validation.
    """

    server: ServerConfig
    observability: ObservabilityConfig
    pipeline: PipelineConfig

    @classmethod
    def from_env(cls) -> "FullSTSConfig":
        """Create configuration from environment variables.

        Returns:
            FullSTSConfig instance with all settings loaded.

        Raises:
            ValueError: If required configuration is missing or invalid.
        """
        config = cls(
            server=ServerConfig(),
            observability=ObservabilityConfig(),
            pipeline=PipelineConfig(),
        )

        # Validate pipeline configuration (required fields)
        config.pipeline.validate()

        return config


# Global singleton configuration
_config: FullSTSConfig | None = None


def get_config() -> FullSTSConfig:
    """Get the global configuration instance.

    Returns:
        The global FullSTSConfig instance.

    Raises:
        ValueError: If configuration validation fails.
    """
    global _config
    if _config is None:
        _config = FullSTSConfig.from_env()
    return _config


def reset_config() -> None:
    """Reset the global configuration (for testing)."""
    global _config
    _config = None


def set_config(config: FullSTSConfig) -> None:
    """Set the global configuration (for testing).

    Args:
        config: The configuration to use.
    """
    global _config
    _config = config


def _is_cuda_available() -> bool:
    """Check if CUDA is available.

    Returns:
        True if CUDA is available, False otherwise.
    """
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False
