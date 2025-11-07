# TSN Traffic Tester

> Web-based Traffic Testing Tool for Time-Sensitive Networking (TSN)

Professional network performance testing suite with real-time visualization, supporting iperf3 and sockperf for comprehensive latency and throughput analysis.

![License](https://img.shields.io/badge/license-Apache%202.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-brightgreen)

## Features

### Traffic Generation & Testing
- **iperf3 Integration**
  - TCP/UDP bandwidth testing with real-time charts
  - Bidirectional and reverse mode support
  - Configurable packet size, duration, and bandwidth limits
  - Live throughput & latency visualization

- **sockperf Integration**
  - Ping-pong latency testing (RTT measurement)
  - Under-load latency testing with configurable message rate
  - Multi-size latency analysis (64B - 1500B)
  - Statistical analysis: Avg, Min, Max, P50, P90, P99

### Visualization & Monitoring
- Real-time Chart.js graphs for bandwidth & latency
- Multi-size latency bar chart comparison
- Live statistics cards (bandwidth, latency, jitter, packet loss)
- Progress tracking for multi-size tests
- Expandable chart view for detailed analysis

### User Interface
- Clean, modern web interface
- Horizontal control panel layout
- WebSocket-based real-time updates
- CSV export for latency test results
- Mobile-responsive design

## Quick Start

### Prerequisites

**System Requirements:**
- Linux (tested on Ubuntu 20.04+)
- Python 3.8 or higher
- iperf3 (for bandwidth tests)
- sockperf (for latency tests)

**Install system dependencies:**
\`\`\`bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-pip iperf3 sockperf

# RHEL/CentOS/Fedora
sudo yum install -y python3 python3-pip iperf3
# sockperf may need to be compiled from source
\`\`\`

### Installation

1. **Clone the repository:**
\`\`\`bash
git clone https://github.com/hwkim3330/TSN-Traffic-Tester.git
cd TSN-Traffic-Tester
\`\`\`

2. **Install Python dependencies:**
\`\`\`bash
pip3 install -r requirements.txt
\`\`\`

3. **Start the server:**
\`\`\`bash
chmod +x start.sh
./start.sh
\`\`\`

4. **Open in browser:**
\`\`\`
http://localhost:9000
\`\`\`

## Usage

### Traffic Generator Mode (iperf3)

1. Select "Traffic Generator" tab
2. Configure test parameters:
   - **Server**: Target IP address
   - **Port**: iperf3 server port (default: 5201)
   - **Protocol**: TCP or UDP
   - **Duration**: Test duration in seconds
   - **Bandwidth**: UDP bandwidth limit (Mbps)
3. Click "Start Test" to begin
4. View real-time charts and statistics
5. Stop anytime with "Stop" button

### Latency Tester Mode (sockperf)

#### Ping-Pong Test (RTT)
1. Select "Latency Tester" tab
2. Choose "Ping-Pong" test type
3. Configure:
   - **Server**: Target IP
   - **Port**: sockperf server port (default: 11111)
   - **Duration**: Test duration
   - **Message Size**: Packet size in bytes
4. Click "Start Test"
5. View latency statistics in stat cards

#### Under-Load Test
1. Choose "Under-Load" test type
2. Configure message rate (MPS - messages per second)
3. Run test to measure latency under specific load
4. Analyze P50, P90, P99 percentiles

#### Multi-Size Latency Test
1. Choose "Multi-Size" test type
2. Test runs automatically across 6 message sizes:
   - 64, 128, 256, 512, 1024, 1500 bytes
3. View results in:
   - **Table**: Detailed statistics for each size
   - **Bar Chart**: Visual comparison of latencies
4. Export results to CSV

## Architecture

\`\`\`
TSN-Traffic-Tester/
├── app.py              # FastAPI backend with WebSocket support
├── app.js              # Frontend logic & Chart.js integration
├── index.html          # Main UI (single-page app)
├── start.sh            # Server startup script
├── requirements.txt    # Python dependencies
├── assets/             # Static resources (logo, images)
└── tools/              # Testing tool wrappers
    ├── iperf3_tool.py  # iperf3 wrapper with real-time parsing
    └── sockperf_tool.py # sockperf wrapper with percentile parsing
\`\`\`

### Technology Stack

**Backend:**
- FastAPI - Modern async Python web framework
- Uvicorn - ASGI server with WebSocket support
- Python asyncio - Concurrent test execution

**Frontend:**
- Vanilla JavaScript (ES6+)
- Chart.js - Real-time data visualization
- WebSocket API - Bidirectional communication
- CSS3 - Modern, responsive styling

**Testing Tools:**
- iperf3 - Network bandwidth measurement
- sockperf - Network latency measurement

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- KETI (Korea Electronics Technology Institute)
- iperf3 project
- sockperf project
- Chart.js contributors

---

**Built with ❤️ for TSN network testing**
