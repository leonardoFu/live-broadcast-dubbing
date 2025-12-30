"""
Mock Translation Components for testing.

Provides deterministic behavior without real translation services.
"""

import random
import time
from dataclasses import dataclass

from .interface import BaseTranslationComponent
from .models import (
    NormalizationPolicy,
    SpeakerPolicy,
    TextAsset,
    TranslationError,
    TranslationErrorType,
    TranslationStatus,
)
from .normalization import TranslationNormalizer
from .preprocessing import SpeakerLabelDetector


@dataclass
class MockTranslatorConfig:
    """Configuration for mock translator behavior.

    Used for deterministic testing without real translation.
    """

    simulate_latency_ms: int = 0
    failure_rate: float = 0.0
    failure_type: TranslationErrorType | None = None


class MockIdentityTranslator(BaseTranslationComponent):
    """Deterministic mock translator that returns input unchanged.

    Returns source text as "translated" text (identity translation).
    Useful for testing preprocessing/postprocessing without actual translation.
    """

    def __init__(self, config: MockTranslatorConfig | None = None):
        """Initialize mock with configuration.

        Args:
            config: Mock behavior configuration
        """
        self._config = config or MockTranslatorConfig()
        self._ready = True
        self._normalizer = TranslationNormalizer()
        self._speaker_detector = SpeakerLabelDetector()

    @property
    def component_instance(self) -> str:
        """Return mock instance identifier."""
        return "mock-identity-v1"

    @property
    def is_ready(self) -> bool:
        """Mock is always ready."""
        return self._ready

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
        """Return source text unchanged (identity translation).

        Args:
            source_text: Text to "translate"
            stream_id: Stream identifier
            sequence_number: Sequence number
            source_language: Source language code
            target_language: Target language code
            parent_asset_ids: References to upstream assets
            speaker_policy: Optional speaker detection policy
            normalization_policy: Optional normalization policy

        Returns:
            TextAsset with source text as translated text
        """
        start_time = time.time()

        # Simulate latency if configured
        if self._config.simulate_latency_ms > 0:
            time.sleep(self._config.simulate_latency_ms / 1000.0)

        # Apply speaker policy
        speaker_id = "default"
        text = source_text
        if speaker_policy and speaker_policy.detect_and_remove:
            speaker_id, text = self._speaker_detector.detect_and_remove(text)

        # Apply normalization policy
        normalized_text = text
        if normalization_policy and normalization_policy.enabled:
            normalized_text = self._normalizer.normalize(text, normalization_policy)

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        return TextAsset(
            stream_id=stream_id,
            sequence_number=sequence_number,
            parent_asset_ids=parent_asset_ids,
            component_instance=self.component_instance,
            source_language=source_language,
            target_language=target_language,
            translated_text=normalized_text,
            normalized_source_text=normalized_text if normalized_text != text else None,
            speaker_id=speaker_id,
            status=TranslationStatus.SUCCESS,
            processing_time_ms=processing_time_ms,
            model_info=self.component_instance,
        )


class MockLatencyTranslator(MockIdentityTranslator):
    """Mock translator with configurable latency.

    Simulates network/API latency for testing timeout handling.
    """

    def __init__(self, latency_ms: int = 100):
        """Initialize with latency configuration.

        Args:
            latency_ms: Simulated latency in milliseconds
        """
        self._latency_ms = latency_ms
        super().__init__(MockTranslatorConfig(simulate_latency_ms=latency_ms))

    @property
    def component_instance(self) -> str:
        """Return mock instance identifier with latency."""
        return f"mock-latency-{self._latency_ms}ms"


class MockFailingTranslator(BaseTranslationComponent):
    """Mock translator with configurable failure rate.

    Useful for testing error handling and retry logic.
    """

    def __init__(
        self,
        failure_rate: float = 0.5,
        failure_type: TranslationErrorType | None = None,
    ):
        """Initialize with failure configuration.

        Args:
            failure_rate: Probability of failure (0.0 to 1.0)
            failure_type: Type of error to produce on failure
        """
        self._failure_rate = failure_rate
        self._failure_type = failure_type or TranslationErrorType.PROVIDER_ERROR
        self._ready = True
        self._normalizer = TranslationNormalizer()
        self._speaker_detector = SpeakerLabelDetector()

    @property
    def component_instance(self) -> str:
        """Return mock instance identifier."""
        return f"mock-failing-{self._failure_rate:.0%}"

    @property
    def is_ready(self) -> bool:
        """Mock is always ready."""
        return self._ready

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
        """Translate with configurable failure rate.

        Args:
            source_text: Text to translate
            stream_id: Stream identifier
            sequence_number: Sequence number
            source_language: Source language code
            target_language: Target language code
            parent_asset_ids: References to upstream assets
            speaker_policy: Optional speaker detection policy
            normalization_policy: Optional normalization policy

        Returns:
            TextAsset with success or failure based on failure_rate
        """
        start_time = time.time()

        # Check for failure
        if self._should_fail():
            return self._create_failed_result(
                stream_id=stream_id,
                sequence_number=sequence_number,
                parent_asset_ids=parent_asset_ids,
                source_language=source_language,
                target_language=target_language,
            )

        # Apply speaker policy
        speaker_id = "default"
        text = source_text
        if speaker_policy and speaker_policy.detect_and_remove:
            speaker_id, text = self._speaker_detector.detect_and_remove(text)

        # Apply normalization policy
        normalized_text = text
        if normalization_policy and normalization_policy.enabled:
            normalized_text = self._normalizer.normalize(text, normalization_policy)

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        return TextAsset(
            stream_id=stream_id,
            sequence_number=sequence_number,
            parent_asset_ids=parent_asset_ids,
            component_instance=self.component_instance,
            source_language=source_language,
            target_language=target_language,
            translated_text=normalized_text,
            speaker_id=speaker_id,
            status=TranslationStatus.SUCCESS,
            processing_time_ms=processing_time_ms,
            model_info=self.component_instance,
        )

    def _should_fail(self) -> bool:
        """Determine if this call should fail based on failure rate."""
        if self._failure_rate <= 0:
            return False
        if self._failure_rate >= 1:
            return True
        return random.random() < self._failure_rate

    def _create_failed_result(
        self,
        stream_id: str,
        sequence_number: int,
        parent_asset_ids: list[str],
        source_language: str,
        target_language: str,
    ) -> TextAsset:
        """Create a failed translation result."""
        error = TranslationError(
            error_type=self._failure_type,
            message=f"Mock failure: {self._failure_type.value}",
            retryable=self._failure_type
            in (TranslationErrorType.TIMEOUT, TranslationErrorType.PROVIDER_ERROR),
        )

        return TextAsset(
            stream_id=stream_id,
            sequence_number=sequence_number,
            parent_asset_ids=parent_asset_ids,
            component_instance=self.component_instance,
            source_language=source_language,
            target_language=target_language,
            translated_text="",
            status=TranslationStatus.FAILED,
            errors=[error],
            model_info=self.component_instance,
        )
