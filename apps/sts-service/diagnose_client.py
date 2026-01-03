#!/usr/bin/env python3
"""Diagnostic client to test Socket.IO events."""
import asyncio
import socketio

sio = socketio.AsyncClient()
events_received = []


@sio.event
async def connect():
    print("✅ Connected to server")
    events_received.append("connect")


@sio.event
async def welcome(data):
    print(f"✅ Received 'welcome' event: {data}")
    events_received.append("welcome")


@sio.event
async def test_response(data):
    print(f"✅ Received 'test_response' event: {data}")
    events_received.append("test_response")


async def main():
    print("Connecting to diagnostic server...")
    await sio.connect("http://127.0.0.1:8999")
    await asyncio.sleep(2)

    print("\n📤 Sending test_request...")
    await sio.emit("test_request", {"test": "data"})
    await asyncio.sleep(2)

    print(f"\n📊 Events received: {events_received}")
    print(f"Expected: ['connect', 'welcome', 'test_response']")

    if len(events_received) == 3:
        print("✅ All events received - Socket.IO working correctly")
    else:
        print(f"❌ Missing events - only received {len(events_received)}/3")

    await sio.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
