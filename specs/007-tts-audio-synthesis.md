# TTS Audio Synthesis Component (STS)

This document specifies the **Text-to-Speech (TTS)** component used by the STS pipeline. It is derived from `specs/sources/TTS.md` and follows the component/asset design in `specs/004-sts-pipeline-design.md`.

## 1. Goal

Provide a TTS component that:
- Produces **multilingual synthesized speech** with predictable latency for live fragments and subtitle-aligned (VTT) use.
- Optionally supports **voice cloning** when a voice sample is available.
- Supports **duration matching** so synthesized audio fits the timing of the source fragment/cue.
- Is **async and replaceable** as a component in the STS pipeline.
- Produces **traceable intermediate assets** for debugging and functional tests (persisted to local filesystem per run).

## 2. Role in STS Pipeline

Within the default STS pipeline (see `specs/004-sts-pipeline-design.md`):
- Input: a `TextAsset` (source or translated) + stream context (e.g., desired language/voice profile) + timing targets.
- Output: a synthesized `AudioAsset` suitable for the downstream mixer (stream worker) to combine with background audio.

This component is responsible for **speech synthesis only**. The stream worker remains responsible for mixing, A/V sync, and higher-level fallbacks (see `specs/001-spec.md`).

## 3. Component Contract (TTS)

The TTS component is a single stage with an async interface aligned to `specs/004-sts-pipeline-design.md`.

### 3.1 Inputs

Required:
- `stream_id`
- `sequence_number`
- `text_asset_id` (the text to be spoken)
- `target_language`
- `voice_profile` (logical voice selection key)
- `target_duration_ms` (desired spoken duration for alignment)
- `output_sample_rate_hz`
- `output_channels`

Optional:
- `only_speed_up` (default: true for live fragments)
- `fast_mode` (default: false; enables a low-latency synthesis path)
- `voice_sample_asset_id` (when voice cloning is enabled and sample is available)
- `speaker_id` (named speaker fallback when multi-speaker synthesis is available)
- `synthesis_speed_hint` (coarse control; exact alignment is handled via duration matching)

### 3.2 Outputs

On success, returns:
- `tts_audio_asset_id` (synthesized speech)
- `final_text` (the exact text used for synthesis after preprocessing)
- `duration_ms` (actual synthesized duration)
- `warnings` (optional list; e.g., “clamped speed factor”)

On failure, returns a structured error:
- `error_type` (e.g., `model_load_failed`, `synthesis_failed`, `alignment_failed`)
- `retryable` (true/false)
- `message`

## 4. Trackable Assets (Lineage & Observability)

To support debugging and functional tests, the TTS stage SHOULD persist (local filesystem per run) and link:
- `tts_input_text_asset` (the text as received by TTS)
- `tts_preprocessed_text_asset` (the exact text used for synthesis)
- `tts_voice_selection_asset` (resolved model/voice parameters used)
- `tts_baseline_audio_asset` (pre-alignment synth output)
- `tts_aligned_audio_asset` (post-duration-matching output; may be the final output)
- `tts_metrics_asset` (durations, applied speed factor, clamping flags, timing breakdown)

Minimum required for STS lineage:
- `tts_preprocessed_text_asset`
- `tts_aligned_audio_asset` (or equivalent final audio asset)

## 5. Configuration (Model, Voice, Fast Mode)

The component supports a voice/model selection mechanism consistent with `specs/sources/TTS.md`:
- Per-language default model selection.
- Optional `fast_model` per language when `fast_mode=true`.
- Per-voice-profile configuration that may include:
  - `voice_sample` (enables cloning when present and valid)
  - `speaker` (named speaker fallback)
  - `multi_speaker` flag (controls whether a speaker selection is applicable)

Operational constraint (STS): language/voice configuration is **fixed for the lifetime of a created worker** and provided via runtime configuration (environment/config file), not changed mid-stream.

## 6. Text Preprocessing (TTS-Quality)

Before synthesis, the component SHOULD apply deterministic preprocessing consistent with `specs/sources/TTS.md` to improve prosody and reduce synthesis failures:
- Normalize punctuation and quotation marks.
- Expand/replace common abbreviations and symbols.
- Normalize repeated punctuation and whitespace.
- Apply domain-safe rules for patterns like score formats (e.g., “15-12” → “15 to 12”).

The post-processed text MUST be recorded as `tts_preprocessed_text_asset` and returned as `final_text`.

## 7. Synthesis Paths

The component supports two synthesis paths (provider-specific naming abstracted at the contract level):

### 7.1 Standard Path (Quality)

- Uses the default per-language model selection.
- Supports voice cloning when `voice_sample_asset_id` is provided and valid.
- Falls back to a named speaker selection when multi-speaker synthesis is available and cloning sample is absent.

### 7.2 Fast Mode (Latency)

When `fast_mode=true`:
- Uses the per-language `fast_model` selection.
- Voice cloning and speaker parameters are typically disabled (treated as single-speaker).
- The output quality may be reduced in exchange for latency improvements.

## 8. Duration Matching (Critical for Live)

The component MUST support duration matching to align synthesized audio with:
- Live fragment duration, or
- Subtitle cue duration (VTT alignment)

### 8.1 Alignment Rule

Compute an alignment speed factor using:
- `baseline_duration_ms` (from baseline synthesized audio)
- `target_duration_ms` (requested)

Then apply a time-stretch operation to achieve the target duration while preserving pitch.

### 8.2 Clamping Policy

To avoid extreme artifacts, the speed factor MUST be clamped.

Defaults:
- Live fragments: clamp to `[1.0, 2.0]` when `only_speed_up=true` (never slow down; only speed up if needed).
- Subtitle alignment: clamp to a broader range (e.g., `[0.5, 2.0]`) when `only_speed_up=false`.

The applied speed factor and clamping decisions MUST be recorded in `tts_metrics_asset`.

## 9. Sample Rate / Channel Alignment

The component MUST return audio matching the requested `output_sample_rate_hz` and `output_channels`.

If the synthesis provider returns a different sample rate:
- Resample deterministically to the requested sample rate.

If the provider returns mono but `output_channels=2`:
- Apply a deterministic mono→stereo strategy (e.g., duplicate channel) and record it in metadata.

## 10. Caching & Performance

To support real-time usage:
- Models SHOULD be cached in-memory per worker lifecycle, keyed by resolved model identifier.
- Aligned outputs MAY be cached on disk (local filesystem) keyed by deterministic inputs (text, language, voice selection, alignment parameters) to improve repeatability and latency in tests and dev runs.

Cache behavior MUST NOT break traceability: returned assets still reference the resolved inputs and configuration that produced the cached artifact.

## 11. Failure Handling & Guardrails

### 11.1 Failure Categories

The component MUST distinguish at least:
- Model load failures (often retryable depending on cause)
- Synthesis failures (may be retryable)
- Alignment/time-stretch failures (may be retryable; fallback to baseline audio may be possible)
- Configuration/validation failures (typically non-retryable)

### 11.2 Guardrails (Optional but Recommended)

For live usage, the component MAY apply “hallucination”/nonsense guardrails consistent with `specs/sources/TTS.md`, such as:
- Detecting excessive repetition or unrealistic word density
- Skipping synthesis when text is likely invalid

When guardrails trigger, the component MUST return a non-success status with a structured reason so the caller can apply higher-level audio fallbacks.

## 12. Functional Testing (Stub-Friendly)

Tests should be able to run deterministically without external services by swapping in stubs consistent with `specs/004-sts-pipeline-design.md`:
- `MockTTSFixedTone`: produces a deterministic tone/silence of `target_duration_ms`.
- `MockTTSFromFixture`: returns per-`sequence_number` fixture audio.
- `MockTTSFailOnce`: fails the first call for a given fragment, then succeeds (retry behavior validation).

Functional tests SHOULD validate:
- Asset lineage (`parent_asset_ids`) from `text_asset_id` → `tts_audio_asset_id`
- Correct handling of `only_speed_up`, `fast_mode`, clamping, and resampling metadata
- Ordered emission behavior when used under the pipeline orchestrator

## 13. Reference (Source Design)

The detailed design rationale and reference pipeline (including voice selection logic, preprocessing, synthesis fallbacks, and duration matching) is captured in:
- `specs/sources/TTS.md`

