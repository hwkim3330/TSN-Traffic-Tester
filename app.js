// ============================================================================
// KETI TSN Traffic Tester - Main Application
// ============================================================================

let ws = null;
let mainChart = null;
let multiSizeChart = null;
let currentMode = 'generator';
let isExpanded = false;
let isTestRunning = false;

const MAX_DATA_POINTS = 100;
const chartData = {
    labels: [],
    bandwidth: [],
    latency: [],
    latencyP99: []
};

// Helper function to format bandwidth with appropriate units
function formatBandwidth(mbps) {
    if (mbps >= 1000) {
        return {
            value: (mbps / 1000).toFixed(2),
            unit: 'Gbps',
            raw: mbps
        };
    }
    return {
        value: mbps.toFixed(2),
        unit: 'Mbps',
        raw: mbps
    };
}

// ============================================================================
// WebSocket Connection
// ============================================================================

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        log('Connected to server', 'success');
        updateStatus(true);
    };

    ws.onclose = () => {
        log('Disconnected from server', 'error');
        updateStatus(false);
        setTimeout(connectWebSocket, 3000);
    };

    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleMessage(message);
    };

    ws.onerror = (error) => {
        log('WebSocket error: ' + error, 'error');
    };
}

function sendMessage(type, data = {}) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type, data }));
    } else {
        log('Not connected to server', 'error');
    }
}

function updateStatus(connected) {
    const statusEl = document.getElementById('status');
    if (connected) {
        statusEl.textContent = 'Connected';
        statusEl.className = 'status-badge connected';
    } else {
        statusEl.textContent = 'Disconnected';
        statusEl.className = 'status-badge disconnected';
    }
}

// ============================================================================
// Message Handling
// ============================================================================

function handleMessage(message) {
    const { type, data, message: msg } = message;

    switch(type) {
        case 'connected':
            log(msg || 'Connected', 'success');
            break;

        case 'iperf_started':
        case 'sockperf_started':
        case 'server_started':
            log(msg, 'success');
            updateServerStatus();
            break;

        case 'server_stopped':
            log(msg, 'info');
            updateServerStatus();
            break;

        case 'progress':
            updateProgress(data);
            break;

        case 'test_complete':
            log('Test complete', 'success');
            updateStats(data);
            isTestRunning = false;
            break;

        case 'error':
            log('Error: ' + (msg || data.message), 'error');
            break;

        case 'server_status':
            updateServerDots(data);
            break;

        case 'sockperf_multisize_started':
            log('Multi-size latency test started', 'success');
            isTestRunning = true;
            // Show progress panel and clear table
            document.getElementById('progress-panel').style.display = 'block';
            document.getElementById('table-panel').style.display = 'block';
            document.getElementById('latency-table-body').innerHTML = '';
            break;

        case 'multi_size_progress':
            updateMultiSizeProgress(data);
            break;

        case 'multi_size_result':
            addLatencyTableRow(data);
            break;

        case 'multi_size_complete':
            log('Multi-size test complete', 'success');
            isTestRunning = false;
            document.getElementById('progress-panel').style.display = 'none';

            // Update bar chart with all results
            if (data.results && data.results.length > 0) {
                updateMultiSizeChart(data.results);
            }
            break;

        default:
            log(`Event: ${type}`, 'info');
    }
}

// ============================================================================
// Mode Switching
// ============================================================================

function switchMode(mode) {
    currentMode = mode;

    // Update tabs
    const tabs = document.querySelectorAll('.mode-tab');
    tabs.forEach((tab, index) => {
        if ((mode === 'generator' && index === 0) || (mode === 'listener' && index === 1)) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    // Update description
    const desc = document.getElementById('mode-description');
    const generatorConfig = document.getElementById('generator-config');

    if (mode === 'generator') {
        desc.textContent = 'Generate traffic and send to remote listener';
        generatorConfig.style.display = 'block';
    } else {
        desc.textContent = 'Listen for incoming traffic and measure performance';
        generatorConfig.style.display = 'none';
    }

    log(`Switched to ${mode} mode`, 'info');
}

// ============================================================================
// Server Control
// ============================================================================

function startServer(serverType) {
    log(`Starting ${serverType} server...`, 'info');
    sendMessage('start_server', { server: serverType });
}

function stopServer(serverType) {
    log(`Stopping ${serverType} server...`, 'info');
    sendMessage('stop_server', { server: serverType });
}

function updateServerStatus() {
    sendMessage('get_server_status');
}

function updateServerDots(status) {
    const iperfDot = document.getElementById('iperf-dot');
    const sockperfDot = document.getElementById('sockperf-dot');

    if (status.iperf_running) {
        iperfDot.classList.add('running');
    } else {
        iperfDot.classList.remove('running');
    }

    if (status.sockperf_running) {
        sockperfDot.classList.add('running');
    } else {
        sockperfDot.classList.remove('running');
    }
}

// ============================================================================
// Test Control
// ============================================================================

function updateTestConfig() {
    const testType = document.getElementById('test-type').value;
    const bandwidthGroup = document.getElementById('bandwidth-group');
    const msgsizeGroup = document.getElementById('msgsize-group');

    // Show/hide relevant fields
    if (testType === 'iperf-udp') {
        bandwidthGroup.style.display = 'block';
        msgsizeGroup.style.display = 'none';
    } else if (testType === 'sockperf-multisize') {
        bandwidthGroup.style.display = 'none';
        msgsizeGroup.style.display = 'none';
    } else if (testType.startsWith('sockperf')) {
        bandwidthGroup.style.display = 'none';
        msgsizeGroup.style.display = 'block';
    } else {
        bandwidthGroup.style.display = 'none';
        msgsizeGroup.style.display = 'none';
    }
}

function startTest() {
    if (currentMode === 'listener') {
        log('Cannot start test in listener mode', 'warning');
        return;
    }

    const testType = document.getElementById('test-type').value;
    const remoteIp = document.getElementById('remote-ip').value;
    const duration = parseInt(document.getElementById('duration').value);
    const bandwidth = document.getElementById('bandwidth').value;
    const msgsize = parseInt(document.getElementById('msgsize').value);

    // Clear previous data
    chartData.labels = [];
    chartData.bandwidth = [];
    chartData.latency = [];
    chartData.latencyP99 = [];
    updateChart();

    isTestRunning = true;
    log(`Starting ${testType} test to ${remoteIp}...`, 'info');

    let messageData = {
        host: remoteIp,
        duration: duration
    };

    // Send appropriate message based on test type
    switch(testType) {
        case 'iperf-tcp':
            sendMessage('start_iperf_client', {
                ...messageData,
                port: 5201,
                udp: false
            });
            break;

        case 'iperf-udp':
            sendMessage('start_iperf_client', {
                ...messageData,
                port: 5201,
                udp: true,
                bandwidth: bandwidth
            });
            break;

        case 'sockperf-pp':
            sendMessage('start_sockperf_pingpong', {
                ...messageData,
                port: 11111,
                msg_size: msgsize
            });
            break;

        case 'sockperf-ul':
            sendMessage('start_sockperf_load', {
                ...messageData,
                port: 11111,
                msg_size: msgsize,
                mps: 10000
            });
            break;

        case 'sockperf-multisize':
            sendMessage('start_sockperf_multisize', {
                ...messageData,
                port: 11111,
                msg_sizes: [64, 128, 256, 512, 1024, 1500]
            });
            break;

        case 'ping':
            sendMessage('start_ping', {
                host: remoteIp,
                count: duration * 10
            });
            break;
    }

    // Auto-expand graph during test
    if (!isExpanded) {
        toggleExpand();
    }
}

function stopTest() {
    log('Stopping test...', 'info');
    const testType = document.getElementById('test-type').value;

    if (testType.startsWith('iperf')) {
        sendMessage('stop_iperf');
    } else if (testType.startsWith('sockperf')) {
        sendMessage('stop_sockperf');
    } else if (testType === 'ping') {
        sendMessage('stop_ping');
    }

    isTestRunning = false;
}

// ============================================================================
// Data Updates
// ============================================================================

function updateProgress(data) {
    // Update stats
    if (data.bandwidth_mbps !== undefined) {
        const bw = formatBandwidth(data.bandwidth_mbps);
        document.getElementById('stat-bandwidth').textContent = `${bw.value} ${bw.unit}`;
        addChartData('bandwidth', data.bandwidth_mbps);
    }

    if (data.latency_avg_us !== undefined) {
        document.getElementById('stat-latency').textContent = data.latency_avg_us.toFixed(2) + ' μs';
        addChartData('latency', data.latency_avg_us);
    }

    if (data.jitter_ms !== undefined) {
        document.getElementById('stat-jitter').textContent = data.jitter_ms.toFixed(2) + ' ms';
    }

    if (data.lost_percent !== undefined) {
        document.getElementById('stat-loss').textContent = data.lost_percent.toFixed(2) + '%';
    }
}

function updateStats(stats) {
    if (stats.bandwidth_mbps !== undefined) {
        const bw = formatBandwidth(stats.bandwidth_mbps);
        document.getElementById('stat-bandwidth').textContent = `${bw.value} ${bw.unit}`;
        addChartData('bandwidth', stats.bandwidth_mbps);
    }

    if (stats.latency_avg_us !== undefined) {
        document.getElementById('stat-latency').textContent = stats.latency_avg_us.toFixed(2) + ' μs';
        addChartData('latency', stats.latency_avg_us);
    }

    if (stats.latency_p99_us !== undefined) {
        addChartData('latencyP99', stats.latency_p99_us);
    }

    if (stats.jitter_ms !== undefined) {
        document.getElementById('stat-jitter').textContent = stats.jitter_ms.toFixed(2) + ' ms';
    }

    if (stats.lost_percent !== undefined) {
        document.getElementById('stat-loss').textContent = stats.lost_percent.toFixed(2) + '%';
    }
}

// ============================================================================
// Chart Management
// ============================================================================

function initChart() {
    const ctx = document.getElementById('mainChart').getContext('2d');

    mainChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Bandwidth (Mbps)',
                    data: [],
                    borderColor: '#0066CC',
                    backgroundColor: 'rgba(0, 102, 204, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                    yAxisID: 'y'
                },
                {
                    label: 'Latency Avg (μs)',
                    data: [],
                    borderColor: '#3385D6',
                    backgroundColor: 'rgba(51, 133, 214, 0.1)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                    yAxisID: 'y1'
                },
                {
                    label: 'Latency P99 (μs)',
                    data: [],
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.05)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: false,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Bandwidth (Mbps)',
                        color: '#0066CC'
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        callback: function(value) {
                            if (value >= 1000) {
                                return (value / 1000).toFixed(1) + ' Gbps';
                            }
                            return value.toFixed(0) + ' Mbps';
                        }
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Latency (μs)',
                        color: '#3385D6'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                },
                x: {
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    titleFont: {
                        size: 14
                    },
                    bodyFont: {
                        size: 13
                    },
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }

                            // Format bandwidth with appropriate units
                            if (context.datasetIndex === 0) {  // Bandwidth dataset
                                const value = context.parsed.y;
                                if (value >= 1000) {
                                    label += (value / 1000).toFixed(2) + ' Gbps';
                                } else {
                                    label += value.toFixed(2) + ' Mbps';
                                }
                            } else {  // Latency datasets
                                label += context.parsed.y.toFixed(2) + ' μs';
                            }

                            return label;
                        }
                    }
                }
            }
        }
    });
}

function initMultiSizeChart() {
    const canvas = document.getElementById('multiSizeChart');
    if (!canvas) {
        console.log('Multi-size chart canvas not found');
        return;
    }

    const ctx = canvas.getContext('2d');

    multiSizeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Avg Latency (μs)',
                    data: [],
                    backgroundColor: 'rgba(51, 133, 214, 0.7)',
                    borderColor: '#3385D6',
                    borderWidth: 1
                },
                {
                    label: 'P50 (μs)',
                    data: [],
                    backgroundColor: 'rgba(102, 126, 234, 0.7)',
                    borderColor: '#667eea',
                    borderWidth: 1
                },
                {
                    label: 'P90 (μs)',
                    data: [],
                    backgroundColor: 'rgba(247, 147, 26, 0.7)',
                    borderColor: '#f7931a',
                    borderWidth: 1
                },
                {
                    label: 'P99 (μs)',
                    data: [],
                    backgroundColor: 'rgba(220, 53, 69, 0.7)',
                    borderColor: '#dc3545',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Latency (μs)',
                        color: '#333'
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Message Size (bytes)',
                        color: '#333'
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    titleFont: {
                        size: 14
                    },
                    bodyFont: {
                        size: 13
                    },
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += context.parsed.y.toFixed(2) + ' μs';
                            return label;
                        }
                    }
                }
            }
        }
    });
}

function updateMultiSizeChart(results) {
    if (!multiSizeChart || !results || results.length === 0) {
        return;
    }

    const labels = results.map(r => r.msg_size + ' B');
    const avgData = results.map(r => r.latency_avg_us);
    const p50Data = results.map(r => r.latency_p50_us);
    const p90Data = results.map(r => r.latency_p90_us);
    const p99Data = results.map(r => r.latency_p99_us);

    multiSizeChart.data.labels = labels;
    multiSizeChart.data.datasets[0].data = avgData;
    multiSizeChart.data.datasets[1].data = p50Data;
    multiSizeChart.data.datasets[2].data = p90Data;
    multiSizeChart.data.datasets[3].data = p99Data;

    multiSizeChart.update();

    log(`Multi-size chart updated with ${results.length} data points`, 'info');
}

function addChartData(type, value) {
    const now = new Date().toLocaleTimeString();

    // Add timestamp if new
    if (chartData.labels.length === 0 || chartData.labels[chartData.labels.length - 1] !== now) {
        chartData.labels.push(now);

        // Keep only last MAX_DATA_POINTS
        if (chartData.labels.length > MAX_DATA_POINTS) {
            chartData.labels.shift();
            chartData.bandwidth.shift();
            chartData.latency.shift();
            chartData.latencyP99.shift();
        }
    }

    // Update appropriate dataset
    if (type === 'bandwidth') {
        chartData.bandwidth[chartData.labels.length - 1] = value;
    } else if (type === 'latency') {
        chartData.latency[chartData.labels.length - 1] = value;
    } else if (type === 'latencyP99') {
        chartData.latencyP99[chartData.labels.length - 1] = value;
    }

    updateChart();
}

function updateChart() {
    if (!mainChart) return;

    mainChart.data.labels = chartData.labels;
    mainChart.data.datasets[0].data = chartData.bandwidth;
    mainChart.data.datasets[1].data = chartData.latency;
    mainChart.data.datasets[2].data = chartData.latencyP99;

    mainChart.update('none');
}

function toggleExpand() {
    isExpanded = !isExpanded;
    const graphPanel = document.getElementById('graph-panel');
    const chartWrapper = document.getElementById('chart-wrapper');
    const expandText = document.getElementById('expand-text');

    if (isExpanded) {
        graphPanel.classList.add('expanded');
        chartWrapper.classList.add('large');
        expandText.textContent = '⛶ Collapse';
    } else {
        graphPanel.classList.remove('expanded');
        chartWrapper.classList.remove('large');
        expandText.textContent = '⛶ Expand';
    }

    // Resize chart
    setTimeout(() => {
        mainChart.resize();
    }, 300);
}

// ============================================================================
// Logging
// ============================================================================

function log(message, type = 'info') {
    const logConsole = document.getElementById('log-console');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;

    const time = new Date().toLocaleTimeString();
    entry.textContent = `[${time}] ${message}`;

    logConsole.appendChild(entry);
    logConsole.scrollTop = logConsole.scrollHeight;

    // Keep only last 100 entries
    while (logConsole.children.length > 100) {
        logConsole.removeChild(logConsole.firstChild);
    }
}

function clearLog() {
    document.getElementById('log-console').innerHTML = '';
}

// ============================================================================
// Export Results
// ============================================================================

function exportResults() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const results = {
        timestamp: new Date().toISOString(),
        mode: currentMode,
        configuration: {
            test_type: document.getElementById('test-type').value,
            remote_ip: document.getElementById('remote-ip').value,
            duration: document.getElementById('duration').value
        },
        results: {
            bandwidth: document.getElementById('stat-bandwidth').textContent,
            latency: document.getElementById('stat-latency').textContent,
            jitter: document.getElementById('stat-jitter').textContent,
            loss: document.getElementById('stat-loss').textContent
        },
        chart_data: {
            labels: chartData.labels.slice(),
            bandwidth: chartData.bandwidth.slice(),
            latency: chartData.latency.slice(),
            latency_p99: chartData.latencyP99.slice()
        }
    };

    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `keti-tsn-results-${timestamp}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    log('Results exported to JSON file', 'success');
}

// ============================================================================
// Multi-Size Latency Test Functions
// ============================================================================

function updateMultiSizeProgress(data) {
    const progressText = document.getElementById('progress-text');
    const progressPercent = document.getElementById('progress-percent');
    const progressBar = document.getElementById('progress-bar');

    if (data.current_size > 0) {
        progressText.textContent = `Testing: ${data.current_size} bytes (${data.current_index}/${data.total_count})`;
    } else {
        progressText.textContent = `Complete (${data.total_count}/${data.total_count})`;
    }

    progressPercent.textContent = `${Math.round(data.progress)}%`;
    progressBar.style.width = `${data.progress}%`;
}

function addLatencyTableRow(data) {
    const tbody = document.getElementById('latency-table-body');
    const row = document.createElement('tr');

    row.innerHTML = `
        <td class="table-size">${data.msg_size} bytes</td>
        <td class="table-value">${data.latency_avg_us.toFixed(2)}</td>
        <td class="table-value">${data.latency_min_us.toFixed(2)}</td>
        <td class="table-value">${data.latency_p50_us.toFixed(2)}</td>
        <td class="table-value">${data.latency_p90_us.toFixed(2)}</td>
        <td class="table-value">${data.latency_p99_us.toFixed(2)}</td>
        <td class="table-value">${data.latency_max_us.toFixed(2)}</td>
    `;

    tbody.appendChild(row);

    log(`Size ${data.msg_size}: avg=${data.latency_avg_us.toFixed(2)}μs, p50=${data.latency_p50_us.toFixed(2)}μs, p90=${data.latency_p90_us.toFixed(2)}μs, p99=${data.latency_p99_us.toFixed(2)}μs`, 'info');
}

function exportTable() {
    const tbody = document.getElementById('latency-table-body');
    const rows = tbody.getElementsByTagName('tr');

    if (rows.length === 0) {
        log('No data to export', 'warning');
        return;
    }

    // Create CSV content
    let csvContent = 'Message Size (bytes),Avg Latency (μs),Min (μs),P50 (μs),P90 (μs),P99 (μs),Max (μs)\n';

    for (let row of rows) {
        const cells = row.getElementsByTagName('td');
        const rowData = [];
        for (let cell of cells) {
            const text = cell.textContent.trim().replace(' bytes', '');
            rowData.push(text);
        }
        csvContent += rowData.join(',') + '\n';
    }

    // Download CSV
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `keti-latency-table-${timestamp}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    log('Latency table exported to CSV file', 'success');
}

// ============================================================================
// Initialization
// ============================================================================

window.onload = () => {
    log('KETI TSN Traffic Tester initialized', 'info');
    initChart();
    initMultiSizeChart();
    connectWebSocket();
    updateTestConfig();

    // Request server status
    setTimeout(() => {
        updateServerStatus();
    }, 1000);
};
