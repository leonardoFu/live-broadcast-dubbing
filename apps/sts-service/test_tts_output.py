#!/usr/bin/env python3
"""
Quick test to generate TTS audio and save to file for inspection.
"""
import os
import sys
import struct
import wave

sys.path.insert(0, 'src')
os.environ['COQUI_TOS_AGREED'] = '1'

from sts_service.tts.coqui_provider import CoquiTTSComponent
from sts_service.tts.models import AudioFormat

# Create TTS component with fast mode
print("Initializing Coqui TTS (fast mode)...")
tts = CoquiTTSComponent(fast_mode=True)

# Create a test text asset
from sts_service.translation.models import TextAsset

text = "Hello! This is a test of the Coqui text to speech system. The dubbing service is now working with real voice synthesis."
text_asset = TextAsset(
    asset_id="test-001",
    stream_id="test-stream",
    sequence_number=0,
    translated_text=text,
    source_text=text,
    target_language="en",
    source_language="en",
    parent_asset_ids=[],
    created_at="2026-01-03T00:00:00Z",
    component="translation",
    component_instance="test",
)

# Synthesize
print(f"Synthesizing: '{text}'")
audio_asset = tts.synthesize(text_asset=text_asset)

if audio_asset.status.value == "success":
    print(f"✓ Synthesis successful!")
    print(f"  Duration: {audio_asset.duration_ms}ms")
    print(f"  Sample rate: {audio_asset.sample_rate_hz}Hz")
    print(f"  Channels: {audio_asset.channels}")
    print(f"  Format: {audio_asset.audio_format}")
    print(f"  Processing time: {audio_asset.processing_time_ms}ms")

    # Decode base64 audio
    import base64
    audio_bytes = base64.b64decode(audio_asset.data_base64)

    # Convert PCM float32 to PCM int16 for WAV file
    num_samples = len(audio_bytes) // 4  # 4 bytes per float32
    float_samples = struct.unpack(f'<{num_samples}f', audio_bytes)

    # Convert to int16 (-32768 to 32767)
    int16_samples = [int(max(-32768, min(32767, sample * 32767))) for sample in float_samples]
    int16_bytes = struct.pack(f'<{len(int16_samples)}h', *int16_samples)

    # Save to WAV file
    output_file = 'artifacts/test_tts_output.wav'
    os.makedirs('artifacts', exist_ok=True)

    with wave.open(output_file, 'wb') as wav_file:
        wav_file.setnchannels(audio_asset.channels)
        wav_file.setsampwidth(2)  # 2 bytes for int16
        wav_file.setframerate(audio_asset.sample_rate_hz)
        wav_file.writeframes(int16_bytes)

    print(f"\n✓ Audio saved to: {output_file}")
    print(f"  File size: {len(int16_bytes)} bytes")
    print(f"  You can play it with: afplay {output_file}")
else:
    print(f"✗ Synthesis failed: {audio_asset.status}")
    if audio_asset.errors:
        for error in audio_asset.errors:
            print(f"  Error: {error.message}")
