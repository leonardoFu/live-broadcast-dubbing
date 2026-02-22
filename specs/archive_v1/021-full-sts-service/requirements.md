# Requirements Checklist: Full STS Service

**Feature**: 021-full-sts-service
**Status**: Draft
**Created**: 2026-01-02

## Functional Requirements

### Socket.IO Server (based on Echo STS)
- [ ] **FR-001**: Service acts as Socket.IO server on configurable port (default 8000)
- [ ] **FR-002**: Service accepts all connections without authentication
- [ ] **FR-003**: Service supports X-Stream-ID and X-Worker-ID extra headers
- [ ] **FR-004**: Service implements Socket.IO ping/pong (25s interval, 10s timeout)
- [ ] **FR-005**: Service implements all message types from spec 016

### Stream Initialization
- [ ] **FR-006**: Service validates stream:init configuration
- [ ] **FR-007**: Service responds with stream:ready (session_id, max_inflight, capabilities)
- [ ] **FR-008**: Service rejects invalid configurations with INVALID_CONFIG error
- [ ] **FR-009**: Service initializes ASR, Translation, TTS components on stream:init

### ASR Processing
- [ ] **FR-010**: Service uses faster-whisper for ASR
- [ ] **FR-011**: Service transcribes audio using source_language from config
- [ ] **FR-012**: Service returns empty transcript for silence (status SUCCESS)
- [ ] **FR-013**: Service detects and handles ASR errors with proper error codes
- [ ] **FR-014**: Service supports domain hints for vocabulary priming
- [ ] **FR-015**: Service produces TranscriptAsset with absolute timestamps

### Translation Processing
- [ ] **FR-016**: Service uses DeepL API for translation
- [ ] **FR-017**: Service translates ASR transcript from source to target language
- [ ] **FR-018**: Service skips translation for empty transcripts
- [ ] **FR-019**: Service handles translation errors with proper error codes
- [ ] **FR-020**: Service preserves parent_asset_ids for lineage tracking

### TTS Processing
- [ ] **FR-021**: Service uses Coqui TTS (XTTS v2) for synthesis
- [ ] **FR-022**: Service synthesizes translated text using voice_profile
- [ ] **FR-023**: Service applies duration matching for A/V sync
- [ ] **FR-024**: Service uses rubberband for time-stretching
- [ ] **FR-025**: Service returns PARTIAL status if speed ratio clamped (>2.0x)
- [ ] **FR-026**: Service skips TTS for empty translations (silence/fallback)
- [ ] **FR-027**: Service handles TTS errors with proper error codes

### Fragment Processing Workflow
- [ ] **FR-028**: Service responds to fragment:data with immediate fragment:ack
- [ ] **FR-029**: Service processes fragments through ASR → Translation → TTS
- [ ] **FR-030**: Service emits fragment:processed in sequence_number order
- [ ] **FR-031**: Service includes processing_time_ms and stage_timings
- [ ] **FR-032**: Service populates dubbed_audio with base64-encoded PCM
- [ ] **FR-033**: Service includes transcript and translated_text for debugging
- [ ] **FR-034**: Service tracks in-flight fragments and enforces max_inflight

### Error Handling
- [ ] **FR-035**: Service returns fragment:processed with status "failed" on errors
- [ ] **FR-036**: Service sets error.retryable=true for transient errors
- [ ] **FR-037**: Service sets error.retryable=false for permanent errors
- [ ] **FR-038**: Service includes error.stage indicating failed stage
- [ ] **FR-039**: Service supports fragment retry (idempotent by fragment_id)
- [ ] **FR-040**: Service emits error events for fatal stream errors

### Flow Control and Backpressure
- [ ] **FR-041**: Service monitors in-flight fragment count per stream
- [ ] **FR-042**: Service emits backpressure events when thresholds exceeded
- [ ] **FR-043**: Service includes severity and action in backpressure events
- [ ] **FR-044**: Service emits backpressure recovery when queue drains

### Stream Lifecycle
- [ ] **FR-045**: Service handles stream:pause (completes in-flight, rejects new)
- [ ] **FR-046**: Service handles stream:resume (accepts new fragments)
- [ ] **FR-047**: Service responds to stream:end with stream:complete statistics
- [ ] **FR-048**: Service auto-closes connection 5s after stream:complete

### Observability
- [ ] **FR-049**: Service exposes Prometheus metrics at /metrics
- [ ] **FR-050**: Service emits structured logs with fragment_id/stream_id
- [ ] **FR-051**: Service logs processing timings per stage
- [ ] **FR-052**: Service tracks and logs GPU memory utilization

### Configuration
- [ ] **FR-053**: Service configurable via environment variables
- [ ] **FR-054**: Service supports configurable max_inflight (default 3, range 1-10)
- [ ] **FR-055**: Service supports configurable timeout (default 8000ms)
- [ ] **FR-056**: Service supports configurable fallback mode (silence vs original)

---

## Success Criteria

- [ ] **SC-001**: Full pipeline processes 6s fragment in <8s (P95 latency)
- [ ] **SC-002**: Dubbed audio duration variance within ±10% of original
- [ ] **SC-003**: ASR transcription accuracy >90% for clear speech
- [ ] **SC-004**: Translation quality acceptable (BLEU >30 or manual review)
- [ ] **SC-005**: Fragment:processed delivered in sequence_number order (100%)
- [ ] **SC-006**: Service handles 3 concurrent streams without degradation
- [ ] **SC-007**: Error retryable flags 100% accurate (transient vs permanent)
- [ ] **SC-008**: Backpressure events emitted when in-flight > max_inflight
- [ ] **SC-009**: Metrics exposed and queryable; logs include correlation IDs
- [ ] **SC-010**: All E2E tests pass with 80% coverage (95% for critical paths)

---

## Testing Checklist

### Unit Tests
- [ ] Pipeline coordinator orchestration logic
- [ ] Fragment ordering and in-order delivery
- [ ] Error propagation and retryable flag logic
- [ ] Backpressure threshold calculations
- [ ] Metrics emission
- [ ] ASR component integration
- [ ] Translation component integration
- [ ] TTS component integration

### Integration Tests
- [ ] Full pipeline with real ASR, Translation, TTS
- [ ] Duration matching accuracy (A/V sync)
- [ ] Error handling with real component failures
- [ ] Multi-fragment processing (ordering, latency)
- [ ] Socket.IO event flow (fragment:data → fragment:processed)

### E2E Tests
- [ ] Complete flow: media-service → Full STS → dubbed output
- [ ] WebSocket protocol compliance (all message types)
- [ ] Backpressure response by media-service
- [ ] Connection resilience (reconnection after failure)
- [ ] Performance under load (concurrent streams)

### Contract Tests
- [ ] fragment:processed payload schema validation
- [ ] stream:ready, stream:complete schema validation
- [ ] Error response schema validation
- [ ] Audio asset schema validation (dubbed_audio structure)

---

## Implementation Progress

### Phase 1: Pipeline Coordinator Foundation (P1)
- [ ] Implement pipeline.py orchestration
- [ ] Unit tests for coordinator logic
- [ ] Error propagation and retryable flag logic
- [ ] Asset lineage tracking

### Phase 2: Socket.IO Server Integration (P1)
- [ ] Extend Echo STS server.py
- [ ] Implement fragment:data handler
- [ ] Implement fragment:processed emission
- [ ] Integration tests with Socket.IO client

### Phase 3: In-Order Delivery and Fragment Tracking (P1)
- [ ] Implement fragment queue with ordering
- [ ] Ensure in-order fragment:processed emission
- [ ] Implement in-flight fragment tracking
- [ ] E2E tests validating ordering

### Phase 4: Error Handling and Retry (P1)
- [ ] Comprehensive error detection
- [ ] Set retryable flags correctly
- [ ] Implement fragment retry (idempotent)
- [ ] E2E tests for error scenarios

### Phase 5: Backpressure and Flow Control (P2)
- [ ] Implement in-flight monitoring
- [ ] Emit backpressure events
- [ ] Integration tests with worker response
- [ ] Prevent GPU OOM under load

### Phase 6: Observability (P2)
- [ ] Implement Prometheus metrics
- [ ] Configure structured logging
- [ ] Expose /metrics endpoint
- [ ] Integration tests querying metrics

### Phase 7: Stream Lifecycle (P3)
- [ ] Implement stream:pause/resume
- [ ] Implement stream:complete with statistics
- [ ] Auto-close connection logic
- [ ] E2E tests for full lifecycle

### Phase 8: Configuration and Deployment (P3)
- [ ] Environment variable configuration
- [ ] Docker image with GPU support
- [ ] Deployment documentation
- [ ] Performance tuning

---

## Notes

- **Reusing Echo STS**: Significant infrastructure can be reused from spec 017 (Socket.IO server setup, session management, event handlers)
- **Component Dependencies**: Requires functional ASR (spec 005), Translation (spec 006), and TTS (spec 008) modules
- **TDD Compliance**: All tests must be written BEFORE implementation per Constitution Principle VIII
- **Coverage Requirements**: 80% minimum overall, 95% for critical paths (ASR, Translation, TTS, pipeline coordinator)
