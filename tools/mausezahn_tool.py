#!/usr/bin/env python3
"""
Mausezahn Tool Wrapper
Advanced packet generator with VLAN/PCP support for TSN testing
"""

import logging
import subprocess
import threading
import time
from typing import Optional, Dict, Callable
import re

logger = logging.getLogger(__name__)


class MausezahnTool:
    """Wrapper for mausezahn packet generator"""

    def __init__(self):
        self.running = False
        self.process = None
        self.thread = None
        self.callback = None

        self.stats = {
            "packets_sent": 0,
            "bytes_sent": 0,
            "start_time": None,
            "end_time": None,
            "duration": 0
        }

    def set_callback(self, callback: Callable):
        """Set callback for events"""
        self.callback = callback

    def _send_event(self, event: str, data: dict):
        """Send event via callback"""
        if self.callback:
            try:
                self.callback(event, data)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def start_vlan_traffic(self,
                          interface: str,
                          dest_ip: str,
                          vlan_id: int,
                          pcp: int = 0,
                          packet_type: str = "udp",
                          dest_port: int = 5000,
                          packet_size: int = 1000,
                          count: int = 1000,
                          delay: str = "1msec",
                          src_mac: Optional[str] = None,
                          dest_mac: Optional[str] = None) -> bool:
        """
        Start VLAN-tagged traffic generation

        Args:
            interface: Network interface (e.g., 'eth0')
            dest_ip: Destination IP address
            vlan_id: VLAN ID (0-4095)
            pcp: Priority Code Point (0-7)
            packet_type: Packet type ('udp', 'tcp', 'icmp')
            dest_port: Destination port for UDP/TCP
            packet_size: Packet payload size in bytes
            count: Number of packets to send
            delay: Delay between packets (e.g., '1msec', '100usec')
            src_mac: Source MAC address (optional)
            dest_mac: Destination MAC address (optional)

        Returns:
            True if started successfully
        """
        if self.running:
            logger.warning("Mausezahn already running")
            return False

        try:
            # Build mausezahn command
            cmd = ['sudo', 'mausezahn', interface]

            # Add VLAN tag with PCP
            cmd.extend(['-Q', f'{vlan_id},{pcp}'])

            # Add MAC addresses if provided
            if src_mac:
                cmd.extend(['-a', src_mac])
            if dest_mac:
                cmd.extend(['-b', dest_mac])

            # Add packet type and parameters
            if packet_type == 'udp':
                cmd.extend(['-t', 'udp', f'dp={dest_port},sp=5000'])
            elif packet_type == 'tcp':
                cmd.extend(['-t', 'tcp', f'dp={dest_port},sp=5000'])
            elif packet_type == 'icmp':
                cmd.extend(['-t', 'icmp', 'type=8'])

            # Add destination IP
            cmd.extend(['-B', dest_ip])

            # Add payload size
            cmd.extend(['-P', str(packet_size)])

            # Add count and delay
            cmd.extend(['-c', str(count)])
            cmd.extend(['-d', delay])

            logger.info(f"Starting mausezahn: {' '.join(cmd)}")

            # Start in background thread
            self.running = True
            self.stats["start_time"] = time.time()
            self.stats["packets_sent"] = 0
            self.stats["bytes_sent"] = 0

            self.thread = threading.Thread(
                target=self._run_mausezahn,
                args=(cmd, count, packet_size),
                daemon=True
            )
            self.thread.start()

            self._send_event("mausezahn_started", {
                "interface": interface,
                "vlan_id": vlan_id,
                "pcp": pcp,
                "packet_type": packet_type,
                "count": count
            })

            return True

        except Exception as e:
            logger.error(f"Failed to start mausezahn: {e}")
            self.running = False
            return False

    def _run_mausezahn(self, cmd: list, count: int, packet_size: int):
        """Run mausezahn command and track progress"""
        try:
            # Run mausezahn
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes max
            )

            # Update stats
            self.stats["end_time"] = time.time()
            self.stats["duration"] = self.stats["end_time"] - self.stats["start_time"]
            self.stats["packets_sent"] = count
            self.stats["bytes_sent"] = count * packet_size

            if result.returncode == 0:
                logger.info(f"Mausezahn completed: {count} packets sent")
                self._send_event("mausezahn_complete", self.stats)
            else:
                logger.error(f"Mausezahn failed: {result.stderr}")
                self._send_event("mausezahn_error", {"error": result.stderr})

        except subprocess.TimeoutExpired:
            logger.error("Mausezahn timed out")
            self._send_event("mausezahn_error", {"error": "Timeout"})
        except Exception as e:
            logger.error(f"Mausezahn error: {e}")
            self._send_event("mausezahn_error", {"error": str(e)})
        finally:
            self.running = False

    def start_custom_traffic(self,
                            interface: str,
                            packet_hex: str,
                            vlan_id: Optional[int] = None,
                            pcp: int = 0,
                            count: int = 1000,
                            delay: str = "1msec") -> bool:
        """
        Start traffic with custom packet hex data

        Args:
            interface: Network interface
            packet_hex: Hexadecimal packet data
            vlan_id: Optional VLAN ID
            pcp: Priority Code Point
            count: Number of packets
            delay: Delay between packets

        Returns:
            True if started successfully
        """
        if self.running:
            logger.warning("Mausezahn already running")
            return False

        try:
            cmd = ['sudo', 'mausezahn', interface]

            if vlan_id is not None:
                cmd.extend(['-Q', f'{vlan_id},{pcp}'])

            cmd.extend(['-c', str(count)])
            cmd.extend(['-d', delay])
            cmd.append(packet_hex)

            logger.info(f"Starting custom mausezahn: {' '.join(cmd)}")

            self.running = True
            self.stats["start_time"] = time.time()

            self.thread = threading.Thread(
                target=self._run_mausezahn,
                args=(cmd, count, len(packet_hex) // 2),
                daemon=True
            )
            self.thread.start()

            self._send_event("mausezahn_started", {
                "interface": interface,
                "vlan_id": vlan_id,
                "pcp": pcp,
                "custom": True
            })

            return True

        except Exception as e:
            logger.error(f"Failed to start custom mausezahn: {e}")
            self.running = False
            return False

    def stop(self):
        """Stop mausezahn"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                self.process.kill()

        self.running = False
        logger.info("Mausezahn stopped")

    def get_stats(self) -> dict:
        """Get current statistics"""
        return self.stats.copy()

    @staticmethod
    def check_available() -> bool:
        """Check if mausezahn is available"""
        try:
            result = subprocess.run(
                ['which', 'mausezahn'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False


if __name__ == "__main__":
    # Test mausezahn tool
    logging.basicConfig(level=logging.INFO)

    tool = MausezahnTool()

    print("Mausezahn Tool Test")
    print("=" * 50)

    if not MausezahnTool.check_available():
        print("ERROR: mausezahn not found")
        exit(1)

    print("mausezahn is available")
    print("\nTest: Send 10 UDP packets with VLAN 100, PCP 5")

    def callback(event, data):
        print(f"Event: {event}")
        print(f"Data: {data}")

    tool.set_callback(callback)

    # Test with lo interface (loopback)
    success = tool.start_vlan_traffic(
        interface='lo',
        dest_ip='127.0.0.1',
        vlan_id=100,
        pcp=5,
        packet_type='udp',
        dest_port=5000,
        packet_size=100,
        count=10,
        delay='100msec'
    )

    if success:
        print("\nTest started, waiting for completion...")
        time.sleep(5)
        stats = tool.get_stats()
        print(f"\nFinal stats: {stats}")
