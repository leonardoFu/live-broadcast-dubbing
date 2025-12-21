# STS Pipeline Design (Gemini Live Streaming)

## 1. Goal

Define a speech-to-speech dubbing design that uses **Gemini Live** as the streaming provider (see the Gemini Live file-stream example) for the live-stream workflow in `specs/001-spec.md`. The design must keep fragments ordered, allow fallbacks, and stay testable with deterministic stubs.

## 2. Non-Goals

- Selecting or hosting local ASR/MT/TTS models (Gemini Live replaces these stages).
- DSP specifics for separation/mixing (covered in worker specs).
- Provider authentication mechanics beyond “use injected credentials/secrets”.

## 3. Design Principles

- **Session-first**: one Gemini Live session per stream with fixed language/voice context.
- **Ordered streaming**: fragments carry sequence numbers; outputs are reordered before emission.
- **Deterministic fallbacks**: pass-through/background-only paths are always available.
- **Traceable lineage**: every response links to the input fragment and session state.
- **Low-leak logging**: no raw audio in logs; redact provider responses that may contain user content.

## 4. Pipeline Model

### 4.1 Stages

1. **Fragment prep**: normalize PCM to the worker’s internal format and attach `stream_id` + `sequence_number`.
2. **Gemini Live send**: stream the fragment into the open Gemini Live session with target language/voice instructions.
3. **Response handling**: collect Gemini Live audio + aligned text responses, map them back to `sequence_number`.
4. **Alignment**: time-stretch/trim returned audio to fragment duration when needed; note any drift.
5. **Emit result**: provide dubbed audio + text to the worker mixer with status and errors.

### 4.2 Ordering & Concurrency

- Multiple fragments may be in-flight; cap by config to bound backpressure.
- Responses may arrive out of order; the orchestrator MUST emit in `sequence_number` order.
- At-least-once delivery: retries use the same `stream_id` + `sequence_number` to avoid duplicate emissions.

## 5. Data Contracts (Inputs, Outputs, Assets)

### 5.1 Core Identifiers

- `stream_id`, `sequence_number`, `session_id`
- `asset_id`, `parent_asset_ids`
- `created_at`, `component` (e.g., `gemini-live`), `component_instance` (e.g., region/profile)

### 5.2 Input: Audio Fragment

- `stream_id`, `sequence_number`
- `audio_format`, `sample_rate_hz`, `channels`
- `start_time_ms`, `end_time_ms`
- `payload_ref` (in-memory bytes or stored asset)
- `gemini_context`: target language, voice style, optional prompt text

### 5.3 Output: Gemini Live Result (Per Fragment)

- `input_audio_fragment_asset`
- `gemini_audio_asset` (target-language speech)
- `gemini_text_asset` (aligned transcript/translation)
- `final_text` (what was spoken in the returned audio)
- `status`: `success | partial | failed | fallback`
- `errors`: list with `stage`, `error_type`, `retryable`, `message`

### 5.4 Trackable Intermediate Assets

- Raw input fragment reference
- Gemini response audio (original sample rate) + normalized/matched audio
- Gemini response text and timing (if provided)
- Per-fragment timing metrics (queue time, provider RTT, alignment delta)

### 5.5 Asset Store Expectations

- Write/read by `stream_id` + `sequence_number`
- Retain enough history for debugging/tests; configurable time-based cleanup
- No provider credentials stored with assets

## 6. Component Contracts

### 6.1 Gemini Live Session Manager

- Open/close a session per stream with fixed target language/voice prompt.
- Stream audio fragments with identifiers; handle backpressure and retries.
- Surface structured errors (timeout, rate-limit, auth, invalid input).

### 6.2 Audio Normalizer & Aligner

- Normalize outbound PCM to the Gemini-supported format.
- Normalize inbound audio to worker format; time-stretch/pad to the fragment duration.
- Flag drift beyond tolerance for logging and metrics.

### 6.3 Asset Recorder (Optional)

- Persist input/output references with lineage, behind a debug flag.
- Omit raw audio unless explicitly enabled.

## 7. Pipeline Orchestration Requirements

- **Configuration**: target language, voice profile/style, maximum in-flight fragments, fallback policy.
- **Error handling**:
  - Provider/auth errors → open breaker, use fallback audio path.
  - Missing/late responses → emit fallback for the fragment and continue.
  - Alignment failure → trim/pad, otherwise fallback.
- **Idempotency**: retries reuse `sequence_number` and do not emit duplicate outputs.
- **Health**: expose Gemini RTT histogram, in-flight gauge, breaker state, and fallback counters.

## 8. Testing Strategy (Stub-Friendly)

- Provide a deterministic stub that maps `sequence_number` → fixed audio/text fixtures.
- Include test cases for:
  - Out-of-order provider responses reordered correctly.
  - Timeout leading to fallback while keeping sequence continuity.
  - Alignment when provider audio duration differs from the fragment.

## 9. Integration with Stream Worker (Boundary)

The worker (`specs/003-gstreamer-stream-worker.md`) calls the Gemini Live session manager per fragment and receives:
- A synthesized audio asset reference (normalized to worker format)
- Gemini text for the fragment (for logs/metrics/optional captions)
- Status + errors for fallback decisions

Worker responsibilities remain:
- Chunking/timestamps, separation/mixing, and A/V sync
- Applying fallback audio when Gemini Live is unavailable or slow

## 10. Success Criteria

- One Gemini Live session per stream delivers ordered, target-language audio for each fragment.
- Intermediate lineage (input → Gemini response → normalized output) is observable for tests/debug.
- Functional tests pass using only deterministic stubs (no network), including ordering and fallback paths.
- Under concurrent fragments, outputs are emitted in fragment order with bounded drift and documented fallbacks.
