#!/usr/bin/env python3
"""Quick test to verify Socket.IO events are received."""
import asyncio
import socketio

sio = socketio.AsyncClient()
events_received = []

@sio.event
async def connect():
    print("✅ Connected")
    events_received.append("connect")

@sio.on('stream:ready')
async def on_stream_ready(data):
    print(f"✅ Received stream:ready: {data}")
    events_received.append("stream:ready")

@sio.on('fragment:ack')
async def on_fragment_ack(data):
    print(f"✅ Received fragment:ack: {data}")
    events_received.append("fragment:ack")

async def main():
    await sio.connect("http://localhost:8005")
    await asyncio.sleep(1)

    # Send stream:init
    print("📤 Sending stream:init...")
    await sio.emit("stream:init", {
        "stream_id": "test-stream",
        "worker_id": "test-worker",
        "config": {
            "source_language": "en",
            "target_language": "es",
            "voice_profile": "default",
            "chunk_duration_ms": 6000,
            "sample_rate_hz": 44100,
            "channels": 1,
            "format": "m4a"
        }
    })

    # Wait for events
    print("⏳ Waiting for events...")
    await asyncio.sleep(5)

    print(f"\n📊 Events received: {events_received}")

    await sio.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
