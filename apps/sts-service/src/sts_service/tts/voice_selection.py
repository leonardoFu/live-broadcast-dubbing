"""
Voice Selection for TTS.

Provides voice and model selection logic based on configuration and voice profiles.
Supports voice cloning, fast mode, and speaker selection.

Features:
- Load voice configuration from YAML
- Select appropriate model based on language and mode
- Validate voice samples for cloning
- Select speaker for multi-speaker models

Based on specs/008-tts-module/plan.md Phase 0 research.
"""

import logging
import os
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import VoiceProfile

logger = logging.getLogger(__name__)


class VoiceConfigError(Exception):
    """Error loading or parsing voice configuration."""

    pass


@dataclass
class VoiceSampleValidation:
    """Result of voice sample validation."""

    is_valid: bool
    error_message: str = ""
    sample_rate_hz: int = 0
    channels: int = 0
    duration_seconds: float = 0.0


# Default voice configuration
DEFAULT_CONFIG: dict[str, Any] = {
    "defaults": {
        "output_sample_rate_hz": 16000,
        "output_channels": 1,
        "device": "cpu",
    },
    "languages": {
        "en": {
            "model": "tts_models/multilingual/multi-dataset/xtts_v2",
            "fast_model": "tts_models/en/vctk/vits",
            "default_speaker": "p225",
            "sample_rate_hz": 24000,
        },
        "es": {
            "model": "tts_models/multilingual/multi-dataset/xtts_v2",
            "fast_model": "tts_models/es/css10/vits",
            "default_speaker": None,
            "sample_rate_hz": 24000,
        },
    },
}


def load_voice_config(config_path: str | None = None) -> dict[str, Any]:
    """Load voice configuration from YAML file.

    Args:
        config_path: Path to configuration file. If None, uses TTS_VOICES_CONFIG
                    environment variable or returns default config.

    Returns:
        Parsed configuration dictionary

    Raises:
        VoiceConfigError: If config file not found or invalid
    """
    # Check for environment variable
    if config_path is None:
        config_path = os.environ.get("TTS_VOICES_CONFIG")

    # Return default config if no path specified
    if config_path is None:
        logger.info("No voice config path specified, using default configuration")
        return DEFAULT_CONFIG

    # Load from file
    path = Path(config_path)
    if not path.exists():
        raise VoiceConfigError(f"Configuration file not found: {config_path}")

    try:
        with open(path) as f:
            config = yaml.safe_load(f)

        # Validate required structure
        if "languages" not in config:
            raise VoiceConfigError("Configuration missing 'languages' section")

        return config

    except yaml.YAMLError as e:
        raise VoiceConfigError(f"Invalid YAML in configuration: {e}") from e


def select_model(
    profile: VoiceProfile,
    config: dict[str, Any],
) -> str:
    """Select TTS model based on voice profile and configuration.

    Args:
        profile: Voice profile with language and mode settings
        config: Voice configuration dictionary

    Returns:
        Model name string (e.g., "tts_models/multilingual/multi-dataset/xtts_v2")
    """
    # Check for explicit model override
    if profile.model_name:
        return profile.model_name

    # Get language config
    lang_config = config.get("languages", {}).get(profile.language, {})

    if profile.fast_mode:
        # Fast mode: prefer fast_model
        fast_model = lang_config.get("fast_model")
        if fast_model:
            return fast_model
        else:
            # Fallback to standard model
            logger.warning(
                f"No fast_model configured for language '{profile.language}', "
                "falling back to standard model"
            )
            return lang_config.get("model", DEFAULT_CONFIG["languages"]["en"]["model"])
    else:
        # Quality mode: use standard model
        return lang_config.get("model", DEFAULT_CONFIG["languages"]["en"]["model"])


def select_voice(
    profile: VoiceProfile,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Select voice settings (cloning or speaker) based on profile.

    Args:
        profile: Voice profile with voice settings
        config: Voice configuration dictionary

    Returns:
        Dictionary with voice settings:
        - use_cloning: bool
        - voice_sample_path: str or None
        - speaker_name: str or None
    """
    result: dict[str, Any] = {
        "use_cloning": False,
        "voice_sample_path": None,
        "speaker_name": None,
    }

    # Get language config
    lang_config = config.get("languages", {}).get(profile.language, {})

    # Check for voice cloning
    if profile.use_voice_cloning and profile.voice_sample_path:
        # Voice cloning not supported in fast mode (VITS)
        if profile.fast_mode:
            logger.warning(
                "Voice cloning not supported in fast mode (VITS), falling back to speaker selection"
            )
        else:
            # Validate voice sample
            validation = validate_voice_sample(profile.voice_sample_path)
            if validation.is_valid:
                result["use_cloning"] = True
                result["voice_sample_path"] = profile.voice_sample_path
                return result
            else:
                logger.warning(
                    f"Voice sample invalid: {validation.error_message}, "
                    "falling back to speaker selection"
                )

    # Speaker selection
    if profile.speaker_name:
        result["speaker_name"] = profile.speaker_name
    else:
        # Use default speaker from config
        result["speaker_name"] = lang_config.get("default_speaker")

    return result


def validate_voice_sample(path: str) -> VoiceSampleValidation:
    """Validate a voice sample file for cloning.

    Validation criteria:
    - Format: WAV only
    - Channels: Mono (1 channel)
    - Sample rate: Minimum 16kHz
    - Duration: Between 3 and 30 seconds

    Args:
        path: Path to voice sample file

    Returns:
        VoiceSampleValidation with validation result
    """
    # Check file exists
    if not os.path.exists(path):
        return VoiceSampleValidation(
            is_valid=False,
            error_message=f"File not found: {path}",
        )

    # Check format (must be WAV)
    if not path.lower().endswith(".wav"):
        return VoiceSampleValidation(
            is_valid=False,
            error_message=f"Invalid format: must be WAV, got {Path(path).suffix}",
        )

    try:
        with wave.open(path, "rb") as wav:
            channels = wav.getnchannels()
            sample_rate = wav.getframerate()
            num_frames = wav.getnframes()
            duration = num_frames / sample_rate

            # Check channels (must be mono)
            if channels != 1:
                return VoiceSampleValidation(
                    is_valid=False,
                    error_message=f"Invalid channel count: must be mono (1), got {channels}",
                    sample_rate_hz=sample_rate,
                    channels=channels,
                    duration_seconds=duration,
                )

            # Check sample rate (minimum 16kHz)
            if sample_rate < 16000:
                return VoiceSampleValidation(
                    is_valid=False,
                    error_message=f"Invalid sample rate: minimum 16kHz, got {sample_rate}Hz",
                    sample_rate_hz=sample_rate,
                    channels=channels,
                    duration_seconds=duration,
                )

            # Check duration (3-30 seconds)
            if duration < 3.0:
                return VoiceSampleValidation(
                    is_valid=False,
                    error_message=f"Invalid duration: minimum 3 seconds, got {duration:.1f}s",
                    sample_rate_hz=sample_rate,
                    channels=channels,
                    duration_seconds=duration,
                )
            if duration > 30.0:
                return VoiceSampleValidation(
                    is_valid=False,
                    error_message=f"Invalid duration: maximum 30 seconds, got {duration:.1f}s",
                    sample_rate_hz=sample_rate,
                    channels=channels,
                    duration_seconds=duration,
                )

            # All checks passed
            return VoiceSampleValidation(
                is_valid=True,
                sample_rate_hz=sample_rate,
                channels=channels,
                duration_seconds=duration,
            )

    except wave.Error as e:
        return VoiceSampleValidation(
            is_valid=False,
            error_message=f"Invalid WAV file: {e}",
        )
    except Exception as e:
        return VoiceSampleValidation(
            is_valid=False,
            error_message=f"Error reading file: {e}",
        )
