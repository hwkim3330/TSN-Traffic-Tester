# TSN Traffic Tester 🚀

**Modern Web-Based Time-Sensitive Networking (TSN) Testing Platform**

A comprehensive web application for testing and analyzing TSN network performance with VLAN/PCP prioritization, real-time video streaming, packet generation, and live monitoring.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![License](https://img.shields.io/badge/License-KETI-orange.svg)

## ✨ Features

### 🎯 Core Capabilities
- 🔌 **Network Interface Management** - Auto-detection with TSN capability analysis
- 📦 **Packet Generator** (Mausezahn) - VLAN/PCP tagging, custom payloads, burst mode
- 🔬 **Performance Testing** - iperf3 (throughput), sockperf (latency), ping (connectivity)
- 📹 **Video Streaming** (GStreamer) - Webcam transmission with H.264 low-latency encoding
- 📊 **Real-Time Monitoring** - Live charts with WebSocket updates
- 🔐 **Secure Sudo Management** - Session-based authentication with timeout

### 🎨 User Interface
- Apple-inspired modern design with SF Pro Display font
- Tabbed interface with smooth transitions
- Responsive layout for desktop and mobile
- Real-time log viewer with color-coded messages
- Interactive performance charts (Chart.js)

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/hwkim3330/TSN-Traffic-Tester.git
cd TSN-Traffic-Tester
```

### 2. Install Dependencies
```bash
# Install Python packages
pip3 install -r requirements.txt

# Install system tools (Ubuntu/Debian)
sudo apt install -y mausezahn iperf3 gstreamer1.0-tools \
                     gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
                     gstreamer1.0-x264 v4l-utils

# For sockperf (optional, Ubuntu 22.04+)
sudo apt install -y sockperf
```

### 3. Run Application
```bash
# Easy start (port 9000)
./start.sh

# Or manually with custom port
python3 app.py --host 0.0.0.0 --port 9000
```

### 4. Open Browser
Navigate to **http://localhost:9000**

## 📋 System Requirements

### Minimum
- **OS**: Ubuntu 20.04+, Debian 11+, or similar Linux distribution
- **Python**: 3.8 or higher
- **RAM**: 2GB minimum, 4GB recommended
- **Network**: At least one Ethernet interface

### Recommended
- **NIC**: Intel i210/i225 or similar TSN-capable network adapter
- **Webcam**: USB camera (for video streaming features)
- **CPU**: Multi-core processor for parallel testing

## 📖 Usage Guide

### 1. Unlock Sudo Access
Click **"🔓 Unlock"** in the header and enter your password. This enables privileged network operations.

### 2. Select Network Interface
Choose your network interface from the dropdown. TSN-capable interfaces will be highlighted.

### 3. Choose Test Mode

#### 🎯 Packet Generator
- **Destination**: Enter target IP and port
- **VLAN/PCP**: Configure 802.1Q VLAN ID (0-4095) and PCP priority (0-7)
- **Payload**: Enter hex payload or use quick presets
- **Count/Rate**: Set packet count and transmission rate
- Start sending packets

#### 📈 Traffic Tests
**iperf3 (Throughput)**
- Configure duration, parallel streams, protocol (TCP/UDP)
- Set bandwidth limit and buffer size
- View real-time throughput graphs

**sockperf (Latency)**
- Select test mode: Ping-Pong, Under-Load, Throughput
- Configure message size and test duration
- Analyze latency distribution (P50, P90, P99, P99.9)

**Ping (Connectivity)**
- Enter target IP address
- Set packet count and interval
- View round-trip time statistics

#### 📹 Video Stream
**Sender**
- Select webcam or test pattern
- Configure resolution (VGA, HD, Full HD)
- Set frame rate (15-60 fps) and bitrate
- Add VLAN/PCP tagging for TSN priority
- Start streaming

**Receiver**
- Set listening port
- Toggle display window
- Optionally save to MP4 file

#### 🌐 Servers
Start background servers for receiving traffic:
- **iperf3 Server**: Port 5201 (default)
- **sockperf Server**: Port 11111 (default)
- **Ping Responder**: ICMP echo reply

## 🏗️ Architecture

```
TSN-Traffic-Tester/
├── app.py                      # FastAPI backend server
├── index.html                  # Frontend HTML UI
├── app.js                      # Frontend JavaScript logic
├── start.sh                    # Startup script
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── LICENSE                     # Apache 2.0 License
├── assets/                     # Static assets (logo, icons)
└── tools/                      # Backend tool wrappers
    ├── network_manager.py      # Network interface management
    ├── sudo_manager.py         # Sudo session management
    ├── mausezahn_tool.py       # Packet generator wrapper
    ├── iperf3_tool.py          # iperf3 wrapper
    ├── sockperf_tool.py        # sockperf wrapper
    └── gstreamer_tool.py       # GStreamer video wrapper
```

## 🔧 Configuration

### Port Configuration
Edit `start.sh` to change the default port:
```bash
PORT=9000  # Change to your desired port
```

### Network Interfaces
The application auto-detects all network interfaces. To configure specific interfaces:
- Edit interface settings in the web UI
- Or modify `/etc/network/interfaces` on Linux

### Video Devices
Default webcam device is `/dev/video0`. To use a different camera:
- Check available devices: `ls -la /dev/video*`
- Update in the web UI "Video Stream" tab

## 🧪 Testing Examples

### Example 1: Basic Throughput Test
```bash
# Terminal 1 (Receiver)
# Start iperf3 server in web UI → Servers tab

# Terminal 2 (Sender)
# Traffic Tests → iperf3 → Configure and start
# Duration: 30s, Protocol: TCP, Parallel: 4
```

### Example 2: Low-Latency Video Streaming
```bash
# Device 1 (Sender - Webcam)
# Video Stream → Sender
# Resolution: 1280x720, FPS: 30, Bitrate: 2000 kbps
# VLAN: 100, PCP: 5 (Video priority)

# Device 2 (Receiver)
# Video Stream → Receiver → Port 5000 → Start
```

### Example 3: TSN Priority Testing
```bash
# Send high-priority packets
# Packet Generator → VLAN ID: 100, PCP: 7
# Payload: Quick preset "Video"
# Rate: 1000 pps, Count: 10000
```

## 🔍 Troubleshooting

### Port Already in Use
```bash
# Check what's using the port
lsof -i :9000

# Kill the process
lsof -ti:9000 | xargs kill -9
```

### GStreamer Not Found
```bash
# Install GStreamer
sudo apt install -y gstreamer1.0-tools gstreamer1.0-plugins-good \
                     gstreamer1.0-plugins-bad gstreamer1.0-x264

# Verify installation
gst-launch-1.0 --version
```

### Webcam Not Detected
```bash
# List video devices
ls -la /dev/video*

# Check permissions
sudo usermod -a -G video $USER
# Then log out and back in
```

### Sudo Session Timeout
- Click "🔓 Unlock" again and re-enter password
- Session expires after 15 minutes of inactivity

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is developed by **KETI** (Korea Electronics Technology Institute) for TSN research and is licensed under the Apache License 2.0.

See [LICENSE](LICENSE) for more information.

## 👥 Authors

- **KETI TSN Research Team**
- **GitHub**: [@hwkim3330](https://github.com/hwkim3330)

## 🙏 Acknowledgments

- FastAPI and Uvicorn teams for the excellent web framework
- GStreamer project for video streaming capabilities
- iperf3 and sockperf developers for performance testing tools
- Mausezahn developers for packet generation

## 📞 Support

For issues and questions:
- Open an issue on [GitHub](https://github.com/hwkim3330/TSN-Traffic-Tester/issues)
- Check existing issues for solutions

---
**Made with ❤️ by KETI TSN Research Team** | [GitHub](https://github.com/hwkim3330/TSN-Traffic-Tester) | [Report Bug](https://github.com/hwkim3330/TSN-Traffic-Tester/issues)
