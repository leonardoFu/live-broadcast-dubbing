"""Environment-based configuration for Echo STS Service.

All configuration is loaded from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EchoConfig:
    """Configuration for the Echo STS Service.

    Loaded from environment variables with defaults suitable for local development.
    """

    # Server settings
    host: str = field(default_factory=lambda: os.getenv("ECHO_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("ECHO_PORT", "8000")))

    # Processing simulation
    processing_delay_ms: int = field(
        default_factory=lambda: int(os.getenv("ECHO_PROCESSING_DELAY_MS", "0"))
    )

    # Backpressure settings
    backpressure_enabled: bool = field(
        default_factory=lambda: os.getenv("BACKPRESSURE_ENABLED", "false").lower() == "true"
    )
    backpressure_threshold_low: float = field(
        default_factory=lambda: float(os.getenv("BACKPRESSURE_THRESHOLD_LOW", "0.5"))
    )
    backpressure_threshold_medium: float = field(
        default_factory=lambda: float(os.getenv("BACKPRESSURE_THRESHOLD_MEDIUM", "0.7"))
    )
    backpressure_threshold_high: float = field(
        default_factory=lambda: float(os.getenv("BACKPRESSURE_THRESHOLD_HIGH", "0.9"))
    )

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

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    @classmethod
    def from_env(cls) -> "EchoConfig":
        """Create configuration from environment variables."""
        return cls()


# Global singleton configuration
_config: EchoConfig | None = None


def get_config() -> EchoConfig:
    """Get the global configuration instance.

    Returns:
        The global EchoConfig instance.
    """
    global _config
    if _config is None:
        _config = EchoConfig.from_env()
    return _config


def reset_config() -> None:
    """Reset the global configuration (for testing)."""
    global _config
    _config = None


def set_config(config: EchoConfig) -> None:
    """Set the global configuration (for testing).

    Args:
        config: The configuration to use.
    """
    global _config
    _config = config


@dataclass
class BackpressureConfig:
    """Backpressure configuration with threshold percentages.

    Used to calculate backpressure severity based on queue depth.
    """

    enabled: bool = False
    threshold_low: float = 0.5  # 50% of max_inflight
    threshold_medium: float = 0.7  # 70% of max_inflight
    threshold_high: float = 0.9  # 90% of max_inflight

    @classmethod
    def from_echo_config(cls, config: EchoConfig) -> "BackpressureConfig":
        """Create backpressure config from echo config."""
        return cls(
            enabled=config.backpressure_enabled,
            threshold_low=config.backpressure_threshold_low,
            threshold_medium=config.backpressure_threshold_medium,
            threshold_high=config.backpressure_threshold_high,
        )
