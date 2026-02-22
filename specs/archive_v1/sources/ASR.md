# ASR (Automatic Speech Recognition) Pipeline

This repo’s ASR logic lives in `.sts-service-archive/utils/transcription.py` and is built around **faster-whisper**. It supports both “batch” transcription of an audio array and a threaded “streaming” wrapper that processes chunks continuously.

## Main Entry Points

- `transcribe_audio_chunk(audio_data, sample_rate, model, domain=...)` → returns `[(start_s, end_s, text, confidence), ...]` relative to the provided chunk.
- `StreamingTranscriber` → a background-thread wrapper that accepts audio chunks and yields `(abs_start_s, abs_end_s, text)` results.

## End-to-End Flow

1. **Model load + cache**
   - `get_whisper_model(model_size="base", device="cpu")` loads a `WhisperModel` once and caches it in `_whisper_cache` by `(model_size, device)`.
   - If `device == "mps"`, it prints a warning and falls back to `cpu` (faster-whisper MPS is not supported here).
   - Uses `compute_type="int8"` on CPU, otherwise `"float16"`.

2. **Audio preprocessing (quality-oriented)**
   - `preprocess_audio_for_transcription(audio_data, sample_rate)`:
     - Casts to `float32` (Whisper compatibility).
     - Normalizes amplitude (`librosa.util.normalize`).
     - High-pass filters at ~80 Hz (4th order Butterworth via `scipy.signal`) to reduce low-frequency rumble.
     - Applies pre-emphasis (`librosa.effects.preemphasis`) as a light “noise reduction / clarity” step.
     - Normalizes again.

3. **Domain priming (prompting)**
   - `get_domain_prompt(domain)` returns an `initial_prompt` string tuned for domains like `sports`, `news`, `interview`, etc.
   - That prompt is passed into Whisper transcription to bias recognition toward expected vocabulary/proper nouns.

4. **Whisper transcription (faster-whisper)**
   - `model.transcribe(...)` is called with:
     - `language="en"` (English assumed)
     - `word_timestamps=True`
     - `vad_filter=True` with `min_silence_duration_ms=300` (more sensitive utterance detection)
     - Accuracy/robustness settings: `beam_size=8`, `best_of=8`, temperature ensemble `[0.0, 0.2, 0.4]`
     - Quality guards: `compression_ratio_threshold=2.4`, `log_prob_threshold=-1.0`, `no_speech_threshold=0.6`
     - Context carryover: `condition_on_previous_text=True`
     - `initial_prompt=<domain prompt>`

5. **Per-segment postprocessing**
   - For each returned Whisper segment with non-empty text:
     - **Confidence score** is derived from `segment.avg_logprob`, mapped into `[0, 1]` via:
       - `confidence = clamp((avg_logprob + 1.0) / 1.0, 0.0, 1.0)`
     - **Text enhancement** via `enhance_with_ner(text, domain)`:
       - Basic punctuation-based capitalization fixes.
       - Sports-only heuristics in `_enhance_sports_entities()` (e.g., `NFL`, `Touchdown`, position names).

6. **Utterance shaping (boundary improvements)**
   - `improve_sentence_boundaries(segments)` merges very short segments (`< 1s`) into the previous segment when the previous text does *not* end with `. ! ?`.
   - `split_long_segments(segments, max_duration=6.0)` breaks up long segments to reduce downstream latency:
     - Prefers sentence boundaries (`". "`), then punctuation, then a forced midpoint split near whitespace.

## Streaming Mode (Threaded)

`StreamingTranscriber` provides a simple real-time interface:

- `start()` loads the Whisper model and starts `_transcription_worker()` in a background thread.
- `add_audio_chunk(audio_data, sample_rate, timestamp)` enqueues `(audio_data, sample_rate, timestamp)` into `audio_buffer`.
- `_transcription_worker()`:
  - Pops chunks from the queue, runs `transcribe_audio_chunk(...)`, then pushes `(abs_start, abs_end, text)` to `result_queue` by adding the chunk’s `timestamp` to each relative segment time.
- `get_transcription_results()` yields results as they become available until `stop()` is called and the queue is drained.

## Key Assumptions / Limitations

- Input language is hard-coded to English (`language="en"`).
- “NER” is heuristic-only (regex/capitalization rules), not a true named-entity model.
- Confidence is a simple mapping from average log probability; it is useful as a relative indicator, not a calibrated probability.

## Reference Code (Python)

This is a copy/paste-friendly reference implementation matching `.sts-service-archive/utils/transcription.py`.

```python
#!/usr/bin/env python3
"""
ASR reference pipeline using faster-whisper with real-time chunk processing.

Primary goals:
- Low-latency chunk transcription suitable for streaming.
- Stable utterance segmentation (merge tiny segments, split long ones).
- Domain prompting + light text cleanup to improve readability.
"""

from __future__ import annotations

import queue
import threading
from typing import Dict, Iterator, List, Optional, Tuple

import librosa
import numpy as np
import scipy.signal

try:
    from faster_whisper import WhisperModel
except ImportError:  # pragma: no cover
    WhisperModel = None  # type: ignore[misc,assignment]


Segment = Tuple[float, float, str, float]  # (start_s, end_s, text, confidence_0to1)

_whisper_cache: Dict[str, WhisperModel] = {}


def preprocess_audio_for_transcription(audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
    audio_data = audio_data.astype(np.float32)
    audio_data = librosa.util.normalize(audio_data).astype(np.float32)

    # High-pass filter (~80 Hz) to reduce low-frequency rumble.
    nyquist = sample_rate // 2
    high_cutoff = 80
    sos = scipy.signal.butter(4, high_cutoff / nyquist, btype='high', output='sos')
    audio_data = scipy.signal.sosfilt(sos, audio_data).astype(np.float32)

    # Light pre-emphasis for speech clarity.
    audio_data = librosa.effects.preemphasis(audio_data, coef=0.97).astype(np.float32)
    audio_data = librosa.util.normalize(audio_data).astype(np.float32)
    return audio_data


def get_whisper_model(model_size: str = 'base', device: str = 'cpu') -> Optional[WhisperModel]:
    if WhisperModel is None:
        return None

    # faster-whisper MPS is not supported in this pipeline.
    if device == 'mps':
        device = 'cpu'

    cache_key = f'{model_size}_{device}'
    if cache_key not in _whisper_cache:
        _whisper_cache[cache_key] = WhisperModel(
            model_size,
            device=device,
            compute_type='float16' if device != 'cpu' else 'int8',
        )
    return _whisper_cache[cache_key]


def get_domain_prompt(domain: str = 'sports') -> str:
    base_prompt = 'This is a {domain_type} broadcast with {key_elements}.'
    domain_configs = {
        'sports': {
            'domain_type': 'sports commentary',
            'key_elements': 'team names, player names, game statistics, play-by-play analysis, and sports terminology',
        },
        'football': {
            'domain_type': 'American football commentary',
            'key_elements': 'team names, player names, yard lines, penalties, touchdowns, field goals, and detailed play descriptions',
        },
        'basketball': {
            'domain_type': 'basketball commentary',
            'key_elements': 'team names, player names, scores, fouls, timeouts, and game strategy analysis',
        },
        'news': {
            'domain_type': 'news broadcast',
            'key_elements': 'proper names, locations, dates, and formal speech patterns',
        },
        'interview': {
            'domain_type': 'interview',
            'key_elements': 'conversational speech, questions and answers, and natural pauses',
        },
        'general': {
            'domain_type': 'general speech',
            'key_elements': 'proper names, locations, and natural conversation patterns',
        },
    }

    config = domain_configs.get(domain, domain_configs['general'])
    return base_prompt.format(**config)


def _enhance_sports_entities(text: str) -> str:
    import re

    sports_patterns = [
        (r'\b(nfl|nba|mlb|nhl)\b', lambda m: m.group(1).upper()),
        (
            r'\b(touchdown|field goal|penalty|yard|yards|first down|second down|third down|fourth down)\b',
            lambda m: m.group(1).title(),
        ),
        (
            r'\b(quarterback|running back|wide receiver|tight end|defensive back|linebacker)\b',
            lambda m: m.group(1).title(),
        ),
        (r'\b(playoff|super bowl|championship|conference)\b', lambda m: m.group(1).title()),
    ]

    enhanced = text
    for pattern, repl in sports_patterns:
        enhanced = re.sub(pattern, repl, enhanced, flags=re.IGNORECASE)
    return enhanced


def enhance_with_ner(text: str, domain: str = 'sports') -> str:
    """
    Heuristic-only cleanup (not a true NER model):
    - Basic capitalization fixes
    - Domain-specific title-casing for common sports entities
    """
    import re

    text = re.sub(r'(\.|!|\?)\s*([a-z])', lambda m: m.group(1) + ' ' + m.group(2).upper(), text)
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    if domain == 'sports':
        text = _enhance_sports_entities(text)
    return text


def improve_sentence_boundaries(segments: List[Segment]) -> List[Segment]:
    if not segments:
        return segments

    improved: List[Segment] = []
    current: Optional[Segment] = None

    for start_s, end_s, text, conf in segments:
        text = text.strip()
        if not text:
            continue

        # Merge very short segments into previous, unless previous already ends a sentence.
        if current and (end_s - start_s) < 1.0:
            prev_text = current[2]
            if not prev_text.endswith(('.', '!', '?')):
                prev_conf = current[3]
                avg_conf = (prev_conf + conf) / 2
                current = (current[0], end_s, f'{prev_text} {text}', avg_conf)
                continue

        if current:
            improved.append(current)
        current = (start_s, end_s, text, conf)

    if current:
        improved.append(current)
    return improved


def split_long_segments(segments: List[Segment], max_duration: float = 6.0) -> List[Segment]:
    """
    Split long segments to reduce downstream latency (MT/TTS) while trying to keep coherence.
    """
    import re

    out: List[Segment] = []
    for start_s, end_s, text, conf in segments:
        duration = end_s - start_s
        if duration <= max_duration:
            out.append((start_s, end_s, text, conf))
            continue

        # Prefer sentence boundaries first.
        sentences = text.split('. ')
        if len(sentences) > 1:
            time_per_sentence = duration / len(sentences)
            for i, sentence in enumerate(sentences):
                if i < len(sentences) - 1:
                    sentence += '.'
                seg_start = start_s + (i * time_per_sentence)
                seg_end = start_s + ((i + 1) * time_per_sentence)
                sentence = sentence.strip()
                if sentence:
                    out.append((seg_start, seg_end, sentence, conf))
            continue

        # Fallback: split by punctuation or conjunction boundaries.
        split_spans = [
            (m.start(), m.end())
            for m in re.finditer(r'(,|;|\s+(?:and|but|so)\s+)', text, flags=re.IGNORECASE)
        ]
        if split_spans:
            prev_pos = 0
            time_per_char = duration / len(text)
            for span_start, span_end in split_spans:
                seg_start = start_s + (prev_pos * time_per_char)
                seg_end = start_s + (span_start * time_per_char)
                part = text[prev_pos:span_start].strip()
                if part:
                    out.append((seg_start, seg_end, part, conf))
                prev_pos = span_end

            if prev_pos < len(text):
                seg_start = start_s + (prev_pos * time_per_char)
                part = text[prev_pos:].strip()
                if part:
                    out.append((seg_start, end_s, part, conf))
            continue

        # Last resort: midpoint split near whitespace.
        mid_time = start_s + (duration / 2)
        mid_pos = len(text) // 2
        for i in range(mid_pos, len(text)):
            if text[i] == ' ':
                mid_pos = i
                break

        first = text[:mid_pos].strip()
        second = text[mid_pos:].strip()
        if first:
            out.append((start_s, mid_time, first, conf))
        if second:
            out.append((mid_time, end_s, second, conf))

    return out


def transcribe_audio_chunk(
    audio_data: np.ndarray,
    sample_rate: int,
    model: WhisperModel,
    domain: str = 'sports',
) -> List[Segment]:
    audio_data = preprocess_audio_for_transcription(audio_data, sample_rate)
    initial_prompt = get_domain_prompt(domain)

    segments, _info = model.transcribe(
        audio_data,
        language='en',
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300),
        beam_size=8,
        best_of=8,
        temperature=[0.0, 0.2, 0.4],
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        no_speech_threshold=0.6,
        condition_on_previous_text=True,
        initial_prompt=initial_prompt,
    )

    results: List[Segment] = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        # Map avg_logprob into a 0..1-ish "confidence" indicator.
        confidence = min(1.0, max(0.0, (seg.avg_logprob + 1.0) / 1.0))
        results.append((seg.start, seg.end, enhance_with_ner(text, domain), confidence))

    results = improve_sentence_boundaries(results)
    results = split_long_segments(results)
    return results


class StreamingTranscriber:
    """
    Threaded wrapper for real-time chunk transcription.

    - Producer: `add_audio_chunk(...)`
    - Consumer: `get_transcription_results()`
    """

    def __init__(self, model_size: str = 'base', device: str = 'cpu'):
        self.model_size = model_size
        self.device = device
        self.model: Optional[WhisperModel] = None
        self.running = False
        self.transcription_thread: Optional[threading.Thread] = None
        self.audio_buffer: 'queue.Queue[Tuple[np.ndarray, int, float]]' = queue.Queue()
        self.result_queue: 'queue.Queue[Tuple[float, float, str]]' = queue.Queue()

    def start(self) -> bool:
        self.model = get_whisper_model(self.model_size, self.device)
        if self.model is None:
            return False
        self.running = True
        self.transcription_thread = threading.Thread(target=self._transcription_worker)
        self.transcription_thread.start()
        return True

    def stop(self) -> None:
        self.running = False
        if self.transcription_thread:
            self.transcription_thread.join()

    def add_audio_chunk(self, audio_data: np.ndarray, sample_rate: int, timestamp: float) -> None:
        self.audio_buffer.put((audio_data, sample_rate, timestamp))

    def get_transcription_results(self) -> Iterator[Tuple[float, float, str]]:
        while self.running or not self.result_queue.empty():
            try:
                yield self.result_queue.get(timeout=0.1)
            except queue.Empty:
                continue

    def _transcription_worker(self) -> None:
        while self.running:
            try:
                audio_data, sample_rate, timestamp = self.audio_buffer.get(timeout=1.0)
            except queue.Empty:
                continue

            if self.model is None:
                continue

            for seg_start, seg_end, text, _conf in transcribe_audio_chunk(
                audio_data, sample_rate, self.model
            ):
                self.result_queue.put((timestamp + seg_start, timestamp + seg_end, text))
```
