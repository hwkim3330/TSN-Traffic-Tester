#!/usr/bin/env python3
"""
sockperf Wrapper Module
Runs sockperf tests and parses output in real-time
"""

import subprocess
import threading
import re
import time
import logging
from typing import Optional, Callable, Dict

logger = logging.getLogger(__name__)

class SockPerfTool:
    """Wrapper for sockperf command line tool"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.callback: Optional[Callable] = None
        self.stats = {
            "latency_avg_us": 0,
            "latency_min_us": 0,
            "latency_max_us": 0,
            "latency_p50_us": 0,
            "latency_p90_us": 0,
            "latency_p99_us": 0,
            "packets_sent": 0,
            "packets_received": 0,
            "packet_loss": 0
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

    def start_server(self, port: int = 11111):
        """Start sockperf server"""
        if self.running:
            logger.warning("sockperf server already running")
            return False

        try:
            cmd = ["sockperf", "server", "-p", str(port)]
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            self.running = True
            logger.info(f"sockperf server started on port {port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start sockperf server: {e}")
            return False

    def start_ping_pong(self, host: str = "127.0.0.1", port: int = 11111,
                       duration: int = 10, msg_size: int = 64):
        """
        Start sockperf ping-pong test

        Args:
            host: Server hostname/IP
            port: Server port
            duration: Test duration in seconds
            msg_size: Message size in bytes
        """
        if self.running:
            logger.warning("sockperf test already running")
            return False

        try:
            cmd = [
                "sockperf", "ping-pong",
                "-i", host, "-p", str(port),
                "-t", str(duration),
                "--msg-size", str(msg_size)
            ]

            self.running = True
            self.thread = threading.Thread(
                target=self._run_test,
                args=(cmd,)
            )
            self.thread.daemon = True
            self.thread.start()

            logger.info(f"sockperf ping-pong started: {' '.join(cmd)}")
            return True

        except Exception as e:
            logger.error(f"Failed to start sockperf test: {e}")
            self.running = False
            return False

    def start_under_load(self, host: str = "127.0.0.1", port: int = 11111,
                        duration: int = 10, msg_size: int = 64, mps: int = 10000):
        """
        Start sockperf under-load test

        Args:
            host: Server hostname/IP
            port: Server port
            duration: Test duration in seconds
            msg_size: Message size in bytes
            mps: Messages per second rate
        """
        if self.running:
            logger.warning("sockperf test already running")
            return False

        try:
            cmd = [
                "sockperf", "under-load",
                "-i", host, "-p", str(port),
                "-t", str(duration),
                "--msg-size", str(msg_size),
                "--mps", str(mps)
            ]

            self.running = True
            self.thread = threading.Thread(
                target=self._run_test,
                args=(cmd,)
            )
            self.thread.daemon = True
            self.thread.start()

            logger.info(f"sockperf under-load started: {' '.join(cmd)}")
            return True

        except Exception as e:
            logger.error(f"Failed to start sockperf test: {e}")
            self.running = False
            return False

    def _run_test(self, cmd: list):
        """Internal test runner with output parsing"""
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            output_lines = []

            # Read output line by line
            for line in self.process.stdout:
                output_lines.append(line)
                logger.debug(f"sockperf: {line.strip()}")

                # Parse real-time updates
                self._parse_line(line)

            # Wait for completion
            self.process.wait()

            # Parse final summary
            full_output = ''.join(output_lines)
            self._parse_summary(full_output)

            self._notify("test_complete", self.stats)

        except Exception as e:
            logger.error(f"sockperf test error: {e}")
            self._notify("error", {"message": str(e)})
        finally:
            self.running = False
            self.process = None

    def _parse_line(self, line: str):
        """Parse sockperf output line"""
        try:
            # Example: sockperf: Total 100 messages sent in 10.001 sec
            if "messages sent" in line:
                match = re.search(r'Total\s+(\d+)\s+messages', line)
                if match:
                    self.stats["packets_sent"] = int(match.group(1))

            # Example: sockperf: Total 100 messages received
            if "messages received" in line:
                match = re.search(r'Total\s+(\d+)\s+messages', line)
                if match:
                    self.stats["packets_received"] = int(match.group(1))

        except Exception as e:
            logger.debug(f"Failed to parse line: {e}")

    def _parse_summary(self, output: str):
        """Parse sockperf summary statistics"""
        try:
            # Example summary:
            # sockperf: Summary: Latency is 41.962 usec
            # sockperf: ---> <MIN> observation =   29.388
            # sockperf: ---> <MAX> observation =  453.549
            # sockperf: ---> percentile 50.000 =   39.988
            # sockperf: ---> percentile 99.000 =  101.886

            # Average latency
            match = re.search(r'Summary:\s+Latency is\s+(\d+\.?\d*)\s+usec', output)
            if match:
                self.stats["latency_avg_us"] = float(match.group(1))

            # Min latency
            match = re.search(r'<MIN> observation\s+=\s+(\d+\.?\d*)', output)
            if match:
                self.stats["latency_min_us"] = float(match.group(1))

            # Max latency
            match = re.search(r'<MAX> observation\s+=\s+(\d+\.?\d*)', output)
            if match:
                self.stats["latency_max_us"] = float(match.group(1))

            # Percentiles
            match = re.search(r'percentile 50\.000\s+=\s+(\d+\.?\d*)', output)
            if match:
                self.stats["latency_p50_us"] = float(match.group(1))

            match = re.search(r'percentile 90\.000\s+=\s+(\d+\.?\d*)', output)
            if match:
                self.stats["latency_p90_us"] = float(match.group(1))

            match = re.search(r'percentile 99\.000\s+=\s+(\d+\.?\d*)', output)
            if match:
                self.stats["latency_p99_us"] = float(match.group(1))

            # Calculate packet loss
            if self.stats["packets_sent"] > 0:
                lost = self.stats["packets_sent"] - self.stats["packets_received"]
                self.stats["packet_loss"] = (lost / self.stats["packets_sent"]) * 100

            logger.info(f"sockperf test complete:")
            logger.info(f"  Avg: {self.stats['latency_avg_us']:.2f} μs")
            logger.info(f"  Min: {self.stats['latency_min_us']:.2f} μs")
            logger.info(f"  P50: {self.stats['latency_p50_us']:.2f} μs")
            logger.info(f"  P90: {self.stats['latency_p90_us']:.2f} μs")
            logger.info(f"  P99: {self.stats['latency_p99_us']:.2f} μs")
            logger.info(f"  Max: {self.stats['latency_max_us']:.2f} μs")

        except Exception as e:
            logger.error(f"Error parsing sockperf output: {e}")

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

    def start_multi_size_test(self, host: str = "127.0.0.1", port: int = 11111,
                             duration: int = 10,
                             msg_sizes: list = None):
        """
        Run ping-pong tests with multiple message sizes sequentially

        Args:
            host: Server hostname/IP
            port: Server port
            duration: Test duration in seconds for each size
            msg_sizes: List of message sizes in bytes (default: [64, 128, 256, 512, 1024, 1500])
        """
        if self.running:
            logger.warning("sockperf test already running")
            return False

        if msg_sizes is None:
            msg_sizes = [64, 128, 256, 512, 1024, 1500]

        try:
            self.running = True
            self.thread = threading.Thread(
                target=self._run_multi_size_test,
                args=(host, port, duration, msg_sizes)
            )
            self.thread.daemon = True
            self.thread.start()

            logger.info(f"sockperf multi-size test started with sizes: {msg_sizes}")
            return True

        except Exception as e:
            logger.error(f"Failed to start multi-size test: {e}")
            self.running = False
            return False

    def _run_multi_size_test(self, host: str, port: int, duration: int, msg_sizes: list):
        """Internal runner for multi-size testing"""
        results = []
        total_sizes = len(msg_sizes)

        try:
            for idx, msg_size in enumerate(msg_sizes):
                if not self.running:
                    break

                # Notify progress
                progress = ((idx) / total_sizes) * 100
                self._notify("multi_size_progress", {
                    "current_size": msg_size,
                    "progress": progress,
                    "current_index": idx + 1,
                    "total_count": total_sizes
                })

                logger.info(f"Testing message size {msg_size} bytes ({idx+1}/{total_sizes})...")

                # Run test for this size
                cmd = [
                    "sockperf", "ping-pong",
                    "-i", host, "-p", str(port),
                    "-t", str(duration),
                    "--msg-size", str(msg_size)
                ]

                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )

                output_lines = []
                for line in self.process.stdout:
                    output_lines.append(line)
                    logger.debug(f"sockperf: {line.strip()}")

                self.process.wait()

                # Parse results for this size
                full_output = ''.join(output_lines)
                size_stats = self._parse_size_test(full_output, msg_size)
                results.append(size_stats)

                # Notify intermediate result
                self._notify("multi_size_result", size_stats)

                logger.info(f"Size {msg_size} bytes - Avg: {size_stats['latency_avg_us']:.2f}μs, Min: {size_stats['latency_min_us']:.2f}μs, P50: {size_stats['latency_p50_us']:.2f}μs, P90: {size_stats['latency_p90_us']:.2f}μs, P99: {size_stats['latency_p99_us']:.2f}μs, Max: {size_stats['latency_max_us']:.2f}μs")

            # Final progress
            self._notify("multi_size_progress", {
                "current_size": 0,
                "progress": 100,
                "current_index": total_sizes,
                "total_count": total_sizes
            })

            # Send all results
            self._notify("multi_size_complete", {"results": results})

        except Exception as e:
            logger.error(f"Multi-size test error: {e}")
            self._notify("error", {"message": str(e)})
        finally:
            self.running = False
            self.process = None

    def _parse_size_test(self, output: str, msg_size: int) -> Dict:
        """Parse results for a single message size test"""
        stats = {
            "msg_size": msg_size,
            "latency_avg_us": 0,
            "latency_min_us": 0,
            "latency_max_us": 0,
            "latency_p50_us": 0,
            "latency_p90_us": 0,
            "latency_p99_us": 0,
        }

        try:
            # Average latency
            match = re.search(r'Summary:\s+Latency is\s+(\d+\.?\d*)\s+usec', output)
            if match:
                stats["latency_avg_us"] = float(match.group(1))

            # Min latency
            match = re.search(r'<MIN> observation\s+=\s+(\d+\.?\d*)', output)
            if match:
                stats["latency_min_us"] = float(match.group(1))

            # Max latency
            match = re.search(r'<MAX> observation\s+=\s+(\d+\.?\d*)', output)
            if match:
                stats["latency_max_us"] = float(match.group(1))

            # Percentiles
            match = re.search(r'percentile 50\.000\s+=\s+(\d+\.?\d*)', output)
            if match:
                stats["latency_p50_us"] = float(match.group(1))

            match = re.search(r'percentile 90\.000\s+=\s+(\d+\.?\d*)', output)
            if match:
                stats["latency_p90_us"] = float(match.group(1))

            match = re.search(r'percentile 99\.000\s+=\s+(\d+\.?\d*)', output)
            if match:
                stats["latency_p99_us"] = float(match.group(1))

        except Exception as e:
            logger.error(f"Error parsing size test: {e}")

        return stats


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def callback(event, data):
        print(f"Event: {event}, Data: {data}")

    # Test ping-pong
    tool = SockPerfTool()
    tool.set_callback(callback)

    print("Starting sockperf ping-pong test...")
    tool.start_ping_pong(host="127.0.0.1", duration=5)

    # Wait for completion
    while tool.running:
        time.sleep(0.5)

    print(f"Final stats: {tool.get_stats()}")
