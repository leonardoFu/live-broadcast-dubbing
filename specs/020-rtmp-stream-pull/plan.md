# Implementation Plan: RTMP Stream Pull Migration

**Branch**: `020-rtmp-stream-pull` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/020-rtmp-stream-pull/spec.md`

## Summary

Migrate media-service input pipeline from RTSP to RTMP stream pulling to reduce pipeline complexity and eliminate audio processing failures caused by RTP depayloader caps negotiation issues. Replace rtspsrc + RTP depayloaders with rtmpsrc + flvdemux, reducing element count by 3 and simplifying dynamic pad handling. Complete RTSP removal with no backward compatibility - RTMP is the single stream pull protocol post-migration.

## Technical Context

**Language/Version**: Python 3.10 (per constitution and pyproject.toml requirement >=3.10,<3.11)
**Primary Dependencies**: GStreamer 1.0 (PyGObject >= 3.44.0), rtmpsrc (gst-plugins-bad), flvdemux (gst-plugins-good)
**Storage**: N/A (in-memory pipeline state, segment buffers written to disk via existing SegmentBuffer)
**Testing**: pytest >= 7.4.0, pytest-mock, Docker Compose (integration/E2E), ffmpeg (test fixtures)
**Target Platform**: Linux server (Ubuntu 20.04+, Docker containers for media-service)
**Project Type**: Single service modification (media-service input pipeline only)
**Performance Goals**: <300ms total latency (MediaMTX RTMP input to segment write), maintain current throughput (1080p30 + AAC)
**Constraints**: 300ms latency budget, 80% test coverage minimum (95% for InputPipeline critical path), audio track mandatory (no video-only streams)
**Scale/Scope**: Single InputPipeline class modification (~200 LOC affected), 3 test files updated, complete RTSP removal

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle VIII - Test-First Development (NON-NEGOTIABLE)**:
- [x] Test strategy defined for all user stories (see contracts/test-expectations.md)
- [x] Mock patterns documented (GStreamer elements, MediaMTX RTMP streams, ffmpeg fixtures)
- [x] Coverage targets specified (80% minimum, 95% for InputPipeline critical path)
- [x] Test infrastructure matches constitution requirements (pytest, pytest-mock, pytest-asyncio, Docker Compose)
- [x] Test organization follows standard structure (apps/media-service/tests/{unit,integration}, tests/e2e)

**Principle I - Real-Time First**:
- [x] RTMP pipeline maintains real-time streaming (no batch processing)
- [x] Latency budget defined: 300ms total (MediaMTX input to segment write)
- [x] Flexible allocation allows optimization based on profiling

**Principle II - Testability Through Isolation**:
- [x] Unit tests use mocked GStreamer elements (no real pipeline execution)
- [x] Integration tests use Docker Compose (MediaMTX + media-service in isolation)
- [x] E2E tests use full environment (optional, for validation only)
- [x] No live RTMP endpoint dependencies in unit tests

**Principle III - Spec-Driven Development (NON-NEGOTIABLE)**:
- [x] Spec created before implementation (spec.md, plan.md, research.md, data-model.md)
- [x] Contracts documented (input-pipeline-interface.py, test-expectations.md)
- [x] Quickstart guide provided (quickstart.md)

**Principle IV - Observability & Debuggability**:
- [x] Existing logging preserved (pipeline state transitions, buffer PTS, element linking)
- [x] Error messages enhanced (audio track validation failures include descriptive messages)
- [x] No new observability gaps introduced by RTMP migration

**Principle VI - A/V Sync Discipline**:
- [x] Video and audio PTS preservation unchanged (appsink callbacks maintain PTS passthrough)
- [x] RTMP pipeline does not alter timestamp handling from RTSP version
- [x] Existing SegmentBuffer A/V sync logic unaffected

**Principle VII - Incremental Delivery**:
- [x] Migration is single atomic change (RTSP -> RTMP, no phased rollout)
- [x] Complete feature removal (no RTSP backward compatibility)
- [x] Independently testable (unit, integration, E2E tests validate migration)

**GATE RESULT**: PASS - All constitution principles satisfied. No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/020-rtmp-stream-pull/
├── plan.md                          # This file (/speckit.plan command output)
├── research.md                      # Phase 0 output (technical research)
├── data-model.md                    # Phase 1 output (entities and state transitions)
├── quickstart.md                    # Phase 1 output (implementation guide)
├── contracts/                       # Phase 1 output (interface contracts)
│   ├── input-pipeline-interface.py  # InputPipeline protocol and validation functions
│   └── test-expectations.md         # Test behavior contracts and assertions
├── spec.md                          # Feature specification (input)
└── tasks.md                         # Phase 2 output (/speckit.tasks - NOT created yet)
```

### Source Code (repository root)

**Structure**: Python monorepo with apps/ and libs/ structure (per CLAUDE.md convention)

```text
apps/media-service/
├── src/media_service/
│   ├── pipeline/
│   │   └── input.py                 # MODIFIED: InputPipeline class (RTSP -> RTMP)
│   ├── worker/
│   │   └── worker_runner.py         # MODIFIED: WorkerRunner URL construction (RTSP -> RTMP)
│   ├── models/
│   │   └── config.py                # MODIFIED: mediamtx_rtsp_port -> mediamtx_rtmp_port
│   └── (other modules unchanged)
│
├── tests/
│   ├── unit/
│   │   ├── test_input_pipeline.py   # MODIFIED: Update URL validation, element creation tests
│   │   └── test_worker_runner.py    # MODIFIED: Update URL construction tests
│   └── integration/
│       ├── test_segment_pipeline.py # MODIFIED: Update ffmpeg publish from RTSP to RTMP
│       └── conftest.py              # MODIFIED: Update test fixtures (RTSP -> RTMP)
│
├── deploy/mediamtx/
│   └── mediamtx.yml                 # MODIFIED: Ensure RTMP enabled on port 1935
│
└── docker-compose.e2e.yml           # MODIFIED: Expose port 1935 instead of 8554

tests/e2e/
└── test_dual_compose_full_pipeline.py  # MODIFIED: Update RTMP publishing, assertions
```

**Structure Decision**: This is a single-service modification affecting media-service only. No new directories created. Changes concentrated in InputPipeline class (~200 LOC) and associated tests (~300 LOC). Follows existing Python monorepo structure per spec 001-python-monorepo-setup.

## Test Strategy

### Test Levels for This Feature

**Unit Tests** (mandatory):
- **Target**: InputPipeline RTMP URL validation, element creation, configuration, WorkerRunner URL construction
- **Tools**: pytest, pytest-mock (mock GStreamer elements)
- **Coverage**: 80% minimum overall, 95% for InputPipeline class (critical path)
- **Mocking**: All GStreamer elements (rtmpsrc, flvdemux, parsers, appsinks), no real pipeline execution
- **Location**: `apps/media-service/tests/unit/`
- **Key Tests**:
  - `test_input_pipeline_rtmp_url_validation()` - URL format checking
  - `test_input_pipeline_build_rtmp_elements()` - Element creation verification
  - `test_input_pipeline_rtmp_element_configuration()` - Property configuration
  - `test_worker_runner_builds_rtmp_pipeline()` - URL construction from config

**Integration Tests** (required for workflows):
- **Target**: Real RTMP stream consumption from MediaMTX, audio track validation, segment writing
- **Tools**: pytest, Docker Compose (MediaMTX + media-service), ffmpeg (stream publishing)
- **Coverage**: Happy path + critical error scenarios (video-only stream rejection)
- **Mocking**: None - real MediaMTX RTMP server, real GStreamer pipeline
- **Location**: `apps/media-service/tests/integration/`
- **Key Tests**:
  - `test_input_pipeline_rtmp_integration()` - Full pipeline with MediaMTX
  - `test_input_pipeline_rejects_video_only_stream()` - Audio validation
  - `test_segment_buffer_writes_rtmp_segments()` - Segment writing verification

**E2E Tests** (optional, for validation only):
- **Target**: Full end-to-end flow (RTMP publish -> media-service -> STS -> output)
- **Tools**: pytest, Docker Compose (full stack), ffmpeg
- **Coverage**: Critical user journey (stream publish to dubbing output)
- **When**: Run on-demand or in CI for regression detection
- **Location**: `tests/e2e/`
- **Key Tests**:
  - `test_dual_compose_full_pipeline_rtmp()` - Complete dubbing pipeline via RTMP

### Mock Patterns (Constitution Principle II)

**GStreamer Element Mocks** (unit tests):
```python
with patch("media_service.pipeline.input.Gst.ElementFactory.make") as mock_make:
    mock_elements = [
        MagicMock(name="rtmpsrc"),    # NOT rtspsrc
        MagicMock(name="flvdemux"),   # NOT rtph264depay/rtpmp4gdepay
        # ... other elements
    ]
    mock_make.side_effect = mock_elements
```

**MediaMTX RTMP Fixtures** (integration tests):
```bash
# Publish test stream via RTMP (NOT RTSP)
ffmpeg -re -i tests/fixtures/test-30s.mp4 \
    -c:v copy -c:a copy \
    -f flv rtmp://mediamtx:1935/live/integration-test/in
```

**Video-Only Stream Fixture** (audio validation tests):
```bash
# Publish video-only stream to test rejection
ffmpeg -re -i tests/fixtures/test-30s.mp4 \
    -c:v copy -an \
    -f flv rtmp://mediamtx:1935/live/video-only-test/in
```

### Coverage Enforcement

**Pre-commit**: `pytest --cov=media_service.pipeline.input --cov-fail-under=95`
**CI**: `pytest --cov=media_service --cov-fail-under=80` (block merge if fails)
**Critical paths**: InputPipeline class → 95% minimum (enhanced from 80% standard)

### Test Naming Conventions

Follow TDD naming from constitution:
- `test_<function>_happy_path()` - Normal RTMP operation
- `test_<function>_error_<condition>()` - Error handling (invalid URL, missing audio)
- `test_<function>_edge_<case>()` - Boundary conditions (empty URL, max_buffers=0)
- `test_<function>_integration_<workflow>()` - Integration scenarios (RTMP publish + consume)

### Test Migration Strategy

**Parallel TDD Update** (per research.md recommendations):
1. Write failing unit tests for RTMP URL validation
2. Implement RTMP URL validation in InputPipeline
3. Write failing unit tests for RTMP element creation
4. Implement RTMP element creation in InputPipeline
5. Write failing integration tests for RTMP stream consumption
6. Update integration test fixtures (ffmpeg RTMP publish)
7. Write failing E2E tests for full RTMP pipeline
8. Update E2E docker-compose configuration

**RTSP Test Removal**: All RTSP-specific tests MUST be deleted (no legacy test retention per clarification decision).

## Complexity Tracking

**No violations** - All constitution principles satisfied. This section intentionally left empty per template guidance ("Fill ONLY if Constitution Check has violations that must be justified").
