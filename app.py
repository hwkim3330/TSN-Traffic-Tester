#!/usr/bin/env python3
"""
TSN Traffic WebUI - Simple FastAPI Backend (Root Server)
Using iperf3 and sockperf for real traffic testing
"""

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import json

# Add tools/webui to path for imports
sys.path.insert(0, str(Path(__file__).parent / "tools" / "webui"))

from iperf3_tool import IPerf3Tool
from sockperf_tool import SockPerfTool

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global event loop reference
main_loop = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events"""
    global main_loop
    # Startup
    main_loop = asyncio.get_running_loop()
    logger.info("Event loop stored for callbacks")
    yield
    # Shutdown
    logger.info("Shutting down TSN Traffic WebUI")

# Initialize FastAPI with lifespan
app = FastAPI(title="KETI TSN Traffic WebUI", lifespan=lifespan)

# Mount static files from root assets
assets_dir = Path(__file__).parent / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Mount tools/webui for app.js and other resources
webui_dir = Path(__file__).parent / "tools" / "webui"
if webui_dir.exists():
    # Don't mount the whole directory, just serve specific files

    pass

# Global tool instances
iperf_tool = IPerf3Tool()
sockperf_tool = SockPerfTool()

# Active WebSocket connections
active_connections = []

# =============================================================================
# WebSocket Connection Manager
# =============================================================================

async def broadcast(message: dict):
    """Broadcast message to all connected clients"""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            pass

# Store the event loop reference
main_loop = None

def tool_callback(event: str, data: dict):
    """Callback from tools - convert to async broadcast"""
    if main_loop is not None:
        asyncio.run_coroutine_threadsafe(
            broadcast({
                "type": event,
                "data": data
            }),
            main_loop
        )

# Set callbacks
iperf_tool.set_callback(tool_callback)
sockperf_tool.set_callback(tool_callback)

# =============================================================================
# Routes
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root index page"""
    html_file = Path(__file__).parent / "index.html"
    if html_file.exists():
        return html_file.read_text()
    return "<h1>KETI TSN Traffic Tester</h1><p>Index page not found</p>"

@app.get("/app.js")
async def app_js():
    """Serve app.js from root"""
    js_file = Path(__file__).parent / "app.js"
    if js_file.exists():
        return HTMLResponse(content=js_file.read_text(), media_type="application/javascript")
    return HTMLResponse(content="// app.js not found", media_type="application/javascript")

@app.get("/api/status")
async def get_status():
    """Get current status"""
    return {
        "iperf_running": iperf_tool.running,
        "sockperf_running": sockperf_tool.running,
        "iperf_stats": iperf_tool.get_stats(),
        "sockperf_stats": sockperf_tool.get_stats()
    }

# =============================================================================
# WebSocket Endpoint
# =============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time communication"""
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"Client connected. Total: {len(active_connections)}")

    try:
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to TSN Traffic WebUI"
        })

        while True:
            data = await websocket.receive_json()
            await handle_message(websocket, data)

    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"Client disconnected. Total: {len(active_connections)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)

async def handle_message(websocket: WebSocket, message: dict):
    """Handle incoming WebSocket messages"""
    msg_type = message.get("type")
    data = message.get("data", {})

    try:
        # iperf3 commands
        if msg_type == "start_iperf_client":
            host = data.get("host", "127.0.0.1")
            port = int(data.get("port", 5201))
            duration = int(data.get("duration", 10))
            udp = data.get("udp", False)
            bandwidth = data.get("bandwidth", "100M")

            success = iperf_tool.start_client(
                host=host,
                port=port,
                duration=duration,
                udp=udp,
                bandwidth=bandwidth
            )

            if success:
                await broadcast({
                    "type": "iperf_started",
                    "message": f"iperf3 test started to {host}:{port}"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to start iperf3 test"
                })

        elif msg_type == "stop_iperf":
            iperf_tool.stop()
            await broadcast({
                "type": "iperf_stopped",
                "message": "iperf3 test stopped"
            })

        # sockperf commands
        elif msg_type == "start_sockperf_pingpong":
            host = data.get("host", "127.0.0.1")
            port = int(data.get("port", 11111))
            duration = int(data.get("duration", 10))
            msg_size = int(data.get("msg_size", 64))

            success = sockperf_tool.start_ping_pong(
                host=host,
                port=port,
                duration=duration,
                msg_size=msg_size
            )

            if success:
                await broadcast({
                    "type": "sockperf_started",
                    "message": f"sockperf ping-pong started to {host}:{port}"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to start sockperf test"
                })

        elif msg_type == "start_sockperf_load":
            host = data.get("host", "127.0.0.1")
            port = int(data.get("port", 11111))
            duration = int(data.get("duration", 10))
            msg_size = int(data.get("msg_size", 64))
            mps = int(data.get("mps", 10000))

            success = sockperf_tool.start_under_load(
                host=host,
                port=port,
                duration=duration,
                msg_size=msg_size,
                mps=mps
            )

            if success:
                await broadcast({
                    "type": "sockperf_started",
                    "message": f"sockperf under-load started to {host}:{port}"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to start sockperf test"
                })

        elif msg_type == "stop_sockperf":
            sockperf_tool.stop()
            await broadcast({
                "type": "sockperf_stopped",
                "message": "sockperf test stopped"
            })

        elif msg_type == "start_sockperf_multisize":
            host = data.get("host", "127.0.0.1")
            port = int(data.get("port", 11111))
            duration = int(data.get("duration", 10))
            msg_sizes = data.get("msg_sizes", [64, 128, 256, 512, 1024, 1500])

            success = sockperf_tool.start_multi_size_test(
                host=host,
                port=port,
                duration=duration,
                msg_sizes=msg_sizes
            )

            if success:
                await broadcast({
                    "type": "sockperf_multisize_started",
                    "message": f"sockperf multi-size test started to {host}:{port}"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to start multi-size test"
                })

        # Get stats
        elif msg_type == "get_stats":
            await websocket.send_json({
                "type": "stats",
                "data": {
                    "iperf": iperf_tool.get_stats(),
                    "sockperf": sockperf_tool.get_stats()
                }
            })

        # Server control
        elif msg_type == "start_server":
            server = data.get("server", "").lower()
            if server == "iperf3":
                await websocket.send_json({
                    "type": "server_started",
                    "message": "iperf3 server should be started with: iperf3 -s -p 5201"
                })
            elif server == "sockperf":
                await websocket.send_json({
                    "type": "server_started",
                    "message": "sockperf server should be started with: sockperf server -p 11111 -d"
                })

        elif msg_type == "stop_server":
            server = data.get("server", "").lower()
            await websocket.send_json({
                "type": "server_stopped",
                "message": f"{server} server control not implemented (use system commands)"
            })

        elif msg_type == "get_server_status":
            import subprocess
            iperf_running = False
            sockperf_running = False

            try:
                result = subprocess.run(['pgrep', '-f', 'iperf3.*-s'], capture_output=True)
                iperf_running = result.returncode == 0
            except:
                pass

            try:
                result = subprocess.run(['pgrep', '-f', 'sockperf.*server'], capture_output=True)
                sockperf_running = result.returncode == 0
            except:
                pass

            await websocket.send_json({
                "type": "server_status",
                "data": {
                    "iperf_running": iperf_running,
                    "sockperf_running": sockperf_running
                }
            })

        # Ping
        elif msg_type == "start_ping":
            host = data.get("host", "127.0.0.1")
            count = data.get("count", 10)

            import subprocess
            import threading

            def run_ping():
                try:
                    result = subprocess.run(
                        ['ping', '-c', str(count), host],
                        capture_output=True,
                        text=True,
                        timeout=count + 5
                    )

                    # Parse ping output
                    output = result.stdout
                    stats = {}

                    # Extract statistics
                    import re
                    match = re.search(r'(\d+) packets transmitted, (\d+) received.*?time (\d+)ms', output)
                    if match:
                        sent = int(match.group(1))
                        received = int(match.group(2))
                        stats['packets_sent'] = sent
                        stats['packets_received'] = received
                        stats['packet_loss'] = ((sent - received) / sent * 100) if sent > 0 else 0

                    match = re.search(r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', output)
                    if match:
                        stats['latency_min_us'] = float(match.group(1)) * 1000
                        stats['latency_avg_us'] = float(match.group(2)) * 1000
                        stats['latency_max_us'] = float(match.group(3)) * 1000

                    asyncio.run(broadcast({
                        "type": "test_complete",
                        "data": stats
                    }))

                except Exception as e:
                    asyncio.run(broadcast({
                        "type": "error",
                        "message": f"Ping failed: {str(e)}"
                    }))

            threading.Thread(target=run_ping, daemon=True).start()
            await websocket.send_json({
                "type": "ping_started",
                "message": f"Ping started to {host} ({count} packets)"
            })

        elif msg_type == "stop_ping":
            await websocket.send_json({
                "type": "ping_stopped",
                "message": "Ping stopped"
            })

    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })

# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--reload", action="store_true")

    args = parser.parse_args()

    logger.info(f"Starting TSN Traffic WebUI on {args.host}:{args.port}")
    logger.info("Open http://localhost:9000 in your browser")

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload
    )
