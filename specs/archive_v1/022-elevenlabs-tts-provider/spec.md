# Feature Specification: ElevenLabs TTS Provider

**Feature Branch**: `022-elevenlabs-tts-provider`
**Created**: 2026-01-03
**Status**: Draft
**Input**: User description: "Add ElevenLabs API as a TTS provider"

## Clarifications

### Session 2026-01-03

- Q: ElevenLabs API Model Selection Strategy → A: Use eleven_flash_v2_5 as default model (ElevenLabs newest fast model)
- Q: Fallback behavior when ElevenLabs API fails → A: No automatic fallback to Coqui; return errors for pipeline-level handling
- Q: Streaming API usage for lower latency → A: No streaming initially; use standard synchronous API
- Q: Default Voice ID Mapping Strategy → A: Use language-specific defaults with well-known ElevenLabs voices (en→Rachel, es→Diego, fr→Thomas, etc.)
- Q: Default TTS Provider → A: ElevenLabs is the DEFAULT provider (not Coqui). Use TTS_PROVIDER env var to switch.
- Q: Default Target Language → A: Japanese (ja) is the default target language for the whole STS service
- Q: Provider Selection Mechanism → A: Use TTS_PROVIDER environment variable (values: "elevenlabs" or "coqui", default: "elevenlabs")

## User Scenarios & Testing

### User Story 1 - Basic ElevenLabs TTS Synthesis (Priority: P1)

The system supports ElevenLabs as an alternative TTS provider, allowing operators to choose between cloud-based high-quality synthesis (ElevenLabs) and local low-latency synthesis (Coqui) based on operational needs.

**Why this priority**: This is the foundational capability that enables ElevenLabs integration. Without basic synthesis working through the ElevenLabs API, no other features matter.

**Independent Test**: Test ElevenLabs provider implementation in isolation
- **Unit test**: `test_elevenlabs_basic_synthesis()` validates text input produces valid audio output via mocked ElevenLabs API
- **Contract test**: `test_elevenlabs_audio_asset_schema()` validates AudioAsset output matches existing TTS contract
- **Integration test**: `test_elevenlabs_real_api_synthesis()` validates real API call produces valid audio (requires API key, marked as optional)
- **Success criteria**: All unit tests pass with mocked API, integration test passes when API key available, audio output matches AudioAsset contract

**Acceptance Scenarios**:

1. **Given** a TextAsset with English text "Hello world" and tts_provider="elevenlabs", **When** TTS component processes it, **Then** an AudioAsset is produced with ElevenLabs-synthesized speech audio
2. **Given** valid ELEVENLABS_API_KEY environment variable, **When** ElevenLabs provider initializes, **Then** component reports is_ready=True
3. **Given** missing or invalid API key, **When** ElevenLabs provider initializes, **Then** component reports is_ready=False and returns initialization error

---

### User Story 2 - Voice Selection and Language Support (Priority: P2)

The system supports ElevenLabs voice selection using voice IDs and provides sensible default voices for common languages, allowing operators to customize voice characteristics without managing voice sample files.

**Why this priority**: Voice selection is critical for production quality output. ElevenLabs provides pre-trained voices that eliminate the need for voice cloning setup, making deployment simpler.

**Independent Test**: Test voice selection logic with different configurations
- **Unit test**: `test_elevenlabs_voice_id_selection()` validates explicit voice_id is used when provided
- **Unit test**: `test_elevenlabs_default_voice_by_language()` validates appropriate default voice is selected per language
- **Integration test**: `test_elevenlabs_multilingual_synthesis()` validates voice switching across different languages
- **Success criteria**: Voice selection logic correctly handles explicit IDs and language-based defaults

**Acceptance Scenarios**:

1. **Given** VoiceProfile with explicit voice_id "21m00Tcm4TlvDq8ikWAM" (Rachel), **When** synthesis runs, **Then** Rachel voice is used regardless of language
2. **Given** VoiceProfile with language="es" and no explicit voice_id, **When** synthesis runs, **Then** default Spanish voice Diego (ThT5KcBeYPX3keUQqHPh) is selected
3. **Given** VoiceProfile with language="zh" (unsupported language), **When** synthesis runs, **Then** fallback to English default voice Rachel (21m00Tcm4TlvDq8ikWAM) with warning recorded

---

### User Story 3 - Error Handling and Rate Limiting (Priority: P3)

The system handles ElevenLabs API errors gracefully by mapping API-specific errors to existing TTSError types and classifying rate limit errors (429) as retryable, enabling pipeline-level retry logic.

**Why this priority**: Robust error handling is essential for production reliability with cloud APIs. Rate limiting is a common occurrence that must be handled transparently.

**Independent Test**: Test error classification with mocked API responses
- **Unit test**: `test_elevenlabs_rate_limit_retryable()` validates 429 errors are marked retryable
- **Unit test**: `test_elevenlabs_auth_error_non_retryable()` validates 401 errors are marked non-retryable
- **Unit test**: `test_elevenlabs_api_error_mapping()` validates ElevenLabs errors map to TTSError types
- **Success criteria**: All error types are correctly classified with appropriate retryability flags

**Acceptance Scenarios**:

1. **Given** ElevenLabs API returns 429 (rate limit exceeded), **When** synthesis fails, **Then** error is mapped to TIMEOUT error type with retryable=True
2. **Given** ElevenLabs API returns 401 (invalid API key), **When** synthesis fails, **Then** error is mapped to INVALID_INPUT error type with retryable=False
3. **Given** ElevenLabs API returns 500 (server error), **When** synthesis fails, **Then** error is mapped to UNKNOWN error type with retryable=True

---

### User Story 4 - Configuration and Provider Selection (Priority: P4)

The system allows operators to configure TTS provider choice via environment variables and configuration, enabling easy switching between Coqui and ElevenLabs without code changes.

**Why this priority**: Flexible configuration enables different deployment scenarios (local development with Coqui, production with ElevenLabs) and A/B testing between providers.

**Independent Test**: Test factory and configuration logic
- **Unit test**: `test_factory_creates_elevenlabs_provider()` validates factory creates ElevenLabs component when provider="elevenlabs"
- **Unit test**: `test_elevenlabs_specific_config()` validates ElevenLabs-specific settings (model_id, stability, similarity_boost)
- **Integration test**: `test_manual_client_provider_flag()` validates manual_test_client.py supports --tts-provider elevenlabs
- **Success criteria**: Factory correctly instantiates provider, configuration is passed through, manual test client supports both providers

**Acceptance Scenarios**:

1. **Given** TTS_PROVIDER env var not set and valid API key, **When** create_tts_component() is called without explicit provider, **Then** ElevenLabsTTSComponent instance is returned (elevenlabs is default)
2. **Given** TTS_PROVIDER=coqui environment variable, **When** create_tts_component() is called without explicit provider, **Then** CoquiTTSComponent instance is returned
3. **Given** TTS_PROVIDER=elevenlabs environment variable, **When** create_tts_component() is called without explicit provider, **Then** ElevenLabsTTSComponent instance is returned
4. **Given** manual_test_client.py with --tts-provider coqui flag, **When** client sends fragment, **Then** Coqui provider is used for synthesis (override env var)

---

### User Story 5 - Quality and Performance Settings (Priority: P5)

The system supports ElevenLabs-specific quality settings (model_id, stability, similarity_boost) to balance synthesis quality and API cost, allowing operators to optimize for different use cases.

**Why this priority**: Fine-grained quality control enables cost optimization and performance tuning, but basic functionality works with defaults.

**Independent Test**: Test ElevenLabs-specific parameter handling
- **Unit test**: `test_elevenlabs_model_selection()` validates model_id parameter is passed to API
- **Unit test**: `test_elevenlabs_voice_settings()` validates stability and similarity_boost parameters
- **Integration test**: `test_elevenlabs_quality_modes()` validates different model/setting combinations produce valid output
- **Success criteria**: All ElevenLabs parameters are correctly passed to API, different settings produce valid audio

**Acceptance Scenarios**:

1. **Given** VoiceProfile with explicit model_id="eleven_multilingual_v2", **When** synthesis runs, **Then** specified model is used instead of default
2. **Given** VoiceProfile with stability=0.8 and similarity_boost=0.9, **When** synthesis runs, **Then** voice settings are applied to API request
3. **Given** VoiceProfile with no explicit model_id, **When** synthesis runs, **Then** default model "eleven_flash_v2_5" is used

---

### Edge Cases

- **API unavailability/timeout**: Return TTSError with retryable=True, error propagates to pipeline (no automatic fallback to Coqui per FR-026)
- **API quota exhaustion**: Treated as retryable error (similar to rate limiting), pipeline decides retry/fallback strategy
- **Invalid voice_id**: Return TTSError with retryable=False (permanent error), pipeline can retry with different voice or fallback
- **Text exceeding character limits**: Truncate at ElevenLabs limit (5000 chars) with warning, or split into chunks if needed
- **Unexpected audio format/sample rate**: Attempt conversion to PCM; if fails, return TTSError with retryable=False
- **Duration matching edge cases**: Same rubberband logic as Coqui (speed clamping, only_speed_up constraints apply identically)

## Requirements

### Functional Requirements

- **FR-001**: TTS factory MUST support "elevenlabs" as a valid ProviderType option
- **FR-001a**: TTS factory MUST read TTS_PROVIDER environment variable to determine default provider (values: "elevenlabs" or "coqui")
- **FR-001b**: TTS factory MUST default to "elevenlabs" when TTS_PROVIDER is not set
- **FR-001c**: StreamConfig default target_language MUST be changed from "es" to "ja" (Japanese)
- **FR-002**: ElevenLabsTTSComponent MUST implement BaseTTSComponent abstract base class
- **FR-003**: ElevenLabsTTSComponent MUST conform to TTSComponent Protocol contract
- **FR-004**: ElevenLabs provider MUST read API key from ELEVENLABS_API_KEY environment variable
- **FR-005**: ElevenLabs provider MUST report is_ready=False when API key is missing or invalid
- **FR-006**: ElevenLabs provider MUST report is_ready=True when API key is valid and API is reachable
- **FR-007**: ElevenLabs provider MUST support explicit voice_id selection via VoiceProfile
- **FR-008**: ElevenLabs provider MUST provide default voice mappings for common languages using well-known ElevenLabs voices: en→21m00Tcm4TlvDq8ikWAM (Rachel), es→ThT5KcBeYPX3keUQqHPh (Diego), fr→N2lVS1w4EtoT3dr4eOWO (Thomas), de→pFZP5JQG7iQjIQuC4Bku (Sarah), it→onwK4e9ZLuTAKqWW03F9 (Giovanni), pt→cjVigY5qzO86Huf0OWal (Domi), ja→EXAVITQu4vr4xnSDxMaL (Hiro)
- **FR-009**: ElevenLabs provider MUST fall back to English default voice (Rachel) for unsupported languages with warning
- **FR-010**: ElevenLabs provider MUST support configurable model_id with default "eleven_flash_v2_5" (ElevenLabs Flash v2.5 model)
- **FR-011**: ElevenLabs provider MUST support voice settings (stability, similarity_boost) as configuration parameters
- **FR-012**: ElevenLabs provider MUST map ElevenLabs API errors to existing TTSError types (no new error types introduced)
- **FR-013**: ElevenLabs provider MUST map 429 (rate limit) errors to TIMEOUT type with retryable=True
- **FR-014**: ElevenLabs provider MUST map 401/403 (authentication) errors to INVALID_INPUT type with retryable=False
- **FR-015**: ElevenLabs provider MUST map 5xx (server) errors to UNKNOWN type with retryable=True
- **FR-015a**: ElevenLabs provider MUST map 400 (bad request) errors to INVALID_INPUT type with retryable=False
- **FR-015b**: ElevenLabs provider MUST map network/connection errors to TIMEOUT type with retryable=True
- **FR-016**: ElevenLabs provider MUST return AudioAsset with same schema as Coqui provider
- **FR-017**: ElevenLabs provider MUST support all existing synthesize() method parameters (target_duration_ms, output_sample_rate_hz, output_channels)
- **FR-018**: ElevenLabs provider MUST apply text preprocessing before API call (same preprocessing as Coqui)
- **FR-019**: ElevenLabs provider MUST resample API-returned audio to match requested output_sample_rate_hz if different
- **FR-020**: ElevenLabs provider MUST convert mono API audio to stereo if output_channels=2
- **FR-021**: ElevenLabs provider MUST apply duration matching using rubberband when target_duration_ms is provided
- **FR-022**: ElevenLabs provider MUST record component_instance as "elevenlabs-{model_id}" for lineage tracking
- **FR-023**: ElevenLabs provider MUST handle API timeouts with configurable timeout_ms from TTSConfig
- **FR-024**: ElevenLabs provider MUST record API call duration, model used, and voice ID as metadata
- **FR-025**: manual_test_client.py MUST support --tts-provider elevenlabs command-line flag
- **FR-026**: ElevenLabs provider MUST NOT automatically fallback to Coqui provider on API failures (errors propagate to pipeline for handling)
- **FR-027**: ElevenLabs provider MUST use synchronous text-to-speech API endpoint (not streaming API)
- **FR-028**: ElevenLabs provider MUST use ElevenLabs Flash v2.5 model (eleven_flash_v2_5) as default when model_id not specified

### Key Entities

- **ElevenLabsTTSComponent**: TTS provider implementation using ElevenLabs API (implements BaseTTSComponent)
- **ElevenLabsConfig**: Extension of VoiceProfile with ElevenLabs-specific settings (model_id, voice_id, stability, similarity_boost)
- **ElevenLabsVoiceMapping**: Internal mapping from language codes to default ElevenLabs voice IDs (en→Rachel, es→Diego, fr→Thomas, de→Sarah, it→Giovanni, pt→Domi, ja→Hiro)
- **AudioAsset**: Synthesized speech output (same schema as Coqui provider)
- **TTSError**: Structured error information (uses existing TTSErrorType enum, no new types added)

## Success Criteria

### Measurable Outcomes

- **SC-001**: ElevenLabs provider successfully synthesizes audio for all supported languages (en, es, fr, de, it, pt, ja) in test cases
- **SC-002**: Error classification correctly identifies retryable vs non-retryable failures for all ElevenLabs error codes (401, 429, 5xx)
- **SC-003**: AudioAsset output from ElevenLabs provider is schema-compatible with existing Coqui provider output
- **SC-004**: Duration matching works identically for ElevenLabs and Coqui providers (same rubberband logic)
- **SC-005**: API key validation completes within 2 seconds during component initialization
- **SC-006**: Voice selection logic handles explicit voice_id and language-based defaults correctly in 100% of test cases
- **SC-007**: System gracefully handles missing API key by returning clear error message without crashing
- **SC-008**: All intermediate assets (preprocessed text, baseline audio, aligned audio) are tracked with correct parent references
- **SC-009**: Manual test client supports both Coqui and ElevenLabs providers via command-line flag
- **SC-010**: Integration tests validate real API calls produce valid audio when API key is available (optional CI gate)

### Assumptions

- ElevenLabs API endpoint is publicly accessible at documented URL (https://api.elevenlabs.io/v1)
- API key is provided via environment variable ELEVENLABS_API_KEY (not hardcoded)
- ElevenLabs synchronous text-to-speech API returns complete audio in single response (not streaming)
- ElevenLabs API returns audio in MP3 or PCM format that can be decoded to PCM
- Rate limits and quotas are enforced by ElevenLabs at the API level
- Voice IDs are stable and do not change frequently
- API authentication uses Bearer token format (Authorization: Bearer {api_key})
- Default ElevenLabs voice IDs are stable and available across accounts (Rachel, Diego, Thomas, Sarah, Giovanni, Domi, Hiro)
- ElevenLabs API supports text inputs up to 5000 characters (document limit, handle via truncation or chunking)
- Network connectivity to ElevenLabs API is available in production environment
- Same text preprocessing rules apply for both Coqui and ElevenLabs
- Duration matching via rubberband time-stretching works the same for ElevenLabs audio as Coqui audio
- No voice cloning needed initially (ElevenLabs has different voice cloning approach via API)
- ElevenLabs Flash v2.5 model (eleven_flash_v2_5) is available and suitable as default for real-time dubbing
- No automatic fallback to Coqui occurs; pipeline-level orchestrator handles provider failover decisions
