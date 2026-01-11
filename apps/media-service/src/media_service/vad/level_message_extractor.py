"""
Utility for extracting RMS values from GStreamer level element messages.

Per spec 023-vad-audio-segmentation:
- Extracts peak RMS across all audio channels
- Extracts running-time timestamp
- Detects level messages by type
- Handles GValue/GValueArray extraction complexities

The level element posts ELEMENT messages to the GStreamer bus with:
- "rms" field: GValueArray of per-channel RMS values in dB
- "running-time" field: Current stream position in nanoseconds
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# Protocol for GStreamer message type checking (duck typing)
class GstMessageLike(Protocol):
    """Protocol for objects that look like Gst.Message."""

    type: int

    def get_structure(self) -> Any: ...


class GstStructureLike(Protocol):
    """Protocol for objects that look like Gst.Structure."""

    def get_name(self) -> str: ...

    def get_array(self, field: str) -> tuple[bool, Any]: ...

    def get_uint64(self, field: str) -> tuple[bool, int]: ...


# GStreamer ELEMENT message type value
# This constant matches Gst.MessageType.ELEMENT
GST_MESSAGE_TYPE_ELEMENT = 16


class LevelMessageExtractor:
    """Extract RMS values from GStreamer level element messages.

    Handles the complexities of GValue/GValueArray extraction
    from GStreamer message structures.

    This class uses static methods to allow easy testing without
    requiring actual GStreamer to be installed.
    """

    @staticmethod
    def extract_peak_rms_db(structure: GstStructureLike) -> float | None:
        """Extract peak RMS value across all channels.

        For multi-channel audio, returns the maximum (loudest) RMS value
        across all channels. This ensures speech in any channel prevents
        segment boundary detection.

        Args:
            structure: GStreamer message structure from level element

        Returns:
            Peak RMS value in dB, or None if extraction fails
        """
        try:
            success, value_array = structure.get_array("rms")
            if not success or value_array is None:
                return None

            if value_array.n_values == 0:
                return None

            rms_values = []
            for i in range(value_array.n_values):
                gvalue = value_array.get_nth(i)
                if gvalue is not None:
                    rms_values.append(gvalue.get_double())

            if not rms_values:
                return None

            return float(max(rms_values))

        except Exception as e:
            logger.warning(f"Failed to extract RMS from level message: {e}")
            return None

    @staticmethod
    def extract_timestamp_ns(structure: GstStructureLike) -> int:
        """Extract running time timestamp from level message.

        Args:
            structure: GStreamer message structure

        Returns:
            Running time in nanoseconds, or 0 if not available
        """
        try:
            success, value = structure.get_uint64("running-time")
            if success:
                return value
            return 0

        except Exception as e:
            logger.warning(f"Failed to extract timestamp from level message: {e}")
            return 0

    @staticmethod
    def is_level_message(message: GstMessageLike) -> bool:
        """Check if message is from level element.

        Args:
            message: GStreamer bus message

        Returns:
            True if message is a level measurement
        """
        try:
            # Check message type is ELEMENT
            if message.type != GST_MESSAGE_TYPE_ELEMENT:
                return False

            structure = message.get_structure()
            if structure is None:
                return False

            return bool(structure.get_name() == "level")

        except Exception as e:
            logger.warning(f"Failed to check level message type: {e}")
            return False
