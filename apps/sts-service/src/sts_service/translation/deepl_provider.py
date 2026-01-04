"""
DeepL Translation Provider implementation.

Provides translation using the DeepL API.
"""

import os
import time
from typing import Any

from .errors import create_translation_error
from .interface import BaseTranslationComponent
from .models import (
    NormalizationPolicy,
    SpeakerPolicy,
    TextAsset,
    TranslationConfig,
    TranslationStatus,
)
from .normalization import TranslationNormalizer
from .postprocessing import TTSCleanup
from .preprocessing import SpeakerLabelDetector


class DeepLTranslator(BaseTranslationComponent):
    """Translation component using DeepL API.

    Requires the `deepl` package and a valid API key.
    """

    def __init__(self, config: TranslationConfig | None = None):
        """Initialize DeepL translator.

        Args:
            config: Translation configuration

        Raises:
            ValueError: If DEEPL_AUTH_KEY is not set
        """
        self._config = config or TranslationConfig()
        self._normalizer = TranslationNormalizer()
        self._speaker_detector = SpeakerLabelDetector()
        self._tts_cleanup = TTSCleanup()
        self._translator: Any = None
        self._ready = False

        # Initialize DeepL client
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the DeepL API client."""
        try:
            import deepl

            auth_key = os.environ.get("DEEPL_AUTH_KEY")
            if not auth_key:
                raise ValueError("DEEPL_AUTH_KEY environment variable is required")

            self._translator = deepl.Translator(auth_key)
            self._ready = True
        except ImportError as e:
            raise ImportError("DeepL package not installed. Run: pip install deepl>=1.0.0") from e

    @property
    def component_instance(self) -> str:
        """Return provider identifier."""
        return "deepl-v1"

    @property
    def is_ready(self) -> bool:
        """Check if DeepL client is ready."""
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
        """Translate text using DeepL API.

        Args:
            source_text: Text to translate
            stream_id: Stream identifier
            sequence_number: Sequence number
            source_language: Source language code (e.g., "en")
            target_language: Target language code (e.g., "es")
            parent_asset_ids: References to upstream assets
            speaker_policy: Optional speaker detection policy
            normalization_policy: Optional normalization policy

        Returns:
            TextAsset with translation results
        """
        start_time = time.time()
        warnings: list[str] = []

        # Use config defaults if policies not provided
        if speaker_policy is None:
            speaker_policy = self._config.default_speaker_policy
        if normalization_policy is None:
            normalization_policy = self._config.default_normalization_policy

        # Apply speaker policy
        speaker_id = "default"
        text = source_text
        if speaker_policy.detect_and_remove:
            speaker_id, text = self._speaker_detector.detect_and_remove(text)

        # Apply pre-translation normalization
        normalized_text = text
        if normalization_policy.enabled:
            normalized_text = self._normalizer.normalize(text, normalization_policy)

        # Handle empty text
        if not normalized_text.strip():
            warnings.append("Empty input after preprocessing")
            return TextAsset(
                stream_id=stream_id,
                sequence_number=sequence_number,
                parent_asset_ids=parent_asset_ids,
                component_instance=self.component_instance,
                source_language=source_language,
                target_language=target_language,
                translated_text="",
                normalized_source_text=normalized_text,
                speaker_id=speaker_id,
                status=TranslationStatus.SUCCESS,
                warnings=warnings,
                processing_time_ms=int((time.time() - start_time) * 1000),
                model_info=self.component_instance,
            )

        # Call DeepL API
        try:
            result = self._translator.translate_text(
                normalized_text,
                source_lang=source_language.upper(),
                target_lang=target_language.upper(),
            )
            translated_text = result.text

            # Apply TTS cleanup if enabled
            if normalization_policy.tts_cleanup:
                translated_text = self._tts_cleanup.cleanup(translated_text)

            processing_time_ms = int((time.time() - start_time) * 1000)

            return TextAsset(
                stream_id=stream_id,
                sequence_number=sequence_number,
                parent_asset_ids=parent_asset_ids,
                component_instance=self.component_instance,
                source_language=source_language,
                target_language=target_language,
                translated_text=translated_text,
                normalized_source_text=normalized_text,
                speaker_id=speaker_id,
                status=TranslationStatus.SUCCESS,
                warnings=warnings,
                processing_time_ms=processing_time_ms,
                model_info=self.component_instance,
            )

        except Exception as e:
            error = create_translation_error(e)
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Fallback to source text if configured
            fallback_text = ""
            if self._config.fallback_to_source_on_error:
                fallback_text = normalized_text
                warnings.append("Fallback to source text due to translation error")

            return TextAsset(
                stream_id=stream_id,
                sequence_number=sequence_number,
                parent_asset_ids=parent_asset_ids,
                component_instance=self.component_instance,
                source_language=source_language,
                target_language=target_language,
                translated_text=fallback_text,
                normalized_source_text=normalized_text,
                speaker_id=speaker_id,
                status=TranslationStatus.FAILED,
                errors=[error],
                warnings=warnings,
                processing_time_ms=processing_time_ms,
                model_info=self.component_instance,
            )

    def shutdown(self) -> None:
        """Release DeepL client resources."""
        self._translator = None
        self._ready = False
