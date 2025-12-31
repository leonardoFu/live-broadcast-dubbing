"""
TTS Component Interface Contract.

This module defines the abstract interface that all TTS implementations must follow.
Both the real Coqui TTS implementation and mock implementations conform to this contract.

Based on specs/008-tts-module/contracts/tts-component.yaml.
"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from sts_service.translation.models import TextAsset

from .models import AudioAsset, VoiceProfile


@runtime_checkable
class TTSComponent(Protocol):
    """Protocol defining the TTS component contract.

    All TTS implementations (real and mock) must implement this interface.
    This follows the component contract from specs/004-sts-pipeline-design.md Section 6.4.
    """

    @property
    def component_name(self) -> str:
        """Return the component name (always 'tts')."""
        ...

    @property
    def component_instance(self) -> str:
        """Return the provider identifier (e.g., 'coqui-xtts-v2')."""
        ...

    @property
    def is_ready(self) -> bool:
        """Check if the component is ready to process requests.

        Returns True if:
        - Models are loaded and available
        - Configuration is valid
        - Required dependencies (rubberband, etc.) are available
        """
        ...

    def synthesize(
        self,
        text_asset: TextAsset,
        target_duration_ms: int | None = None,
        output_sample_rate_hz: int = 16000,
        output_channels: int = 1,
        voice_profile: VoiceProfile | None = None,
    ) -> AudioAsset:
        """Synthesize speech audio from translated text.

        Args:
            text_asset: TextAsset from Translation module containing text to synthesize
            target_duration_ms: Optional target duration for duration matching
                               If None, no duration matching is applied
            output_sample_rate_hz: Desired output sample rate (default 16kHz)
            output_channels: Desired output channels (1=mono, 2=stereo)
            voice_profile: Optional voice configuration override

        Returns:
            AudioAsset with synthesized speech audio

        The component MUST:
        - Return SUCCESS status with valid audio for successful synthesis
        - Return PARTIAL status if audio produced but with warnings (e.g., clamped speed)
        - Return FAILED status with retryable=True for transient errors
        - Return FAILED status with retryable=False for permanent errors
        - Track parent_asset_ids from text_asset.asset_id for lineage
        - Apply preprocessing before synthesis
        - Apply duration matching if target_duration_ms is provided
        """
        ...

    def shutdown(self) -> None:
        """Release resources (model cache, etc.)."""
        ...


class BaseTTSComponent(ABC):
    """Abstract base class for TTS component implementations.

    Provides common functionality and enforces the TTS contract.
    """

    _component_name: str = "tts"

    @property
    def component_name(self) -> str:
        """Return the component name (always 'tts')."""
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
    def synthesize(
        self,
        text_asset: TextAsset,
        target_duration_ms: int | None = None,
        output_sample_rate_hz: int = 16000,
        output_channels: int = 1,
        voice_profile: VoiceProfile | None = None,
    ) -> AudioAsset:
        """Subclasses must implement synthesis logic."""
        pass

    def shutdown(self) -> None:
        """Default implementation does nothing. Override if cleanup needed."""
        return  # noqa: B027 - intentionally empty default implementation
