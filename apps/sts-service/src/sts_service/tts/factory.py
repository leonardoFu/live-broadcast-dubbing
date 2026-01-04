"""
TTS Component Factory.

Creates TTS component instances based on provider configuration.
Supports mock providers for testing, Coqui provider for local synthesis,
and ElevenLabs provider for cloud-based synthesis.

The default provider is controlled by the TTS_PROVIDER environment variable.
Default: "elevenlabs" (cloud TTS for production).
"""

import os
from typing import Any, Literal

from .interface import TTSComponent
from .models import TTSConfig

ProviderType = Literal[
    "elevenlabs", "coqui", "mock", "mock_fixed_tone", "mock_from_fixture", "mock_fail_once"
]

# Default provider (can be overridden by TTS_PROVIDER env var)
DEFAULT_PROVIDER: ProviderType = "elevenlabs"


def create_tts_component(
    provider: ProviderType | None = None,
    config: TTSConfig | None = None,
    **kwargs: Any,
) -> TTSComponent:
    """Create a TTS component instance.

    Args:
        provider: The TTS provider to use. If None, uses TTS_PROVIDER env var
                  or defaults to "elevenlabs".
            - "elevenlabs": ElevenLabs cloud TTS (default for production)
            - "coqui": Local Coqui TTS (XTTS-v2 or VITS)
            - "mock": Alias for "mock_fixed_tone"
            - "mock_fixed_tone": Produces deterministic 440Hz tone
            - "mock_from_fixture": Returns pre-recorded audio from fixtures
            - "mock_fail_once": Fails first call, succeeds on retry
        config: Optional TTS configuration
        **kwargs: Additional provider-specific arguments:
            For elevenlabs:
                - api_key: ElevenLabs API key (defaults to ELEVENLABS_API_KEY env var)
                - model_id: Model ID (defaults to eleven_flash_v2_5)
            For coqui:
                - fast_mode: Use fast model (VITS) instead of quality (XTTS-v2)
                - voices_config_path: Path to coqui-voices.yaml

    Returns:
        TTSComponent instance

    Raises:
        ValueError: If provider is not supported
    """
    # Determine provider from parameter, env var, or default
    if provider is None:
        provider = os.environ.get("TTS_PROVIDER", DEFAULT_PROVIDER)  # type: ignore

    if config is None:
        config = TTSConfig()

    if provider == "elevenlabs":
        from .elevenlabs_provider import ElevenLabsTTSComponent

        return ElevenLabsTTSComponent(config=config, **kwargs)

    elif provider == "coqui":
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
        supported = "elevenlabs, coqui, mock, mock_fixed_tone, mock_from_fixture, mock_fail_once"
        raise ValueError(f"Unknown TTS provider: {provider}. Supported providers: {supported}")
