"""
Factory function for creating ASR components.

Provides a unified interface for creating ASR component instances.
"""


from .interface import ASRComponent
from .mock import MockASRComponent
from .models import ASRConfig


def create_asr_component(
    config: ASRConfig | None = None,
    mock: bool = False,
) -> ASRComponent:
    """Create an ASR component instance.

    Args:
        config: ASR configuration (uses defaults if not provided)
        mock: If True, return MockASRComponent instead of real implementation

    Returns:
        ASRComponent instance (either FasterWhisperASR or MockASRComponent)
    """
    if config is None:
        config = ASRConfig()

    if mock:
        return MockASRComponent()

    # Import here to avoid loading faster-whisper when not needed
    from .transcriber import FasterWhisperASR

    return FasterWhisperASR(config=config)
