#!/bin/bash
# Start TSN Traffic WebUI Server (Root)

PORT=9000

echo "Starting TSN Traffic WebUI..."
echo "Server will run on http://localhost:$PORT"
echo ""

# Check if port is already in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "Warning: Port $PORT is already in use"
    echo "Stopping existing process..."
    lsof -ti:$PORT | xargs -r kill -9
    sleep 1
fi

# Start the server
python3 app.py --host 0.0.0.0 --port $PORT 2>&1 | tee /tmp/webui.log
