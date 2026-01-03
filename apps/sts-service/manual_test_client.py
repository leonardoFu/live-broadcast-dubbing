#!/usr/bin/env python3
"""
Manual Test Client for Full STS Service

This script sends audio chunks to the running STS service and displays results.
"""
import asyncio
import base64
import subprocess
import sys
import time
from pathlib import Path

try:
    import socketio
except ImportError:
    print("ERROR: python-socketio not installed")
    print("Run: pip install python-socketio")
    sys.exit(1)


async def main():
    print("=" * 60)
    print("Full STS Service - Manual Test Client")
    print("=" * 60)

    # Audio file path
    audio_file = Path("../../tests/fixtures/test-streams/1-min-nfl.m4a")
    if not audio_file.exists():
        print(f"ERROR: Audio file not found: {audio_file}")
        sys.exit(1)

    # Extract 6 seconds of audio starting at 5 seconds in M4A/AAC format
    print("\n📁 Extracting audio chunk (6 seconds from 5s mark) as M4A/AAC...")
    temp_file = Path("/tmp/claude/test_chunk.m4a")
    temp_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-ss", "5.0", "-t", "6.0",
        "-i", str(audio_file),
        "-ar", "44100", "-ac", "1",  # 44.1kHz mono
        "-c:a", "aac",  # AAC codec
        str(temp_file)
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"ERROR: ffmpeg failed: {result.stderr.decode()}")
        sys.exit(1)

    # Read and encode the M4A file
    audio_bytes = temp_file.read_bytes()
    audio_b64 = base64.b64encode(audio_bytes).decode()

    print(f"✓ Audio chunk ready: {len(audio_bytes)} bytes (M4A/AAC format)")

    # Socket.IO client
    sio = socketio.AsyncClient()
    results = []

    @sio.event
    async def connect():
        print("\n✅ Connected to server")

    @sio.event
    async def disconnect():
        print("\n❌ Disconnected from server")

    @sio.event
    async def stream_ready(data):
        print(f"\n🎬 Stream Ready!")
        print(f"   Session ID: {data.get('session_id')}")
        print(f"   Capabilities: {data.get('capabilities', {})}")

    @sio.event
    async def fragment_ack(data):
        print(f"\n✓ Fragment ACK received:")
        print(f"   Fragment ID: {data.get('fragment_id')}")
        print(f"   Timestamp: {data.get('timestamp')}")

    @sio.event
    async def fragment_processed(data):
        print(f"\n📦 Fragment Processed:")
        print(f"   Fragment ID: {data.get('fragment_id')}")
        print(f"   Status: {data.get('status')}")
        print(f"   Processing time: {data.get('processing_time_ms')}ms")

        if data.get('transcript'):
            transcript = data['transcript']
            print(f"\n   🎤 Transcript (EN):")
            print(f"      {transcript}")

        if data.get('translated_text'):
            translation = data['translated_text']
            print(f"\n   🌍 Translation (ES):")
            print(f"      {translation}")

        if data.get('dubbed_audio'):
            audio_data = data['dubbed_audio']
            audio_b64 = audio_data.get('data_base64', '')
            print(f"\n   🔊 Dubbed Audio:")
            print(f"      Format: {audio_data.get('format')}")
            print(f"      Sample rate: {audio_data.get('sample_rate_hz')} Hz")
            print(f"      Duration: {audio_data.get('duration_ms')} ms")
            print(f"      Size: {len(audio_b64)} bytes (base64)")

            # Save dubbed audio (already in M4A format)
            if audio_b64:
                dubbed_bytes = base64.b64decode(audio_b64)
                m4a_file = Path("./test_dubbed_output.m4a")
                m4a_file.write_bytes(dubbed_bytes)
                print(f"      ✓ Saved to: {m4a_file}")
                print(f"      ✓ Ready to play: ffplay {m4a_file}")

        if data.get('stage_timings'):
            timings = data['stage_timings']
            print(f"\n   ⏱️  Stage Timings:")
            print(f"      ASR: {timings.get('asr_ms')}ms")
            print(f"      Translation: {timings.get('translation_ms')}ms")
            print(f"      TTS: {timings.get('tts_ms')}ms")

        results.append(data)

    @sio.event
    async def backpressure_state(data):
        print(f"\n   ⚠️  Backpressure: {data.get('severity')} - {data.get('current_inflight')} in-flight")

    @sio.event
    async def error(data):
        print(f"\n❌ Error received:")
        print(f"   Code: {data.get('code')}")
        print(f"   Message: {data.get('message')}")
        print(f"   Severity: {data.get('severity')}")

    # Run test
    try:
        # Connect
        print("\n🔌 Connecting to http://localhost:8003...")
        await sio.connect("http://localhost:8003")
        await asyncio.sleep(1)

        # Init stream
        print("\n📝 Initializing stream with config:")
        config = {
            "source_language": "en",
            "target_language": "es",
            "voice_profile": "default",
            "chunk_duration_ms": 6000,
            "sample_rate_hz": 44100,
            "channels": 1,
            "format": "m4a"
        }
        print(f"   Source: {config['source_language']} → Target: {config['target_language']}")
        print(f"   Chunk duration: {config['chunk_duration_ms']}ms")
        print(f"   Audio format: {config['format']} @ {config['sample_rate_hz']}Hz")

        # StreamInitPayload requires stream_id and worker_id
        stream_init_payload = {
            "stream_id": "manual-test-stream",
            "worker_id": "manual-test-worker",
            "config": config
        }
        await sio.emit("stream:init", stream_init_payload)
        await asyncio.sleep(3)

        # Send fragment
        print("\n⬆️  Sending fragment...")
        fragment_data = {
            "fragment_id": "manual-test-001",
            "stream_id": "manual-test-stream",
            "sequence_number": 0,
            "timestamp": int(time.time() * 1000),  # Unix timestamp in milliseconds
            "audio": {
                "format": "m4a",
                "sample_rate_hz": 44100,
                "channels": 1,
                "duration_ms": 6000,
                "data_base64": audio_b64
            }
        }
        await sio.emit("fragment:data", fragment_data)

        # Wait for processing
        print("\n⏳ Waiting for processing (up to 25 seconds)...")
        await asyncio.sleep(25)

        # End stream
        print("\n🛑 Ending stream...")
        await sio.emit("stream:end", {})
        await asyncio.sleep(2)

        # Disconnect
        print("\n👋 Disconnecting...")
        await sio.disconnect()

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        if sio.connected:
            await sio.disconnect()
        return

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Fragments processed: {len(results)}")

    if results:
        result = results[0]
        print(f"\nResult Details:")
        print(f"  Status: {result.get('status')}")
        print(f"  Processing time: {result.get('processing_time_ms')}ms")
        print(f"  Has transcript: {bool(result.get('transcript'))}")
        print(f"  Has translation: {bool(result.get('translated_text'))}")
        print(f"  Has dubbed audio: {bool(result.get('dubbed_audio'))}")

    print("\n💾 Check artifacts at: /tmp/claude/sts-artifacts/manual-test-stream/manual-test-001/")
    print("   - transcript.txt")
    print("   - translation.txt")
    print("   - dubbed_audio.m4a")
    print("   - original_audio.m4a")
    print("   - metadata.json")

    print("\n✅ Manual test complete!")


if __name__ == "__main__":
    asyncio.run(main())
