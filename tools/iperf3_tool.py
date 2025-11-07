#!/usr/bin/env python3
"""
iperf3 Wrapper Module
Runs iperf3 tests and parses output in real-time
"""

import subprocess
import threading
import json
import re
import time
import logging
from typing import Optional, Callable, Dict

logger = logging.getLogger(__name__)

class IPerf3Tool:
    """Wrapper for iperf3 command line tool"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.callback: Optional[Callable] = None
        self.stats = {
            "bandwidth_mbps": 0,
            "retransmits": 0,
            "packets_sent": 0,
            "packets_received": 0,
            "jitter_ms": 0,
            "lost_packets": 0,
            "lost_percent": 0
        }

    def set_callback(self, callback: Callable):
        """Set callback for real-time updates"""
        self.callback = callback

    def _notify(self, event: str, data: Dict):
        """Send callback notification"""
        if self.callback:
            try:
                self.callback(event, data)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def start_server(self, port: int = 5201):
        """Start iperf3 server"""
        if self.running:
            logger.warning("iperf3 server already running")
            return False

        try:
            cmd = ["iperf3", "-s", "-p", str(port), "-1"]  # -1 = exit after one test
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            self.running = True
            logger.info(f"iperf3 server started on port {port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start iperf3 server: {e}")
            return False

    def start_client(self, host: str = "127.0.0.1", port: int = 5201,
                    duration: int = 10, udp: bool = False,
                    bandwidth: str = "100M", parallel: int = 1):
        """
        Start iperf3 client test

        Args:
            host: Server hostname/IP
            port: Server port
            duration: Test duration in seconds
            udp: Use UDP instead of TCP
            bandwidth: Target bandwidth (e.g., "100M", "1G")
            parallel: Number of parallel streams
        """
        if self.running:
            logger.warning("iperf3 client already running")
            return False

        try:
            # Use stdbuf to disable output buffering for real-time updates
            cmd = [
                "stdbuf", "-oL",  # Line-buffered output
                "iperf3", "-c", host, "-p", str(port),
                "-t", str(duration), "-P", str(parallel),
                "-i", "1"  # Report every 1 second
            ]

            if udp:
                cmd.extend(["-u", "-b", bandwidth])

            self.running = True
            self.thread = threading.Thread(
                target=self._run_client,
                args=(cmd,)
            )
            self.thread.daemon = True
            self.thread.start()

            logger.info(f"iperf3 client started: {' '.join(cmd)}")
            return True

        except Exception as e:
            logger.error(f"Failed to start iperf3 client: {e}")
            self.running = False
            return False

    def _run_client(self, cmd: list):
        """Internal client runner with output parsing"""
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Read output line by line
            for line in self.process.stdout:
                # Try to parse progress lines
                if "sec" in line and ("Bytes" in line or "bits/sec" in line):
                    self._parse_progress_line(line)

            # Wait for completion
            self.process.wait()

            self._notify("test_complete", self.stats)

        except Exception as e:
            logger.error(f"iperf3 client error: {e}")
            self._notify("error", {"message": str(e)})
        finally:
            self.running = False
            self.process = None

    def _parse_progress_line(self, line: str):
        """Parse iperf3 progress line"""
        try:
            # Example: [  5]   0.00-1.00   sec  12.5 MBytes   105 Mbits/sec
            # Look for pattern: number followed by bits/sec
            match = re.search(r'(\d+\.?\d*)\s+([KMG]?bits/sec)', line, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                unit = match.group(2).lower()

                # Convert to Mbps
                if 'gbits' in unit:
                    bandwidth_mbps = value * 1000
                elif 'kbits' in unit:
                    bandwidth_mbps = value / 1000
                else:
                    bandwidth_mbps = value

                self.stats["bandwidth_mbps"] = bandwidth_mbps
                logger.info(f"Progress: {bandwidth_mbps:.2f} Mbps")
                self._notify("progress", {"bandwidth_mbps": bandwidth_mbps})
            else:
                logger.debug(f"No match in line: {line.strip()}")

        except Exception as e:
            logger.error(f"Failed to parse progress line: {e}, line: {line}")

    def _parse_json_output(self, output: str):
        """Parse iperf3 JSON output"""
        try:
            # Find JSON block
            json_start = output.find('{')
            if json_start == -1:
                return

            json_str = output[json_start:]
            data = json.loads(json_str)

            # Extract summary statistics
            if "end" in data:
                end_data = data["end"]

                # TCP stats
                if "sum_sent" in end_data:
                    sent = end_data["sum_sent"]
                    self.stats["bandwidth_mbps"] = sent.get("bits_per_second", 0) / 1e6
                    self.stats["packets_sent"] = sent.get("bytes", 0)
                    self.stats["retransmits"] = sent.get("retransmits", 0)

                if "sum_received" in end_data:
                    recv = end_data["sum_received"]
                    self.stats["packets_received"] = recv.get("bytes", 0)

                # UDP stats
                if "sum" in end_data:
                    sum_data = end_data["sum"]
                    self.stats["bandwidth_mbps"] = sum_data.get("bits_per_second", 0) / 1e6
                    self.stats["jitter_ms"] = sum_data.get("jitter_ms", 0)
                    self.stats["lost_packets"] = sum_data.get("lost_packets", 0)
                    self.stats["lost_percent"] = sum_data.get("lost_percent", 0)

                logger.info(f"iperf3 test complete: {self.stats}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse iperf3 JSON: {e}")
        except Exception as e:
            logger.error(f"Error parsing iperf3 output: {e}")

    def stop(self):
        """Stop running test"""
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                self.process.kill()
            self.process = None

    def get_stats(self) -> Dict:
        """Get current statistics"""
        return self.stats.copy()


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def callback(event, data):
        print(f"Event: {event}, Data: {data}")

    # Test client (assumes server is running on localhost)
    tool = IPerf3Tool()
    tool.set_callback(callback)

    print("Starting iperf3 test...")
    tool.start_client(host="127.0.0.1", duration=5, udp=False)

    # Wait for completion
    while tool.running:
        time.sleep(0.5)

    print(f"Final stats: {tool.get_stats()}")
