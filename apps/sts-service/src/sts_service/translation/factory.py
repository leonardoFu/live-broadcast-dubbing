"""
Factory function for creating Translation components.

Provides a unified interface for creating Translation component instances.
"""

import os

from .interface import TranslationComponent
from .mock import MockIdentityTranslator
from .models import TranslationConfig


def create_translation_component(
    config: TranslationConfig | None = None,
    mock: bool = False,
    provider: str = "deepl",
) -> TranslationComponent:
    """Create a Translation component instance.

    Args:
        config: Translation configuration (uses defaults if not provided)
        mock: If True, return MockIdentityTranslator instead of real implementation
        provider: Provider name ("deepl" is the only supported provider currently)

    Returns:
        TranslationComponent instance (either DeepLTranslator or MockIdentityTranslator)

    Raises:
        ValueError: If provider is "deepl" and no auth key is available
    """
    if config is None:
        config = TranslationConfig()

    if mock:
        return MockIdentityTranslator()

    # Real provider implementation
    if provider == "deepl":
        # Check for auth key
        auth_key = os.environ.get("DEEPL_AUTH_KEY")
        if not auth_key:
            raise ValueError(
                "DeepL auth key required. Set DEEPL_AUTH_KEY environment variable "
                "or use mock=True for testing."
            )

        # Import here to avoid loading deepl when not needed
        from .deepl_provider import DeepLTranslator

        return DeepLTranslator(config=config)

    raise ValueError(f"Unknown provider: {provider}. Supported: deepl")
