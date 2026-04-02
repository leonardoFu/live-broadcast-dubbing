"""
Unit tests for VADAudioSegmenter.

Tests MUST be written FIRST per Constitution Principle VIII.
This is the core VAD state machine - coverage target 95%.

Per spec 023-vad-audio-segmentation:
- US1: Silence boundary detection triggers segment emission
- US2: Maximum duration forces segment emission
- US3: Minimum duration buffers short segments
- US6: EOS flush handling
- RMS validation with fatal error on 10+ consecutive invalid
"""

from __future__ import annotations

import pytest

# =============================================================================
# US1: VAD-Based Silence Detection Emits Segments
# =============================================================================


class TestVADAudioSegmenterSilenceDetection:
    """Tests for US1: Silence boundary detection triggers segment emission."""

    def test_silence_boundary_emits_segment(self):
        """Verify 1 second of silence triggers segment emission."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # Accumulate 2 seconds of audio
        segmenter.on_audio_buffer(b"audio1", pts_ns=0, duration_ns=1_000_000_000)
        segmenter.on_audio_buffer(b"audio2", pts_ns=1_000_000_000, duration_ns=1_000_000_000)

        # Simulate silence for 1 second (10 level messages at 100ms intervals)
        for i in range(11):
            segmenter.on_level_message(rms_db=-60.0, timestamp_ns=2_000_000_000 + i * 100_000_000)

        assert len(segments_emitted) == 1
        assert segments_emitted[0][0] == b"audio1audio2"
        assert segments_emitted[0][1] == 0  # t0_ns
        assert segments_emitted[0][2] == 2_000_000_000  # duration_ns
        assert segmenter.silence_detections == 1

    def test_speech_resets_silence_tracking(self):
        """Verify speech after brief silence resets silence duration."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # Accumulate audio
        segmenter.on_audio_buffer(b"audio", pts_ns=0, duration_ns=2_000_000_000)

        # Silence for 0.5s (5 messages)
        for i in range(5):
            segmenter.on_level_message(rms_db=-60.0, timestamp_ns=i * 100_000_000)

        # Speech resumes
        segmenter.on_level_message(rms_db=-30.0, timestamp_ns=500_000_000)

        # More silence for 0.5s
        for i in range(5):
            segmenter.on_level_message(rms_db=-60.0, timestamp_ns=600_000_000 + i * 100_000_000)

        # No emission - silence duration was reset
        assert len(segments_emitted) == 0

    def test_accumulator_captures_first_buffer_pts(self):
        """Verify t0_ns is captured from first buffer."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # First buffer at PTS=5s
        segmenter.on_audio_buffer(b"first", pts_ns=5_000_000_000, duration_ns=1_000_000_000)
        segmenter.on_audio_buffer(b"second", pts_ns=6_000_000_000, duration_ns=1_000_000_000)

        # Trigger silence emission
        for i in range(11):
            segmenter.on_level_message(rms_db=-60.0, timestamp_ns=7_000_000_000 + i * 100_000_000)

        assert len(segments_emitted) == 1
        assert segments_emitted[0][1] == 5_000_000_000  # t0_ns from first buffer

    def test_empty_accumulator_does_not_emit(self):
        """Verify empty accumulator doesn't emit segments."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # No audio accumulated, just silence
        for i in range(20):
            segmenter.on_level_message(rms_db=-60.0, timestamp_ns=i * 100_000_000)

        assert len(segments_emitted) == 0

    def test_state_transitions_accumulating_to_in_silence(self):
        """Verify state transition from ACCUMULATING to IN_SILENCE."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter, VADState

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        assert segmenter._state == VADState.ACCUMULATING

        # Trigger silence
        segmenter.on_level_message(rms_db=-60.0, timestamp_ns=0)

        assert segmenter._state == VADState.IN_SILENCE

    def test_state_resets_after_emission(self):
        """Verify state resets to ACCUMULATING after segment emission."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter, VADState

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        # Accumulate audio
        segmenter.on_audio_buffer(b"audio", pts_ns=0, duration_ns=2_000_000_000)

        # Trigger emission
        for i in range(11):
            segmenter.on_level_message(rms_db=-60.0, timestamp_ns=i * 100_000_000)

        # State should reset
        assert segmenter._state == VADState.ACCUMULATING
        assert len(segmenter._accumulator) == 0


# =============================================================================
# US2: Maximum Duration Forces Segment Emission
# =============================================================================


class TestVADAudioSegmenterMaxDuration:
    """Tests for US2: Maximum duration forces segment emission."""

    def test_max_duration_forces_emission(self):
        """Verify segment is emitted at max duration regardless of silence."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig(max_segment_duration_s=15.0)
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # Accumulate exactly 15 seconds of audio (continuous speech)
        for i in range(15):
            segmenter.on_audio_buffer(
                data=b"x" * 1000,
                pts_ns=i * 1_000_000_000,
                duration_ns=1_000_000_000,
            )
            # Send speech level (above threshold)
            segmenter.on_level_message(rms_db=-30.0, timestamp_ns=i * 1_000_000_000)

        assert len(segments_emitted) == 1
        assert segmenter.forced_emissions == 1

    def test_max_duration_counter_incremented(self):
        """Verify forced_emissions counter increments."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        config = SegmentationConfig(max_segment_duration_s=5.0)
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        # Accumulate 10 seconds in two batches
        for i in range(5):
            segmenter.on_audio_buffer(
                data=b"x" * 1000,
                pts_ns=i * 1_000_000_000,
                duration_ns=1_000_000_000,
            )
        # First forced emission

        for i in range(5, 10):
            segmenter.on_audio_buffer(
                data=b"x" * 1000,
                pts_ns=i * 1_000_000_000,
                duration_ns=1_000_000_000,
            )
        # Second forced emission

        assert segmenter.forced_emissions == 2

    def test_accumulator_resets_after_forced_emission(self):
        """Verify accumulator resets after forced emission."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        config = SegmentationConfig(max_segment_duration_s=5.0)
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        # Accumulate 5 seconds to trigger forced emission
        for i in range(5):
            segmenter.on_audio_buffer(
                data=b"x" * 1000,
                pts_ns=i * 1_000_000_000,
                duration_ns=1_000_000_000,
            )

        # Accumulator should be empty
        assert len(segmenter._accumulator) == 0
        assert segmenter._duration_ns == 0

    def test_no_segments_exceed_max_duration(self):
        """Verify no segments exceed maximum duration."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig(max_segment_duration_s=10.0)
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # Accumulate 30 seconds of continuous speech
        for i in range(30):
            segmenter.on_audio_buffer(
                data=b"x" * 1000,
                pts_ns=i * 1_000_000_000,
                duration_ns=1_000_000_000,
            )

        # All emitted segments should be <= 10s
        for segment in segments_emitted:
            assert segment[2] <= 10_000_000_000


class TestVADAudioSegmenterMemoryLimit:
    """Tests for US2: Memory limit enforcement."""

    def test_memory_limit_forces_emission(self):
        """Verify segment is emitted when memory limit reached."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        # Small memory limit for testing (1MB)
        config = SegmentationConfig(memory_limit_bytes=1_048_576)
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # Accumulate more than 1MB (each buffer is 100KB)
        for i in range(15):
            segmenter.on_audio_buffer(
                data=b"x" * 100_000,
                pts_ns=i * 100_000_000,
                duration_ns=100_000_000,
            )

        # Should have emitted at least once due to memory limit
        assert len(segments_emitted) >= 1
        assert segmenter.memory_limit_emissions >= 1

    def test_memory_limit_counter_incremented(self):
        """Verify memory_limit_emissions counter increments."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        # Use minimum valid memory limit (1MB)
        config = SegmentationConfig(memory_limit_bytes=1_048_576)  # 1MB
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        # Accumulate 2MB in 200KB chunks
        for i in range(10):
            segmenter.on_audio_buffer(
                data=b"x" * 200_000,
                pts_ns=i * 100_000_000,
                duration_ns=100_000_000,
            )

        assert segmenter.memory_limit_emissions >= 1


# =============================================================================
# US3: Minimum Duration Buffers Short Segments
# =============================================================================


class TestVADAudioSegmenterMinDuration:
    """Tests for US3: Minimum duration buffers short segments."""

    def test_min_duration_buffers_segment(self):
        """Verify segments under 1 second are not emitted."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig()  # Default min is 1.0s
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # Accumulate only 0.5 seconds
        segmenter.on_audio_buffer(b"short", pts_ns=0, duration_ns=500_000_000)

        # Trigger silence
        for i in range(11):
            segmenter.on_level_message(rms_db=-60.0, timestamp_ns=500_000_000 + i * 100_000_000)

        assert len(segments_emitted) == 0  # Not emitted
        assert segmenter.min_duration_violations == 1

    def test_short_audio_remains_in_accumulator(self):
        """Verify short audio stays in accumulator after silence boundary."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        # Accumulate 0.5 seconds
        segmenter.on_audio_buffer(b"short", pts_ns=0, duration_ns=500_000_000)

        # Trigger silence (not emitted due to min duration)
        for i in range(11):
            segmenter.on_level_message(rms_db=-60.0, timestamp_ns=i * 100_000_000)

        # Audio still in accumulator
        assert len(segmenter._accumulator) == 5  # "short" is 5 bytes

    def test_new_audio_appends_to_buffered_short_segment(self):
        """Verify new audio appends to existing buffered short segment."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # Accumulate 0.5 seconds
        segmenter.on_audio_buffer(b"first", pts_ns=0, duration_ns=500_000_000)

        # Trigger silence (not emitted due to min duration)
        for i in range(11):
            segmenter.on_level_message(rms_db=-60.0, timestamp_ns=i * 100_000_000)

        # Speech resumes, add more audio
        segmenter.on_level_message(rms_db=-30.0, timestamp_ns=1_100_000_000)
        segmenter.on_audio_buffer(b"second", pts_ns=1_100_000_000, duration_ns=700_000_000)

        # Now trigger silence again - total is 1.2s, above min
        for i in range(11):
            segmenter.on_level_message(rms_db=-60.0, timestamp_ns=1_800_000_000 + i * 100_000_000)

        # Now it should emit both buffers combined
        assert len(segments_emitted) == 1
        assert segments_emitted[0][0] == b"firstsecond"

    def test_min_duration_violation_counter_incremented(self):
        """Verify min_duration_violations counter increments."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        # Multiple short segments
        for _ in range(3):
            segmenter.on_audio_buffer(b"x", pts_ns=0, duration_ns=100_000_000)  # 0.1s
            for i in range(11):
                segmenter.on_level_message(rms_db=-60.0, timestamp_ns=i * 100_000_000)
            # Speech resumes
            segmenter.on_level_message(rms_db=-30.0, timestamp_ns=1_100_000_000)

        assert segmenter.min_duration_violations == 3


# =============================================================================
# US6: End-of-Stream Flush Handling
# =============================================================================


class TestVADAudioSegmenterEOSFlush:
    """Tests for US6: EOS flush handling."""

    def test_flush_emits_segment_above_minimum(self):
        """Verify flush() emits segment when duration >= minimum."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # Accumulate 3 seconds (above minimum)
        segmenter.on_audio_buffer(b"audio", pts_ns=0, duration_ns=3_000_000_000)

        segmenter.flush()

        assert len(segments_emitted) == 1
        assert segments_emitted[0][2] == 3_000_000_000

    def test_flush_discards_segment_below_minimum(self):
        """Verify flush() discards segment when duration < minimum."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # Accumulate only 0.5 seconds
        segmenter.on_audio_buffer(b"short", pts_ns=0, duration_ns=500_000_000)

        segmenter.flush()

        assert len(segments_emitted) == 0  # Discarded

    def test_flush_with_empty_accumulator(self):
        """Verify flush() with empty accumulator doesn't error."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # No audio accumulated
        segmenter.flush()

        assert len(segments_emitted) == 0

    def test_flush_resets_state(self):
        """Verify flush() resets state after emission."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter, VADState

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        segmenter.on_audio_buffer(b"audio", pts_ns=0, duration_ns=2_000_000_000)
        segmenter.flush()

        assert segmenter._state == VADState.ACCUMULATING
        assert len(segmenter._accumulator) == 0
        assert segmenter._duration_ns == 0


# =============================================================================
# RMS Validation
# =============================================================================


class TestVADAudioSegmenterRMSValidation:
    """Tests for RMS validation with warnings and fatal error."""

    def test_invalid_rms_treated_as_speech(self):
        """Verify invalid RMS values are treated as speech (no boundary)."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        segments_emitted: list[tuple[bytes, int, int, str]] = []

        def on_segment(data: bytes, t0_ns: int, duration_ns: int, trigger: str) -> None:
            segments_emitted.append((data, t0_ns, duration_ns, trigger))

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=on_segment)

        # Accumulate audio
        segmenter.on_audio_buffer(b"audio", pts_ns=0, duration_ns=2_000_000_000)

        # Send invalid RMS (> 0 dB)
        segmenter.on_level_message(rms_db=10.0, timestamp_ns=0)

        # Should NOT emit (invalid treated as speech)
        assert len(segments_emitted) == 0

    def test_invalid_rms_above_zero_tracked(self):
        """Verify invalid RMS > 0 dB is tracked."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        # Send invalid RMS
        segmenter.on_level_message(rms_db=5.0, timestamp_ns=0)

        assert segmenter._consecutive_invalid_rms == 1

    def test_invalid_rms_below_minus_hundred_tracked(self):
        """Verify invalid RMS < -100 dB is tracked."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        # Send invalid RMS
        segmenter.on_level_message(rms_db=-150.0, timestamp_ns=0)

        assert segmenter._consecutive_invalid_rms == 1

    def test_valid_rms_resets_invalid_counter(self):
        """Verify first valid RMS resets invalid counter."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        # Send 5 invalid RMS values
        for i in range(5):
            segmenter.on_level_message(rms_db=10.0, timestamp_ns=i * 100_000_000)

        assert segmenter._consecutive_invalid_rms == 5

        # Send valid RMS
        segmenter.on_level_message(rms_db=-45.0, timestamp_ns=500_000_000)

        assert segmenter._consecutive_invalid_rms == 0

    def test_consecutive_invalid_rms_raises_error(self):
        """Verify 10+ consecutive invalid RMS values raises RuntimeError."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        # Send 10 invalid RMS values
        with pytest.raises(RuntimeError, match="Pipeline malfunction"):
            for i in range(10):
                segmenter.on_level_message(rms_db=10.0, timestamp_ns=i * 100_000_000)


# =============================================================================
# Metrics Accessors
# =============================================================================


class TestVADAudioSegmenterMetrics:
    """Tests for metrics accessor properties."""

    def test_accumulated_duration_ns(self):
        """Verify accumulated_duration_ns property."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        assert segmenter.accumulated_duration_ns == 0

        segmenter.on_audio_buffer(b"audio", pts_ns=0, duration_ns=2_000_000_000)

        assert segmenter.accumulated_duration_ns == 2_000_000_000

    def test_accumulated_bytes(self):
        """Verify accumulated_bytes property."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        assert segmenter.accumulated_bytes == 0

        segmenter.on_audio_buffer(b"audiodata", pts_ns=0, duration_ns=1_000_000_000)

        assert segmenter.accumulated_bytes == 9  # "audiodata" is 9 bytes

    def test_silence_detections_counter(self):
        """Verify silence_detections counter."""
        from media_service.config.segmentation_config import SegmentationConfig
        from media_service.vad.vad_audio_segmenter import VADAudioSegmenter

        config = SegmentationConfig()
        segmenter = VADAudioSegmenter(config=config, on_segment_ready=lambda *args: None)

        assert segmenter.silence_detections == 0

        # Accumulate audio and trigger silence emission
        segmenter.on_audio_buffer(b"audio", pts_ns=0, duration_ns=2_000_000_000)
        for i in range(11):
            segmenter.on_level_message(rms_db=-60.0, timestamp_ns=i * 100_000_000)

        assert segmenter.silence_detections == 1
