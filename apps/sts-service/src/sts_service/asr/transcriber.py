"""
FasterWhisperASR - Production ASR component using faster-whisper.

Provides CPU-friendly Whisper transcription with model caching.
"""

import time
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel

from .confidence import calculate_confidence
from .domain_prompts import get_domain_prompt
from .errors import create_asr_error
from .interface import BaseASRComponent
from .models import (
    ASRConfig,
    TranscriptAsset,
    TranscriptSegment,
    TranscriptStatus,
    WordTiming,
)
from .postprocessing import shape_utterances
from .preprocessing import preprocess_audio

# Global model cache keyed by (model_size, device, compute_type)
_MODEL_CACHE: dict[tuple[str, str, str], WhisperModel] = {}


def _get_or_load_model(
    model_size: str,
    device: str = "cpu",
    compute_type: str = "int8",
) -> WhisperModel:
    """Get cached model or load a new one.

    Args:
        model_size: Whisper model size (tiny, base, small, etc.)
        device: Compute device (cpu, cuda, cuda:0)
        compute_type: Compute precision (int8, float16, float32)

    Returns:
        Loaded WhisperModel instance
    """
    cache_key = (model_size, device, compute_type)

    if cache_key not in _MODEL_CACHE:
        _MODEL_CACHE[cache_key] = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )

    return _MODEL_CACHE[cache_key]


def _clear_model_cache() -> None:
    """Clear the model cache to free memory."""
    global _MODEL_CACHE
    _MODEL_CACHE = {}


class FasterWhisperASR(BaseASRComponent):
    """Production ASR component using faster-whisper.

    Features:
    - Model caching across fragments
    - Preprocessing (highpass, preemphasis, normalization)
    - Domain-specific vocabulary priming
    - VAD filtering
    - Utterance shaping (merge/split)
    - Error classification and retry hints
    """

    def __init__(self, config: ASRConfig | None = None):
        """Initialize with configuration.

        Args:
            config: ASR configuration (uses defaults if not provided)
        """
        self._config = config or ASRConfig()
        self._model: WhisperModel | None = None
        self._load_model()

    def _load_model(self) -> None:
        """Load the Whisper model."""
        model_config = self._config.model
        self._model = _get_or_load_model(
            model_size=model_config.model_size,
            device=model_config.device,
            compute_type=model_config.compute_type,
        )

    @property
    def component_instance(self) -> str:
        """Return instance identifier with model info."""
        model_config = self._config.model
        return f"faster-whisper-{model_config.model_size}-{model_config.compute_type}"

    @property
    def is_ready(self) -> bool:
        """Check if model is loaded and ready."""
        return self._model is not None

    def transcribe(
        self,
        audio_data: bytes,
        stream_id: str,
        sequence_number: int,
        start_time_ms: int,
        end_time_ms: int,
        sample_rate_hz: int = 16000,
        domain: str = "general",
        language: str = "en",
    ) -> TranscriptAsset:
        """Transcribe an audio fragment.

        Args:
            audio_data: Raw PCM audio bytes (float32 little-endian)
            stream_id: Logical stream/session identifier
            sequence_number: Fragment index within stream
            start_time_ms: Fragment start in stream timeline
            end_time_ms: Fragment end in stream timeline
            sample_rate_hz: Audio sample rate (default 16kHz)
            domain: Domain hint for vocabulary priming
            language: Expected language code

        Returns:
            TranscriptAsset with transcription results
        """
        start_time = time.time()

        try:
            # Preprocess audio
            audio = preprocess_audio(
                audio_data,
                sample_rate=sample_rate_hz,
                target_sample_rate=16000,
            )

            # DEBUG
            import logging
            import numpy as np

            logger = logging.getLogger(__name__)
            logger.info(
                f"DEBUG transcriber: Audio shape={audio.shape if hasattr(audio, 'shape') else len(audio)}, dtype={audio.dtype if hasattr(audio, 'dtype') else type(audio)}"
            )
            if hasattr(audio, "shape"):
                logger.info(
                    f"DEBUG transcriber: Audio min={audio.min():.4f}, max={audio.max():.4f}, mean={np.abs(audio).mean():.4f}"
                )

            # Get domain prompt
            initial_prompt = get_domain_prompt(domain)

            # Configure VAD
            vad_config = self._config.vad
            vad_filter = vad_config.enabled
            vad_parameters = {
                "threshold": vad_config.threshold,
                "min_silence_duration_ms": vad_config.min_silence_duration_ms,
                "min_speech_duration_ms": vad_config.min_speech_duration_ms,
                "speech_pad_ms": vad_config.speech_pad_ms,
            }

            # Configure transcription
            trans_config = self._config.transcription

            # Run transcription
            if self._model is None:
                raise RuntimeError("Model not loaded")

            # DEBUG: Log transcription config
            logger.info(
                f"DEBUG transcriber: no_speech_threshold={trans_config.no_speech_threshold}"
            )
            logger.info(f"DEBUG transcriber: vad_filter={vad_filter}, vad_params={vad_parameters}")

            # DEBUG: Save audio to file for comparison
            import tempfile
            from pathlib import Path

            debug_audio_file = Path("/tmp/debug_audio_from_transcriber.npy")
            np.save(debug_audio_file, audio)
            logger.info(f"DEBUG transcriber: Saved audio to {debug_audio_file}")

            segments_iter, info = self._model.transcribe(
                audio,
                language=language,
                initial_prompt=initial_prompt,
                beam_size=trans_config.beam_size,
                best_of=trans_config.best_of,
                temperature=trans_config.temperature,
                compression_ratio_threshold=trans_config.compression_ratio_threshold,
                log_prob_threshold=trans_config.log_prob_threshold,
                no_speech_threshold=trans_config.no_speech_threshold,
                word_timestamps=trans_config.word_timestamps,
                vad_filter=vad_filter,
                vad_parameters=vad_parameters if vad_filter else None,
            )

            # DEBUG: Convert to list immediately to check
            import logging

            logger = logging.getLogger(__name__)
            segments_list = list(segments_iter)
            logger.info(
                f"DEBUG transcriber: faster-whisper returned {len(segments_list)} raw segments"
            )
            for i, seg in enumerate(segments_list):
                logger.info(
                    f"DEBUG transcriber: Raw segment {i}: [{seg.start:.2f}s-{seg.end:.2f}s] '{seg.text}'"
                )

            # Convert segments (use segments_list, not the exhausted iterator!)
            transcript_segments = self._convert_segments(
                segments_list,
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
            )

            # DEBUG
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"DEBUG transcriber: Converted {len(transcript_segments)} segments")

            # Apply utterance shaping
            shaped_segments = shape_utterances(
                transcript_segments,
                self._config.utterance_shaping,
            )

            # DEBUG
            logger.info(f"DEBUG transcriber: Shaped {len(shaped_segments)} segments")

            processing_time_ms = int((time.time() - start_time) * 1000)

            result = TranscriptAsset(
                stream_id=stream_id,
                sequence_number=sequence_number,
                component_instance=self.component_instance,
                language=info.language,
                language_probability=info.language_probability,
                segments=shaped_segments,
                status=TranscriptStatus.SUCCESS,
                processing_time_ms=processing_time_ms,
                model_info=self.component_instance,
            )
            self._emit_transcript_artifact(result)
            return result

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            error = create_asr_error(e)

            result = TranscriptAsset(
                stream_id=stream_id,
                sequence_number=sequence_number,
                component_instance=self.component_instance,
                language=language,
                segments=[],
                status=TranscriptStatus.FAILED,
                errors=[error],
                processing_time_ms=processing_time_ms,
                model_info=self.component_instance,
            )
            self._emit_transcript_artifact(result)
            return result

    def _convert_segments(
        self,
        segments_iter: Any,
        start_time_ms: int,
        end_time_ms: int,
    ) -> list[TranscriptSegment]:
        """Convert faster-whisper segments to TranscriptSegment.

        Converts relative timestamps (within fragment) to absolute
        timestamps (in stream timeline).

        Args:
            segments_iter: Iterator of faster-whisper segments
            start_time_ms: Fragment start time in stream
            end_time_ms: Fragment end time in stream

        Returns:
            List of TranscriptSegment with absolute timestamps
        """
        result = []
        fragment_duration_s = (end_time_ms - start_time_ms) / 1000.0

        import logging

        logger = logging.getLogger(__name__)
        segment_count = 0

        for segment in segments_iter:
            segment_count += 1
            logger.info(
                f"DEBUG _convert_segments: Processing segment {segment_count}: '{segment.text}'"
            )
            # Convert relative seconds to absolute milliseconds
            seg_start_s = segment.start
            seg_end_s = segment.end

            # Clamp to fragment bounds
            seg_start_s = max(0, min(seg_start_s, fragment_duration_s))
            seg_end_s = max(seg_start_s, min(seg_end_s, fragment_duration_s))

            # Convert to absolute milliseconds
            abs_start_ms = start_time_ms + int(seg_start_s * 1000)
            abs_end_ms = start_time_ms + int(seg_end_s * 1000)

            # Ensure valid range
            abs_start_ms = max(start_time_ms, abs_start_ms)
            abs_end_ms = min(end_time_ms, max(abs_end_ms, abs_start_ms + 1))

            # Skip empty segments
            text = segment.text.strip()
            if not text:
                continue

            # Calculate confidence
            confidence = calculate_confidence(segment.avg_logprob)

            # Convert words if available
            words = None
            if hasattr(segment, "words") and segment.words:
                words = self._convert_words(
                    segment.words,
                    start_time_ms=start_time_ms,
                    fragment_duration_s=fragment_duration_s,
                )

            result.append(
                TranscriptSegment(
                    start_time_ms=abs_start_ms,
                    end_time_ms=abs_end_ms,
                    text=text,
                    confidence=confidence,
                    words=words,
                    no_speech_probability=segment.no_speech_prob,
                )
            )

        return result

    def _convert_words(
        self,
        words: list[Any],
        start_time_ms: int,
        fragment_duration_s: float,
    ) -> list[WordTiming]:
        """Convert faster-whisper words to WordTiming.

        Args:
            words: List of faster-whisper word objects
            start_time_ms: Fragment start time
            fragment_duration_s: Fragment duration in seconds

        Returns:
            List of WordTiming with absolute timestamps
        """
        result = []

        for word in words:
            # Clamp to fragment bounds
            word_start_s = max(0, min(word.start, fragment_duration_s))
            word_end_s = max(word_start_s, min(word.end, fragment_duration_s))

            # Convert to absolute milliseconds
            abs_start = start_time_ms + int(word_start_s * 1000)
            abs_end = start_time_ms + int(word_end_s * 1000)

            # Ensure valid range
            abs_end = max(abs_end, abs_start + 1)

            result.append(
                WordTiming(
                    start_time_ms=abs_start,
                    end_time_ms=abs_end,
                    word=word.word.strip(),
                    confidence=word.probability if hasattr(word, "probability") else None,
                )
            )

        return result

    def _emit_transcript_artifact(self, result: TranscriptAsset) -> None:
        """Append transcript text to session file when debug_artifacts is enabled.

        Appends each fragment's transcript to a single file per session,
        allowing inspection of the full transcript for the whole session.

        Args:
            result: The transcript asset to emit
        """
        if not self._config.debug_artifacts:
            return

        output_dir = Path(".artifacts/asr") / result.stream_id
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / "transcript.txt"
        content = result.total_text if result.total_text else ""

        # Append to session file (skip empty segments)
        if content:
            with output_file.open("a", encoding="utf-8") as f:
                f.write(f"{content}\n")

    def shutdown(self) -> None:
        """Release model resources."""
        # Clear the model cache to free memory
        _clear_model_cache()
        self._model = None
