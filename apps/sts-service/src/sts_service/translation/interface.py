"""
Translation Component Interface Contract.

This module defines the abstract interface that all Translation implementations must follow.
Both real provider implementations (e.g., DeepL) and mock implementations conform to this contract.
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from .models import NormalizationPolicy, SpeakerPolicy, TextAsset


@runtime_checkable
class TranslationComponent(Protocol):
    """Protocol defining the Translation component contract.

    All Translation implementations (real and mock) must implement this interface.
    This follows the component contract from specs/004-sts-pipeline-design.md Section 6.3.
    """

    @property
    def component_name(self) -> str:
        """Return the component name (always 'translate')."""
        ...

    @property
    def component_instance(self) -> str:
        """Return the provider identifier (e.g., 'mock-identity-v1')."""
        ...

    @property
    def is_ready(self) -> bool:
        """Check if the component is ready to process requests."""
        ...

    def translate(
        self,
        source_text: str,
        stream_id: str,
        sequence_number: int,
        source_language: str,
        target_language: str,
        parent_asset_ids: list[str],
        speaker_policy: SpeakerPolicy | None = None,
        normalization_policy: NormalizationPolicy | None = None,
    ) -> TextAsset:
        """Translate text from source to target language.

        Args:
            source_text: Text to translate
            stream_id: Logical stream/session identifier
            sequence_number: Fragment index within stream
            source_language: Source language code (e.g., "en")
            target_language: Target language code (e.g., "es")
            parent_asset_ids: References to upstream assets (e.g., TranscriptAsset)
            speaker_policy: Optional speaker detection policy
            normalization_policy: Optional text normalization policy

        Returns:
            TextAsset with translation results

        The component MUST:
        - Return SUCCESS status with translated_text for successful translation
        - Return FAILED status with retryable=True for transient errors
        - Return FAILED status with retryable=False for permanent errors
        - Preserve parent_asset_ids for lineage tracking
        """
        ...

    def shutdown(self) -> None:
        """Release resources (API connections, etc.)."""
        ...


class BaseTranslationComponent(ABC):
    """Abstract base class for Translation component implementations.

    Provides common functionality and enforces the Translation contract.
    """

    _component_name: str = "translate"

    @property
    def component_name(self) -> str:
        """Return the component name (always 'translate')."""
        return self._component_name

    @property
    @abstractmethod
    def component_instance(self) -> str:
        """Subclasses must provide their instance identifier."""
        pass

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Subclasses must indicate readiness."""
        pass

    @abstractmethod
    def translate(
        self,
        source_text: str,
        stream_id: str,
        sequence_number: int,
        source_language: str,
        target_language: str,
        parent_asset_ids: list[str],
        speaker_policy: SpeakerPolicy | None = None,
        normalization_policy: NormalizationPolicy | None = None,
    ) -> TextAsset:
        """Subclasses must implement translation logic."""
        pass

    def shutdown(self) -> None:
        """Default implementation does nothing. Override if cleanup needed."""
        return  # noqa: B027 - intentionally empty default implementation
