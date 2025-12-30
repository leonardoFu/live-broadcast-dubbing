"""
Translation component for STS (Speech-to-Speech) service.

This module provides text translation with deterministic preprocessing
for improved translation quality and real-time stability.

Exports:
    - create_translation_component: Factory function for component creation
    - TranslationComponent: Protocol interface
    - BaseTranslationComponent: Abstract base class
    - TextAsset: Translation output model
    - TranslationStatus: Status enum
    - TranslationError: Error model
    - TranslationErrorType: Error type enum
    - SpeakerPolicy: Speaker detection policy
    - NormalizationPolicy: Text normalization policy
    - TranslationConfig: Component configuration
"""

from .factory import create_translation_component
from .interface import BaseTranslationComponent, TranslationComponent
from .models import (
    NormalizationPolicy,
    SpeakerPolicy,
    TextAsset,
    TranslationConfig,
    TranslationError,
    TranslationErrorType,
    TranslationStatus,
)

__all__ = [
    # Factory
    "create_translation_component",
    # Interface
    "TranslationComponent",
    "BaseTranslationComponent",
    # Models
    "TextAsset",
    "TranslationStatus",
    "TranslationError",
    "TranslationErrorType",
    "SpeakerPolicy",
    "NormalizationPolicy",
    "TranslationConfig",
]
