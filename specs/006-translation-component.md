# Translation Component Spec (STS Service)

This spec defines the **Translation** component in the Speech → Text → Speech (STS) service, with a focus on **lightweight, deterministic text preprocessing** that improves translation quality and real-time stability.

It is intended to be a Stage 2 component in the STS pipeline described in `specs/004-sts-pipeline-design.md`.

---

## 1. Goal

Provide a Translation component that:
- Translates per-fragment transcript text from a source language to a target language.
- Uses **low-latency, deterministic** text normalization to reduce translation variance and improve downstream speech synthesis readability.
- Supports real-time fragment processing with ordering guarantees handled by the pipeline orchestrator (`specs/004-sts-pipeline-design.md`).

## 2. Non-Goals

- Selecting a specific machine translation provider/model.
- Defining streaming ingest/egress pipelines (see `specs/001-spec.md`, `specs/002-mediamtx.md`, `specs/003-gstreamer-stream-worker.md`).
- Performing heavy NLP post-editing (summarization, semantic rewriting, named entity disambiguation).

## 3. Where This Fits (STS Pipeline)

Per audio fragment:
1. **ASR** produces a transcript (and optional metadata).
2. **Translate (this spec)** optionally:
   - Extracts/removes speaker labels (text-only) so the label is not translated/spoken.
   - Normalizes the transcript text to reduce translation errors.
   - Produces translated text with language metadata.
3. **TTS** consumes translated text; optional TTS-oriented cleanup may be applied after translation output.

The Translation component MUST conform to the Translate stage contract in `specs/004-sts-pipeline-design.md` (§6.3).

## 4. Component Contract

### 4.1 Inputs

The Translation request MUST include:
- Fragment identifiers: `stream_id`, `sequence_number`, and a stable request/asset identifier.
- `source_text`: transcript text for the fragment.
- `source_language`: language of `source_text` (detected or specified).
- `target_language`: desired output language.

The request SHOULD include:
- `speaker_policy`: whether to detect/remove speaker labels.
- `normalization_policy`: toggles for translation-oriented normalization and optional TTS-oriented cleanup.
- `context_hints`: optional business-level context (e.g., “sports commentary”, “news”), used only to select rule presets (no semantic rewriting).

### 4.2 Outputs

The Translation response MUST include:
- `translated_text`: text in `target_language`.
- Metadata: `source_language`, `target_language`, plus lineage references (`parent_asset_ids`) per `specs/004-sts-pipeline-design.md`.

The response SHOULD include:
- `normalized_source_text`: the normalized text that was actually fed to translation.
- `speaker_id`: detected speaker label or `default`.
- `warnings`: non-fatal issues (e.g., “speaker label detected but stripped resulted in empty string”).

### 4.3 Determinism Requirement

Given the same `source_text` and policies, the normalization step MUST yield the same `normalized_source_text` (for stable caching and repeatability in tests).

## 5. Text Processing Pipeline (Pre/Post)

This component includes lightweight text processing around translation and (optionally) around TTS readiness. The processing MUST be cheap enough to run per fragment without introducing unpredictable latency spikes.

### 5.1 Speaker Label Handling (Optional)

Purpose: prevent translation and TTS from translating/speaking a label that is present as plain text.

Behavior:
- Detect a speaker label at the start of the string using conservative patterns such as:
  - `"Name: ..."` (single leading name token)
  - `">> Name: ..."`
- If detected, set `speaker_id` and remove the prefix from the text before further processing.
- If no label is detected, set `speaker_id = default` and keep text unchanged.

Constraints:
- Speaker detection MUST be text-only and MUST NOT rely on diarization or audio features.
- Speaker detection SHOULD avoid false positives that would remove legitimate sentence content.

### 5.2 Translation-Oriented Normalization (Pre-Translation)

Purpose: reduce translation errors and reduce cache churn by normalizing common ASR formatting noise.

Rules (representative, deterministic):
- **Time/clock phrases**: normalize scoreboard-style phrases by preserving the time value while making following words readable and consistently cased.
  - Example intent: `"1:54 REMAINING"` → `"1:54 remaining"`
- **Hyphen handling**: replace hyphens that frequently harm tokenization with spaces.
  - Example intent: `"TEN-YARD"` → `"TEN YARD"`
- **Abbreviation and symbol expansion**: expand/standardize common acronyms and symbols into words or spoken-letter forms.
  - Examples of intent:
    - `"NFL"` → `"N F L"` (better spoken output; may reduce translation weirdness)
    - `"vs."` → `"versus"`
    - `"&"` → `"and"`, `"%"` → `"percent"`, `"$"` → `"dollars"`, `"@"` → `"at"`
- **Numeral strategy**: by default, translation-oriented normalization SHOULD preserve numerals (to avoid unintended rewrites of numbers and time values).

### 5.3 TTS-Oriented Cleanup (Post-Translation, Optional)

Purpose: produce a string that is more consistently pronounceable and stable for speech synthesis.

Rules (representative, deterministic):
- Normalize “smart punctuation” to simple equivalents (quotes, dashes, ellipsis).
- Preserve ellipses as a natural pause marker; compress excessive punctuation runs.
- Rewrite score-like numeric hyphens to avoid being read as subtraction.
  - Example intent: `"15-12"` → `"15 to 12"`
- Normalize whitespace.

Optional numeral conversion mode:
- In contexts where converting digits to words improves spoken output or translation robustness, a policy MAY convert numerals/time expressions to words.
- This mode MUST be explicitly enabled via policy because it can change meaning in some domains.

## 6. Real-Time & Operational Constraints

- **Per-fragment bounded work**: preprocessing MUST run in bounded time and avoid unbounded backtracking or large dictionary expansions.
- **No heavy dependencies**: the component SHOULD avoid heavyweight NLP dependencies or network calls solely for preprocessing.
- **Predictable behavior**: failures in preprocessing MUST degrade gracefully (fall back to the original string and emit warnings).

## 7. Error Handling & Fallbacks

The Translation component MUST return structured errors (retryable vs non-retryable) consistent with `specs/004-sts-pipeline-design.md` (§7.2).

Fallback policies (configured at pipeline level):
- If translation fails and fallback is enabled, the pipeline MAY pass through the source transcript as the “translated” text (with an error recorded).
- If speaker removal yields an empty string, the pipeline SHOULD treat it as a non-fatal warning and fall back to the unstripped text.

## 8. Testing Strategy (Deterministic, Stub-Friendly)

### 8.1 Normalization Rule Tests (Unit)

Provide deterministic tests for:
- Speaker label detection and stripping behavior.
- Time phrase normalization.
- Hyphen-to-space normalization (including not breaking numeric score patterns when in translation-oriented mode).
- Abbreviation and symbol expansion.
- Punctuation cleanup (ellipsis preservation, punctuation collapse, whitespace normalization).
- Numeral conversion policy toggles.

### 8.2 Component Contract Tests (Functional)

Using a stub translation provider, verify:
- The component produces `translated_text` with correct language metadata.
- `normalized_source_text` reflects the applied preprocessing policy.
- Errors and warnings are surfaced without breaking the response contract.

### 8.3 Test Assets

No audio fixtures are required for this component. Recommended deterministic text fixtures:
- Sports-style samples (clock phrases, scores, acronyms).
- Conversation-style samples (speaker labels).
- Punctuation-heavy samples (ellipsis, smart quotes, repeated punctuation).

## 9. Success Criteria

- Translation preprocessing is deterministic for identical inputs and policy.
- For a representative set of domain fixtures, normalized inputs reduce translation variance (fewer distinct normalized forms for semantically equivalent text).
- The component supports per-fragment processing without causing fragment ordering violations (ordering remains the orchestrator’s responsibility per `specs/004-sts-pipeline-design.md`).

