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
sys.path.insert(0, str(Path(__file__).parent / "tools"))

from iperf3_tool import IPerf3Tool
from sockperf_tool import SockPerfTool
from mausezahn_tool import MausezahnTool
from network_manager import NetworkManager
from sudo_manager import sudo_manager

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
mausezahn_tool = MausezahnTool()
network_manager = NetworkManager()

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
mausezahn_tool.set_callback(tool_callback)

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
# Network Interface API
# =============================================================================

@app.get("/api/interfaces")
async def get_interfaces(refresh: bool = False):
    """
    Get all network interfaces

    Args:
        refresh: Force refresh of interface list
    """
    if refresh:
        interfaces = network_manager.refresh_interfaces()
    else:
        interfaces = network_manager.interfaces

    return {
        "interfaces": interfaces,
        "count": len(interfaces)
    }

@app.get("/api/interfaces/active")
async def get_active_interfaces():
    """Get only active (up) interfaces"""
    active = network_manager.get_active_interfaces()
    return {
        "interfaces": active,
        "count": len(active)
    }

@app.get("/api/interfaces/{interface_name}")
async def get_interface_details(interface_name: str):
    """Get detailed information for a specific interface"""
    interface = network_manager.get_interface(interface_name)

    if not interface:
        return {
            "error": f"Interface {interface_name} not found"
        }, 404

    return interface

@app.get("/api/interfaces/{interface_name}/ethtool")
async def get_interface_ethtool(interface_name: str):
    """Get ethtool information for an interface"""
    ethtool_info = network_manager.get_ethtool_info(interface_name)
    return ethtool_info

@app.get("/api/interfaces/{interface_name}/queues")
async def get_interface_queues(interface_name: str):
    """Get queue information for an interface"""
    queue_info = network_manager.get_interface_queues(interface_name)
    return queue_info

@app.post("/api/interfaces/{interface_name}/state")
async def set_interface_state(interface_name: str, data: dict):
    """
    Set interface state (up/down)

    Request body:
        {
            "state": "up" or "down",
            "sudo_password": "optional_password"
        }
    """
    state = data.get("state", "up")
    sudo_password = data.get("sudo_password", None)

    success = network_manager.set_interface_state(interface_name, state, sudo_password)

    if success:
        # Refresh interface list after state change
        network_manager.refresh_interfaces()
        return {
            "success": True,
            "message": f"Interface {interface_name} set to {state}"
        }
    else:
        return {
            "success": False,
            "message": f"Failed to set interface {interface_name} to {state}"
        }

# =============================================================================
# Sudo Management API
# =============================================================================

@app.post("/api/sudo/auth")
async def sudo_auth(data: dict):
    """Authenticate sudo password"""
    password = data.get("password", "")

    if not password:
        return {"success": False, "message": "Password required"}

    success, message = sudo_manager.set_password(password)

    if success:
        session_info = sudo_manager.get_session_info()
        return {
            "success": True,
            "message": message,
            "session": session_info
        }
    else:
        return {"success": False, "message": message}

@app.get("/api/sudo/session")
async def get_sudo_session():
    """Get current sudo session status"""
    session_info = sudo_manager.get_session_info()
    return {
        "session": session_info,
        "sudo_available": sudo_manager.check_sudo_available()
    }

@app.post("/api/sudo/clear")
async def clear_sudo_session():
    """Clear sudo session"""
    sudo_manager.clear_password()
    return {"success": True, "message": "Session cleared"}

# =============================================================================
# Mausezahn Packet Generator API
# =============================================================================

@app.post("/api/mausezahn/start_vlan")
async def start_mausezahn_vlan(data: dict):
    """
    Start VLAN-tagged packet generation

    Request body:
        {
            "interface": "eth0",
            "dest_ip": "192.168.1.2",
            "vlan_id": 100,
            "pcp": 5,
            "packet_type": "udp",
            "dest_port": 5000,
            "packet_size": 1000,
            "count": 1000,
            "delay": "1msec",
            "src_mac": "optional",
            "dest_mac": "optional"
        }
    """
    interface = data.get("interface")
    dest_ip = data.get("dest_ip")
    vlan_id = int(data.get("vlan_id", 100))
    pcp = int(data.get("pcp", 0))
    packet_type = data.get("packet_type", "udp")
    dest_port = int(data.get("dest_port", 5000))
    packet_size = int(data.get("packet_size", 1000))
    count = int(data.get("count", 1000))
    delay = data.get("delay", "1msec")
    src_mac = data.get("src_mac", None)
    dest_mac = data.get("dest_mac", None)

    if not interface or not dest_ip:
        return {"success": False, "message": "Interface and dest_ip are required"}

    success = mausezahn_tool.start_vlan_traffic(
        interface=interface,
        dest_ip=dest_ip,
        vlan_id=vlan_id,
        pcp=pcp,
        packet_type=packet_type,
        dest_port=dest_port,
        packet_size=packet_size,
        count=count,
        delay=delay,
        src_mac=src_mac,
        dest_mac=dest_mac
    )

    if success:
        return {
            "success": True,
            "message": f"Started VLAN-tagged traffic on {interface} (VLAN {vlan_id}, PCP {pcp})"
        }
    else:
        return {"success": False, "message": "Failed to start mausezahn"}

@app.post("/api/mausezahn/start_custom")
async def start_mausezahn_custom(data: dict):
    """
    Start custom packet generation with hex data

    Request body:
        {
            "interface": "eth0",
            "packet_hex": "aabbccddeeff",
            "vlan_id": 100,
            "pcp": 5,
            "count": 1000,
            "delay": "1msec"
        }
    """
    interface = data.get("interface")
    packet_hex = data.get("packet_hex")
    vlan_id = data.get("vlan_id", None)
    pcp = int(data.get("pcp", 0))
    count = int(data.get("count", 1000))
    delay = data.get("delay", "1msec")

    if not interface or not packet_hex:
        return {"success": False, "message": "Interface and packet_hex are required"}

    success = mausezahn_tool.start_custom_traffic(
        interface=interface,
        packet_hex=packet_hex,
        vlan_id=int(vlan_id) if vlan_id else None,
        pcp=pcp,
        count=count,
        delay=delay
    )

    if success:
        return {
            "success": True,
            "message": f"Started custom traffic on {interface}"
        }
    else:
        return {"success": False, "message": "Failed to start mausezahn"}

@app.post("/api/mausezahn/stop")
async def stop_mausezahn():
    """Stop mausezahn packet generation"""
    mausezahn_tool.stop()
    return {"success": True, "message": "Mausezahn stopped"}

@app.get("/api/mausezahn/stats")
async def get_mausezahn_stats():
    """Get mausezahn statistics"""
    stats = mausezahn_tool.get_stats()
    return {"stats": stats}

@app.get("/api/mausezahn/status")
async def get_mausezahn_status():
    """Get mausezahn running status"""
    return {
        "running": mausezahn_tool.running,
        "available": MausezahnTool.check_available()
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

        # mausezahn commands
        elif msg_type == "start_mausezahn_vlan":
            interface = data.get("interface")
            dest_ip = data.get("dest_ip")
            vlan_id = int(data.get("vlan_id", 100))
            pcp = int(data.get("pcp", 0))
            packet_type = data.get("packet_type", "udp")
            dest_port = int(data.get("dest_port", 5000))
            packet_size = int(data.get("packet_size", 1000))
            count = int(data.get("count", 1000))
            delay = data.get("delay", "1msec")

            success = mausezahn_tool.start_vlan_traffic(
                interface=interface,
                dest_ip=dest_ip,
                vlan_id=vlan_id,
                pcp=pcp,
                packet_type=packet_type,
                dest_port=dest_port,
                packet_size=packet_size,
                count=count,
                delay=delay
            )

            if success:
                await broadcast({
                    "type": "mausezahn_started",
                    "message": f"Mausezahn started on {interface} (VLAN {vlan_id}, PCP {pcp})"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to start mausezahn"
                })

        elif msg_type == "start_mausezahn_custom":
            interface = data.get("interface")
            packet_hex = data.get("packet_hex")
            vlan_id = data.get("vlan_id", None)
            pcp = int(data.get("pcp", 0))
            count = int(data.get("count", 1000))
            delay = data.get("delay", "1msec")

            success = mausezahn_tool.start_custom_traffic(
                interface=interface,
                packet_hex=packet_hex,
                vlan_id=int(vlan_id) if vlan_id else None,
                pcp=pcp,
                count=count,
                delay=delay
            )

            if success:
                await broadcast({
                    "type": "mausezahn_started",
                    "message": f"Mausezahn custom traffic started on {interface}"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to start mausezahn"
                })

        elif msg_type == "stop_mausezahn":
            mausezahn_tool.stop()
            await broadcast({
                "type": "mausezahn_stopped",
                "message": "Mausezahn stopped"
            })

        # Get stats
        elif msg_type == "get_stats":
            await websocket.send_json({
                "type": "stats",
                "data": {
                    "iperf": iperf_tool.get_stats(),
                    "sockperf": sockperf_tool.get_stats(),
                    "mausezahn": mausezahn_tool.get_stats()
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
