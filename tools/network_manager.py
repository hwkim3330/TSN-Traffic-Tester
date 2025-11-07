#!/usr/bin/env python3
"""
Network Interface Manager
Provides interface discovery and management capabilities using netifaces and psutil
"""

import logging
import subprocess
import json
from typing import List, Dict, Optional
import netifaces
import psutil

logger = logging.getLogger(__name__)


class NetworkManager:
    """Manages network interfaces and provides detailed interface information"""

    def __init__(self):
        self.interfaces = []
        self.refresh_interfaces()

    def refresh_interfaces(self) -> List[Dict]:
        """
        Refresh and return list of network interfaces with their details

        Returns:
            List of interface dictionaries with name, mac, ipv4, ipv6, status, stats
        """
        self.interfaces = []

        # Get all interface names
        interface_names = netifaces.interfaces()

        for iface in interface_names:
            # Skip loopback
            if iface == 'lo':
                continue

            iface_info = {
                "name": iface,
                "mac": None,
                "ipv4": None,
                "ipv6": None,
                "netmask": None,
                "status": "unknown",
                "mtu": None,
                "speed": None,
                "duplex": None,
                "stats": {}
            }

            # Get addresses
            addrs = netifaces.ifaddresses(iface)

            # MAC address
            if netifaces.AF_LINK in addrs:
                iface_info["mac"] = addrs[netifaces.AF_LINK][0].get('addr', None)

            # IPv4 address
            if netifaces.AF_INET in addrs:
                iface_info["ipv4"] = addrs[netifaces.AF_INET][0].get('addr', None)
                iface_info["netmask"] = addrs[netifaces.AF_INET][0].get('netmask', None)

            # IPv6 address
            if netifaces.AF_INET6 in addrs:
                ipv6_addrs = [addr['addr'] for addr in addrs[netifaces.AF_INET6]]
                # Filter out link-local addresses
                global_ipv6 = [addr for addr in ipv6_addrs if not addr.startswith('fe80:')]
                if global_ipv6:
                    iface_info["ipv6"] = global_ipv6[0]

            # Get status and stats using psutil
            try:
                stats = psutil.net_if_stats().get(iface)
                if stats:
                    iface_info["status"] = "up" if stats.isup else "down"
                    iface_info["mtu"] = stats.mtu
                    iface_info["speed"] = f"{stats.speed}Mbps" if stats.speed > 0 else "unknown"
                    iface_info["duplex"] = self._get_duplex_string(stats.duplex)

                # Get I/O counters
                io_counters = psutil.net_io_counters(pernic=True).get(iface)
                if io_counters:
                    iface_info["stats"] = {
                        "bytes_sent": io_counters.bytes_sent,
                        "bytes_recv": io_counters.bytes_recv,
                        "packets_sent": io_counters.packets_sent,
                        "packets_recv": io_counters.packets_recv,
                        "errin": io_counters.errin,
                        "errout": io_counters.errout,
                        "dropin": io_counters.dropin,
                        "dropout": io_counters.dropout
                    }
            except Exception as e:
                logger.warning(f"Could not get stats for {iface}: {e}")

            self.interfaces.append(iface_info)

        logger.info(f"Found {len(self.interfaces)} network interfaces")
        return self.interfaces

    def _get_duplex_string(self, duplex) -> str:
        """Convert psutil duplex constant to string"""
        if duplex == psutil.NIC_DUPLEX_FULL:
            return "full"
        elif duplex == psutil.NIC_DUPLEX_HALF:
            return "half"
        else:
            return "unknown"

    def get_interface(self, name: str) -> Optional[Dict]:
        """Get specific interface by name"""
        for iface in self.interfaces:
            if iface["name"] == name:
                return iface
        return None

    def get_active_interfaces(self) -> List[Dict]:
        """Get only interfaces that are up"""
        return [iface for iface in self.interfaces if iface["status"] == "up"]

    def get_ethtool_info(self, interface: str) -> Dict:
        """
        Get detailed interface information using ethtool
        Requires sudo/root privileges

        Args:
            interface: Interface name (e.g., 'enp11s0')

        Returns:
            Dictionary with ethtool information
        """
        info = {
            "interface": interface,
            "driver": None,
            "version": None,
            "firmware": None,
            "bus_info": None,
            "link_detected": None,
            "speed": None,
            "duplex": None,
            "auto_negotiation": None,
            "tsn_capable": False,
            "offload": {}
        }

        try:
            # Get driver info
            result = subprocess.run(
                ['ethtool', '-i', interface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace('-', '_')
                        value = value.strip()

                        if key == "driver":
                            info["driver"] = value
                        elif key == "version":
                            info["version"] = value
                        elif key == "firmware_version":
                            info["firmware"] = value
                        elif key == "bus_info":
                            info["bus_info"] = value

            # Get link status and speed
            result = subprocess.run(
                ['ethtool', interface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) < 2:
                            continue
                        key = parts[0].strip().lower().replace(' ', '_')
                        value = parts[1].strip()

                        if key == "speed":
                            info["speed"] = value
                        elif key == "duplex":
                            info["duplex"] = value
                        elif key == "auto-negotiation" or key == "auto_negotiation":
                            info["auto_negotiation"] = value
                        elif key == "link_detected":
                            info["link_detected"] = value == "yes"

            # Check for TSN capabilities (look for i210, i211, LAN966x, etc.)
            if info["driver"]:
                tsn_drivers = ['igb', 'igc', 'lan966x', 'stmmac', 'cpsw']
                info["tsn_capable"] = any(drv in info["driver"].lower() for drv in tsn_drivers)

            # Get offload features
            result = subprocess.run(
                ['ethtool', '-k', interface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if ':' in line:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            key = parts[0].strip()
                            value = parts[1].strip().split()[0]  # Get first word (on/off)
                            info["offload"][key] = value == "on"

        except subprocess.TimeoutExpired:
            logger.error(f"ethtool command timed out for {interface}")
        except FileNotFoundError:
            logger.warning("ethtool not found - install with: sudo apt install ethtool")
        except Exception as e:
            logger.error(f"Error getting ethtool info for {interface}: {e}")

        return info

    def set_interface_state(self, interface: str, state: str, sudo_password: Optional[str] = None) -> bool:
        """
        Bring interface up or down
        Requires sudo privileges

        Args:
            interface: Interface name
            state: 'up' or 'down'
            sudo_password: Optional sudo password

        Returns:
            True if successful
        """
        if state not in ['up', 'down']:
            logger.error(f"Invalid state: {state} (must be 'up' or 'down')")
            return False

        try:
            cmd = ['sudo', 'ip', 'link', 'set', interface, state]

            if sudo_password:
                # Use sudo with password
                process = subprocess.Popen(
                    ['sudo', '-S'] + cmd[1:],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout, stderr = process.communicate(input=sudo_password + '\n', timeout=5)

                if process.returncode == 0:
                    logger.info(f"Interface {interface} set to {state}")
                    return True
                else:
                    logger.error(f"Failed to set {interface} to {state}: {stderr}")
                    return False
            else:
                # Try without password (user may have NOPASSWD sudo)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

                if result.returncode == 0:
                    logger.info(f"Interface {interface} set to {state}")
                    return True
                else:
                    logger.error(f"Failed to set {interface} to {state}: {result.stderr}")
                    return False

        except Exception as e:
            logger.error(f"Error setting interface state: {e}")
            return False

    def get_interface_queues(self, interface: str) -> Dict:
        """
        Get TX queue information for an interface

        Args:
            interface: Interface name

        Returns:
            Dictionary with queue information
        """
        info = {
            "interface": interface,
            "num_queues": 0,
            "queues": []
        }

        try:
            # Get queue info using tc
            result = subprocess.run(
                ['tc', 'qdisc', 'show', 'dev', interface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                info["qdisc_config"] = result.stdout

            # Try to get queue count from sysfs
            try:
                with open(f'/sys/class/net/{interface}/queues', 'r') as f:
                    # This is a directory, we need to list it
                    pass
            except:
                pass

            # Alternative: use ethtool -l
            result = subprocess.run(
                ['ethtool', '-l', interface],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'TX:' in line and 'Combined:' not in line:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            try:
                                info["num_queues"] = int(parts[1].strip())
                            except:
                                pass

        except Exception as e:
            logger.error(f"Error getting queue info: {e}")

        return info


# Global instance
network_manager = NetworkManager()


if __name__ == "__main__":
    # Test the network manager
    logging.basicConfig(level=logging.INFO)

    print("Network Interfaces:")
    print("=" * 80)

    interfaces = network_manager.refresh_interfaces()

    for iface in interfaces:
        print(f"\nInterface: {iface['name']}")
        print(f"  MAC: {iface['mac']}")
        print(f"  IPv4: {iface['ipv4']}")
        print(f"  Status: {iface['status']}")
        print(f"  Speed: {iface['speed']}")
        print(f"  MTU: {iface['mtu']}")

        if iface['stats']:
            print(f"  RX: {iface['stats']['bytes_recv']:,} bytes, {iface['stats']['packets_recv']:,} packets")
            print(f"  TX: {iface['stats']['bytes_sent']:,} bytes, {iface['stats']['packets_sent']:,} packets")

    # Test ethtool on first active interface
    active = network_manager.get_active_interfaces()
    if active:
        iface_name = active[0]['name']
        print(f"\n\nDetailed info for {iface_name}:")
        print("=" * 80)

        ethtool_info = network_manager.get_ethtool_info(iface_name)
        print(json.dumps(ethtool_info, indent=2))
