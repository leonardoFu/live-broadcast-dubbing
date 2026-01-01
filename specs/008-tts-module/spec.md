# Feature Specification: TTS Audio Synthesis Module

**Feature Branch**: `008-tts-module`
**Created**: 2025-12-30
**Status**: Draft
**Input**: User description: "Create a feature specification for the TTS (Text-to-Speech) module for the STS service."

## User Scenarios & Testing

### User Story 1 - Basic Text-to-Speech Conversion (Priority: P1)

The system receives translated text from the Translation module and converts it into synthesized speech audio that matches the original audio duration. This is the core TTS capability needed for the live dubbing pipeline.

**Why this priority**: This is the foundational capability that the entire TTS module is built upon. Without basic synthesis working, no other features matter.

**Independent Test**: Test TTS component in isolation with mock text inputs
- **Unit test**: `test_tts_basic_synthesis()` validates text input produces valid audio output with correct sample rate and channels
- **Contract test**: `test_audio_asset_schema()` validates AudioAsset output structure matches pipeline contract
- **Integration test**: `test_tts_receives_text_asset()` validates TTS component receives TextAsset from Translation module and produces AudioAsset
- **Success criteria**: All tests pass with 80% coverage, audio output is valid PCM with correct format

**Acceptance Scenarios**:

1. **Given** a TextAsset with English text "Hello world", **When** TTS component processes it with target language English, **Then** an AudioAsset is produced with synthesized speech audio
2. **Given** a TextAsset with Spanish text "Hola mundo", **When** TTS component processes it with target language Spanish, **Then** an AudioAsset is produced with correct Spanish pronunciation
3. **Given** invalid or empty text input, **When** TTS component processes it, **Then** a structured error is returned with appropriate error type

---

### User Story 2 - Duration Matching for Live Streams (Priority: P2)

The system time-stretches synthesized speech to match the original audio fragment duration, ensuring the dubbed audio stays synchronized with the video without introducing noticeable pitch artifacts.

**Why this priority**: Duration matching is critical for maintaining audio-video sync in live streams. Without it, the dubbed audio will drift out of sync.

**Independent Test**: Test duration alignment with known input/target durations
- **Unit test**: `test_duration_matching_speed_up()` validates audio is sped up when synthesis is longer than target
- **Contract test**: `test_audio_asset_duration_metadata()` validates duration metadata is correctly recorded
- **Integration test**: `test_end_to_end_duration_alignment()` validates synthesized audio matches target duration within tolerance
- **Success criteria**: 95% of test cases achieve target duration within 50ms tolerance

**Acceptance Scenarios**:

1. **Given** synthesized audio of 5 seconds and target duration of 4 seconds, **When** duration matching is applied, **Then** audio is sped up to 4 seconds while preserving pitch
2. **Given** synthesized audio of 3 seconds and target duration of 5 seconds with only_speed_up enabled, **When** duration matching is applied, **Then** audio remains 3 seconds (no slow down)
3. **Given** extreme duration mismatch requiring 3x speed, **When** duration matching is applied, **Then** speed factor is clamped to 2.0x maximum and warning is recorded

---

### User Story 3 - Voice Selection and Quality Modes (Priority: P3)

The system supports multiple synthesis modes (quality vs fast) and voice profiles to balance quality and latency based on operational needs. For quality mode, voice cloning from sample audio is supported when available.

**Why this priority**: Flexibility in quality vs latency tradeoffs allows operators to optimize for different scenarios (high-quality recordings vs low-latency live streams).

**Independent Test**: Test voice selection logic and model switching
- **Unit test**: `test_voice_selection_fast_mode()` validates fast model is selected when fast_mode enabled
- **Unit test**: `test_voice_cloning_with_sample()` validates voice sample is used when provided and valid
- **Integration test**: `test_model_caching()` validates models are loaded once and reused across requests
- **Success criteria**: Model load time under 5 seconds on first request, subsequent requests use cached model

**Acceptance Scenarios**:

1. **Given** fast_mode enabled and target language Spanish, **When** voice selection runs, **Then** fast model (VITS) is selected and speaker parameters are disabled
2. **Given** quality mode with valid voice sample provided, **When** synthesis runs, **Then** XTTS-v2 model is used with voice cloning enabled
3. **Given** quality mode without voice sample, **When** synthesis runs, **Then** XTTS-v2 model is used with fallback speaker voice

---

### User Story 4 - Text Preprocessing for TTS Quality (Priority: P4)

The system preprocesses text before synthesis to normalize punctuation, expand abbreviations, and handle special patterns that improve speech naturalness and reduce synthesis failures.

**Why this priority**: Text preprocessing significantly improves TTS quality and reduces failure rates, but the system can function without it.

**Independent Test**: Test preprocessing rules independently
- **Unit test**: `test_preprocess_punctuation_normalization()` validates smart quotes are normalized to ASCII
- **Unit test**: `test_preprocess_abbreviation_expansion()` validates abbreviations like "NBA" expand to "N B A"
- **Unit test**: `test_preprocess_score_rewriting()` validates patterns like "15-12" become "15 to 12"
- **Success criteria**: All preprocessing rules are deterministic (same input always produces same output)

**Acceptance Scenarios**:

1. **Given** text containing smart quotes "Hello", **When** preprocessing runs, **Then** output contains ASCII quotes "Hello"
2. **Given** text "NBA Finals", **When** preprocessing runs, **Then** output is "N B A Finals"
3. **Given** text "Score is 21-14", **When** preprocessing runs, **Then** output is "Score is 21 to 14"

---

### User Story 5 - Error Handling and Fallbacks (Priority: P5)

The system handles synthesis failures gracefully by classifying errors as retryable or non-retryable and providing structured error information to enable pipeline-level fallback decisions.

**Why this priority**: Robust error handling is essential for production reliability, but basic functionality must work first.

**Independent Test**: Test error classification and recovery
- **Unit test**: `test_classify_model_load_error()` validates model load failures are marked as retryable
- **Unit test**: `test_classify_synthesis_failure()` validates synthesis failures return structured error
- **Integration test**: `test_retry_on_transient_failure()` validates retryable errors trigger retry logic
- **Success criteria**: All error types are correctly classified, structured errors include retryable flag and error type

**Acceptance Scenarios**:

1. **Given** model file is temporarily unavailable, **When** synthesis fails, **Then** error is marked retryable and includes model_load_failed type
2. **Given** synthesis produces invalid output, **When** validation fails, **Then** error is marked non-retryable with synthesis_failed type
3. **Given** empty or whitespace-only text input, **When** TTS processes it, **Then** validation error is returned immediately without attempting synthesis

---

### Edge Cases

- What happens when target duration is extremely short (under 500ms) and synthesized audio cannot be sped up enough without severe artifacts?
- How does the system handle multilingual text mixing (e.g., English text with embedded Spanish phrases)?
- What happens when voice sample file is corrupted or in wrong format?
- How does the system handle very long text inputs that exceed model context limits?
- What happens when rubberband time-stretching fails or produces corrupted audio?
- How does the system behave when model cache is full or disk space is exhausted?

## Requirements

### Functional Requirements

- **FR-001**: TTS component MUST accept TextAsset from Translation module as input
- **FR-002**: TTS component MUST produce AudioAsset with synthesized speech as output
- **FR-003**: TTS component MUST support configurable output sample rate and channel count
- **FR-004**: TTS component MUST support duration matching to align synthesized audio with target duration
- **FR-005**: TTS component MUST clamp speed adjustment factors to avoid extreme artifacts (default: 0.5x to 2.0x range)
- **FR-006**: TTS component MUST support two synthesis modes: quality mode (XTTS-v2) and fast mode (VITS)
- **FR-007**: TTS component MUST support voice cloning when voice sample is provided in quality mode
- **FR-008**: TTS component MUST fall back to named speaker voice when no voice sample is available
- **FR-009**: TTS component MUST apply text preprocessing before synthesis to normalize punctuation and expand abbreviations
- **FR-010**: TTS component MUST record preprocessed text as asset for debugging and lineage tracking
- **FR-011**: TTS component MUST cache loaded models in memory to reduce latency for subsequent requests
- **FR-012**: TTS component MUST preserve pitch when applying time-stretching for duration matching
- **FR-013**: TTS component MUST resample audio to match requested output sample rate if model produces different rate
- **FR-014**: TTS component MUST record synthesis duration, speed factor, and clamping decisions as metadata
- **FR-015**: TTS component MUST classify errors as retryable or non-retryable
- **FR-016**: TTS component MUST return structured errors with error type, message, and retryability flag
- **FR-017**: TTS component MUST track asset lineage from TextAsset input to AudioAsset output
- **FR-018**: TTS component MUST support mono-to-stereo conversion when output channels is 2 but synthesis produces mono
- **FR-019**: TTS component MUST validate text input is non-empty before attempting synthesis
- **FR-020**: TTS component MUST use CPU device for synthesis to avoid GPU compatibility issues

### Key Entities

- **AudioAsset**: Synthesized speech audio output with metadata (duration, sample rate, channels, lineage)
- **TextAsset**: Translated text input from Translation module with language and speaker metadata
- **VoiceProfile**: Configuration defining voice selection (model, voice sample path, speaker name)
- **TTSMetrics**: Timing and quality metrics (baseline duration, applied speed factor, clamping flags, processing time)
- **SynthesisError**: Structured error information (error type, retryability, message, details)

## Success Criteria

### Measurable Outcomes

- **SC-001**: TTS component processes text inputs and produces valid audio outputs in 95% of test cases
- **SC-002**: Duration matching achieves target duration within 50ms for 95% of fragments
- **SC-003**: First model load completes within 5 seconds, subsequent synthesis requests complete within 2 seconds using cached model
- **SC-004**: Text preprocessing is fully deterministic (identical inputs always produce identical outputs)
- **SC-005**: Error classification correctly identifies retryable vs non-retryable failures in 100% of test cases
- **SC-006**: Voice cloning is activated when valid voice sample is provided in quality mode
- **SC-007**: Fast mode reduces synthesis latency by at least 40% compared to quality mode
- **SC-008**: Time-stretched audio maintains pitch stability (no audible pitch shift artifacts)
- **SC-009**: All intermediate assets (preprocessed text, baseline audio, aligned audio) are tracked with correct parent references
- **SC-010**: System handles empty inputs, invalid voice samples, and model load failures without crashing

### Assumptions

- Rubberband time-stretching tool is available in system PATH
- Coqui TTS library is compatible with Python 3.10
- Voice sample files meet validation criteria:
  - Format: WAV only
  - Channels: Mono (1 channel)
  - Sample rate: Minimum 16kHz (22050Hz or 24000Hz preferred)
  - Duration: Between 3 and 30 seconds
  - Content: Clear speech (not silence/music/noise)
- Language codes follow ISO 639-1 format (e.g., "en", "es", "fr")
- Model files are accessible and valid at configured paths
- Output audio format is PCM WAV (raw audio data, not compressed)
- Component runs on CPU to avoid GPU compatibility issues (per reference implementation)
