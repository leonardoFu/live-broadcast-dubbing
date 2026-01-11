"""
VAD (Voice Activity Detection) module for audio segmentation.

This module provides VAD-based audio segmentation using GStreamer's
native level element, replacing the fixed 6-second segmentation
with dynamic segmentation based on natural speech boundaries.

Per spec 023-vad-audio-segmentation:
- Silence detection using RMS levels from GStreamer level element
- State machine for tracking silence duration
- Min/max duration constraints (1-15 seconds)
- Memory limit enforcement
- Prometheus metrics exposure

Exports:
    VADAudioSegmenter: State machine for VAD-based audio segmentation
    VADState: Enum for segmenter state (ACCUMULATING, IN_SILENCE)
    LevelMessageExtractor: Utility for extracting RMS from GStreamer messages
"""

from media_service.vad.level_message_extractor import LevelMessageExtractor
from media_service.vad.vad_audio_segmenter import VADAudioSegmenter, VADState

__all__ = [
    "VADAudioSegmenter",
    "VADState",
    "LevelMessageExtractor",
]
