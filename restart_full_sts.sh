#!/bin/bash
# Restart Full STS Service
# This script kills old instances and starts a fresh service

set -e

echo "=== Restarting Full STS Service ==="
echo ""

# Kill old processes
echo "1. Stopping old STS service instances..."
for port in 8000 8001 8002 8003; do
    pid=$(lsof -ti:$port 2>/dev/null || echo "")
    if [ -n "$pid" ]; then
        echo "   Killing process on port $port (PID $pid)..."
        kill $pid 2>/dev/null || echo "   (already stopped)"
        sleep 1
    fi
done

echo ""
echo "2. Waiting for ports to be released..."
sleep 2

echo ""
echo "3. Starting Full STS Service on port 8003..."
echo "   Logs will be written to: /tmp/claude/sts-service.log"
echo ""

# Activate virtual environment and start service
cd apps/sts-service
source ../../.venv/bin/activate

# Set port to 8003
export PORT=8003
export ENABLE_ARTIFACT_LOGGING=true
export ARTIFACTS_PATH=/tmp/claude/sts-artifacts

# Start the service
nohup python -m sts_service.full > /tmp/claude/sts-service.log 2>&1 &

echo ""
echo "✅ Full STS Service started!"
echo "   Port: 8003"
echo "   PID: $!"
echo "   Logs: /tmp/claude/sts-service.log"
echo ""
echo "To monitor logs: tail -f /tmp/claude/sts-service.log"
echo "To test: python manual_test_client.py"
echo ""
