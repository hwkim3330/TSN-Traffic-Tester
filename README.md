# KETI TSN Traffic Tester

**Comprehensive Time-Sensitive Networking (TSN) Traffic Testing Tool**

A web-based application for testing and analyzing TSN network performance with VLAN/PCP prioritization, packet generation, and real-time monitoring.

## ✨ Features

- 🔌 **Network Interface Management** with TSN capability detection
- 📦 **Packet Generator** (Mausezahn) with VLAN/PCP support
- 🔬 **Traffic Testing** (iperf3, sockperf, ping)
- 📊 **Real-Time Monitoring** with live performance graphs
- 🔐 **Secure Sudo Management** with session timeout
- 🎨 **Modern UI** with tabbed interface and WebSocket updates

## 🚀 Quick Start

```bash
# Run the application
./start.sh

# Or manually
python3 app.py --host 0.0.0.0 --port 9001
```

Open in browser: **http://localhost:9001**

## 📋 Requirements

**Python 3.7+** and:
- fastapi, uvicorn, websockets, psutil, netifaces

**Optional tools:**
- mausezahn (packet generation)
- iperf3 (throughput testing)
- sockperf (latency testing)
- GStreamer (video streaming)

Install on Ubuntu:
```bash
sudo apt install mausezahn iperf3 python3-pip
pip3 install fastapi uvicorn websockets psutil netifaces
```

## 📖 Usage

1. **Unlock Sudo**: Click "Unlock" in header and enter password
2. **Select Interface**: Choose network interface from dropdown
3. **Choose Mode**: Sender (generate traffic) or Receiver (listen)
4. **Run Tests**: Use Packet Generator, Traffic Tests, or Servers tabs

## 🏗️ Architecture

```
TSN-Traffic-Tester/
├── app.py                 # FastAPI backend
├── index.html            # Frontend UI
├── app.js                # Frontend logic
├── start.sh              # Startup script
└── tools/                # Tool wrappers
    ├── network_manager.py
    ├── sudo_manager.py
    ├── mausezahn_tool.py
    ├── iperf_tool.py
    ├── sockperf_tool.py
    └── gstreamer_tool.py
```

## 🤝 Contributing

Contributions welcome! Fork, create a feature branch, and submit a PR.

## 📄 License

Developed by **KETI** (Korea Electronics Technology Institute) for TSN research.

---
Made with ❤️ by KETI TSN Research Team
