# Live Stream Dubbing Constitution

<!--
SYNC IMPACT REPORT - Constitution v1.0.0
===========================================
Version: Initial → 1.0.0
Modified Principles: N/A (initial constitution)
Added Sections: All sections (initial creation)
Removed Sections: None

Templates Requiring Updates:
✅ plan-template.md - Constitution Check section aligns with new principles
✅ spec-template.md - User scenarios align with real-time processing requirements
✅ tasks-template.md - Task organization supports TDD and modular development
✅ CLAUDE.md - Testing guidelines match constitution expectations

Follow-up TODOs: None
===========================================
-->

## Core Principles

### I. Real-Time First

All components MUST be designed for live streaming with minimal latency. Processing pipelines must handle continuous data flow, not batch operations. Target added latency: 3-8 seconds end-to-end.

**Rationale**: The system processes live streams in real-time. Any design optimized for batch processing or file-based workflows will fail to meet core requirements. Components blocking on completion before output violate this principle.

### II. Testability Through Isolation

Every module MUST be independently testable without requiring live RTMP endpoints or external services. Mock STS events (`fragment:data`, `fragment:processed`) and use deterministic test fixtures.

**Rationale**: Live stream dependencies make tests flaky, slow, and environment-dependent. Mock-based testing enables fast iteration, CI/CD automation, and reliable quality gates. Tests requiring actual MediaMTX instances or cloud services are acceptable only in dedicated integration test suites.

### III. Spec-Driven Development (NON-NEGOTIABLE)

Changes to architecture, data models, or inter-service contracts MUST be documented in `specs/` before implementation. Specs provide the source of truth. Implementation follows specs, not the reverse.

**Rationale**: This project's complexity (GStreamer, STS, A/V sync, multiple services) demands clear documentation before coding. Ad-hoc implementation leads to integration failures, sync issues, and maintenance nightmares. The `specs/` directory is the project's blueprint.

### IV. Observability & Debuggability

All processing pipelines MUST emit structured logs with `streamId`, `fragment.id`, and `batchNumber`. Metrics MUST track fragment latency, queue depth, A/V sync delta, and fallback activation. Rolling audio dumps for debugging are encouraged.

**Rationale**: Real-time A/V processing failures are hard to reproduce. Without comprehensive logging and metrics, debugging latency spikes, sync drift, or STS failures becomes impossible. Observability is not optional—it's survival.

### V. Graceful Degradation

When STS processing fails or overloads, the system MUST maintain stream continuity using configurable fallback modes (passthrough, background-only, silence). Circuit breakers MUST prevent cascading failures.

**Rationale**: Live streams cannot tolerate hard failures. A crashed STS module should not kill the entire stream. Fallback policies ensure viewers receive output even when dubbing is degraded or disabled.

### VI. A/V Sync Discipline

Video passthrough MUST preserve original timestamps. Audio processing MUST track PTSs relative to the GStreamer pipeline clock. A/V drift detection and correction via audio time-stretch is mandatory.

**Rationale**: Out-of-sync audio ruins user experience. GStreamer's timestamp management is the authoritative source. Any component ignoring PTSs or fabricating timestamps will cause drift.

### VII. Incremental Delivery

Features MUST be implemented in independently deployable milestones: (1) Video passthrough + dubbed audio, (2) Background separation and remix, (3) Overlap + crossfade, (4) Fallback modes, (5) Quality tuning.

**Rationale**: Attempting to build everything at once delays validation and increases risk. Each milestone delivers measurable value and can be tested end-to-end. Incremental delivery enables fast feedback and course correction.

## Technology Constraints

### Language & Frameworks

- **Primary Language**: Python 3.11+
- **Streaming**: GStreamer (audio/video processing), MediaMTX (ingest/egress)
- **STS Pipeline**: Whisper (ASR), translation service (MT), TTS synthesis
- **Audio Processing**: 2-stem speech separation or VAD + spectral gating
- **Testing**: pytest (mocked STS events, deterministic audio fixtures)

**Justification**: GStreamer is the industry standard for low-latency A/V processing. Python provides rich ML/audio libraries for STS. MediaMTX handles multi-protocol ingest (RTMP/RTSP/SRT/WebRTC) with minimal configuration.

### Storage & State

- **Configuration**: YAML or environment variables (no hardcoded stream keys)
- **State Management**: Per-stream workers maintain in-memory state (fragment queues, circuit breaker status)
- **Persistence**: Optional rolling audio dumps for debugging; MediaMTX handles stream recording if required

**Constraints**: Real-time systems minimize disk I/O. State should be ephemeral and recoverable.

### Performance & Scale

- **One worker per stream**: Scale horizontally by running more workers
- **FIFO ordering**: Fragments processed in arrival order (per stream)
- **Max in-flight fragments**: Configurable (default: 3-5 to balance latency vs. throughput)
- **Circuit breaker thresholds**: Configurable STS timeout and failure rate

**Trade-offs**: Per-stream isolation simplifies state management but requires orchestration (see Stream Orchestrator spec).

## Development Workflow

### Code Organization

- **`specs/`**: Architecture and design documents (source of truth)
- **`.specify/`**: Spec templates and constitution (this file)
- **`apps/sts-service/`**: Speech-to-text-to-speech module (in-process library)
- **`apps/stream-worker/`**: GStreamer-based worker (pulls from MediaMTX, processes, republishes)
- **`infra/` or `deploy/`**: Container configs, MediaMTX configuration, docker-compose files

**Convention**: Use kebab-case for spec filenames (`002-mediamtx.md`). Keep headings stable across spec revisions.

### Testing Levels

1. **Unit Tests**: Test individual functions (audio chunking, time-stretching, PTS calculations) with mock inputs
2. **Contract Tests**: Verify STS module contracts (`fragment:data` → `fragment:processed`) with deterministic fixtures
3. **Integration Tests**: Test GStreamer pipeline assembly and MediaMTX communication with mock streams
4. **E2E Tests** (optional): Full pipeline with real MediaMTX instance (slow, reserved for critical path validation)

**Rule**: Unit and contract tests run on every commit. Integration tests in CI. E2E tests on demand.

### Commit & PR Standards

- **Commit Format**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`)
- **PR Requirements**:
  - Link to relevant spec (e.g., `specs/003-gstreamer-stream-worker.md`)
  - Describe latency/A/V-sync impact
  - Document config changes or new env vars (add to `.env.example`)
  - Include test evidence (logs showing fragment processing, sync deltas)

**Security**: Never commit secrets (RTMP stream keys, API tokens). Use `.env` files excluded from git.

### Code Review Focus

1. **Spec Compliance**: Does the code match the spec? If not, update spec first or justify deviation.
2. **Latency Impact**: Does this change add buffering, blocking, or processing time?
3. **Sync Safety**: Are timestamps preserved? Is A/V drift monitored?
4. **Observability**: Are logs/metrics sufficient to debug this in production?
5. **Testability**: Can this be tested without live streams?

## Governance

### Amendment Process

Constitution changes require:

1. Proposal with rationale (why does current principle block progress?)
2. Review against existing specs (will this invalidate prior decisions?)
3. Version bump following semantic versioning:
   - **MAJOR**: Principle removal or incompatible redefinition (e.g., dropping real-time requirement)
   - **MINOR**: New principle or materially expanded guidance (e.g., adding security requirements)
   - **PATCH**: Clarifications, wording, typo fixes
4. Update to this file and sync report in HTML comment header

### Compliance & Enforcement

- **All PRs**: Reviewers verify compliance with Principles I-VII
- **Complexity Justification**: Violations of simplicity (e.g., adding 4th service when 3 exist) require documented rationale in `plan.md` Complexity Tracking section
- **Spec Updates**: Architectural changes without spec updates are rejected
- **Test Coverage**: Code without deterministic tests (per Principle II) requires explicit justification

### Development Guidance

Runtime development guidance (build commands, local dev setup, framework versions) lives in `CLAUDE.md`, not in this constitution. The constitution defines what (principles), CLAUDE.md defines how (commands).

**Version**: 1.0.0 | **Ratified**: 2025-12-24 | **Last Amended**: 2025-12-24
