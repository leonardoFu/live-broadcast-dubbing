# Tasks: Full STS Service with Socket.IO Integration

**Input**: Design documents from `/specs/021-full-sts-service/`
**Prerequisites**: plan.md (✅), spec.md (✅), research-cache.md (✅), contracts/fragment-processed-schema.yaml (✅)

**Feature Branch**: `021-full-sts-service`
**Status**: Ready for implementation

**Total Tasks**: 60 tasks across 7 phases (Phases 0-6)
**Estimated Duration**: 1-2 weeks (1 developer, part-time)

**Note**: ASR, Translation, and TTS modules (8,390 lines) already exist and will be reused. This plan focuses only on integration work: Pipeline Coordinator + Socket.IO + Observability + Configuration + E2E testing.

**Tests**: Tests are MANDATORY per Constitution Principle VIII. Every user story MUST have tests written FIRST before implementation. The tasks below enforce a test-first workflow.

**Organization**: Tasks are grouped by implementation phase from plan.md. User stories (US1-US5) are mapped to phases:
- **US1 (P1)**: Complete STS Pipeline Processing → Phases 1-6
- **US2 (P1)**: Graceful Error Handling → Phase 4
- **US3 (P2)**: Backpressure and Flow Control → Phase 5
- **US4 (P2)**: Observability and Monitoring → Phase 7
- **US5 (P3)**: Stream Lifecycle Management → Phases 7-8

---

## Format: `[ID] [P?] [Story] Description (Size: S/M/L, Priority: P1/P2/P3)`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US5)
- **Size**: S (small, <4h), M (medium, 4-8h), L (large, 8h+)
- **Priority**: P1 (critical), P2 (high), P3 (medium)
- Include exact file paths in descriptions

---

## Phase 1: Data Models & Contracts (PRIORITY: P1)

**Goal**: Define data models and API contracts for type safety and schema validation.

**Dependencies**: None
**Estimated Time**: 2-3 days
**Success Criteria**: All contract tests pass, Pydantic models validate against JSON schemas

### Tests for Phase 1 (MANDATORY - Test-First) ✅

> **CRITICAL: These tests MUST be written FIRST and MUST FAIL before implementation begins**

**Coverage Target**: 100% of all contracts

- [x] T001 [P] [US1] **Contract test** for fragment:data schema in `apps/sts-service/tests/contract/test_fragment_schemas.py` (Size: S, Priority: P1)
  - Load `contracts/fragment-schema.json`
  - Validate sample fragment:data payload (base64 audio, sequence_number, fragment_id, stream_id)
  - Test required fields: fragment_id, stream_id, sequence_number, timestamp, audio, sample_rate, channels, format, duration_ms
  - Test field types: string, integer, base64 string
  - Verify schema validation passes with valid payload

- [x] T002 [P] [US1] **Contract test** for fragment:ack schema in `apps/sts-service/tests/contract/test_fragment_schemas.py` (Size: S, Priority: P1)
  - Validate fragment:ack payload structure (status: "queued", fragment_id, timestamp)
  - Test required fields: fragment_id, status, timestamp
  - Test status enum values: "queued"

- [x] T003 [P] [US1] **Contract test** for fragment:processed SUCCESS schema in `apps/sts-service/tests/contract/test_fragment_schemas.py` (Size: M, Priority: P1)
  - Validate fragment:processed payload with status "success"
  - Test required fields: fragment_id, status, dubbed_audio, transcript, translated_text, metadata (original_duration_ms, dubbed_duration_ms, duration_variance_percent, speed_ratio), processing_time_ms, stage_timings (asr_ms, translation_ms, tts_ms)
  - Test dubbed_audio is base64-encoded PCM
  - Test metadata includes duration matching stats

- [x] T004 [P] [US2] **Contract test** for fragment:processed FAILED schema in `apps/sts-service/tests/contract/test_fragment_schemas.py` (Size: M, Priority: P1)
  - Validate fragment:processed payload with status "failed"
  - Test required error fields: error.stage, error.code, error.message, error.retryable
  - Test error.stage enum: "asr", "translation", "tts"
  - Test error.code enum: "TIMEOUT", "RATE_LIMIT_EXCEEDED", "DURATION_MISMATCH_EXCEEDED", etc.
  - Test error.retryable boolean

- [x] T005 [P] [US1] **Contract test** for stream:init schema in `apps/sts-service/tests/contract/test_stream_schemas.py` (Size: S, Priority: P1)
  - Validate stream:init payload structure
  - Test required fields: source_language, target_language, voice_profile, chunk_duration_ms, sample_rate_hz, channels, format
  - Test optional fields: domain_hints
  - Test language codes: "en", "es", "fr", etc.

- [x] T006 [P] [US1] **Contract test** for stream:ready schema in `apps/sts-service/tests/contract/test_stream_schemas.py` (Size: S, Priority: P1)
  - Validate stream:ready payload structure
  - Test required fields: session_id, max_inflight, capabilities
  - Test capabilities array: ["asr", "translation", "tts", "duration_matching"]

- [x] T007 [P] [US5] **Contract test** for stream:pause/resume/end schemas in `apps/sts-service/tests/contract/test_stream_schemas.py` (Size: S, Priority: P3)
  - Validate stream:pause payload (empty or with reason)
  - Validate stream:resume payload (empty)
  - Validate stream:end payload (empty)

- [x] T008 [P] [US5] **Contract test** for stream:complete schema in `apps/sts-service/tests/contract/test_stream_schemas.py` (Size: S, Priority: P3)
  - Validate stream:complete payload structure
  - Test required fields: total_fragments, success_count, failed_count, avg_processing_time_ms
  - Test optional fields: error_breakdown (by stage and code)

- [x] T009 [P] [US3] **Contract test** for backpressure event schema in `apps/sts-service/tests/contract/test_backpressure_schema.py` (Size: S, Priority: P2)
  - Validate backpressure event payload structure
  - Test required fields: stream_id, severity, action, current_inflight, max_inflight, threshold_exceeded
  - Test severity enum: "low", "medium", "high"
  - Test action enum: "none", "slow_down", "pause"

- [x] T010 [P] [US2] **Contract test** for error response schema in `apps/sts-service/tests/contract/test_error_schema.py` (Size: S, Priority: P1)
  - Validate error response structure for all error codes
  - Test STREAM_NOT_FOUND, STREAM_PAUSED, INVALID_CONFIG, INVALID_VOICE_PROFILE, BACKPRESSURE_EXCEEDED
  - Test retryable flag consistency (TIMEOUT=true, INVALID_CONFIG=false)

**Verification**: Run `pytest apps/sts-service/tests/contract/ -v` - ALL tests MUST FAIL with "FileNotFoundError" (schemas not created yet)

### Implementation for Phase 1

- [x] T011 [P] [US1] Create JSON schema for fragment events in `specs/021-full-sts-service/contracts/fragment-schema.json` (Size: M, Priority: P1)
  - Define fragment:data schema (incoming from worker)
  - Define fragment:ack schema (acknowledgment response)
  - Define fragment:processed schema (SUCCESS, PARTIAL, FAILED statuses)
  - Include all required fields from spec.md FR-028 to FR-033

- [x] T012 [P] [US1] Create JSON schema for stream events in `specs/021-full-sts-service/contracts/stream-schema.json` (Size: M, Priority: P1)
  - Define stream:init schema (worker configuration)
  - Define stream:ready schema (service initialization response)
  - Define stream:pause, stream:resume, stream:end schemas
  - Define stream:complete schema (final statistics)

- [x] T013 [P] [US3] Create JSON schema for backpressure events in `specs/021-full-sts-service/contracts/backpressure-schema.json` (Size: S, Priority: P2)
  - Define backpressure event structure per spec.md FR-042 to FR-044
  - Include severity thresholds from config (low: 1-3, medium: 4-6, high: 7-10, critical: >10)

- [x] T014 [P] [US2] Create JSON schema for error responses in `specs/021-full-sts-service/contracts/error-schema.json` (Size: S, Priority: P1)
  - Define error response structure per spec.md FR-035 to FR-040
  - Document all error codes and retryable flags

- [x] T015 [P] [US1] Create StreamConfig model in `apps/sts-service/src/sts_service/full/models/stream.py` (Size: M, Priority: P1)
  - Pydantic model for stream:init validation
  - Fields: source_language, target_language, voice_profile, chunk_duration_ms, sample_rate_hz, channels, format, domain_hints (optional)
  - Validators: language codes, voice_profile existence, audio format

- [x] T016 [P] [US1] Create StreamState and StreamSession models in `apps/sts-service/src/sts_service/full/models/stream.py` (Size: M, Priority: P1)
  - StreamState enum: initializing, active, paused, ending
  - StreamSession model: session_id, state, config, statistics, inflight_tracker
  - Statistics model: total_fragments, success_count, failed_count, processing_times

- [x] T017 [P] [US1] Create FragmentData model in `apps/sts-service/src/sts_service/full/models/fragment.py` (Size: M, Priority: P1)
  - Pydantic model for fragment:data validation
  - Fields: fragment_id, stream_id, sequence_number, timestamp, audio (base64), sample_rate, channels, format, duration_ms
  - Validators: base64 audio, positive integers, valid format

- [x] T018 [P] [US1] Create FragmentResult model in `apps/sts-service/src/sts_service/full/models/fragment.py` (Size: M, Priority: P1)
  - Pydantic model for fragment:processed payload
  - Fields: fragment_id, status (SUCCESS, PARTIAL, FAILED), dubbed_audio (optional), transcript, translated_text, metadata, processing_time_ms, stage_timings, error (optional)
  - Conditional fields based on status

- [x] T019 [P] [US1] Create Asset models in `apps/sts-service/src/sts_service/full/models/asset.py` (Size: L, Priority: P1)
  - TranscriptAsset: status, transcript, segments, confidence, parent_asset_ids, latency_ms
  - TranslationAsset: status, translated_text, source_text, language_pair, parent_asset_ids, latency_ms
  - AudioAsset: status, audio (PCM bytes), sample_rate, duration_ms, duration_metadata (variance, speed_ratio), parent_asset_ids, latency_ms
  - Shared AssetStatus enum: SUCCESS, PARTIAL, FAILED

- [x] T020 [P] [US2] Create ErrorResponse and ErrorCode models in `apps/sts-service/src/sts_service/full/models/error.py` (Size: M, Priority: P1)
  - ErrorResponse model: stage, code, message, retryable
  - ErrorCode enum: TIMEOUT, RATE_LIMIT_EXCEEDED, INVALID_CONFIG, INVALID_VOICE_PROFILE, BACKPRESSURE_EXCEEDED, DURATION_MISMATCH_EXCEEDED, etc.
  - ErrorStage enum: asr, translation, tts

- [x] T021 [P] [US3] Create BackpressureState model in `apps/sts-service/src/sts_service/full/models/backpressure.py` (Size: S, Priority: P2)
  - BackpressureState model: current_inflight, severity, action
  - Severity enum: low, medium, high
  - Action enum: none, slow_down, pause

- [x] T022 [US1] Re-run contract tests with created schemas and models (Size: S, Priority: P1)
  - Verify `pytest apps/sts-service/tests/contract/ -v` PASSES
  - Validate Pydantic models parse sample payloads from tests
  - Ensure 100% contract test coverage

- [x] T023 [P] [US1] Create data-model.md documentation in `specs/021-full-sts-service/data-model.md` (Size: M, Priority: P1)
  - Document all Pydantic models (StreamConfig, FragmentData, Assets, etc.)
  - Include field descriptions, validators, example payloads
  - Document state machine for StreamState (initializing → active → paused → ending)
  - Document asset lineage tracking (parent_asset_ids)

**Checkpoint**: Phase 1 complete - All contract tests pass, data models validated ✅

## Phase 2: Pipeline Coordinator (PRIORITY: P1)

**Goal**: Orchestrate ASR → Translation → TTS pipeline with error handling and in-order delivery.

**Dependencies**: Phase 1 (Data models); ASR/Translation/TTS modules already exist and will be reused
**Estimated Time**: 3-4 days
**Success Criteria**: All unit tests pass, in-order delivery guaranteed, error handling validated

### Tests for Phase 2 (MANDATORY - Test-First) ✅

**Coverage Target**: 95% (critical path)

- [x] T066 [P] [US1] **Unit test** for Pipeline chains ASR→Translation→TTS in `apps/sts-service/tests/unit/full/test_pipeline_coordinator.py` (Size: L, Priority: P1)
  - Mock ASR to return SUCCESS TranscriptAsset
  - Mock Translation to return SUCCESS TranslationAsset
  - Mock TTS to return SUCCESS AudioAsset
  - Call `PipelineCoordinator.process_fragment(fragment_data)`
  - Assert calls ASR, then Translation, then TTS in sequence
  - Assert returns FragmentResult with status=SUCCESS, dubbed_audio, transcript, translated_text

- [x] T067 [P] [US2] **Unit test** for Pipeline handles ASR failure in `apps/sts-service/tests/unit/full/test_pipeline_coordinator.py` (Size: M, Priority: P1)
  - Mock ASR to return FAILED TranscriptAsset (error.code="TIMEOUT")
  - Assert Pipeline returns FragmentResult with status=FAILED, error.stage="asr", error.retryable=True
  - Assert Translation and TTS are NOT called (pipeline stops)

- [x] T068 [P] [US2] **Unit test** for Pipeline handles Translation failure in `apps/sts-service/tests/unit/full/test_pipeline_coordinator.py` (Size: M, Priority: P1)
  - Mock ASR to return SUCCESS
  - Mock Translation to return FAILED (error.code="RATE_LIMIT_EXCEEDED")
  - Assert Pipeline returns FragmentResult with status=FAILED, error.stage="translation", error.retryable=True
  - Assert TTS is NOT called

- [x] T069 [P] [US2] **Unit test** for Pipeline handles TTS failure in `apps/sts-service/tests/unit/full/test_pipeline_coordinator.py` (Size: M, Priority: P1)
  - Mock ASR and Translation to return SUCCESS
  - Mock TTS to return FAILED (error.code="DURATION_MISMATCH_EXCEEDED")
  - Assert Pipeline returns FragmentResult with status=FAILED, error.stage="tts", error.retryable=False

- [x] T070 [P] [US1] **Unit test** for Pipeline preserves asset lineage in `apps/sts-service/tests/unit/full/test_pipeline_coordinator.py` (Size: M, Priority: P1)
  - Assert TranslationAsset.parent_asset_ids includes TranscriptAsset ID
  - Assert AudioAsset.parent_asset_ids includes TranslationAsset ID
  - Verify lineage chain: Fragment → Transcript → Translation → Audio

- [x] T071 [P] [US1] **Unit test** for Pipeline tracks stage timings in `apps/sts-service/tests/unit/full/test_pipeline_coordinator.py` (Size: M, Priority: P1)
  - Mock ASR latency=3500ms, Translation=250ms, TTS=1500ms
  - Assert FragmentResult.stage_timings.asr_ms=3500, translation_ms=250, tts_ms=1500
  - Assert FragmentResult.processing_time_ms = sum of stage timings + overhead

- [x] T072 [P] [US1] **Unit test** for Fragment ordering by sequence_number in `apps/sts-service/tests/unit/full/test_fragment_ordering.py` (Size: L, Priority: P1)
  - Submit fragments with sequence_number: 3, 1, 2 (out of order)
  - Assert fragments emitted in order: 1, 2, 3
  - Use in-memory queue with heapq or sorted list

- [x] T073 [P] [US3] **Unit test** for Backpressure tracker - low severity in `apps/sts-service/tests/unit/full/test_backpressure_tracker.py` (Size: M, Priority: P2)
  - Set in_flight=2, max_inflight=3
  - Assert BackpressureState: severity="low", action="none", current_inflight=2

- [x] T074 [P] [US3] **Unit test** for Backpressure tracker - medium severity in `apps/sts-service/tests/unit/full/test_backpressure_tracker.py` (Size: M, Priority: P2)
  - Set in_flight=5, max_inflight=3
  - Assert BackpressureState: severity="medium", action="slow_down", current_inflight=5

- [x] T075 [P] [US3] **Unit test** for Backpressure tracker - high severity in `apps/sts-service/tests/unit/full/test_backpressure_tracker.py` (Size: M, Priority: P2)
  - Set in_flight=9, max_inflight=3
  - Assert BackpressureState: severity="high", action="pause", current_inflight=9

- [x] T076 [P] [US3] **Unit test** for Backpressure tracker - critical rejection in `apps/sts-service/tests/unit/full/test_backpressure_tracker.py` (Size: M, Priority: P2)
  - Set in_flight=11, max_inflight=3
  - Call `BackpressureTracker.should_reject_fragment()`
  - Assert returns True (reject with BACKPRESSURE_EXCEEDED error)

- [ ] T077 [P] [US1] **Integration test** for full pipeline ASR→TTS in `apps/sts-service/tests/integration/full/test_full_pipeline_asr_to_tts.py` (Size: L, Priority: P1)
  - Use real ASR, Translation, TTS modules (mock DeepL if no API key)
  - Process 6-second English audio fragment
  - Assert returns FragmentResult with status=SUCCESS, dubbed_audio (Spanish), duration variance <10%
  - Measure end-to-end latency (target <8s)

- [ ] T078 [P] [US1] **Integration test** for empty transcript handling in `apps/sts-service/tests/integration/full/test_full_pipeline_asr_to_tts.py` (Size: M, Priority: P1)
  - Process silence audio (6 seconds of zeros)
  - Assert ASR returns empty transcript
  - Assert Translation and TTS return SUCCESS with empty/silence outputs

**Verification**: Run `pytest apps/sts-service/tests/unit/full/test_pipeline_coordinator.py -v` - ALL tests MUST FAIL

### Implementation for Phase 2

- [x] T079 [US1] Create PipelineCoordinator class in `apps/sts-service/src/sts_service/full/pipeline.py` (Size: L, Priority: P1)
  - Class to orchestrate ASR → Translation → TTS workflow
  - Method `async def process_fragment(fragment_data: FragmentData, session: StreamSession) -> FragmentResult`
  - Initialize ASR, Translation, TTS modules on first call (lazy loading)

- [x] T080 [US1] Implement pipeline orchestration logic in `apps/sts-service/src/sts_service/full/pipeline.py` (Size: L, Priority: P1)
  - Step 1: Decode audio (base64 → PCM bytes)
  - Step 2: Call ASR.transcribe() → check status, stop if FAILED
  - Step 3: Call Translation.translate() → check status, stop if FAILED
  - Step 4: Call TTS.synthesize() → check status, return result
  - Step 5: Encode dubbed audio (PCM → base64)
  - Step 6: Build FragmentResult payload with all data

- [x] T081 [US1] Implement asset lineage tracking in `apps/sts-service/src/sts_service/full/pipeline.py` (Size: M, Priority: P1)
  - Generate unique asset IDs for each stage (TranscriptAsset, TranslationAsset, AudioAsset)
  - Link parent_asset_ids: TranslationAsset → TranscriptAsset ID, AudioAsset → TranslationAsset ID
  - Include fragment_id and stream_id in all assets for traceability

- [x] T082 [US1] Implement stage timing tracking in `apps/sts-service/src/sts_service/full/pipeline.py` (Size: M, Priority: P1)
  - Measure latency for each stage (ASR, Translation, TTS) using time.perf_counter()
  - Populate FragmentResult.stage_timings with asr_ms, translation_ms, tts_ms
  - Calculate total processing_time_ms (sum of stages + overhead)

- [x] T083 [US2] Implement error propagation in `apps/sts-service/src/sts_service/full/pipeline.py` (Size: M, Priority: P1)
  - After each stage, check Asset.status
  - If FAILED, construct FragmentResult with status=FAILED, error from Asset
  - Stop pipeline immediately, do not proceed to next stage
  - Preserve error.stage, error.code, error.retryable from Asset

- [x] T084 [US1] Create FragmentQueue for in-order delivery in `apps/sts-service/src/sts_service/full/fragment_queue.py` (Size: L, Priority: P1)
  - Priority queue (heapq) sorted by sequence_number
  - Method `add_fragment(fragment_result: FragmentResult, sequence_number: int)`
  - Method `async def get_next_in_order() -> FragmentResult` (blocks until next sequence available)
  - Track next_expected_sequence_number

- [x] T085 [US3] Create BackpressureTracker class in `apps/sts-service/src/sts_service/full/backpressure_tracker.py` (Size: M, Priority: P2)
  - Track in_flight count per stream
  - Method `increment_inflight()`, `decrement_inflight()`
  - Method `get_backpressure_state() -> BackpressureState`
    - in_flight 1-3 → severity="low", action="none"
    - in_flight 4-6 → severity="medium", action="slow_down"
    - in_flight 7-10 → severity="high", action="pause"
  - Method `should_reject_fragment() -> bool` (in_flight >10 → True)

- [x] T086 [US3] Integrate BackpressureTracker into PipelineCoordinator in `apps/sts-service/src/sts_service/full/pipeline.py` (Size: M, Priority: P2)
  - Increment in_flight when fragment received
  - Decrement in_flight when fragment:processed emitted
  - Emit backpressure event when threshold crossed
  - Reject fragment if critical threshold exceeded (>10)

- [x] T087 [US1] Re-run Pipeline unit tests (Size: S, Priority: P1)
  - Verify `pytest apps/sts-service/tests/unit/full/test_pipeline_coordinator.py -v` PASSES
  - Verify coverage ≥95% for pipeline orchestration logic

- [ ] T088 [US1] Re-run Pipeline integration tests (Size: M, Priority: P1)
  - Verify `pytest apps/sts-service/tests/integration/full/test_full_pipeline_asr_to_tts.py -v` PASSES
  - Measure end-to-end latency (should be <8s)

**Checkpoint**: Phase 2 complete - Pipeline orchestration functional, in-order delivery validated ✅

---

## Phase 3: Socket.IO Server Integration (PRIORITY: P1)

**Goal**: Extend Echo STS server patterns for Full STS with fragment processing.

**Dependencies**: Phase 5 (PipelineCoordinator required)
**Estimated Time**: 3-4 days
**Success Criteria**: All Socket.IO events handled, fragment:ack <50ms, fragment:processed in-order

### Tests for Phase 3 (MANDATORY - Test-First) ✅

**Coverage Target**: 80% minimum

- [ ] T089 [P] [US1] **Unit test** for stream:init validates config in `apps/sts-service/tests/unit/full/test_handlers_stream.py` (Size: M, Priority: P1)
  - Mock sio.emit
  - Send stream:init with valid config (source_language="en", target_language="es", voice_profile="spanish_male_1")
  - Assert emits stream:ready with session_id, max_inflight=3, capabilities

- [ ] T090 [P] [US1] **Unit test** for stream:init validates voice_profile in `apps/sts-service/tests/unit/full/test_handlers_stream.py` (Size: M, Priority: P1)
  - Send stream:init with invalid voice_profile="nonexistent"
  - Assert emits error event with code="INVALID_VOICE_PROFILE"

- [ ] T091 [P] [US1] **Unit test** for stream:init initializes ASR/Translation/TTS in `apps/sts-service/tests/unit/full/test_handlers_stream.py` (Size: M, Priority: P1)
  - Mock ASR.get_model(), Translation.client, TTS.get_model()
  - Send stream:init
  - Assert all modules initialized (call counts > 0)

- [ ] T092 [P] [US5] **Unit test** for stream:pause rejects new fragments in `apps/sts-service/tests/unit/full/test_handlers_stream.py` (Size: M, Priority: P3)
  - Initialize stream, send stream:pause
  - Send fragment:data
  - Assert emits error event with code="STREAM_PAUSED"

- [ ] T093 [P] [US5] **Unit test** for stream:resume accepts fragments in `apps/sts-service/tests/unit/full/test_handlers_stream.py` (Size: S, Priority: P3)
  - Pause stream, then send stream:resume
  - Send fragment:data
  - Assert emits fragment:ack (not error)

- [ ] T094 [P] [US5] **Unit test** for stream:end emits statistics in `apps/sts-service/tests/unit/full/test_handlers_stream.py` (Size: M, Priority: P3)
  - Process 5 fragments (4 success, 1 failed)
  - Send stream:end
  - Assert emits stream:complete with total_fragments=5, success_count=4, failed_count=1, avg_processing_time_ms

- [ ] T095 [P] [US1] **Unit test** for fragment:data emits immediate ack in `apps/sts-service/tests/unit/full/test_handlers_fragment.py` (Size: M, Priority: P1)
  - Mock sio.emit
  - Send fragment:data
  - Assert emits fragment:ack within <50ms with status="queued"

- [ ] T096 [P] [US1] **Unit test** for fragment:data calls pipeline in `apps/sts-service/tests/unit/full/test_handlers_fragment.py` (Size: M, Priority: P1)
  - Mock PipelineCoordinator.process_fragment()
  - Send fragment:data
  - Assert process_fragment() called with FragmentData

- [ ] T097 [P] [US1] **Unit test** for fragment:processed emitted on success in `apps/sts-service/tests/unit/full/test_handlers_fragment.py` (Size: M, Priority: P1)
  - Mock Pipeline to return SUCCESS FragmentResult
  - Send fragment:data
  - Assert emits fragment:processed with status="success", dubbed_audio, transcript, translated_text

- [ ] T098 [P] [US2] **Unit test** for fragment:processed emitted on failure in `apps/sts-service/tests/unit/full/test_handlers_fragment.py` (Size: M, Priority: P1)
  - Mock Pipeline to return FAILED FragmentResult (ASR timeout)
  - Send fragment:data
  - Assert emits fragment:processed with status="failed", error.stage="asr", error.code="TIMEOUT"

- [ ] T099 [P] [US1] **Unit test** for connection saves session in `apps/sts-service/tests/unit/full/test_handlers_lifecycle.py` (Size: S, Priority: P1)
  - Mock sio.save_session()
  - Trigger connect event with X-Stream-ID, X-Worker-ID headers
  - Assert session saved with stream_id, worker_id metadata

- [ ] T100 [P] [US1] **Unit test** for disconnect cleans up in `apps/sts-service/tests/unit/full/test_handlers_lifecycle.py` (Size: S, Priority: P1)
  - Mock session cleanup
  - Trigger disconnect event
  - Assert session removed, in-flight fragments cleared

- [ ] T101 [P] [US1] **Integration test** for client connects and initializes in `apps/sts-service/tests/integration/full/test_socketio_event_flow.py` (Size: L, Priority: P1)
  - Start Full STS server (python-socketio AsyncClient)
  - Connect → send stream:init → receive stream:ready
  - Assert session_id, max_inflight in response

- [ ] T102 [P] [US1] **Integration test** for client sends fragment receives processed in `apps/sts-service/tests/integration/full/test_socketio_event_flow.py` (Size: L, Priority: P1)
  - Send fragment:data → receive fragment:ack → receive fragment:processed
  - Assert fragment:processed contains dubbed_audio, transcript, translated_text
  - Assert latency <8s

- [ ] T103 [P] [US3] **Integration test** for client receives backpressure event in `apps/sts-service/tests/integration/full/test_socketio_event_flow.py` (Size: M, Priority: P2)
  - Send 5 fragments rapidly (in_flight >3)
  - Assert receives backpressure event with severity="medium", action="slow_down"

- [ ] T104 [P] [US5] **Integration test** for client ends stream receives complete in `apps/sts-service/tests/integration/full/test_socketio_event_flow.py` (Size: M, Priority: P3)
  - Send stream:end → receive stream:complete with statistics
  - Assert connection closes after 5s

**Verification**: Run `pytest apps/sts-service/tests/unit/full/test_handlers_*.py -v` - ALL tests MUST FAIL

### Implementation for Phase 3

- [ ] T105 [US1] Create Socket.IO server setup in `apps/sts-service/src/sts_service/full/server.py` (Size: M, Priority: P1)
  - Initialize AsyncServer with async_mode='asgi'
  - Combine with FastAPI for /health, /metrics endpoints
  - Create ASGIApp combining Socket.IO and FastAPI

- [ ] T106 [US1] Create SessionStore in `apps/sts-service/src/sts_service/full/session.py` (Size: M, Priority: P1)
  - Extend Echo STS SessionStore pattern
  - Store StreamSession per sid (session ID)
  - Methods: create_session(), get_session(), update_session(), delete_session()
  - Store session state: config, statistics, inflight_tracker, pipeline_coordinator

- [ ] T107 [US1] Create STSNamespace class in `apps/sts-service/src/sts_service/full/handlers/__init__.py` (Size: M, Priority: P1)
  - Inherit from socketio.AsyncNamespace
  - Register event handlers: on_connect, on_disconnect, on_stream_init, on_fragment_data, on_stream_pause, on_stream_resume, on_stream_end

- [ ] T108 [US1] Implement stream:init handler in `apps/sts-service/src/sts_service/full/handlers/stream.py` (Size: L, Priority: P1)
  - Validate stream:init payload using StreamConfig model
  - Validate voice_profile exists in voices.json
  - Initialize ASR, Translation, TTS modules
  - Create StreamSession with config, state=initializing
  - Emit stream:ready with session_id, max_inflight=3, capabilities
  - Update session state to active

- [ ] T109 [US5] Implement stream:pause handler in `apps/sts-service/src/sts_service/full/handlers/stream.py` (Size: M, Priority: P3)
  - Update session state to paused
  - Allow in-flight fragments to complete
  - Reject new fragment:data with error code="STREAM_PAUSED"

- [ ] T110 [US5] Implement stream:resume handler in `apps/sts-service/src/sts_service/full/handlers/stream.py` (Size: S, Priority: P3)
  - Update session state to active
  - Accept new fragment:data normally

- [ ] T111 [US5] Implement stream:end handler in `apps/sts-service/src/sts_service/full/handlers/stream.py` (Size: M, Priority: P3)
  - Wait for in-flight fragments to complete (asyncio.wait_for with timeout)
  - Calculate statistics: total_fragments, success_count, failed_count, avg_processing_time_ms
  - Emit stream:complete with statistics
  - Schedule connection close after 5s (asyncio.create_task)

- [ ] T112 [US1] Implement fragment:data handler in `apps/sts-service/src/sts_service/full/handlers/fragment.py` (Size: L, Priority: P1)
  - Validate fragment:data payload using FragmentData model
  - Check session state (reject if paused or not initialized)
  - Emit fragment:ack immediately with status="queued"
  - Increment in_flight count (BackpressureTracker)
  - Call PipelineCoordinator.process_fragment() asynchronously
  - Add result to FragmentQueue for in-order emission

- [ ] T113 [US1] Implement fragment:processed emission in `apps/sts-service/src/sts_service/full/handlers/fragment.py` (Size: M, Priority: P1)
  - Background task: FragmentQueue.get_next_in_order()
  - Emit fragment:processed with FragmentResult payload
  - Decrement in_flight count
  - Update session statistics (increment success/failed count, track processing time)
  - Check backpressure state, emit backpressure event if threshold crossed

- [ ] T114 [US1] Implement connect handler in `apps/sts-service/src/sts_service/full/handlers/lifecycle.py` (Size: M, Priority: P1)
  - Extract X-Stream-ID, X-Worker-ID from environ headers
  - Create initial session with stream_id, worker_id, state=connected
  - Save session using sio.save_session(sid, session_data)
  - Log connection with stream_id, worker_id

- [ ] T115 [US1] Implement disconnect handler in `apps/sts-service/src/sts_service/full/handlers/lifecycle.py` (Size: M, Priority: P1)
  - Retrieve session data
  - Clean up resources (cancel in-flight tasks, clear queue)
  - Delete session
  - Log disconnect with stream_id, worker_id, reason

- [ ] T116 [US1] Create main entry point in `apps/sts-service/src/sts_service/full/__main__.py` (Size: S, Priority: P1)
  - Load configuration from environment
  - Initialize voice profiles (load voices.json)
  - Pre-load ASR, Translation, TTS models (warm start)
  - Register STSNamespace with Socket.IO server
  - Run with uvicorn: `uvicorn sts_service.full.server:app --host 0.0.0.0 --port 8000`

- [ ] T117 [US1] Re-run Socket.IO unit tests (Size: S, Priority: P1)
  - Verify `pytest apps/sts-service/tests/unit/full/test_handlers_*.py -v` PASSES
  - Verify coverage ≥80%

- [ ] T118 [US1] Re-run Socket.IO integration tests (Size: M, Priority: P1)
  - Verify `pytest apps/sts-service/tests/integration/full/test_socketio_event_flow.py -v` PASSES
  - Measure fragment:ack latency (<50ms), end-to-end latency (<8s)

**Checkpoint**: Phase 3 complete - Socket.IO server functional, all events handled ✅

---

## Phase 4: Observability (PRIORITY: P2)

**Goal**: Add Prometheus metrics and structured logging for production monitoring.

**Dependencies**: Phase 6 (handlers required)
**Estimated Time**: 2 days
**Success Criteria**: All metrics exposed, logs include fragment_id/stream_id

### Tests for Phase 4 (MANDATORY - Test-First) ✅

**Coverage Target**: 80% minimum

- [ ] T119 [P] [US4] **Unit test** for metrics recorded on success in `apps/sts-service/tests/unit/full/test_metrics.py` (Size: M, Priority: P2)
  - Mock prometheus_client metrics
  - Process fragment successfully
  - Assert sts_fragment_processing_seconds histogram incremented with status="success"
  - Assert sts_asr_duration_seconds, sts_translation_duration_seconds, sts_tts_duration_seconds updated

- [ ] T120 [P] [US4] **Unit test** for metrics recorded on failure in `apps/sts-service/tests/unit/full/test_metrics.py` (Size: M, Priority: P2)
  - Process fragment with ASR failure
  - Assert sts_fragment_errors_total counter incremented with stage="asr", error_code="TIMEOUT"

- [ ] T121 [P] [US4] **Unit test** for GPU utilization tracked in `apps/sts-service/tests/unit/full/test_metrics.py` (Size: M, Priority: P2)
  - Mock pynvml (NVIDIA GPU monitoring library)
  - Assert sts_gpu_utilization_percent gauge updated
  - Assert sts_gpu_memory_used_bytes gauge updated

- [ ] T122 [P] [US4] **Unit test** for in-flight gauge updated in `apps/sts-service/tests/unit/full/test_metrics.py` (Size: S, Priority: P2)
  - Increment in_flight count
  - Assert sts_fragments_in_flight gauge reflects current count

- [ ] T123 [P] [US4] **Unit test** for logs include fragment_id in `apps/sts-service/tests/unit/full/test_logging.py` (Size: M, Priority: P2)
  - Mock logging handler
  - Process fragment
  - Assert log entries include fragment_id, stream_id, sequence_number fields

- [ ] T124 [P] [US4] **Unit test** for stage timings logged in `apps/sts-service/tests/unit/full/test_logging.py` (Size: S, Priority: P2)
  - Process fragment
  - Assert log entry includes asr_duration_ms, translation_duration_ms, tts_duration_ms

- [ ] T125 [P] [US4] **Integration test** for /metrics endpoint in `apps/sts-service/tests/integration/full/test_metrics_endpoint.py` (Size: M, Priority: P2)
  - Start Full STS server
  - Query GET /metrics (HTTP)
  - Assert response is Prometheus format (text/plain)
  - Assert includes sts_fragment_processing_seconds, sts_fragments_in_flight, sts_gpu_utilization_percent

**Verification**: Run `pytest apps/sts-service/tests/unit/full/test_metrics.py -v` - ALL tests MUST FAIL

### Implementation for Phase 4

- [ ] T126 [US4] Create Prometheus metrics in `apps/sts-service/src/sts_service/full/metrics.py` (Size: L, Priority: P2)
  - Histogram: sts_fragment_processing_seconds (labels: status, stream_id)
  - Histogram: sts_asr_duration_seconds, sts_translation_duration_seconds, sts_tts_duration_seconds
  - Gauge: sts_fragments_in_flight (labels: stream_id)
  - Counter: sts_fragment_errors_total (labels: stage, error_code)
  - Gauge: sts_gpu_utilization_percent, sts_gpu_memory_used_bytes
  - Function to record metrics: record_fragment_success(), record_fragment_failure(), record_stage_timing()

- [ ] T127 [US4] Integrate metrics into handlers in `apps/sts-service/src/sts_service/full/handlers/fragment.py` (Size: M, Priority: P2)
  - Record sts_fragment_processing_seconds on fragment:processed emission
  - Record stage timings (ASR, Translation, TTS) from FragmentResult
  - Record errors with stage and code labels
  - Update sts_fragments_in_flight on increment/decrement

- [ ] T128 [US4] Add /metrics endpoint in `apps/sts-service/src/sts_service/full/server.py` (Size: S, Priority: P2)
  - FastAPI route: @app.get("/metrics")
  - Return prometheus_client.generate_latest() response
  - Content-Type: text/plain

- [ ] T129 [US4] Create GPU monitoring background task in `apps/sts-service/src/sts_service/full/metrics.py` (Size: M, Priority: P2)
  - Use pynvml to query GPU utilization and memory every 5 seconds
  - Update sts_gpu_utilization_percent, sts_gpu_memory_used_bytes gauges
  - Start background task on server startup (asyncio.create_task)

- [ ] T130 [US4] Create structured logging configuration in `apps/sts-service/src/sts_service/full/logging_config.py` (Size: M, Priority: P2)
  - Use structlog or python-json-logger for JSON output
  - Configure log format: timestamp, level, message, fragment_id, stream_id, sequence_number
  - Set log level from environment (default INFO)

- [ ] T131 [US4] Integrate logging into handlers in `apps/sts-service/src/sts_service/full/handlers/` (Size: M, Priority: P2)
  - Log fragment:data received with fragment_id, stream_id, sequence_number
  - Log pipeline processing start/end with stage timings
  - Log errors with error.stage, error.code, error.retryable
  - Log backpressure events with severity, action

- [ ] T132 [US4] Re-run observability unit tests (Size: S, Priority: P2)
  - Verify `pytest apps/sts-service/tests/unit/full/test_metrics.py -v` PASSES
  - Verify `pytest apps/sts-service/tests/unit/full/test_logging.py -v` PASSES

- [ ] T133 [US4] Re-run observability integration tests (Size: M, Priority: P2)
  - Verify `pytest apps/sts-service/tests/integration/full/test_metrics_endpoint.py -v` PASSES
  - Query /metrics manually, verify all expected metrics present

**Checkpoint**: Phase 4 complete - Observability functional, metrics and logs validated ✅

---

## Phase 5: Configuration & Deployment (PRIORITY: P3)

**Goal**: Environment variable configuration, Docker image, deployment documentation.

**Dependencies**: Phases 1-7 (all implementation complete)
**Estimated Time**: 2 days
**Success Criteria**: Docker image builds, service starts with environment variables

### Implementation for Phase 5

- [ ] T134 [P] [US5] Create configuration module in `apps/sts-service/src/sts_service/full/config.py` (Size: M, Priority: P3)
  - Load environment variables: PORT (default 8000), DEEPL_API_KEY (required), ASR_MODEL_PATH, TTS_MODEL_PATH, VOICE_PROFILES_PATH
  - Backpressure thresholds: BACKPRESSURE_THRESHOLD_LOW=3, MEDIUM=6, HIGH=10, CRITICAL=10
  - Timeouts: ASR_TIMEOUT_MS=5000, TRANSLATION_TIMEOUT_MS=5000, TTS_TIMEOUT_MS=10000
  - Duration variance: DURATION_VARIANCE_SUCCESS_MAX=0.10, PARTIAL_MAX=0.20
  - Validate required variables on startup, fail fast if missing

- [ ] T135 [P] [US5] Create Dockerfile for Full STS in `apps/sts-service/deploy/Dockerfile.full` (Size: L, Priority: P3)
  - Base image: nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04
  - Install Python 3.10, pip, GStreamer (for future RTMP support), rubberband
  - Copy source code from apps/sts-service/src/
  - Install dependencies from requirements.txt (python-socketio, faster-whisper, deepl, TTS, torch, etc.)
  - Download faster-whisper medium model (or mount as volume)
  - Download XTTS v2 model (or mount as volume)
  - Set entrypoint: CMD ["python", "-m", "sts_service.full"]
  - Expose port 8000

- [ ] T136 [P] [US5] Create docker-compose.yml for Full STS in `apps/sts-service/docker-compose.full.yml` (Size: M, Priority: P3)
  - Service: full-sts-service
  - Build: deploy/Dockerfile.full
  - GPU support: deploy.resources.reservations.devices (NVIDIA GPU)
  - Environment variables: DEEPL_API_KEY, PORT, MODEL_PATHS
  - Volume mounts: ./config/voices.json:/config/voices.json:ro, ./models:/models:ro
  - Ports: 8000:8000
  - Healthcheck: curl http://localhost:8000/health

- [ ] T137 [P] [US5] Update requirements.txt in `apps/sts-service/requirements.txt` (Size: M, Priority: P3)
  - Add production dependencies: python-socketio>=5.0, uvicorn>=0.24.0, fastapi>=0.100.0
  - Add ASR: faster-whisper>=0.9.0 (CUDA support)
  - Add Translation: deepl>=1.15.0
  - Add TTS: TTS (Coqui TTS library), torch>=2.0, torchaudio
  - Add observability: prometheus_client>=0.18.0, structlog>=23.0.0, pynvml>=11.5.0
  - Add utilities: pydantic>=2.0, numpy, pydub, rubberband-py (Python wrapper)
  - Lock versions with `pip freeze > requirements.txt`

- [ ] T138 [P] [US5] Create quickstart.md in `specs/021-full-sts-service/quickstart.md` (Size: L, Priority: P3)
  - **Section 1: Developer Setup** - Clone repo, install dependencies, download models
  - **Section 2: Configuration** - Set DEEPL_API_KEY, create voices.json, configure GPU
  - **Section 3: Running Locally** - `docker-compose -f apps/sts-service/docker-compose.full.yml up`
  - **Section 4: Testing** - `pytest apps/sts-service/tests/unit/full/ -v`, `pytest apps/sts-service/tests/integration/full/ -v`
  - **Section 5: Testing with Socket.IO Client** - Example python-socketio client to send fragment:data
  - **Section 6: Deployment to RunPod** - Docker image push, pod configuration, environment variables
  - **Section 7: Troubleshooting** - Common issues (GPU OOM, DeepL API errors, voice profile not found)

- [ ] T139 [US5] Build and test Docker image locally (Size: M, Priority: P3)
  - Build: `docker build -f apps/sts-service/deploy/Dockerfile.full -t full-sts-service:latest .`
  - Run: `docker-compose -f apps/sts-service/docker-compose.full.yml up`
  - Test health endpoint: `curl http://localhost:8000/health` (should return 200)
  - Test Socket.IO connection: Use python-socketio client to connect, send stream:init, receive stream:ready
  - Test fragment processing: Send fragment:data, verify fragment:ack and fragment:processed received

- [ ] T140 [US5] Create .env.example in `apps/sts-service/.env.example` (Size: S, Priority: P3)
  - Document all required environment variables: DEEPL_API_KEY, PORT, MODEL_PATHS, VOICE_PROFILES_PATH
  - Include example values for development

**Checkpoint**: Phase 5 complete - Docker image functional, documentation complete ✅

---

## Phase 6: E2E Testing (PRIORITY: P3)

**Goal**: Validate full pipeline with media-service integration.

**Dependencies**: Phase 8 (deployment artifacts required)
**Estimated Time**: 2 days
**Success Criteria**: All E2E tests pass, full pipeline validated

### Tests for Phase 6 (MANDATORY - Test-First) ✅

**Coverage Target**: E2E validation only (not included in code coverage)

- [ ] T141 [P] [US1] **E2E test** for full pipeline media→STS→output in `tests/e2e/test_full_pipeline.py` (Size: L, Priority: P1)
  - Start MediaMTX, media-service, Full STS service via Docker Compose
  - Publish 1-min-nfl.mp4 (English speech) to MediaMTX RTSP endpoint
  - media-service processes stream, sends fragments to Full STS via Socket.IO
  - Full STS performs ASR→Translation→TTS, returns dubbed audio
  - media-service publishes dubbed output to MediaMTX RTMP endpoint
  - Validate RTMP output stream exists, contains dubbed audio
  - Validate A/V sync (duration variance <10%)
  - Validate transcription accuracy (compare against expected transcript)

- [ ] T142 [P] [US1] **E2E test** for ASR/Translation/TTS accuracy in `tests/e2e/test_full_pipeline.py` (Size: M, Priority: P1)
  - Extract fragment from output stream
  - Validate transcript matches expected English text (>90% word accuracy)
  - Validate translation matches expected Spanish text (manual review or BLEU score >30)
  - Validate dubbed audio has Spanish speech (manual listening or ASR verification)

- [ ] T143 [P] [US1] **E2E test** for A/V sync maintained in `tests/e2e/test_full_pipeline.py` (Size: M, Priority: P1)
  - Compare original fragment duration vs. dubbed fragment duration
  - Assert duration variance <10% for all fragments
  - Validate no drift over time (cumulative duration variance <5%)

- [ ] T144 [P] [US3] **E2E test** for backpressure slows worker in `tests/e2e/test_resilience.py` (Size: M, Priority: P2)
  - Configure Full STS with max_inflight=3
  - Send fragments rapidly from media-service (>3 in-flight)
  - Assert media-service receives backpressure event with severity="medium", action="slow_down"
  - Assert media-service slows fragment submission rate
  - Assert no GPU OOM errors occur

- [ ] T145 [P] [US2] **E2E test** for circuit breaker on STS failures in `tests/e2e/test_resilience.py` (Size: M, Priority: P2)
  - Inject ASR timeout errors (mock or rate limit)
  - Assert media-service receives fragment:processed with status="failed", error.retryable=true
  - Assert media-service retries fragment (exponential backoff)
  - Assert circuit breaker opens after threshold failures
  - Assert media-service falls back to original audio

- [ ] T146 [P] [US5] **E2E test** for worker reconnects after disconnect in `tests/e2e/test_reconnection.py` (Size: M, Priority: P3)
  - Start Full STS service, connect media-service worker
  - Kill Full STS service (simulate crash)
  - Assert worker detects disconnect
  - Restart Full STS service
  - Assert worker reconnects, reinitializes stream with stream:init
  - Assert fragment processing resumes normally

**Verification**: Run `pytest tests/e2e/test_full_pipeline.py -v` - Tests should PASS after Phase 6-8 implementation

### Implementation for Phase 6

- [ ] T147 [P] [US1] Create E2E test fixtures in `tests/e2e/fixtures/` (Size: M, Priority: P1)
  - Copy 1-min-nfl.mp4 test stream to fixtures/test_streams/
  - Create expected transcript file: fixtures/expected_transcripts/1-min-nfl_en.txt
  - Create expected translation file: fixtures/expected_translations/1-min-nfl_es.txt

- [ ] T148 [US1] Update E2E docker-compose.yml in `tests/e2e/docker-compose.yml` (Size: M, Priority: P1)
  - Add full-sts-service with GPU support
  - Link to media-service and MediaMTX
  - Environment variables: DEEPL_API_KEY, STS_SERVICE_URL=http://full-sts-service:8000
  - Volume mounts: voices.json, models/

- [ ] T149 [US1] Implement E2E test helpers in `tests/e2e/helpers/` (Size: L, Priority: P1)
  - Update socketio_monitor.py to listen for Full STS events (fragment:processed, backpressure)
  - Update stream_analyzer.py to validate dubbed audio format (ffprobe)
  - Create transcript_validator.py to compare ASR output vs. expected transcript (word accuracy)

- [ ] T150 [US1] Run E2E tests and validate (Size: L, Priority: P1)
  - Start services: `make e2e-up`
  - Run tests: `pytest tests/e2e/test_full_pipeline.py -v --log-cli-level=INFO`
  - Verify all tests PASS
  - Measure end-to-end latency (target <8s per fragment)
  - Stop services: `make e2e-down`

**Checkpoint**: Phase 6 complete - E2E tests pass, full pipeline validated ✅

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Data Models)**: No dependencies - can start immediately
- **Phase 2 (ASR Module)**: Depends on Phase 1 (Asset models required)
- **Phase 3 (Translation Module)**: Depends on Phase 1 (Asset models required)
- **Phase 4 (TTS Module)**: Depends on Phase 1 (Asset models required)
- **Phase 5 (Pipeline Coordinator)**: Depends on Phases 2, 3, 4 (all modules required)
- **Phase 6 (Socket.IO Server)**: Depends on Phase 5 (PipelineCoordinator required)
- **Phase 7 (Observability)**: Depends on Phase 6 (handlers required)
- **Phase 8 (Deployment)**: Depends on Phases 1-7 (all implementation complete)
- **Phase 9 (E2E Testing)**: Depends on Phase 8 (deployment artifacts required)

### Critical Path (P1 Tasks)

**Fastest path to MVP (US1: Complete STS Pipeline)**:
1. Phase 1: Data Models & Contracts (2-3 days) → T001-T023
2. Phase 2: ASR Module (2-3 days) → T024-T035 (can run parallel with Phase 3, 4)
3. Phase 3: Translation Module (1-2 days) → T036-T047 (can run parallel with Phase 2, 4)
4. Phase 4: TTS Module (3-4 days) → T048-T065 (can run parallel with Phase 2, 3)
5. Phase 5: Pipeline Coordinator (3-4 days) → T066-T088
6. Phase 6: Socket.IO Server (3-4 days) → T089-T118
7. **MVP Complete** - Full STS pipeline functional ✅

**Total MVP Time**: ~15-20 days (assuming sequential execution)

### Parallel Opportunities

**After Phase 1 completes, Phases 2, 3, 4 can run in parallel** (if team has 3 developers):
- Developer A: ASR Module (Phase 2)
- Developer B: Translation Module (Phase 3)
- Developer C: TTS Module (Phase 4)
- **Time savings**: 3-4 days (instead of 6-9 days sequential)

**Phase 7 (Observability) can run parallel with Phase 8 (Deployment)**:
- Developer A: Metrics and logging (Phase 7)
- Developer B: Docker image and docs (Phase 8)
- **Time savings**: 2 days

### Incremental Delivery Strategy

**MVP 1: Core Pipeline (P1 User Stories)**
- Phases 1-6 → US1 (Complete STS Pipeline) + US2 (Error Handling)
- **Deliverable**: Full STS service processes fragments, returns dubbed audio
- **Demo**: Send fragment:data via Socket.IO client, receive fragment:processed with Spanish dubbed audio

**MVP 2: Production Readiness (P2 User Stories)**
- Phase 5 (Backpressure) + Phase 7 (Observability) → US3 (Backpressure) + US4 (Observability)
- **Deliverable**: Backpressure monitoring, Prometheus metrics, structured logs
- **Demo**: Query /metrics endpoint, send high fragment rate to trigger backpressure

**MVP 3: Operational Features (P3 User Stories)**
- Phase 8 (Deployment) + Phase 9 (E2E) → US5 (Lifecycle Management)
- **Deliverable**: Docker image, deployment docs, E2E tests
- **Demo**: Deploy to RunPod, run E2E test with media-service

---

## Test Coverage Summary

### Unit Tests
- **Phase 1**: 10 contract tests (100% of contracts)
- **Phase 2**: 6 ASR unit tests (95% coverage for transcribe function)
- **Phase 3**: 6 Translation unit tests (80% coverage)
- **Phase 4**: 9 TTS unit tests (95% coverage for duration matching)
- **Phase 5**: 13 Pipeline unit tests (95% coverage)
- **Phase 6**: 12 Socket.IO unit tests (80% coverage)
- **Phase 7**: 6 Observability unit tests (80% coverage)
- **Total Unit Tests**: 62 tests

### Integration Tests
- **Phase 2**: 1 ASR integration test (optional, requires GPU)
- **Phase 3**: 1 Translation integration test (optional, requires API key)
- **Phase 4**: 1 TTS integration test (optional, requires GPU)
- **Phase 5**: 2 Pipeline integration tests
- **Phase 6**: 4 Socket.IO integration tests
- **Phase 7**: 1 Observability integration test
- **Total Integration Tests**: 10 tests

### E2E Tests
- **Phase 9**: 6 E2E tests (full pipeline validation)
- **Total E2E Tests**: 6 tests

**Grand Total**: 78 tests across all levels

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story (US1-US5) for traceability
- Size: S (<4h), M (4-8h), L (8h+)
- Priority: P1 (critical), P2 (high), P3 (medium)
- Tests MUST be written FIRST and MUST FAIL before implementation (TDD)
- Coverage enforcement: 80% minimum, 95% for critical paths (ASR, Translation, TTS, Pipeline)
- Checkpoints are informational - run automated tests to validate, then continue
- Commit after each task or logical group (e.g., after all Phase 1 tests pass)

---

## Quick Reference Commands

**Run all tests**:
```bash
# Unit tests only
pytest apps/sts-service/tests/unit/full/ -v --cov=sts_service.full --cov-report=term-missing

# Contract tests only
pytest apps/sts-service/tests/contract/ -v

# Integration tests only
pytest apps/sts-service/tests/integration/full/ -v

# E2E tests only (requires services running)
make e2e-up
pytest tests/e2e/test_full_pipeline.py -v --log-cli-level=INFO
make e2e-down

# All tests with coverage
pytest apps/sts-service/tests/ --cov=sts_service.full --cov-fail-under=80 --cov-report=html
```

**Build and run Docker image**:
```bash
# Build
docker build -f apps/sts-service/deploy/Dockerfile.full -t full-sts-service:latest .

# Run
docker-compose -f apps/sts-service/docker-compose.full.yml up

# Test health
curl http://localhost:8000/health
```

**Development workflow** (TDD):
```bash
# 1. Write failing tests
# 2. Run tests - verify they FAIL
pytest apps/sts-service/tests/unit/full/test_<module>.py -v

# 3. Implement code
# 4. Run tests - verify they PASS
pytest apps/sts-service/tests/unit/full/test_<module>.py -v

# 5. Check coverage
pytest apps/sts-service/tests/unit/full/test_<module>.py --cov=sts_service.full.<module> --cov-report=term-missing

# 6. Commit
git add . && git commit -m "feat(full-sts): implement <feature>"
```
