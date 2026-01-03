# Implementation Plan: Full STS Service with Socket.IO Integration

**Branch**: `021-full-sts-service` | **Date**: 2026-01-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/021-full-sts-service/spec.md`

## Summary

The Full STS Service implements production-grade Speech-to-Speech (ASR → Translation → TTS) processing with Socket.IO integration for real-time bidirectional communication with media-service. This is the core component that transforms source audio fragments into dubbed audio fragments while maintaining real-time constraints (3-8 seconds added latency) and A/V synchronization.

**Technical Approach**:
- **ASR**: faster-whisper medium model (1.5GB, 3-4s latency, 3GB VRAM) loaded once as singleton
- **Translation**: DeepL API with hard fail strategy (no local fallback), worker implements retry
- **TTS**: Coqui TTS XTTS v2 (2-3GB VRAM) with voice profiles from JSON config, duration matching via rubberband
- **Backpressure**: Hybrid monitoring + soft cap (warnings at 4, 6, 10 in-flight, reject >10)
- **A/V Sync**: Soft limits (0-10% SUCCESS, 10-20% PARTIAL, >20% FAILED)
- **Socket.IO**: python-socketio AsyncServer with class-based namespace, reusing Echo STS patterns

**GPU Memory Budget**: 6GB total (3GB ASR + 2-3GB TTS + 500MB overhead) fits comfortably in 8GB target.

**Expected Latency**: 5-7.5 seconds (3-4s ASR + 0.2-0.5s Translation + 1-2s TTS + 0.3-1s overhead).

## Technical Context

**Language/Version**: Python 3.10.x (per constitution and pyproject.toml requirement >=3.10,<3.11)

**Primary Dependencies**:
- python-socketio>=5.0 (AsyncServer, ASGI integration)
- uvicorn>=0.24.0 (ASGI server)
- faster-whisper (ASR, CUDA acceleration)
- deepl (Translation API client)
- TTS (Coqui TTS XTTS v2)
- torch, torchaudio (GPU inference)
- pydantic>=2.0 (data models)
- prometheus_client (metrics)
- rubberband (time-stretching for duration matching)

**Storage**:
- In-memory session state (Socket.IO session store)
- Model cache (faster-whisper medium, XTTS v2, speaker embeddings)
- Voice profiles JSON configuration file (voices.json)
- Optional debug artifacts to local filesystem (when debug_artifacts=True)

**Testing**: pytest>=7.0, pytest-asyncio, pytest-mock, python-socketio[client] (Socket.IO client for testing)

**Target Platform**: RunPod GPU pod (NVIDIA GPU with 8GB+ VRAM, CUDA 11.8+, Docker with GPU passthrough)

**Project Type**: Service application (apps/sts-service/)

**Performance Goals**:
- P95 latency: <8 seconds (end-to-end ASR→Translation→TTS)
- Throughput: 3 concurrent streams per pod (max_inflight=3 per stream)
- ASR accuracy: >90% for clear speech
- Translation quality: BLEU score >30
- Duration variance: ±10% for SUCCESS status

**Constraints**:
- GPU VRAM: 6GB usage for 8GB target (2GB buffer)
- Real-time processing: Fragments must be processed in sequence_number order
- No persistent state: Stateless service, workers reconnect on failure
- DeepL API dependency: Hard fail if unavailable (no local fallback)
- A/V sync requirement: Duration variance <20% or fail

**Scale/Scope**:
- 56 functional requirements (spec.md)
- 5 user stories (P1: 2, P2: 2, P3: 1)
- **REUSE 3 existing modules** (ASR, Translation, TTS - 8,390 lines already implemented)
- **NEW: 1 core module** (Pipeline Coordinator + Socket.IO integration)
- 34 research code examples (research-cache.md)
- Target: 80% test coverage (95% for critical paths)
- **Estimated NEW code**: ~1,500-2,000 lines (implementation) + ~1,500-2,000 lines (tests)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle VIII - Test-First Development (NON-NEGOTIABLE)**:
- [x] Test strategy defined for all user stories (see Test Strategy section)
- [x] Mock patterns documented for Socket.IO events (fragment:data, fragment:processed)
- [x] Coverage targets specified (80% minimum, 95% for critical paths: ASR, Translation, TTS, Pipeline)
- [x] Test infrastructure matches constitution requirements (pytest, pytest-asyncio, pytest-mock)
- [x] Test organization follows standard structure (apps/sts-service/tests/{unit,contract,integration}/)

**Principle I - Real-Time First**:
- [x] Pipeline designed for streaming (ASR→Translation→TTS without batch buffering)
- [x] Target latency: 5-7.5s (within 3-8s budget)
- [x] In-order fragment processing (sequence_number ordering)
- [x] Async event handlers prevent blocking

**Principle II - Testability Through Isolation**:
- [x] All components independently testable (mocked ASR/Translation/TTS)
- [x] Mock Socket.IO client for testing event handling
- [x] Deterministic test fixtures (research-cache.md examples)
- [x] No live dependencies in unit/contract tests

**Principle III - Spec-Driven Development**:
- [x] Spec fully defined (spec.md with 56 functional requirements)
- [x] Research completed (research-cache.md with 34 code examples)
- [x] Clarifications resolved (5 critical decisions documented)
- [x] Implementation plan follows spec (this document)

**Principle IV - Observability & Debuggability**:
- [x] Structured logging with fragment_id, stream_id, sequence_number
- [x] Prometheus metrics (latency, error rate, GPU utilization)
- [x] Stage timings tracked (ASR, Translation, TTS)
- [x] Debug artifacts configurable (debug_artifacts=True)

**Principle V - Graceful Degradation**:
- [x] Error handling with retryable flags (transient vs permanent errors)
- [x] Backpressure monitoring (prevents GPU OOM)
- [x] Empty transcript/translation handling (return silence, not error)
- [x] Duration mismatch degradation (SUCCESS → PARTIAL → FAILED)

**Principle VI - A/V Sync Discipline**:
- [x] Duration matching implemented (target_duration_ms preserved)
- [x] Soft limits prevent extreme distortion (0-10% SUCCESS, 10-20% PARTIAL, >20% FAILED)
- [x] Rubberband time-stretching for quality preservation
- [x] Duration variance tracked in metadata

**Principle VII - Incremental Delivery**:
- [x] Implementation phases defined (see Implementation Phases section)
- [x] Phase 1-4 deliver core functionality (P1 user stories)
- [x] Phase 5-6 add robustness (P2 user stories)
- [x] Phase 7-8 add lifecycle management (P3 user stories)

## Project Structure

### Documentation (this feature)

```text
specs/021-full-sts-service/
├── spec.md              # Feature specification (56 functional requirements)
├── research-cache.md    # Technical research (34 code examples)
├── plan.md              # This file (implementation plan)
├── data-model.md        # Data models (Phase 1 output)
├── quickstart.md        # Developer quickstart (Phase 1 output)
├── contracts/           # API contracts (Phase 1 output)
│   ├── fragment-schema.json          # fragment:data, fragment:ack, fragment:processed
│   ├── stream-schema.json            # stream:init, stream:ready, stream:complete
│   ├── backpressure-schema.json      # backpressure event
│   └── error-schema.json             # error response structure
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created yet)
```

### Source Code (repository root)

```text
apps/sts-service/
├── pyproject.toml              # Package metadata and dependencies
├── requirements.txt            # Locked production dependencies
├── requirements-dev.txt        # Locked development/test dependencies
├── src/
│   └── sts_service/            # Python package (snake_case)
│       ├── __init__.py
│       ├── echo/               # Echo STS service (existing, spec 017)
│       │   ├── __init__.py
│       │   ├── server.py
│       │   ├── session.py
│       │   └── handlers/
│       │
│       └── full/               # Full STS service (NEW, this feature)
│           ├── __init__.py
│           ├── __main__.py           # Entry point (python -m sts_service.full)
│           ├── server.py             # Socket.IO server setup (extends echo/server.py)
│           ├── config.py             # Configuration management
│           ├── session.py            # Session store (extends echo/session.py)
│           ├── pipeline.py           # Pipeline coordinator (ASR→Translation→TTS)
│           ├── handlers/
│           │   ├── __init__.py
│           │   ├── stream.py         # stream:init, pause, resume, end handlers
│           │   ├── fragment.py       # fragment:data handler, fragment:processed emission
│           │   └── lifecycle.py      # Connection lifecycle (connect, disconnect)
│           ├── models/
│           │   ├── __init__.py
│           │   ├── stream.py         # Stream session models (StreamConfig, StreamState)
│           │   ├── fragment.py       # Fragment models (FragmentData, FragmentResult)
│           │   ├── asset.py          # Asset models (TranscriptAsset, TranslationAsset, AudioAsset)
│           │   └── error.py          # Error models (ErrorResponse, ErrorCode)
│           ├── metrics.py            # Prometheus metrics
│           └── logging_config.py     # Structured logging setup
│
├── tests/
│   ├── unit/                   # Unit tests (mocked dependencies)
│   │   ├── __init__.py
│   │   ├── full/               # Full STS unit tests
│   │   │   ├── __init__.py
│   │   │   ├── test_pipeline_coordinator.py
│   │   │   ├── test_fragment_ordering.py
│   │   │   ├── test_backpressure_tracker.py
│   │   │   ├── test_error_handling.py
│   │   │   └── test_metrics_emission.py
│   │
│   ├── contract/               # Contract tests (API schemas)
│   │   ├── __init__.py
│   │   ├── test_fragment_schemas.py
│   │   ├── test_stream_schemas.py
│   │   ├── test_backpressure_schema.py
│   │   └── test_error_schema.py
│   │
│   └── integration/            # Integration tests (real components)
│       ├── __init__.py
│       └── full/
│           ├── __init__.py
│           ├── test_full_pipeline_asr_to_tts.py
│           ├── test_socketio_event_flow.py
│           ├── test_duration_matching.py
│           └── test_multi_fragment_ordering.py
│
├── deploy/                     # Deployment configurations
│   └── Dockerfile              # Container image definition (GPU support)
│
├── config/                     # Configuration files
│   └── voices.json             # Voice profiles configuration
│
├── docker-compose.yml          # Local dev environment
└── README.md

tests/e2e/                      # Cross-service E2E tests (media-service + STS)
├── test_full_pipeline.py       # P1: Full dubbing pipeline (real STS)
├── test_pipeline_echo.py       # P1: Pipeline with Echo STS (basic test)
├── test_resilience.py          # P2: Fault tolerance
└── test_reconnection.py        # P3: Connection resilience
```

**Structure Decision**:
The Full STS Service is implemented as a new subpackage `sts_service.full/` within the existing `apps/sts-service/` service. This approach:
1. Reuses Socket.IO infrastructure from Echo STS (spec 017)
2. Shares common models and utilities (session management, event handling)
3. Allows independent deployment (python -m sts_service.full vs. python -m sts_service.echo)
4. Maintains clear separation between testing stub (Echo) and production service (Full)

## Test Strategy

### Test Levels for This Feature

**Unit Tests** (mandatory, 80% minimum coverage):
- **Target**: Pipeline coordinator orchestration, fragment ordering, error propagation, backpressure calculations, metrics emission
- **Tools**: pytest, pytest-asyncio, pytest-mock
- **Coverage**: 80% minimum, 95% for critical paths (pipeline coordinator, error handling)
- **Mocking**: Mock ASR module (return fake transcripts), mock Translation module (return fake translations), mock TTS module (return fake audio), mock Socket.IO emit
- **Location**: `apps/sts-service/tests/unit/full/`
- **Examples**:
  - `test_pipeline_coordinator_chains_components()` - Validates ASR→Translation→TTS flow with mocked components
  - `test_pipeline_handles_asr_failure()` - Validates error propagation when ASR returns FAILED
  - `test_fragment_ordering_by_sequence_number()` - Validates in-order delivery
  - `test_backpressure_emitted_at_threshold()` - Validates backpressure event emission
  - `test_retryable_flag_for_transient_errors()` - Validates error classification

**Contract Tests** (mandatory, 100% of contracts):
- **Target**: API contracts, event schemas (fragment:data, fragment:ack, fragment:processed, stream:init, stream:ready, backpressure, error)
- **Tools**: pytest with JSON schema validation (jsonschema library)
- **Coverage**: 100% of all contracts in `contracts/` directory
- **Mocking**: Use deterministic fixtures from research-cache.md
- **Location**: `apps/sts-service/tests/contract/`
- **Examples**:
  - `test_fragment_data_schema()` - Validates incoming fragment:data payload structure
  - `test_fragment_processed_success_schema()` - Validates outgoing fragment:processed (status: success)
  - `test_fragment_processed_failed_schema()` - Validates outgoing fragment:processed (status: failed)
  - `test_stream_ready_schema()` - Validates stream:ready payload
  - `test_backpressure_schema()` - Validates backpressure event structure
  - `test_error_response_schema()` - Validates error payload structure

**Integration Tests** (required for workflows, happy path + critical errors):
- **Target**: Full pipeline with real ASR, Translation, TTS components; Socket.IO event flow; duration matching accuracy
- **Tools**: pytest, pytest-asyncio, python-socketio[client]
- **Coverage**: Happy path (fragment:data → fragment:processed SUCCESS) + critical error scenarios (ASR timeout, DeepL API failure, TTS synthesis error)
- **Mocking**: Mock DeepL API with responses (use httpx mock or similar), use real ASR/TTS models if VRAM available, otherwise mock
- **Location**: `apps/sts-service/tests/integration/full/`
- **Examples**:
  - `test_full_pipeline_english_to_spanish()` - Real audio → ASR → Translation → TTS → dubbed audio
  - `test_duration_matching_preserves_sync()` - Validates A/V sync (±10% variance)
  - `test_socketio_client_receives_fragment_processed()` - Validates Socket.IO event flow
  - `test_multi_fragment_ordering()` - Send 5 fragments, verify in-order delivery
  - `test_empty_transcript_returns_silence()` - Silence fragment → empty transcript → silence output

**E2E Tests** (optional, validation only):
- **Target**: Complete flow: media-service → Full STS → dubbed output via Socket.IO
- **Tools**: pytest, Docker Compose (MediaMTX + media-service + Full STS), python-socketio[client]
- **Coverage**: Critical user journeys only (P1 user stories)
- **When**: Run on-demand, not in CI (requires GPU)
- **Location**: `tests/e2e/`
- **Examples**:
  - `test_full_pipeline_media_to_sts_to_output()` - RTSP stream → media-service → STS → RTMP output
  - `test_pipeline_handles_backpressure()` - High fragment rate → backpressure event → worker slows
  - `test_reconnection_after_sts_failure()` - STS service restart → worker reconnects → stream resumes

### Mock Patterns (Constitution Principle II)

**Socket.IO Event Mocks**:
```python
# Mock Socket.IO emit (unit tests)
@pytest.fixture
def mock_sio_emit(mocker):
    return mocker.patch('sts_service.full.server.sio.emit', new_callable=AsyncMock)

# Mock Socket.IO client (integration tests)
@pytest.fixture
async def socketio_client():
    client = socketio.AsyncClient()
    await client.connect('http://localhost:8000')
    yield client
    await client.disconnect()
```

**ASR Module Mocks**:
```python
# Mock ASR transcription (unit tests)
@pytest.fixture
def mock_asr_transcribe(mocker):
    async def fake_transcribe(audio_data, source_language):
        return {
            'status': 'success',
            'transcript': 'This is a test transcript.',
            'segments': [{'start': 0.0, 'end': 6.0, 'text': 'This is a test transcript.'}],
            'confidence': 0.95,
            'latency_ms': 3500
        }
    return mocker.patch('sts_service.full.pipeline.ASRModule.transcribe', new_callable=AsyncMock, side_effect=fake_transcribe)
```

**Translation Module Mocks**:
```python
# Mock DeepL translation (unit tests)
@pytest.fixture
def mock_translation_translate(mocker):
    async def fake_translate(text, source_lang, target_lang):
        return {
            'status': 'success',
            'translated_text': 'Esta es una transcripción de prueba.',
            'billed_characters': 30,
            'latency_ms': 250
        }
    return mocker.patch('sts_service.full.pipeline.TranslationModule.translate', new_callable=AsyncMock, side_effect=fake_translate)
```

**TTS Module Mocks**:
```python
# Mock TTS synthesis (unit tests)
@pytest.fixture
def mock_tts_synthesize(mocker):
    async def fake_synthesize(text, voice_profile, language, target_duration_ms):
        import numpy as np
        # Generate fake audio (6 seconds at 24kHz)
        fake_audio = np.random.randn(24000 * 6).astype(np.float32)
        return {
            'status': 'success',
            'audio': fake_audio,
            'sample_rate': 24000,
            'duration_ms': 6000,
            'variance': 0.05,  # 5% variance
            'latency_ms': 1500
        }
    return mocker.patch('sts_service.full.pipeline.TTSModule.synthesize', new_callable=AsyncMock, side_effect=fake_synthesize)
```

**Deterministic Audio Fixtures** (from research-cache.md):
```python
# Generate deterministic PCM audio for testing
@pytest.fixture
def sample_audio_fragment():
    import numpy as np
    import base64

    # 6 seconds at 48kHz, mono, 16-bit PCM
    sample_rate = 48000
    duration_s = 6
    frequency = 440  # A4 note

    t = np.linspace(0, duration_s, int(sample_rate * duration_s))
    audio = np.sin(2 * np.pi * frequency * t) * 0.3  # 30% amplitude
    audio_int16 = (audio * 32767).astype(np.int16)

    return {
        'fragment_id': 'test-fragment-001',
        'stream_id': 'test-stream-123',
        'sequence_number': 1,
        'timestamp': 1234567890,
        'audio': base64.b64encode(audio_int16.tobytes()).decode('utf-8'),
        'sample_rate': sample_rate,
        'channels': 1,
        'format': 'pcm_s16le',
        'duration_ms': 6000
    }
```

### Coverage Enforcement

**Pre-commit**:
```bash
# Run pytest with coverage check (fails if <80%)
pytest apps/sts-service/tests/unit/full/ --cov=sts_service.full --cov-fail-under=80
```

**CI**:
```bash
# Run all tests with coverage enforcement
pytest apps/sts-service/tests/ --cov=sts_service.full --cov-fail-under=80 --cov-report=html
# Check critical paths have 95% coverage
pytest apps/sts-service/tests/unit/full/test_pipeline_coordinator.py --cov=sts_service.full.pipeline --cov-fail-under=95
```

**Critical Paths** (95% minimum):
- `sts_service.full.pipeline` - Pipeline coordinator orchestration
- `sts_service.full.handlers.fragment` - Fragment processing logic
- `sts_service.full.session` - Session state management
- Error handling code paths (retryable flag logic)

### Test Naming Conventions

**Unit Tests**:
- `test_<function>_happy_path()` - Normal operation (e.g., `test_pipeline_coordinator_happy_path()`)
- `test_<function>_error_<condition>()` - Error handling (e.g., `test_pipeline_handles_asr_timeout()`)
- `test_<function>_edge_<case>()` - Boundary conditions (e.g., `test_backpressure_edge_threshold()`)

**Contract Tests**:
- `test_<event>_schema()` - Schema validation (e.g., `test_fragment_processed_schema()`)
- `test_<event>_required_fields()` - Required field validation
- `test_<event>_field_types()` - Field type validation

**Integration Tests**:
- `test_<workflow>_integration()` - Workflow tests (e.g., `test_full_pipeline_integration()`)
- `test_<component>_<component>_integration()` - Component integration (e.g., `test_asr_translation_integration()`)

**E2E Tests**:
- `test_<user_story>_e2e()` - End-to-end user story (e.g., `test_full_dubbing_pipeline_e2e()`)

## Implementation Phases

### Phase 0: Research & Planning (COMPLETED)
**Status**: ✅ COMPLETED (research-cache.md with 34 code examples)

**Deliverables**:
- [x] Research cache with working code examples (research-cache.md)
- [x] Technology decisions validated (ASR: faster-whisper medium, Translation: DeepL API, TTS: XTTS v2)
- [x] GPU memory budget confirmed (6GB for 8GB target)
- [x] Latency budget validated (5-7.5s achievable)
- [x] Implementation plan created (this document)

---

### Phase 1: Data Models & Contracts (PRIORITY: P1)
**Goal**: Define data models and API contracts for type safety and schema validation.

**Tasks**:
1. Create data models (apps/sts-service/src/sts_service/full/models/)
   - StreamConfig, StreamState, StreamSession (stream.py)
   - FragmentData, FragmentResult, FragmentMetadata (fragment.py)
   - TranscriptAsset, TranslationAsset, AudioAsset (asset.py)
   - ErrorResponse, ErrorCode enum (error.py)

2. Create API contracts (specs/021-full-sts-service/contracts/)
   - fragment-schema.json (fragment:data, fragment:ack, fragment:processed)
   - stream-schema.json (stream:init, stream:ready, stream:pause, stream:resume, stream:end, stream:complete)
   - backpressure-schema.json (backpressure event)
   - error-schema.json (error response structure)

3. Write contract tests (apps/sts-service/tests/contract/)
   - test_fragment_schemas.py (validate all fragment events)
   - test_stream_schemas.py (validate all stream events)
   - test_backpressure_schema.py (validate backpressure structure)
   - test_error_schema.py (validate error response structure)

**TDD Workflow**:
```bash
# 1. Write contract tests FIRST (define expected schemas)
# apps/sts-service/tests/contract/test_fragment_schemas.py
def test_fragment_data_schema():
    schema = load_schema('contracts/fragment-schema.json')
    sample_payload = {...}
    jsonschema.validate(sample_payload, schema)  # Should pass

# 2. Create JSON schema files
# specs/021-full-sts-service/contracts/fragment-schema.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "definitions": {
    "fragment_data": {...}
  }
}

# 3. Create Pydantic models matching schemas
# apps/sts-service/src/sts_service/full/models/fragment.py
class FragmentData(BaseModel):
    fragment_id: str
    stream_id: str
    sequence_number: int
    # ...

# 4. Run contract tests - verify they PASS
pytest apps/sts-service/tests/contract/ -v
```

**Deliverables**:
- data-model.md (comprehensive data model documentation)
- contracts/ directory with JSON schemas
- models/ package with Pydantic models
- 100% contract test coverage

**Success Criteria**:
- All contract tests pass
- Pydantic models validate against JSON schemas
- No "NEEDS CLARIFICATION" fields in data-model.md

---

### Phase 2: Pipeline Coordinator (PRIORITY: P1)
**Goal**: Orchestrate ASR → Translation → TTS pipeline with error handling and in-order delivery.

**Tasks**:
1. Create Pipeline Coordinator (apps/sts-service/src/sts_service/full/pipeline.py)
   - Fragment processing workflow (ASR → Translation → TTS)
   - Error propagation (check status after each stage)
   - Asset lineage tracking (parent_asset_ids)
   - In-order delivery queue (sort by sequence_number)
   - Processing statistics (latency, stage timings)
   - Backpressure monitoring (in-flight count tracking)

2. Write Pipeline unit tests (apps/sts-service/tests/unit/full/)
   - test_pipeline_coordinator.py:
     - `test_pipeline_chains_asr_translation_tts()` - Full pipeline with mocked components
     - `test_pipeline_handles_asr_failure()` - ASR error → return error, skip Translation/TTS
     - `test_pipeline_handles_translation_failure()` - Translation error → return error, skip TTS
     - `test_pipeline_handles_tts_failure()` - TTS error → return error
     - `test_pipeline_preserves_asset_lineage()` - parent_asset_ids tracked
     - `test_pipeline_tracks_stage_timings()` - ASR, Translation, TTS timings recorded
   - test_fragment_ordering.py:
     - `test_fragments_emitted_in_order()` - Fragments processed in sequence_number order
     - `test_out_of_order_arrival_reordered()` - Fragments arrive out of order, emitted in order
   - test_backpressure_tracker.py:
     - `test_backpressure_low_severity()` - In-flight 1-3 → severity low
     - `test_backpressure_medium_severity()` - In-flight 4-6 → severity medium
     - `test_backpressure_high_severity()` - In-flight 7-10 → severity high
     - `test_backpressure_critical_reject()` - In-flight >10 → reject fragment

3. Write Pipeline integration tests (apps/sts-service/tests/integration/full/)
   - test_full_pipeline_asr_to_tts.py:
     - `test_full_pipeline_english_to_spanish()` - Real audio → ASR → Translation → TTS
     - `test_duration_matching_preserves_sync()` - Variance <10% for SUCCESS
     - `test_empty_transcript_returns_silence()` - Silence → empty transcript → silence output

**TDD Workflow**:
```bash
# 1. Write failing unit tests FIRST (mock ASR/Translation/TTS)
# 2. Implement Pipeline Coordinator
# 3. Run tests - verify they PASS
pytest apps/sts-service/tests/unit/full/test_pipeline_coordinator.py -v

# 4. Write integration tests (real components if GPU available)
# 5. Verify integration tests PASS
```

**Deliverables**:
- Pipeline Coordinator module
- Unit tests (95% coverage - critical path)
- Integration tests (happy path + critical errors)

**Success Criteria**:
- All unit tests pass
- In-order delivery guaranteed (integration test)
- Error handling for all stages validated
- Backpressure thresholds enforced

---

### Phase 3: Socket.IO Server Integration (PRIORITY: P1)
**Goal**: Extend Echo STS server patterns for Full STS with fragment processing.

**Tasks**:
1. Create Socket.IO server (apps/sts-service/src/sts_service/full/)
   - server.py (AsyncServer with ASGI, reuse Echo STS patterns)
   - session.py (SessionStore, extend Echo STS session)
   - handlers/stream.py (stream:init, pause, resume, end handlers)
   - handlers/fragment.py (fragment:data handler, fragment:processed emission)
   - handlers/lifecycle.py (connect, disconnect handlers)

2. Write Socket.IO unit tests (apps/sts-service/tests/unit/full/)
   - test_handlers_stream.py:
     - `test_stream_init_validates_config()` - Validate stream:init payload
     - `test_stream_init_validates_voice_profile()` - Voice profile exists check
     - `test_stream_init_emits_stream_ready()` - Emit stream:ready with session_id
     - `test_stream_pause_rejects_new_fragments()` - Pause → reject fragment:data
     - `test_stream_resume_accepts_fragments()` - Resume → accept fragment:data
     - `test_stream_end_emits_statistics()` - End → emit stream:complete with stats
   - test_handlers_fragment.py:
     - `test_fragment_data_emits_ack()` - Immediate fragment:ack emission
     - `test_fragment_data_calls_pipeline()` - Pipeline coordinator invoked
     - `test_fragment_processed_emitted_on_success()` - Success → emit fragment:processed
     - `test_fragment_processed_emitted_on_failure()` - Failure → emit fragment:processed with error
   - test_handlers_lifecycle.py:
     - `test_connect_saves_session()` - Connection → session created
     - `test_disconnect_cleans_up()` - Disconnect → session cleaned

3. Write Socket.IO integration tests (apps/sts-service/tests/integration/full/)
   - test_socketio_event_flow.py:
     - `test_client_connects_and_initializes()` - Connect → stream:init → stream:ready
     - `test_client_sends_fragment_receives_processed()` - fragment:data → fragment:ack → fragment:processed
     - `test_client_receives_backpressure_event()` - High in-flight → backpressure event
     - `test_client_ends_stream_receives_complete()` - stream:end → stream:complete → disconnect

**TDD Workflow**:
```bash
# 1. Write failing unit tests FIRST (mock pipeline, mock sio.emit)
# 2. Implement Socket.IO handlers
# 3. Run tests - verify they PASS
pytest apps/sts-service/tests/unit/full/test_handlers_*.py -v

# 4. Write integration tests (real Socket.IO client)
# 5. Verify integration tests PASS
pytest apps/sts-service/tests/integration/full/test_socketio_event_flow.py -v
```

**Deliverables**:
- Socket.IO server and handlers
- Unit tests (80% coverage)
- Integration tests (event flow validation)

**Success Criteria**:
- All Socket.IO events handled correctly
- fragment:ack emitted immediately (<50ms)
- fragment:processed emitted in sequence_number order
- Session state managed correctly (init, pause, resume, end)

---

### Phase 4: Observability (PRIORITY: P2)
**Goal**: Add Prometheus metrics and structured logging for production monitoring.

**Tasks**:
1. Create metrics module (apps/sts-service/src/sts_service/full/metrics.py)
   - Prometheus metrics:
     - sts_fragment_processing_seconds (histogram, labels: status, stream_id)
     - sts_asr_duration_seconds (histogram)
     - sts_translation_duration_seconds (histogram)
     - sts_tts_duration_seconds (histogram)
     - sts_fragments_in_flight (gauge, labels: stream_id)
     - sts_fragment_errors_total (counter, labels: stage, error_code)
     - sts_gpu_utilization_percent (gauge)
   - /metrics endpoint (FastAPI route)

2. Create logging config (apps/sts-service/src/sts_service/full/logging_config.py)
   - Structured logging with JSON output
   - Include fragment_id, stream_id, sequence_number in all log entries
   - Log processing timings per stage (ASR, Translation, TTS)

3. Create artifact logger (apps/sts-service/src/sts_service/full/artifact_logger.py)
   - **Log intermediate assets to disk for troubleshooting**
   - Write transcript (ASR output) to `{artifacts_path}/{stream_id}/{fragment_id}/transcript.txt`
   - Write translation to `{artifacts_path}/{stream_id}/{fragment_id}/translation.txt`
   - Write dubbed audio to `{artifacts_path}/{stream_id}/{fragment_id}/dubbed_audio.m4a`
   - Write original audio to `{artifacts_path}/{stream_id}/{fragment_id}/original_audio.m4a`
   - Write metadata JSON with timings, status, errors
   - Configurable via ENABLE_ARTIFACT_LOGGING env var (default: true)
   - Configurable retention policy (e.g., keep last 24 hours, or last N fragments)
   - Automatic cleanup of old artifacts (async background task)

4. Write observability unit tests (apps/sts-service/tests/unit/full/)
   - test_metrics.py:
     - `test_metrics_recorded_on_success()` - Success → latency histogram incremented
     - `test_metrics_recorded_on_failure()` - Failure → error counter incremented
     - `test_gpu_utilization_tracked()` - GPU util gauge updated
     - `test_inflight_gauge_updated()` - In-flight gauge accurate
   - test_logging.py:
     - `test_logs_include_fragment_id()` - Log entries include fragment_id
     - `test_logs_include_stream_id()` - Log entries include stream_id
     - `test_stage_timings_logged()` - ASR/Translation/TTS timings in logs
   - test_artifact_logger.py:
     - `test_artifact_logger_writes_transcript()` - Transcript saved to disk
     - `test_artifact_logger_writes_translation()` - Translation saved to disk
     - `test_artifact_logger_writes_dubbed_audio()` - Dubbed audio saved to disk
     - `test_artifact_logger_writes_metadata()` - Metadata JSON with timings/status
     - `test_artifact_logger_respects_enable_flag()` - Skip if ENABLE_ARTIFACT_LOGGING=false
     - `test_artifact_cleanup_removes_old_files()` - Retention policy enforced

5. Write observability integration tests (apps/sts-service/tests/integration/full/)
   - test_metrics_endpoint.py:
     - `test_metrics_endpoint_returns_prometheus_format()` - GET /metrics → Prometheus format
     - `test_metrics_include_all_keys()` - All expected metrics present

**TDD Workflow**:
```bash
# 1. Write failing unit tests FIRST (mock prometheus_client)
# 2. Implement metrics and logging modules
# 3. Run tests - verify they PASS
pytest apps/sts-service/tests/unit/full/test_metrics.py -v

# 4. Write integration tests (query /metrics endpoint)
# 5. Verify integration tests PASS
```

**Deliverables**:
- Prometheus metrics module
- Structured logging configuration
- Unit tests (80% coverage)
- Integration tests (/metrics endpoint validation)

**Success Criteria**:
- All metrics exposed at /metrics endpoint
- Logs include fragment_id/stream_id for correlation
- Metrics queryable via Prometheus (manual validation)

---

### Phase 5: Configuration & Deployment (PRIORITY: P3)
**Goal**: Environment variable configuration and deployment documentation. **REUSE existing Dockerfile**.

**Reuse Existing Infrastructure**:
- ✅ apps/sts-service/deploy/Dockerfile (EXISTING - update for Full STS entrypoint)
- ✅ apps/sts-service/deploy/Dockerfile.echo (EXISTING - reference for patterns)

**Tasks**:
1. Create configuration module (apps/sts-service/src/sts_service/full/config.py)
   - Load environment variables (PORT, DEEPL_API_KEY, MODEL_PATH, etc.)
   - Voice profiles JSON path (VOICE_PROFILES_PATH)
   - Backpressure thresholds (BACKPRESSURE_THRESHOLD_LOW/MEDIUM/HIGH/CRITICAL)
   - Timeout configurations (ASR_TIMEOUT_MS, TRANSLATION_TIMEOUT_MS, TTS_TIMEOUT_MS)
   - **Artifact logging configuration**:
     - ENABLE_ARTIFACT_LOGGING (default: true)
     - ARTIFACTS_PATH (default: /tmp/sts-artifacts or ./artifacts)
     - ARTIFACT_RETENTION_HOURS (default: 24 - keep last 24 hours)
     - ARTIFACT_MAX_COUNT (default: 1000 - keep last N fragments per stream)

2. Update existing Dockerfile (apps/sts-service/deploy/Dockerfile)
   - Add entrypoint option for Full STS: `CMD ["python", "-m", "sts_service.full"]`
   - Ensure faster-whisper, DeepL, Coqui TTS dependencies included
   - Verify GPU passthrough configuration (already present for Echo STS)
   - Add volume mount documentation for voices.json

3. Create .env.example (apps/sts-service/.env.example)
   - Document all required environment variables
   - Provide example values for local dev
   - Include:
     - DeepL API key (DEEPL_API_KEY)
     - Voice profiles path (VOICE_PROFILES_PATH)
     - Model paths (MODEL_PATH)
     - **Artifact logging** (ENABLE_ARTIFACT_LOGGING, ARTIFACTS_PATH, ARTIFACT_RETENTION_HOURS, ARTIFACT_MAX_COUNT)
     - Backpressure thresholds
     - Timeout configurations

4. Create quickstart.md (specs/021-full-sts-service/quickstart.md)
   - Developer setup instructions (install dependencies, download models)
   - Running locally: `python -m sts_service.full`
   - Running with Docker: Use existing deploy/Dockerfile
   - Testing (pytest commands)
   - Deployment to RunPod (environment variables)

**TDD Workflow**:
```bash
# 1. No new tests required (configuration is tested indirectly)
# 2. Implement configuration module
# 3. Update existing Dockerfile entrypoint
# 4. Test locally: python -m sts_service.full
# 5. Test with Docker: docker build -f deploy/Dockerfile -t full-sts .
```

**Deliverables**:
- Configuration module (config.py)
- Updated Dockerfile (reuse existing, add Full STS entrypoint)
- .env.example with documented variables
- quickstart.md with setup instructions

**Success Criteria**:
- Service starts with environment variables
- Dockerfile builds successfully
- Test fragment processing works end-to-end (manual validation)
- Documentation complete and accurate
- NO new Dockerfiles created (reuse existing)

---

### Phase 6: E2E Testing (PRIORITY: P3)
**Goal**: Test Full STS service directly with chunked audio segments from test client.

**Test Approach**: Direct STS service testing (NOT full media-service pipeline)
- Test client chunks `1-min-nfl.m4a` into 6-second segments
- Sends `fragment:data` events to Full STS service via Socket.IO
- Receives `fragment:processed` events with dubbed audio back
- Validates ASR → Translation → TTS pipeline outputs

**Reuse Existing Infrastructure**:
- ✅ tests/e2e/docker-compose.yml (EXISTING - add Full STS service)
- ✅ tests/e2e/fixtures/test_streams/1-min-nfl.m4a (EXISTING - test audio file)
- ✅ tests/e2e/helpers/socketio_monitor.py (EXISTING - Socket.IO client wrapper)
- ✅ apps/sts-service/deploy/Dockerfile (EXISTING - reuse for Full STS)

**Tasks**:
1. Update E2E docker-compose.yml (tests/e2e/docker-compose.yml)
   - Add `e2e-full-sts` service (parallel to existing `e2e-echo-sts`)
   - Command: `python -m sts_service.full`
   - GPU passthrough for ASR/TTS models
   - Environment variables: DEEPL_API_KEY, VOICE_PROFILES_PATH
   - Volume mounts: voices.json, model cache

2. Create test helper: Audio chunker (tests/e2e/helpers/audio_chunker.py)
   - Load `1-min-nfl.m4a` (existing test fixture)
   - Chunk into 6-second segments (matching fragment size)
   - Encode to base64 PCM for `fragment:data` payloads
   - Return list of FragmentData models

3. Write E2E tests (tests/e2e/test_full_sts_service.py - NEW file)
   - `test_full_sts_processes_audio_fragments()`
     - Chunk 1-min-nfl.m4a into 10 segments (6s each)
     - Send fragment:data events sequentially
     - Receive fragment:processed events
     - Validate all fragments processed successfully
   - `test_asr_transcription_quality()`
     - Send English audio fragment
     - Validate ASR transcript matches expected text (>90% accuracy)
   - `test_translation_to_spanish()`
     - Validate translation output is Spanish
     - Check translation quality (not empty, reasonable length)
   - `test_tts_duration_matching()`
     - Validate dubbed audio duration within ±10% of original
     - Check status=SUCCESS for variance <10%
   - `test_end_to_end_latency()`
     - Measure time from fragment:data sent to fragment:processed received
     - Validate P95 latency <8 seconds
   - `test_backpressure_events()`
     - Send 15 fragments rapidly (exceeds max_inflight=10)
     - Validate backpressure events emitted at thresholds (4, 6, 10)
   - `test_in_order_delivery()`
     - Send fragments out of order (sequence_number: 3, 1, 2)
     - Validate fragment:processed events emitted in order (1, 2, 3)

4. Configure voices.json for E2E
   - Add test voice profile for Spanish (e.g., "spanish_test")
   - Include sample speaker WAV file in fixtures
   - Mount to Full STS container

**TDD Workflow**:
```bash
# 1. Write E2E tests FIRST (they will fail - STS not running)
# 2. Update docker-compose.yml to add Full STS service
# 3. Start services: docker-compose -f tests/e2e/docker-compose.yml up e2e-full-sts
# 4. Run E2E tests: pytest tests/e2e/test_full_sts_service.py -v
# 5. Verify all tests PASS
```

**Deliverables**:
- Updated tests/e2e/docker-compose.yml (add e2e-full-sts service)
- tests/e2e/helpers/audio_chunker.py (chunk m4a into segments)
- tests/e2e/test_full_sts_service.py (7 E2E tests)
- voices.json test configuration
- Sample speaker WAV file for test voice profile

**Success Criteria**:
- Full STS service starts successfully in Docker
- Test client chunks 1-min-nfl.m4a and sends 10 fragments
- Receives 10 dubbed audio fragments back (in order)
- ASR transcription >90% accuracy
- TTS duration matching <10% variance
- P95 latency <8 seconds
- Backpressure events emitted correctly
- NO new Dockerfiles created (reuse existing)

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| GPU VRAM exhaustion (>8GB) | HIGH | MEDIUM | Monitor GPU memory usage, enforce backpressure, reduce model size (INT8 quantization) |
| DeepL API rate limiting | HIGH | MEDIUM | Implement worker-side exponential backoff, monitor usage proactively |
| ASR latency exceeds 4s | MEDIUM | LOW | Use faster-whisper medium (not large), optimize audio preprocessing |
| TTS duration variance >20% | MEDIUM | MEDIUM | Test with diverse text lengths, tune speed ratio clamping (0.8-1.2) |
| Socket.IO connection instability | MEDIUM | LOW | Implement reconnection logic in worker, use persistent session store (Redis) if needed |
| Model loading fails (missing files) | HIGH | LOW | Validate model files at startup, fail fast with clear error messages |
| Test coverage below 80% | MEDIUM | MEDIUM | Enforce pre-commit hooks, CI coverage gates, prioritize critical paths |

## Next Steps

1. **Create data-model.md** - Document all data models (StreamConfig, FragmentData, Assets, etc.)
2. **Create API contracts** - JSON schemas for all Socket.IO events (fragment, stream, backpressure, error)
3. **Write contract tests** - Validate all schemas before implementation
4. **Implement ASR module** - Singleton loading, async wrapper, error handling
5. **Implement Translation module** - DeepL integration, error handling, retry configuration
6. **Implement TTS module** - XTTS v2 integration, voice profiles, duration matching
7. **Implement Pipeline Coordinator** - ASR→Translation→TTS orchestration, in-order delivery
8. **Implement Socket.IO server** - Event handlers, session management, backpressure monitoring
9. **Add observability** - Prometheus metrics, structured logging
10. **Create deployment artifacts** - Dockerfile, docker-compose.yml, configuration
11. **Write E2E tests** - Validate full pipeline with media-service integration
12. **Performance tuning** - Optimize latency, GPU memory usage, throughput

**Estimated Timeline**: 3-4 weeks (assuming 1 developer, part-time)
- Phase 1-2: 3 days (data models, ASR module)
- Phase 3-4: 4 days (Translation, TTS modules)
- Phase 5-6: 5 days (Pipeline, Socket.IO server)
- Phase 7-8: 3 days (Observability, deployment)
- Phase 9: 2 days (E2E testing)
- Buffer: 3 days (debugging, tuning)

**Ready for /speckit.tasks**: After Phase 1 (data models and contracts) is complete, run `/speckit.tasks` to generate detailed implementation tasks with TDD workflow.
