"""
Focused logging configuration for debugging VAD, A/V sync, and output.

Usage:
  Set LOG_FOCUS=1 environment variable to enable focused logging.
  Only logs from VAD, A/V sync, and output pipeline will be shown at INFO level.
  Other modules will be set to WARNING level to reduce noise.

Modules included in focused logging:
  - media_service.sync.av_sync (A/V pairing)
  - media_service.vad.vad_audio_segmenter (VAD segmentation)
  - media_service.pipeline.output (RTMP output)
  - media_service.worker.worker_runner (orchestration)

Example:
  LOG_LEVEL=DEBUG LOG_FOCUS=1 docker compose up media-service
"""

import logging
import os


def configure_focused_logging() -> None:
    """Configure logging to focus on VAD, A/V sync, and output modules.

    When LOG_FOCUS=1 is set:
    - Focused modules log at LOG_LEVEL (default INFO)
    - Other modules log at WARNING only
    - Reduces noise from input pipeline, STS client, etc.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_focus = os.getenv("LOG_FOCUS", "0") == "1"

    # Base format with timestamps for timeline analysis
    log_format = "%(asctime)s.%(msecs)03d | %(name)s | %(levelname)s | %(message)s"
    date_format = "%H:%M:%S"

    # Configure root logger
    logging.basicConfig(
        level=log_level if not log_focus else logging.WARNING,
        format=log_format,
        datefmt=date_format,
        force=True,  # Override any existing config
    )

    if not log_focus:
        return

    # Focused modules - set to requested log level
    focused_modules = [
        "media_service.sync.av_sync",
        "media_service.vad.vad_audio_segmenter",
        "media_service.pipeline.output",
        "media_service.worker.worker_runner",
    ]

    for module in focused_modules:
        logger = logging.getLogger(module)
        logger.setLevel(log_level)

    # Log the configuration
    root_logger = logging.getLogger()
    root_logger.warning(
        f"Focused logging enabled: {', '.join(focused_modules)} at {log_level}"
    )


# Predefined log filter patterns for grep
LOG_PATTERNS = {
    "vad": [
        "VAD RMS",
        "VAD audio segment",
        "Silence",
        "ACCUMULATING",
        "IN_SILENCE",
        "Emitting segment",
    ],
    "av_pair": [
        "A/V PAIR",
        "Video paired",
        "Audio paired",
        "BUFFERED PAIR",
        "Video buffered",
        "Audio buffered",
        "AUDIO WAITING",
    ],
    "push": [
        "VIDEO PUSHED",
        "AUDIO PUSHED",
        "OUTPUTTING PAIR",
        "OUTPUT BUFFER",
        "push-buffer",
    ],
    "pts": [
        "pts=",
        "video_pts=",
        "audio_pts=",
        "PTS",
        "First video PTS",
        "First audio PTS",
        "Base PTS",
    ],
    "timeline": [
        "A/V TIMELINE",
        "video_end=",
        "audio_end=",
        "delta=",
        "SYNC",
        "V_AHEAD",
        "A_AHEAD",
    ],
}


def get_grep_pattern(focus: str) -> str:
    """Get grep pattern for filtering logs.

    Args:
        focus: One of 'vad', 'av_pair', 'push', 'pts', or 'all'

    Returns:
        Grep-compatible regex pattern
    """
    if focus == "all":
        all_patterns = []
        for patterns in LOG_PATTERNS.values():
            all_patterns.extend(patterns)
        return "|".join(all_patterns)

    patterns = LOG_PATTERNS.get(focus, [])
    return "|".join(patterns)
