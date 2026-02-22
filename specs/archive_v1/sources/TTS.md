# TTS (Text-to-Speech) Pipeline

This repo’s TTS is implemented primarily in `.sts-service-archive/talk_multi_coqui.py` and used by the live servers (`.sts-service-archive/stream_audio_client.py`, `.sts-service-archive/simple_vits_server.py`). The design goal is **real-time multilingual speech synthesis** with predictable latency, optional **voice cloning**, and **duration matching** so synthesized speech fits the timing of the source audio (live fragments) or subtitles (VTT).

## Main Entry Points (as used in STS)

- Model + voice selection
  - `.sts-service-archive/coqui-voices.yaml` provides per-language `model` (typically XTTS-v2) and optional `fast_model` (often VITS).
  - `get_speaker_voice(voices, language, speaker)` chooses `(model_name, speaker_id, voice_sample_path)`.
- Synthesis
  - `get_tts(model_name)` loads and caches the Coqui model (`TTS.api.TTS`) by name.
  - `synth_to_wav(text, model_name, speaker=..., target_language=..., voice_sample_path=..., speed=...)` generates a WAV file (XTTS-v2 path or VITS path).
- Duration alignment (post-processing)
  - `adjust_audio_speed(...)` (and server equivalents) call the `rubberband` CLI to time-stretch while preserving pitch.

## Dependencies and External Tools

- **Coqui TTS**: `TTS.api.TTS` (Torch-based synthesis, model zoo IDs like `tts_models/multilingual/multi-dataset/xtts_v2`).
- **PyTorch**: required by Coqui models; STS forces TTS to **CPU** to avoid Apple MPS limits with XTTS-v2.
- **Audio I/O**: `soundfile` (read/write WAV), `sounddevice` (local playback in scripts).
- **Resampling**: `librosa` (resample TTS audio to match original sample rate).
- **Time-stretching**: `rubberband` (external binary) for high-quality tempo change with pitch/formant preservation.
- **(Live path) Encoding**: `ffmpeg` (via `ffmpeg-python`) to package the synthesized audio back into the streaming container.

## End-to-End Flow (Real-Time)

1. **Input text arrives**
   - Usually from ASR + MT (see `.sts-service-archive/ASR.md` and `.sts-service-archive/TRANSLATION.md`).
   - Speaker labels may be detected and removed before MT/TTS (text-based or audio-based, depending on server).

2. **Voice/model selection**
   - Choose a language-specific model from `coqui-voices.yaml`:
     - **Standard**: XTTS-v2 (multilingual, supports cloning via `speaker_wav`).
     - **Fast mode**: often VITS/Tacotron2 variants for lower latency (usually no cloning).
   - Choose the speaker profile:
     - If a `voice_sample` is configured and exists, use it for cloning (XTTS-v2).
     - Otherwise fall back to a named speaker (e.g., `Andrew Chipper`) or single-speaker synthesis.

3. **Model load + caching**
   - Coqui models are loaded once and cached in-memory by `model_name`.
   - STS forces `DEVICE = "cpu"` for XTTS-v2 stability.
   - `talk_multi_coqui.py` monkey-patches `torch.load(weights_only=False)` for Coqui compatibility.

4. **TTS text preprocessing (TTS-quality)**
   - Runs `preprocess_text_for_tts(text, convert_numbers=False)` before synthesis to normalize punctuation/abbreviations and avoid number-conversion issues for non-English targets.

5. **Synthesis**
   - **XTTS-v2 path**
     - Calls `tts.tts_to_file(...)` with:
       - `language=<target_language>`
       - Optional `speaker_wav=<voice_sample>` for cloning
       - Optional `speed=<speed>` (used as a coarse control; exact timing is handled by post-processing)
   - **VITS path (fast models)**
     - Uses a simplified synthesis path and multiple fallbacks:
       - Try `tts_to_file(text, file_path)`
       - Try `tts_to_file(..., speed=...)`
       - Fall back to `tts.tts(...)` and write the returned audio array to WAV

6. **Duration matching (critical for real-time)**
   - Compute:
     - `original_duration` (fragment duration or VTT cue duration)
     - `baseline_duration` (duration of synthesized WAV)
     - `required_speed = baseline_duration / original_duration`
   - Apply clamping to avoid extreme artifacts:
     - **Live fragments** typically clamp to `[1.0, 2.0]` (only speed up; never slow down).
     - **VTT alignment** may clamp to a broader range (e.g., `[0.5, 2.0]`).
   - Apply `rubberband` time-stretching to match the target duration while preserving pitch.

7. **Sample rate alignment**
   - Load the synthesized WAV (`soundfile`) and resample (`librosa`) if the model sample rate differs from the live audio sample rate.

8. **(Optional) Background mixing**
   - `simple_vits_server.py` optionally mixes synthesized speech with the original audio’s background/ambient noise to preserve the “live” feel.

9. **Output**
   - Live servers encode the final PCM back into the stream container (via FFmpeg) and emit it downstream.

## Real-Time “Quality Tuning” Heuristics

- **Two-stage timing control**: generate a baseline voice, then match timing with `rubberband` (higher quality than forcing the model to speak extremely fast/slow).
- **Speed clamping**: prevents unintelligible speech and artifacts under timing pressure.
- **Fast TTS mode**: switches to fast models (often VITS) to reduce latency and reduce the need for extreme time-stretching.
- **Hallucination guardrails** (live): skip TTS if text is likely nonsense (excess repetition / unrealistic word density), and fall back to original audio.
- **Voice cloning validation**: voice samples are validated/preprocessed (duration, mono, sample rate) by `.sts-service-archive/utils/voice_management.py`.

## Reference Code (Python)

This is a copy/paste-friendly reference implementation for the STS-style TTS pipeline (model caching, XTTS-v2 cloning path, VITS fast path, and rubberband duration matching). It’s designed as a spec; adapt I/O and error handling to your application.

```python
#!/usr/bin/env python3
"""
STS-style TTS reference pipeline.

Key goals:
- Real-time friendly model caching
- XTTS-v2 voice cloning when a sample is available
- Optional fast-model path (often VITS) with fallback strategies
- Post-process duration matching with rubberband (tempo change, pitch preserved)
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import librosa
import numpy as np
import soundfile as sf
import torch
import yaml

from TTS.api import TTS as CoquiTTS


# ----------------------------
# Config + caching
# ----------------------------

CACHE_DIR = Path(".cache_coqui")
CACHE_DIR.mkdir(exist_ok=True)

# XTTS-v2 is forced to CPU in STS to avoid MPS issues.
DEVICE = "cpu"

_tts_cache: Dict[str, CoquiTTS] = {}


def _sha1(*parts: str) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(p.encode("utf-8"))
    return h.hexdigest()


def load_voices_cfg(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass(frozen=True)
class VoiceSelection:
    model_name: str
    speaker: Optional[str] = None
    voice_sample_path: Optional[str] = None


def get_speaker_voice(
    voices_cfg: dict, language: str, speaker_name: str, *, fast: bool = False
) -> VoiceSelection:
    """
    Minimal selection logic matching STS usage:
    - Choose per-language model
    - Optional fast path uses `fast_model` and disables cloning/speaker params
    - Prefer speaker-specific config, else default
    - For multi-speaker XTTS, a speaker name can be used as fallback when no sample is provided
    """
    language_cfg = (voices_cfg.get("languages") or {}).get(language, {}) or {}
    model_name = language_cfg.get("fast_model") if fast else language_cfg.get("model")
    multi_speaker = bool(language_cfg.get("multi_speaker", False))

    speakers_cfg = language_cfg.get("speakers", {}) or {}
    speaker_cfg = speakers_cfg.get(speaker_name) or speakers_cfg.get("default") or {}

    voice_sample_path = speaker_cfg.get("voice_sample")
    fallback_speaker = speaker_cfg.get("speaker")

    # Fast models are treated as single-speaker/no-cloning in the STS live path.
    if fast:
        return VoiceSelection(model_name=model_name, speaker=None, voice_sample_path=None)

    # Single-speaker models should not receive a speaker param.
    speaker = fallback_speaker if multi_speaker else None
    return VoiceSelection(model_name=model_name, speaker=speaker, voice_sample_path=voice_sample_path)


def get_tts(model_name: str) -> CoquiTTS:
    """
    Load and cache a Coqui model.
    STS also patches torch.load(weights_only=False) for compatibility with some Coqui models.
    """
    if model_name not in _tts_cache:
        original_torch_load = torch.load

        def patched_torch_load(*args, **kwargs):
            kwargs["weights_only"] = False
            return original_torch_load(*args, **kwargs)

        torch.load = patched_torch_load  # type: ignore[assignment]
        _tts_cache[model_name] = CoquiTTS(model_name=model_name, progress_bar=False).to(DEVICE)
    return _tts_cache[model_name]


# ----------------------------
# TTS synthesis
# ----------------------------

def preprocess_text_for_tts(text: str) -> str:
    """
    TTS-focused cleanup matching STS defaults (convert_numbers=False):
    - Remove hyphens that cause odd prosody
    - Expand common abbreviations/symbols
    - Normalize punctuation to stable ASCII-ish forms
    """
    abbreviations: Dict[str, str] = {
        "NBA": "N B A",
        "NFL": "N F L",
        "MLB": "M L B",
        "NHL": "N H L",
        "vs": "versus",
        "vs.": "versus",
        "&": "and",
        "%": "percent",
        "$": "dollars",
        "#": "number",
        "@": "at",
        "+": "plus",
        "=": "equals",
        "/": "slash",
        "\\": "backslash",
        "*": "asterisk",
        "...": "...",
        "..": "..",
    }

    punctuation_replacements: Dict[str, str] = {
        "¡": "",
        "¿": "",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "–": "-",
        "—": "-",
        "…": "...",
    }

    text = text.strip()
    text = text.replace("-", " ")

    for abbrev, replacement in abbreviations.items():
        text = text.replace(abbrev, replacement)

    for old, new in punctuation_replacements.items():
        text = text.replace(old, new)

    # Keep ellipses; treat stray ".." (not part of "...") as a pause marker.
    text = re.sub(r"(?<!\.)\.\.(?!\.)", " .. ", text)

    # Score-like patterns: "15-12" -> "15 to 12"
    text = re.sub(r"(\d+)-(\d+)", r"\1 to \2", text)

    text = re.sub(r"[!]{2,}", "!", text)
    text = re.sub(r"[?]{2,}", "?", text)
    text = re.sub(r"[.]{4,}", "...", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def synth_to_wav_vits(text: str, model_name: str, wav_path: Path) -> None:
    """
    STS-style VITS synthesis with fallbacks.
    """
    tts = get_tts(model_name)
    processed = preprocess_text_for_tts(text)

    # 1) Basic synthesis to file
    try:
        tts.tts_to_file(text=processed, file_path=str(wav_path))
        return
    except Exception:
        pass

    # 2) Try speed param (not always supported)
    try:
        tts.tts_to_file(text=processed, file_path=str(wav_path), speed=1.0)
        return
    except Exception:
        pass

    # 3) Last resort: synthesize array and write
    audio = tts.tts(text=processed)
    if isinstance(audio, list):
        audio = np.array(audio)
    if not isinstance(audio, np.ndarray):
        raise TypeError(f"Unexpected audio type: {type(audio)}")
    sf.write(str(wav_path), audio.astype(np.float32), 22050)


def synth_to_wav_xtts(
    text: str,
    model_name: str,
    wav_path: Path,
    target_language: str,
    speaker: Optional[str],
    voice_sample_path: Optional[str],
    speed: float = 1.0,
) -> None:
    """
    XTTS-v2 path:
    - If voice_sample_path exists: clone via speaker_wav
    - Else: optionally use configured speaker name
    """
    tts = get_tts(model_name)
    processed = preprocess_text_for_tts(text)

    voice_sample = None
    if voice_sample_path and Path(voice_sample_path).exists():
        voice_sample = voice_sample_path

    if voice_sample:
        tts.tts_to_file(
            text=processed,
            file_path=str(wav_path),
            speaker_wav=voice_sample,
            language=target_language,
            speed=speed,
        )
        return

    # No cloning sample available: use speaker fallback if provided, otherwise default voice.
    kwargs = dict(text=processed, file_path=str(wav_path), language=target_language, speed=speed)
    if speaker:
        kwargs["speaker"] = speaker
    tts.tts_to_file(**kwargs)


def synth_to_wav(
    text: str,
    selection: VoiceSelection,
    target_language: str,
    speed: float = 1.0,
) -> Path:
    """
    Unified wrapper: routes to VITS fast models vs XTTS-v2-style models.
    """
    wav_path = Path(tempfile.mkstemp(suffix=".wav")[1])
    model_name = selection.model_name
    if "vits" in model_name.lower():
        synth_to_wav_vits(text, model_name, wav_path)
    else:
        synth_to_wav_xtts(
            text,
            model_name,
            wav_path,
            target_language=target_language,
            speaker=selection.speaker,
            voice_sample_path=selection.voice_sample_path,
            speed=speed,
        )
    return wav_path


# ----------------------------
# Duration matching + resampling
# ----------------------------

def get_wav_duration_s(path: Path) -> float:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=False)
    return len(audio) / sr


def adjust_audio_speed_rubberband(input_wav: Path, output_wav: Path, speed_factor: float) -> Path:
    """
    Uses rubberband tempo change:
    - speed_factor > 1.0: faster (shorter)
    - speed_factor < 1.0: slower (longer)
    """
    cmd = [
        "rubberband",
        "-T",
        str(speed_factor),
        "-p",
        "0",
        "-F",
        "-3",
        str(input_wav),
        str(output_wav),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"rubberband failed: {result.stderr}")
    return output_wav


def synthesize_aligned_audio(
    text: str,
    selection: VoiceSelection,
    target_language: str,
    target_duration_s: float,
    output_sample_rate: int,
    only_speed_up: bool = True,
) -> Tuple[np.ndarray, int]:
    """
    High-level spec function:
    - Synthesizes baseline speech to WAV
    - Time-stretches to match target_duration_s
    - Resamples to output_sample_rate
    """
    # Disk cache key is optional but matches the STS pattern.
    cache_key = _sha1("TTS", text, target_language, selection.model_name, str(selection.speaker), "aligned")
    cached_wav = CACHE_DIR / f"{cache_key}.wav"

    if cached_wav.exists():
        wav_path = cached_wav
    else:
        wav_path = synth_to_wav(text, selection, target_language=target_language, speed=1.0)

        baseline_duration = get_wav_duration_s(wav_path)
        required_speed = baseline_duration / target_duration_s
        if only_speed_up:
            required_speed = max(1.0, required_speed)
        required_speed = max(0.5, min(2.0, required_speed))

        aligned_tmp = Path(tempfile.mkstemp(suffix=".wav")[1])
        adjust_audio_speed_rubberband(wav_path, aligned_tmp, required_speed)
        wav_path.unlink(missing_ok=True)
        aligned_tmp.rename(cached_wav)
        wav_path = cached_wav

    audio, sr = sf.read(str(wav_path), dtype="float32", always_2d=False)
    if sr != output_sample_rate:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=output_sample_rate)
        sr = output_sample_rate
    return audio.astype(np.float32), sr
```
