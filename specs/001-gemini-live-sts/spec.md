# Feature Specification: Live STS Cloud Integration

**Feature Branch**: `001-gemini-live-sts`  
**Created**: 2025-12-18  
**Status**: Draft  
**Input**: User description: "Switch STS from self-hosted models to a managed live speech service that translates to a target language and returns dubbed audio clips in real time."

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Live dubbed audio for a stream (Priority: P1)

A stream operator runs the live pipeline and selects a target language for a stream. The system produces dubbed speech audio in the target language as time-aligned audio clips suitable for mixing and republishing the stream.

**Why this priority**: This is the core value: producing intelligible, target-language dubbed speech for a live stream without hosting models locally.

**Independent Test**: Can be fully tested by feeding a short, recorded speech clip into the STS path and confirming it outputs (a) dubbed audio clips and (b) optional transcript text for the selected target language.

**Acceptance Scenarios**:

1. **Given** valid provider credentials and a supported target language, **When** live/recorded speech audio is provided, **Then** the system returns dubbed audio clips in the target language and associates them to the correct stream timeline.
2. **Given** the same input audio and configuration, **When** the same test is run twice, **Then** the system produces output that is stable enough to validate correctness (no missing clips; consistent clip ordering and timing metadata).

---

### User Story 2 - Keep the stream running during STS disruptions (Priority: P2)

A stream operator expects the stream to remain playable even when the managed STS service is slow or temporarily unavailable. The system continues producing output audio using explicit fallbacks while recording the failure for troubleshooting.

**Why this priority**: Live streams cannot pause for STS failures; continuity and predictable fallback behavior prevents outages and makes issues diagnosable.

**Independent Test**: Can be fully tested with a deterministic stub that simulates timeouts/rate limits and validates fallback audio behavior and error recording without contacting any external services.

**Acceptance Scenarios**:

1. **Given** the STS provider returns transient errors or times out, **When** audio continues arriving, **Then** the system applies the configured fallback (e.g., pass-through original audio) and continues producing output without blocking indefinitely.

---

### User Story 3 - Control latency/cost and observe quality (Priority: P3)

A stream operator configures operational limits (timeouts, concurrency, and usage guardrails) and can see whether dubbing is healthy via logs/metrics, without exposing secrets or raw media.

**Why this priority**: Managed STS introduces usage-based costs and variable latency; guardrails and observability prevent runaway spend and enable fast debugging.

**Independent Test**: Can be fully tested by running a controlled input stream and verifying emitted metrics/logs reflect latency, error rates, and applied workload limits without containing sensitive values.

**Acceptance Scenarios**:

1. **Given** configured limits (timeouts, max in-flight work), **When** the system is overloaded, **Then** it limits queued work and degrades in a bounded way while surfacing the condition via metrics/logs.

---

### Edge Cases

- Missing/invalid provider credentials at startup.
- Target language is unsupported or malformed.
- Long silence/no-speech input (should not hallucinate continuous output).
- Provider returns audio but no transcript (or transcript but no audio).
- Provider latency spikes beyond the configured timeout budget.
- Rate limiting/quota exhaustion mid-stream.
- Out-of-order or duplicated output chunks/clips (ordering must be enforced before emission).

### Test Assets (Mock Fixtures)

- **Required assets**:
  - 5–10s deterministic speech audio clip (clean voice, single speaker)
  - 5–10s silence/near-silence clip
  - Optional: 5–10s “noisy background + speech” clip (to validate robustness)
- **How to provide**: Store locally outside the repo and point tests to it via a configurable path.
- **Constraints**: No secrets, no production media, keep deterministic and redistributable.

## Requirements *(mandatory)*

### Functional Requirements

**Dependencies & assumptions (for scope/boundedness)**:
- Requires access to a managed live speech service account and credentials in the runtime environment.
- Assumes the system can make outbound network connections to the managed service with stable enough bandwidth for real-time audio.
- Assumes each stream session has a configured target language for the duration of the session.

- **FR-001**: System MUST support using a managed live Speech→Text→(Translate)→Speech capability to produce target-language dubbed speech for live audio input (verifiable by producing dubbed audio from a recorded speech clip).
- **FR-002**: System MUST allow configuring a per-stream target language and voice/profile selection at session start (verifiable by running two sessions with different settings and confirming the system records and applies the chosen settings for each session).
- **FR-003**: System MUST emit dubbed speech as discrete, ordered audio clips with associated stream timing metadata (verifiable by confirming clip ordering and timing that never goes backwards per stream).
- **FR-004**: System MUST provide an optional text transcript output aligned to the same stream timeline as the dubbed clips (verifiable by enabling transcript output and receiving text with timing metadata).
- **FR-005**: System MUST limit concurrency and queue growth to avoid unbounded backlog and uncontrolled usage (verifiable by load testing and observing capped in-flight work and explicit degradation behavior).
- **FR-006**: System MUST define and apply explicit fallback behavior when the managed STS service is unavailable (e.g., pass-through original audio or silence), without stopping the stream (verifiable by injecting failures and confirming continuous output).
- **FR-007**: System MUST classify and record errors in a structured way that supports retries for transient failures and “fail fast” for non-retryable failures (verifiable by simulated error cases producing expected classifications).
- **FR-008**: System MUST be testable without external service access via deterministic stubs/mocks that emulate audio-clip outputs and error modes (verifiable by running the test suite offline).
- **FR-009**: System MUST avoid logging secrets and MUST avoid logging raw audio payloads by default (verifiable by inspecting logs from a representative run).
- **FR-010**: System MUST emit operational metrics for latency, error rate, and fallback rates per stream (verifiable by observing metrics populated during a run).

### Key Entities *(include if feature involves data)*

- **Stream Session**: A live processing session for a single stream, including selected target language, voice/profile, and the session lifecycle state.
- **Audio Fragment**: A time-bounded slice of incoming audio associated with a stream timeline and sequence number.
- **Dubbed Audio Clip**: A time-bounded slice of synthesized target-language speech aligned to the stream timeline (and optionally paired with transcript text).
- **STS Outcome Record**: A per-fragment record of status (`success | partial | failed | fallback`), latency, and any error classifications used for debugging and reporting.

## Interfaces & Operational Constraints *(if applicable)*

<!--
  If this feature changes how systems communicate (Socket.IO/HTTP/files) or touches real-time media
  processing, capture the contract and operational expectations here.
-->

### Interfaces / Protocols

- **Changed interfaces**: Internal STS execution changes from self-hosted models to a managed live speech service; the worker continues to request “dubbed audio per fragment” from an STS backend boundary.
- **Contract documentation**: `specs/004-sts-pipeline-design.md`, `specs/003-gstreamer-stream-worker.md`
- **Compatibility**: Backward compatible at the worker↔STS boundary if the existing in-process interface remains; implementation behind the boundary changes.

### Real-Time / Streaming Constraints

- **Latency budget impact**: Expected to reduce local compute constraints but introduce network + provider processing variability; measure end-to-end “speech in → dubbed speech out” latency distribution (including 50th and 95th percentile) per stream.
- **Latency budget impact**: Expected to reduce local compute constraints but introduce network + provider processing variability; measure end-to-end “speech in → dubbed speech out” latency (typical and worst-case) per stream.
- **A/V sync risks**: Variable STS latency can cause dubbed speech drift vs video; bound drift via per-fragment timing metadata and apply defined fallback if drift exceeds a configured threshold.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: First dubbed audio is audible within 5 seconds of starting a session in a local test run (measured from session start to first emitted dubbed clip).
- **SC-002**: Steady-state dubbing latency (speech input to dubbed output) is ≤ 8 seconds for at least 95% of 1–2s audio fragments in a controlled test run.
- **SC-003**: Over a 10-minute test run, dubbed audio timing drift relative to the stream timeline remains within ±250 ms for at least 95% of fragments, or the system triggers the documented fallback behavior.
- **SC-004**: In a controlled failure injection test, the stream remains continuously playable and recovers from a transient STS outage within 10 seconds without manual intervention.
