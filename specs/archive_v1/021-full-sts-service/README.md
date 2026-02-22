# 021 - Full STS Service with Socket.IO Integration

**Status**: Draft
**Created**: 2026-01-02
**Priority**: P1 (Production Critical)

## Quick Summary

Implements the complete Speech-to-Speech (STS) processing pipeline with Socket.IO integration:
- **ASR (Automatic Speech Recognition)**: Whisper (faster-whisper) transcribes audio to text
- **Translation**: DeepL translates text from source to target language
- **TTS (Text-to-Speech)**: Coqui TTS synthesizes dubbed audio with duration matching
- **Socket.IO Server**: Bidirectional WebSocket communication with media-service

This is the **production-critical core** of the live broadcast dubbing system, transforming source audio into dubbed audio in real-time (target latency: 3-8 seconds added).

## Key Deliverables

1. **Pipeline Coordinator**: Orchestrates ASR → Translation → TTS workflow
2. **Socket.IO Server**: Implements WebSocket Audio Fragment Protocol (spec 016)
3. **Error Handling**: Comprehensive error detection with retryable flags
4. **Backpressure**: Flow control to prevent GPU overload
5. **Observability**: Prometheus metrics and structured logging
6. **In-Order Delivery**: Guarantees fragment:processed events emitted in sequence order

## Files

- `spec.md` - Complete feature specification
- `requirements.md` - Functional requirements checklist
- `contracts/fragment-processed-schema.yaml` - fragment:processed event schema and examples

## Dependencies

- [specs/016-websocket-audio-protocol.md](../016-websocket-audio-protocol.md) - WebSocket protocol
- [specs/017-echo-sts-service/](../017-echo-sts-service/) - Socket.IO server foundation
- [specs/005-audio-transcription-module.md](../005-audio-transcription-module.md) - ASR component
- [specs/006-translation-component/](../006-translation-component/) - Translation component
- [specs/008-tts-module/](../008-tts-module/) - TTS component

## Implementation Location

```
apps/sts-service/src/sts_service/full/
├── __init__.py
├── __main__.py              # Entry point (python -m sts_service.full)
├── server.py                # Socket.IO server setup
├── config.py                # Configuration management
├── session.py               # Session store
├── pipeline.py              # Pipeline coordinator (ASR→Translation→TTS)
├── handlers/
│   ├── stream.py            # stream:init, pause, resume, end
│   ├── fragment.py          # fragment:data, fragment:processed
│   └── lifecycle.py         # connect, disconnect
├── models/
│   ├── stream.py
│   ├── fragment.py
│   └── error.py
├── metrics.py               # Prometheus metrics
└── logging_config.py        # Structured logging
```

## Key Success Criteria

- **SC-001**: Full pipeline processes 6s fragment in <8s (P95 latency)
- **SC-002**: Dubbed audio duration within ±10% of original (A/V sync)
- **SC-003**: ASR accuracy >90% for clear speech
- **SC-005**: fragment:processed delivered in sequence_number order (100%)
- **SC-010**: All E2E tests pass with 80% coverage (95% for critical paths)

## User Stories Priority

1. **P1**: Complete STS Pipeline Processing (core functionality)
2. **P1**: Graceful Error Handling and Fallback (reliability)
3. **P2**: Backpressure and Flow Control (prevent GPU overload)
4. **P2**: Observability and Performance Monitoring (operations)
5. **P3**: Stream Lifecycle Management (graceful startup/shutdown)

## Testing Strategy

### Unit Tests
- Pipeline coordinator orchestration
- Fragment ordering logic
- Error propagation and retryable flags
- Backpressure threshold calculations

### Integration Tests
- Full pipeline with real ASR, Translation, TTS
- Duration matching accuracy (A/V sync validation)
- Error handling with real component failures
- Socket.IO event flow

### E2E Tests
- Complete flow: media-service → Full STS → dubbed output
- WebSocket protocol compliance
- Backpressure response
- Connection resilience
- Performance under load

### Contract Tests
- fragment:processed schema validation
- stream:ready, stream:complete schema validation
- Error response schema validation

## Open Questions

1. **Voice Profile Management**: Static config file vs database? (Recommendation: static config, extensible to DB later)
2. **Model Caching**: In-memory cache vs per-stream loading? (Recommendation: singleton cache)
3. **Fallback Audio**: Silence vs original audio on TTS failure? (Recommendation: configurable via env var)
4. **GPU Allocation**: How to allocate GPU across concurrent streams? (Recommendation: PyTorch automatic management)
5. **Language Pair Support**: Validate on init vs fail during processing? (Recommendation: validate on init)

## Implementation Phases

1. **Phase 1**: Pipeline Coordinator Foundation (P1)
2. **Phase 2**: Socket.IO Server Integration (P1)
3. **Phase 3**: In-Order Delivery and Fragment Tracking (P1)
4. **Phase 4**: Error Handling and Retry (P1)
5. **Phase 5**: Backpressure and Flow Control (P2)
6. **Phase 6**: Observability (P2)
7. **Phase 7**: Stream Lifecycle (P3)
8. **Phase 8**: Configuration and Deployment (P3)

## Related Specs

- **016**: WebSocket Audio Fragment Protocol (protocol definition)
- **017**: Echo STS Service (Socket.IO server foundation)
- **005**: ASR Module (Whisper integration)
- **006**: Translation Component (DeepL integration)
- **008**: TTS Module (Coqui TTS with duration matching)
- **004**: STS Pipeline Design (original architecture)
- **015**: Deployment Architecture (RunPod context)

## Quick Start (Future)

```bash
# Run Full STS Service
make sts-full

# Run with custom config
STS_PORT=8001 MAX_INFLIGHT=5 python -m sts_service.full

# Run tests
make sts-test-full
make sts-test-full-integration
make e2e-test-full-pipeline
```
