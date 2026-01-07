# Feature Specification: Dynamic VAD-Based Audio Segmentation

**Feature Branch**: `022-vad-audio-segmentation`
**Created**: 2026-01-06
**Status**: Draft
**Input**: User description: "Dynamic VAD-Based Audio Segmentation - Replace fixed 6-second audio fragment approach with Voice Activity Detection using GStreamer level element"

## Overview

This specification defines a Voice Activity Detection (VAD) system for the media service to replace the current fixed 6-second audio segmentation approach with intelligent, speech-aware segmentation. The system will use GStreamer's native `level` element to detect silence boundaries in real-time, breaking audio into complete speaking segments (full sentences/phrases) rather than arbitrary time-based chunks.

The current implementation accumulates audio into fixed 6-second segments regardless of speech content, which can split words or sentences mid-phrase, degrading translation quality and user experience. VAD-based segmentation will detect natural speech boundaries (1-second silence threshold) to create segments that align with how humans speak, improving translation accuracy and maintaining A/V synchronization.

**Current Behavior**:
- Fixed 6-second segments (`DEFAULT_SEGMENT_DURATION_NS = 6_000_000_000`)
- Segments split arbitrarily regardless of speech content
- Located in `apps/media-service/src/media_service/buffer/segment_buffer.py`

**New Behavior**:
- Dynamic segments based on speech boundaries (1-second silence detection)
- Complete sentences/phrases sent to STS service
- Min/max duration guards (1s minimum, 15s maximum) to handle edge cases

**Related Specs**:
- [specs/003-gstreamer-stream-worker](../003-gstreamer-stream-worker/spec.md) - GStreamer pipeline implementation
- [specs/017-echo-sts-service](../017-echo-sts-service/spec.md) - STS service fragment protocol
- [specs/018-e2e-stream-handler-tests](../018-e2e-stream-handler-tests/spec.md) - E2E testing framework

## User Scenarios & Testing

### User Story 1 - Natural Speech Segmentation: Detect Silence Boundaries (Priority: P1)

A dubbing operator streams live broadcast content through the media service. The system detects when speakers pause (1-second silence), emits audio segments at natural speech boundaries, and sends complete sentences to the STS service for translation and dubbing.

**Why this priority**: This is the core value proposition of the feature. Natural speech segmentation is essential for translation quality and user experience. Without speech-aware boundaries, translations will be poor quality and the entire dubbing pipeline is compromised.

**Independent Test**: This can be tested with synthetic audio containing known silence patterns.
- **Unit test**: `test_vad_detector_silence_threshold()` validates RMS level drops below threshold for 1 second triggers segment boundary
- **Contract test**: Verify variable-length audio fragments still conform to STS fragment:data schema (AudioData model)
- **Integration test**: `test_vad_segments_natural_speech()` validates full pipeline with test audio containing speech + 1s silence + speech pattern
- **Success criteria**: Segments emitted within 100ms of silence boundary detection, RMS threshold accuracy >95%, all segments contain complete phrases without mid-word cuts

**Acceptance Scenarios**:

1. **Given** audio stream with speaker talking for 3 seconds, **When** speaker pauses for 1 second, **Then** system emits 3-second segment at silence boundary
2. **Given** audio stream with RMS levels above threshold, **When** RMS drops below threshold for exactly 1 second, **Then** segment boundary is detected and accumulated audio is emitted
3. **Given** continuous speech with no pauses, **When** 15 seconds elapse (max duration), **Then** segment is forcibly emitted to prevent unbounded accumulation
4. **Given** brief background noise or mouth clicks causing momentary silence (<1s), **When** RMS drops below threshold for 0.5 seconds, **Then** no segment boundary is triggered (must be 1 full second)
5. **Given** audio segment emitted at silence boundary, **When** segment is sent to STS service, **Then** segment duration is variable (1-15s range) and conforms to fragment:data schema

---

### User Story 2 - Minimum Duration Guard: Prevent Tiny Fragments (Priority: P1)

The system enforces a minimum segment duration (1 second) to prevent sending tiny audio fragments that are too short for meaningful translation. If a segment would be shorter than 1 second, it is either buffered until the next speech or discarded if it contains no meaningful content.

**Why this priority**: Short fragments (< 1s) cause processing overhead, poor translation quality, and inefficient STS resource utilization. This guard is essential for production stability and translation quality.

**Independent Test**: Test with rapid speech patterns and short utterances.
- **Unit test**: `test_vad_min_duration_guard()` validates segments shorter than 1s are not emitted until next speech appended
- **Contract test**: Verify all emitted fragments have `duration_ms >= 1000` in AudioData payload
- **Integration test**: `test_vad_prevents_short_fragments()` validates no sub-1s fragments reach STS service
- **Success criteria**: Zero segments < 1s sent to STS, short utterances are accumulated until minimum threshold reached, metrics show min_duration_violations=0

**Acceptance Scenarios**:

1. **Given** speaker says brief word (0.5s), **When** silence boundary detected, **Then** audio is held in buffer and not emitted as segment
2. **Given** 0.5s audio buffered from previous utterance, **When** speaker says another word (0.8s), **Then** accumulated 1.3s audio is emitted as single segment at next silence boundary
3. **Given** stream ending with 0.7s partial audio buffered, **When** EOS (end of stream) signal received, **Then** partial segment is discarded per existing MIN_PARTIAL_DURATION_NS logic
4. **Given** audio buffered for 14s without silence, **When** another 0.5s of speech arrives reaching 14.5s, **Then** segment is forcibly emitted at 15s max duration even without silence boundary

---

### User Story 3 - Maximum Duration Guard: Prevent Unbounded Segments (Priority: P1)

The system enforces a maximum segment duration (15 seconds) to handle edge cases like continuous speech, background noise, or streams without natural pauses. When accumulated audio reaches 15 seconds without detecting a silence boundary, the segment is forcibly emitted.

**Why this priority**: Without a maximum duration, the system could accumulate unbounded audio during continuous speech or noisy environments, causing memory exhaustion, processing delays, and STS timeouts. This guard is critical for production resilience.

**Independent Test**: Test with continuous speech audio longer than 15 seconds without pauses.
- **Unit test**: `test_vad_max_duration_guard()` validates segments forcibly emitted at 15s regardless of silence detection
- **Contract test**: Verify forced segments still conform to AudioData schema with valid duration_ms
- **Integration test**: `test_vad_handles_continuous_speech()` validates pipeline stability with 30s continuous speech stream
- **Success criteria**: No segment exceeds 15s duration, forced emission occurs within 100ms of 15s threshold, metrics show max_duration_forced_emissions count

**Acceptance Scenarios**:

1. **Given** speaker talking continuously for 20 seconds without pausing, **When** 15 seconds of audio accumulated, **Then** segment is forcibly emitted even without silence boundary
2. **Given** forced emission at 15s, **When** speaker continues talking, **Then** new segment starts accumulating immediately from the continuation point
3. **Given** background music or ambient noise stream with no clear speech, **When** RMS stays above silence threshold continuously, **Then** segments are emitted every 15s to prevent unbounded accumulation
4. **Given** segment forcibly emitted at max duration, **When** metrics endpoint is queried, **Then** `vad_forced_emissions_total` counter increments and segment duration is exactly 15000ms

---

### User Story 4 - Configurable Silence Threshold: Tune for Different Content (Priority: P2)

Operators can configure the silence detection RMS threshold (dB level) and silence duration (default 1 second) to optimize segmentation for different audio content types (studio speech, live broadcast, noisy environments, multiple speakers).

**Why this priority**: Different audio sources have varying noise floors and speaking styles. Studio recordings may have -60dB silence, while live broadcasts might have -40dB ambient noise. Configurable thresholds allow optimization for specific use cases without code changes.

**Independent Test**: Test with various RMS thresholds and validate detection accuracy.
- **Unit test**: `test_vad_configurable_threshold()` validates threshold parameter is respected; `test_vad_configurable_duration()` validates silence duration parameter
- **Contract test**: N/A (internal configuration, no contract impact)
- **Integration test**: `test_vad_threshold_tuning()` validates different thresholds produce different segmentation patterns on same audio
- **Success criteria**: Threshold configurable via environment variable or config file, default -40dB for broadcast audio, documented tuning guide for common scenarios

**Acceptance Scenarios**:

1. **Given** operator sets `VAD_SILENCE_THRESHOLD_DB=-50`, **When** audio RMS drops below -50dB for 1 second, **Then** segment boundary is detected
2. **Given** operator sets `VAD_SILENCE_DURATION_MS=1500`, **When** audio RMS drops below threshold for 1.5 seconds, **Then** segment boundary is detected
3. **Given** noisy live broadcast with -35dB ambient noise floor, **When** operator configures threshold=-30dB, **Then** system only detects speaker pauses (not background noise) as silence boundaries
4. **Given** studio recording with -65dB noise floor, **When** operator uses default threshold=-40dB, **Then** all natural speech pauses are detected correctly without false positives

---

### User Story 5 - A/V Sync Preservation: Maintain Synchronization with Variable Segments (Priority: P1)

The system maintains A/V synchronization with variable-length audio segments by tracking precise PTS (presentation timestamps) and duration for each segment. Video segments remain fixed at 6 seconds while audio segments are variable, requiring careful timestamp management.

**Why this priority**: A/V sync is critical for dubbing quality. If variable audio segments break timestamp tracking, the entire pipeline fails. This must work correctly from day one or the feature is unusable.

**Independent Test**: Test with variable-length audio and fixed video segments, verify PTS alignment.
- **Unit test**: `test_vad_preserves_pts_tracking()` validates PTS captured correctly for variable segments; `test_audio_segment_metadata()` validates duration_ns matches actual accumulated duration
- **Contract test**: Verify AudioSegment model includes correct t0_ns and duration_ns for variable-length segments
- **Integration test**: `test_av_sync_with_vad_segments()` validates full pipeline maintains sync delta <120ms with variable audio segments
- **Success criteria**: A/V sync delta remains <120ms for 95% of segments, PTS tracking accuracy within 1ms, no sync drift over 5-minute streams

**Acceptance Scenarios**:

1. **Given** audio segment of variable length (3.2s) emitted at silence boundary, **When** segment metadata created, **Then** t0_ns reflects first buffer PTS and duration_ns reflects accumulated 3.2s duration exactly
2. **Given** video segments at fixed 6s intervals and audio segments at variable intervals, **When** A/V sync manager pairs segments, **Then** sync delta calculated correctly using variable audio duration
3. **Given** forced audio segment emission at 15s max duration mid-phrase, **When** next audio segment starts, **Then** PTS continues from exact end point of previous segment with no gap or overlap
4. **Given** full pipeline processing 5-minute stream with VAD segmentation, **When** output analyzed, **Then** cumulative A/V sync drift is <500ms total (no accumulating error)

---

### User Story 6 - Fallback to Fixed Duration: Graceful Degradation (Priority: P2)

If VAD processing encounters errors (GStreamer element fails, audio format incompatible, or excessive latency), the system automatically falls back to the original fixed 6-second segmentation to maintain pipeline stability.

**Why this priority**: Production resilience requires graceful degradation. If VAD fails, the pipeline should continue operating with reduced quality (fixed segments) rather than complete failure. This is important for reliability but not as critical as core VAD functionality.

**Independent Test**: Simulate VAD failures and verify fallback behavior.
- **Unit test**: `test_vad_fallback_on_element_error()` validates fallback to fixed duration when GStreamer level element fails
- **Contract test**: Verify fallback segments still conform to AudioData schema (6s fixed duration)
- **Integration test**: `test_vad_graceful_degradation()` validates full pipeline continues operating after VAD failure
- **Success criteria**: Fallback triggered within 1 second of VAD error detection, metrics show vad_fallback_total counter, pipeline continues without interruption, operators alerted via logs

**Acceptance Scenarios**:

1. **Given** VAD processing enabled, **When** GStreamer level element initialization fails, **Then** system logs error, increments vad_fallback_total metric, and switches to fixed 6s segmentation
2. **Given** VAD processing running normally, **When** level element reports critical error during runtime, **Then** system switches to fallback mode mid-stream without dropping segments
3. **Given** audio format incompatible with level element (e.g., unsupported sample rate), **When** incompatibility detected, **Then** system falls back to fixed segmentation and logs warning with audio format details
4. **Given** system operating in fallback mode, **When** metrics endpoint queried, **Then** vad_enabled gauge shows 0 (disabled), vad_fallback_total shows failure count, segments continue at fixed 6s intervals

---

### Edge Cases

- **Rapid speakers with short pauses (<1s)**: System may not detect pauses shorter than 1s threshold, treating rapid speech as continuous. Will trigger max duration guard at 15s. Configurable silence duration allows tuning for fast speakers (reduce to 0.5s).
- **Background noise masking silence**: Noisy environments may prevent RMS from dropping below threshold. Configurable threshold allows tuning for noisy content. Max duration guard prevents unbounded accumulation.
- **Multiple speakers with overlapping speech**: Simultaneous speakers may never drop below silence threshold. Max duration guard forcibly emits segments. Post-processing could detect speaker changes via additional signal processing (future enhancement).
- **Music or non-speech audio**: Instrumental passages may never trigger silence detection. Max duration guard ensures segments are still emitted every 15s. Operators may disable VAD for music-only streams via configuration.
- **Sudden stream termination**: If stream ends mid-phrase with buffered audio <1s, existing MIN_PARTIAL_DURATION_NS logic discards short partials. If >1s buffered, emitted as partial segment per existing flush logic.
- **GStreamer level element not available**: System checks for level element availability during initialization. If unavailable, falls back to fixed segmentation with warning log. Operators must install gst-plugins-base for VAD support.
- **Extremely long sentences (>15s)**: Segment forcibly emitted at 15s max duration even if mid-sentence. Translation quality may degrade for incomplete sentences. Operators can increase max duration via configuration if needed for specific content.
- **Silence during EOS flush**: If stream ends with 1.5s audio followed by 0.5s silence, system flushes 1.5s segment (meets 1s minimum). Silence portion is discarded (not sent to STS).

## Requirements

### Functional Requirements

#### VAD Core Functionality

- **FR-001**: System MUST use GStreamer `level` element to monitor real-time audio RMS (Root Mean Square) levels in the pipeline
- **FR-002**: System MUST detect silence boundaries when audio RMS level drops below a configurable threshold (default -40dB) for a configurable duration (default 1 second)
- **FR-003**: System MUST emit accumulated audio as a segment when a silence boundary is detected (1 second of audio below threshold)
- **FR-004**: System MUST track audio buffer PTS (presentation timestamp) and duration with nanosecond precision for variable-length segments
- **FR-005**: System MUST replace the existing fixed `segment_duration_ns` logic in `SegmentBuffer` with VAD-based dynamic segmentation

#### Duration Guards

- **FR-006**: System MUST enforce a minimum segment duration of 1 second (1_000_000_000 nanoseconds) - segments shorter than 1s are buffered until next speech or discarded at EOS
- **FR-007**: System MUST enforce a maximum segment duration of 15 seconds (15_000_000_000 nanoseconds) - segments are forcibly emitted at 15s even without detecting silence boundary
- **FR-008**: System MUST accumulate sub-minimum segments (< 1s) across silence boundaries until minimum threshold is reached before emission
- **FR-009**: System MUST continue segment accumulation after forced emission at max duration, starting new segment from continuation point

#### Configuration

- **FR-010**: System MUST allow operators to configure silence detection RMS threshold in dB (default -40dB for broadcast audio)
- **FR-011**: System MUST allow operators to configure silence duration threshold in milliseconds (default 1000ms)
- **FR-012**: System MUST allow operators to configure minimum segment duration (default 1s)
- **FR-013**: System MUST allow operators to configure maximum segment duration (default 15s)
- **FR-014**: Configuration MUST be provided via environment variables or configuration file (not hardcoded)

#### A/V Synchronization

- **FR-015**: System MUST preserve A/V synchronization with variable-length audio segments by tracking precise PTS and duration for each segment
- **FR-016**: System MUST ensure AudioSegment metadata (t0_ns, duration_ns) accurately reflects the variable accumulated duration
- **FR-017**: System MUST maintain compatibility with existing A/V sync manager logic that expects AudioSegment and VideoSegment objects with PTS and duration
- **FR-018**: System MUST ensure cumulative A/V sync drift remains within acceptable threshold (< 500ms) over multi-minute streams

#### Resilience and Fallback

- **FR-019**: System MUST detect GStreamer level element initialization failures and fall back to fixed 6-second segmentation
- **FR-020**: System MUST detect runtime VAD processing errors and gracefully degrade to fixed segmentation without dropping segments
- **FR-021**: System MUST log VAD failures with sufficient detail for operator troubleshooting (element name, error code, audio format)
- **FR-022**: System MUST increment metrics counter `vad_fallback_total` when falling back to fixed segmentation
- **FR-023**: System MUST expose metrics gauge `vad_enabled` (1=VAD active, 0=fallback mode) for monitoring

#### Metrics and Observability

- **FR-024**: System MUST expose Prometheus metrics for VAD segmentation: `vad_segments_total` (total segments emitted), `vad_forced_emissions_total` (max duration forced emissions), `vad_silence_detections_total` (natural silence boundaries detected)
- **FR-025**: System MUST expose histogram `vad_segment_duration_seconds` to track distribution of variable segment durations
- **FR-026**: System MUST log segment emission events with duration, trigger reason (silence_detected | max_duration_reached | eos_flush), and RMS level at boundary
- **FR-027**: System MUST maintain existing segment emission logs for compatibility with monitoring tools

#### Backward Compatibility

- **FR-028**: System MUST maintain existing `SegmentBuffer` API surface (push_audio, flush_audio methods) to minimize changes to pipeline code
- **FR-029**: System MUST continue to produce AudioSegment objects compatible with existing STS fragment protocol (AudioData schema)
- **FR-030**: System MUST preserve existing EOS (end-of-stream) flush behavior for partial segments (minimum 1s, discard if shorter)

### Key Entities

- **VADAudioSegmenter**: Component responsible for integrating GStreamer level element, monitoring RMS levels, detecting silence boundaries, and triggering segment emission. Wraps or extends existing SegmentBuffer logic.

- **SilenceBoundary**: Represents a detected silence period in the audio stream. Contains RMS level, duration of silence, and timestamp. Used to trigger segment emission.

- **SegmentationConfig**: Configuration object containing VAD parameters (silence_threshold_db, silence_duration_ms, min_segment_duration_ns, max_segment_duration_ns). Loaded from environment variables or config file.

- **AudioSegment** (existing): Metadata object representing an audio segment with variable duration. Already contains stream_id, batch_number, t0_ns, duration_ns, file_path. No schema changes required for VAD support.

- **VADMetrics**: Metrics collection for VAD operations including segments_total, forced_emissions_total, silence_detections_total, vad_enabled gauge, segment_duration_seconds histogram.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Variable-length audio segments emitted at natural speech boundaries with 95% accuracy (silence boundaries detected within 100ms of actual 1s silence)
- **SC-002**: Zero audio segments shorter than 1 second sent to STS service under normal operation (min_duration_violations_total = 0)
- **SC-003**: Zero audio segments longer than 15 seconds emitted (max_duration enforced 100% of the time)
- **SC-004**: A/V synchronization maintained within 120ms delta for 95% of segments with variable-length audio segmentation
- **SC-005**: VAD processing introduces less than 50ms additional latency compared to fixed segmentation
- **SC-006**: System continues operating without interruption when VAD fails (fallback to fixed segmentation within 1 second)
- **SC-007**: Translation quality improves measurably due to complete phrase segmentation (baseline: fixed 6s segments, target: 20% reduction in mid-phrase splits as measured by manual review)
- **SC-008**: Segment duration histogram shows natural distribution between 1-15s with peak around 3-5s for typical speech patterns
- **SC-009**: System handles 5-minute continuous streams without memory leaks, with cumulative A/V drift < 500ms
- **SC-010**: Operators can tune VAD parameters (threshold, duration) for different content types without code changes, with tuning guide documentation providing clear guidance for common scenarios (studio, broadcast, noisy, multi-speaker)

## Assumptions

1. **GStreamer level element availability**: Assumes `gst-plugins-base` package is installed in the media-service environment, providing the `level` element for RMS monitoring. If not available, system falls back to fixed segmentation.

2. **Audio format compatibility**: Assumes audio streams are in formats compatible with the level element (AAC, PCM, etc.). The level element supports most common formats, but exotic formats may require additional plugins.

3. **Single speaker dominant**: Assumes typical use case is single speaker or sequential speakers (news broadcast, commentary) rather than simultaneous multi-speaker conversations. Overlapping speech may prevent silence detection, triggering max duration guard.

4. **Silence as speech boundary**: Assumes 1 second of silence is a reasonable heuristic for sentence/phrase boundaries in most spoken content. Fast speakers or continuous speech may require tuning.

5. **15-second maximum is acceptable**: Assumes 15-second maximum segment duration is acceptable for translation quality and STS processing. Very long sentences may be split mid-phrase, but this is preferable to unbounded accumulation.

6. **Existing A/V sync logic is robust**: Assumes the current A/V sync manager can handle variable audio segment durations without modification. PTS and duration tracking should be sufficient for synchronization.

7. **STS service accepts variable durations**: Assumes STS service (Echo and Full implementations) can process audio fragments of variable duration (1-15s) without issues. AudioData schema already supports arbitrary duration_ms values.

8. **RMS is adequate for VAD**: Assumes RMS level monitoring is sufficient for simple silence detection. More sophisticated VAD algorithms (spectral analysis, ML-based) are out of scope but could be added in future iterations.

9. **Operators can tune thresholds**: Assumes operators have sufficient audio engineering knowledge to tune RMS thresholds and silence durations for their specific content. Documentation will provide guidance for common scenarios.

10. **Fixed video segments remain unchanged**: Assumes video segmentation remains at fixed 6-second intervals. Only audio segmentation becomes variable. Video and audio segment counts will no longer match 1:1.
