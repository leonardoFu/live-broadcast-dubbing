"""
TTS Component Factory.

Creates TTS component instances based on provider configuration.
Supports mock providers for testing and Coqui provider for production.
"""

from typing import Any, Literal

from .interface import TTSComponent
from .models import TTSConfig

ProviderType = Literal[
    "coqui", "mock", "mock_fixed_tone", "mock_from_fixture", "mock_fail_once"
]


def create_tts_component(
    provider: ProviderType = "coqui",
    config: TTSConfig | None = None,
    **kwargs: Any,
) -> TTSComponent:
    """Create a TTS component instance.

    Args:
        provider: The TTS provider to use:
            - "coqui": Production Coqui TTS (XTTS-v2 or VITS)
            - "mock": Alias for "mock_fixed_tone"
            - "mock_fixed_tone": Produces deterministic 440Hz tone
            - "mock_from_fixture": Returns pre-recorded audio from fixtures
            - "mock_fail_once": Fails first call, succeeds on retry
        config: Optional TTS configuration
        **kwargs: Additional provider-specific arguments

    Returns:
        TTSComponent instance

    Raises:
        ValueError: If provider is not supported
    """
    if config is None:
        config = TTSConfig()

    if provider == "coqui":
        from .coqui_provider import CoquiTTSComponent

        return CoquiTTSComponent(config=config, **kwargs)

    elif provider in ("mock", "mock_fixed_tone"):
        from .mock import MockTTSFixedTone

        return MockTTSFixedTone(config=config, **kwargs)

    elif provider == "mock_from_fixture":
        from .mock import MockTTSFromFixture

        return MockTTSFromFixture(config=config, **kwargs)

    elif provider == "mock_fail_once":
        from .mock import MockTTSFailOnce

        return MockTTSFailOnce(config=config, **kwargs)

    else:
        raise ValueError(
            f"Unknown TTS provider: {provider}. "
            f"Supported providers: coqui, mock, mock_fixed_tone, mock_from_fixture, mock_fail_once"
        )
