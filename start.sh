#!/bin/bash
# TSN Traffic Tester - Startup Script
# Developed by KETI (Korea Electronics Technology Institute)

PORT=${PORT:-9000}
HOST=${HOST:-0.0.0.0}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  TSN Traffic Tester - Network Performance Testing Tool  "
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $PYTHON_VERSION"

# Check if port is already in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠ Warning: Port $PORT is already in use"
    echo "Stopping existing process..."
    lsof -ti:$PORT | xargs -r kill -9
    sleep 1
    echo "✓ Port cleared"
fi

# Check optional tools
echo ""
echo "Checking optional tools..."
command -v mausezahn &> /dev/null && echo "  ✓ mausezahn (packet generator)" || echo "  ⚠ mausezahn not found"
command -v iperf3 &> /dev/null && echo "  ✓ iperf3 (throughput testing)" || echo "  ⚠ iperf3 not found"
command -v sockperf &> /dev/null && echo "  ✓ sockperf (latency testing)" || echo "  ⚠ sockperf not found"
command -v gst-launch-1.0 &> /dev/null && echo "  ✓ GStreamer (video streaming)" || echo "  ⚠ GStreamer not found"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Starting server on http://$HOST:$PORT"
echo "Logs: /tmp/tsn-traffic-tester.log"
echo ""
echo "Press Ctrl+C to stop the server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start the server
python3 app.py --host $HOST --port $PORT 2>&1 | tee /tmp/tsn-traffic-tester.log
