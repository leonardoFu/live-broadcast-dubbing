"""
Configuration module for media service.

This module provides Pydantic-based configuration models
loaded from environment variables.

Per spec 023-vad-audio-segmentation:
- SegmentationConfig: VAD parameters with VAD_ prefix

Exports:
    SegmentationConfig: VAD segmentation configuration
"""

from media_service.config.segmentation_config import SegmentationConfig

__all__ = [
    "SegmentationConfig",
]
