"""
Unit tests for LevelMessageExtractor.

Tests MUST be written FIRST per Constitution Principle VIII.
These tests verify GStreamer level message parsing without GStreamer installed.

Per spec 023-vad-audio-segmentation:
- Extract peak RMS from multi-channel audio
- Extract running-time timestamp
- Detect level messages by type
- Handle invalid/malformed messages gracefully
"""

from __future__ import annotations

from unittest.mock import MagicMock


class MockGValueArray:
    """Mock GStreamer GValueArray for testing."""

    def __init__(self, values: list[float]):
        self._values = values
        self.n_values = len(values)

    def get_nth(self, index: int) -> MagicMock | None:
        if 0 <= index < len(self._values):
            gvalue = MagicMock()
            gvalue.get_double.return_value = self._values[index]
            return gvalue
        return None


class MockStructure:
    """Mock GStreamer Structure for testing."""

    def __init__(
        self,
        name: str = "level",
        rms: list[float] | None = None,
        running_time: int = 0,
        has_rms: bool = True,
        has_running_time: bool = True,
    ):
        self._name = name
        self._rms = rms or []
        self._running_time = running_time
        self._has_rms = has_rms
        self._has_running_time = has_running_time

    def get_name(self) -> str:
        return self._name

    def get_array(self, field: str) -> tuple[bool, MockGValueArray | None]:
        if field == "rms" and self._has_rms:
            return (True, MockGValueArray(self._rms))
        return (False, None)

    def get_uint64(self, field: str) -> tuple[bool, int]:
        if field == "running-time" and self._has_running_time:
            return (True, self._running_time)
        return (False, 0)


class MockMessage:
    """Mock GStreamer Message for testing."""

    def __init__(
        self,
        msg_type: int = 0,  # Use int instead of Gst.MessageType
        structure: MockStructure | None = None,
    ):
        self.type = msg_type
        self._structure = structure

    def get_structure(self) -> MockStructure | None:
        return self._structure


# Mock Gst.MessageType values for testing
class MockMessageType:
    ELEMENT = 16  # Gst.MessageType.ELEMENT value
    EOS = 1
    ERROR = 2
    WARNING = 4


class TestLevelMessageExtractorPeakRMS:
    """Tests for extract_peak_rms_db method."""

    def test_extract_peak_rms_single_channel(self):
        """Verify peak RMS extraction from single channel audio."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(rms=[-45.0])
        result = LevelMessageExtractor.extract_peak_rms_db(structure)

        assert result == -45.0

    def test_extract_peak_rms_stereo_returns_max(self):
        """Verify peak RMS is maximum across stereo channels."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(rms=[-45.0, -42.0])  # Right channel is louder
        result = LevelMessageExtractor.extract_peak_rms_db(structure)

        assert result == -42.0  # Max of channels

    def test_extract_peak_rms_multi_channel_returns_max(self):
        """Verify peak RMS is maximum across 6-channel audio."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(rms=[-50.0, -45.0, -60.0, -55.0, -40.0, -48.0])
        result = LevelMessageExtractor.extract_peak_rms_db(structure)

        assert result == -40.0  # Max of all channels

    def test_extract_peak_rms_empty_array_returns_none(self):
        """Verify empty RMS array returns None."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(rms=[])
        result = LevelMessageExtractor.extract_peak_rms_db(structure)

        assert result is None

    def test_extract_peak_rms_missing_field_returns_none(self):
        """Verify missing RMS field returns None."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(has_rms=False)
        result = LevelMessageExtractor.extract_peak_rms_db(structure)

        assert result is None

    def test_extract_peak_rms_all_negative_values(self):
        """Verify negative RMS values (typical for dB) are handled correctly."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(rms=[-80.0, -75.0, -90.0])
        result = LevelMessageExtractor.extract_peak_rms_db(structure)

        assert result == -75.0  # Max (least negative = loudest)

    def test_extract_peak_rms_zero_value(self):
        """Verify 0 dB (maximum level) is handled correctly."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(rms=[-10.0, 0.0])  # 0 dB = max level
        result = LevelMessageExtractor.extract_peak_rms_db(structure)

        assert result == 0.0


class TestLevelMessageExtractorTimestamp:
    """Tests for extract_timestamp_ns method."""

    def test_extract_timestamp_ns_valid(self):
        """Verify running-time timestamp extraction."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(running_time=5_000_000_000)  # 5 seconds
        result = LevelMessageExtractor.extract_timestamp_ns(structure)

        assert result == 5_000_000_000

    def test_extract_timestamp_ns_zero(self):
        """Verify zero timestamp is returned correctly."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(running_time=0)
        result = LevelMessageExtractor.extract_timestamp_ns(structure)

        assert result == 0

    def test_extract_timestamp_ns_large_value(self):
        """Verify large timestamp (long stream) is handled."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        # 24 hours in nanoseconds
        timestamp = 24 * 60 * 60 * 1_000_000_000
        structure = MockStructure(running_time=timestamp)
        result = LevelMessageExtractor.extract_timestamp_ns(structure)

        assert result == timestamp

    def test_extract_timestamp_ns_missing_field_returns_zero(self):
        """Verify missing running-time returns 0."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(has_running_time=False)
        result = LevelMessageExtractor.extract_timestamp_ns(structure)

        assert result == 0


class TestLevelMessageExtractorIsLevelMessage:
    """Tests for is_level_message method."""

    def test_is_level_message_true_for_level(self):
        """Verify level messages are correctly identified."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(name="level")
        message = MockMessage(msg_type=MockMessageType.ELEMENT, structure=structure)

        result = LevelMessageExtractor.is_level_message(message)

        assert result is True

    def test_is_level_message_false_for_non_element(self):
        """Verify non-ELEMENT messages return False."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(name="level")
        message = MockMessage(msg_type=MockMessageType.EOS, structure=structure)

        result = LevelMessageExtractor.is_level_message(message)

        assert result is False

    def test_is_level_message_false_for_non_level_structure(self):
        """Verify non-level structures return False."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(name="video-info")
        message = MockMessage(msg_type=MockMessageType.ELEMENT, structure=structure)

        result = LevelMessageExtractor.is_level_message(message)

        assert result is False

    def test_is_level_message_false_for_null_structure(self):
        """Verify null structure returns False."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        message = MockMessage(msg_type=MockMessageType.ELEMENT, structure=None)

        result = LevelMessageExtractor.is_level_message(message)

        assert result is False

    def test_is_level_message_false_for_error_message(self):
        """Verify ERROR messages return False."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        message = MockMessage(msg_type=MockMessageType.ERROR, structure=None)

        result = LevelMessageExtractor.is_level_message(message)

        assert result is False


class TestLevelMessageExtractorEdgeCases:
    """Tests for edge cases and error handling."""

    def test_extract_peak_rms_with_single_very_low_value(self):
        """Verify very quiet audio (-100dB) is handled."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(rms=[-100.0])
        result = LevelMessageExtractor.extract_peak_rms_db(structure)

        assert result == -100.0

    def test_extract_peak_rms_with_typical_speech(self):
        """Verify typical speech levels (-30 to -40 dB) are handled."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(rms=[-35.0, -38.0])
        result = LevelMessageExtractor.extract_peak_rms_db(structure)

        assert result == -35.0

    def test_extract_peak_rms_with_typical_silence(self):
        """Verify typical silence levels (-60 to -80 dB) are handled."""
        from media_service.vad.level_message_extractor import LevelMessageExtractor

        structure = MockStructure(rms=[-65.0, -70.0])
        result = LevelMessageExtractor.extract_peak_rms_db(structure)

        assert result == -65.0
