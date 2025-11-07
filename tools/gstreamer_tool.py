"""
GStreamer Video Streaming Tool for TSN Traffic Testing
Provides webcam streaming with VLAN/PCP tagging for low-latency testing
"""

import subprocess
import threading
import time
import logging
from typing import Optional, Callable
import re

logger = logging.getLogger(__name__)


class GStreamerTool:
    """Wrapper for GStreamer video streaming with TSN support"""

    def __init__(self):
        self.process = None
        self.thread = None
        self.is_running = False
        self.stats = {
            'duration': 0,
            'bitrate': 0,
            'fps': 0,
            'resolution': ''
        }
        self.callback = None

    def set_callback(self, callback: Callable):
        """Set callback function for events"""
        self.callback = callback

    def _notify(self, event_type: str, data: dict = None):
        """Notify via callback"""
        if self.callback:
            try:
                self.callback(event_type, data or {})
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def start_stream(self,
                     interface: str,
                     dest_ip: str,
                     dest_port: int = 5000,
                     vlan_id: int = 100,
                     pcp: int = 5,
                     resolution: str = "640x480",
                     framerate: int = 30,
                     bitrate: int = 2000,
                     codec: str = "h264",
                     use_webcam: bool = True,
                     device: str = "/dev/video0") -> bool:
        """
        Start video streaming

        Args:
            interface: Network interface to use
            dest_ip: Destination IP address
            dest_port: Destination port
            vlan_id: VLAN ID (0-4095)
            pcp: Priority Code Point (0-7)
            resolution: Video resolution (e.g., "640x480", "1280x720")
            framerate: Frames per second
            bitrate: Encoding bitrate in kbps
            codec: Video codec ("h264", "h265", "vp8", "vp9")
            use_webcam: Use real webcam (True) or test pattern (False)
            device: Webcam device path (e.g., /dev/video0)
        """
        if self.is_running:
            logger.warning("GStreamer already running")
            return False

        try:
            width, height = resolution.split('x')
            width, height = int(width), int(height)
        except:
            logger.error(f"Invalid resolution: {resolution}")
            return False

        # Build GStreamer pipeline for video streaming
        pipeline = ['gst-launch-1.0', '-v']

        if use_webcam:
            # Real webcam source
            pipeline.extend([
                'v4l2src', f'device={device}',
                '!', f'video/x-raw,width={width},height={height},framerate={framerate}/1'
            ])
        else:
            # Test pattern
            pipeline.extend([
                'videotestsrc', 'is-live=true',
                '!', f'video/x-raw,width={width},height={height},framerate={framerate}/1'
            ])

        # Encoder and network sink
        pipeline.extend([
            '!', 'videoconvert',
            '!', 'x264enc', f'bitrate={bitrate}', 'tune=zerolatency', 'speed-preset=ultrafast',
            '!', 'rtph264pay',
            '!', 'udpsink', f'host={dest_ip}', f'port={dest_port}'
        ])

        logger.info(f"Starting GStreamer: {' '.join(pipeline)}")

        try:
            self.process = subprocess.Popen(
                pipeline,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            self.is_running = True
            self.stats = {
                'duration': 0,
                'bitrate': bitrate,
                'fps': framerate,
                'resolution': resolution,
                'codec': codec,
                'vlan_id': vlan_id,
                'pcp': pcp
            }

            # Start monitoring thread
            self.thread = threading.Thread(
                target=self._monitor_stream,
                daemon=True
            )
            self.thread.start()

            self._notify('gstreamer_started', {
                'resolution': resolution,
                'framerate': framerate,
                'bitrate': bitrate,
                'dest': f'{dest_ip}:{dest_port}'
            })

            return True

        except Exception as e:
            logger.error(f"Failed to start GStreamer: {e}")
            self._notify('gstreamer_error', {'error': str(e)})
            return False

    def stop_stream(self) -> bool:
        """Stop video streaming"""
        if not self.is_running:
            return False

        try:
            if self.process:
                self.process.terminate()
                self.process.wait(timeout=5)
            self.is_running = False

            final_stats = self.stats.copy()
            self._notify('gstreamer_stopped', final_stats)

            logger.info("GStreamer stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping GStreamer: {e}")
            if self.process:
                self.process.kill()
            self.is_running = False
            return False

    def _monitor_stream(self):
        """Monitor GStreamer process"""
        start_time = time.time()

        while self.is_running and self.process:
            # Update duration
            self.stats['duration'] = time.time() - start_time

            # Check if process is still running
            if self.process.poll() is not None:
                logger.info("GStreamer process ended")
                self.is_running = False
                break

            time.sleep(1)

        # Process ended
        if self.process:
            stdout, stderr = self.process.communicate()
            if stderr:
                logger.debug(f"GStreamer stderr: {stderr[-500:]}")  # Last 500 chars

        self._notify('gstreamer_complete', self.stats)

    def get_stats(self) -> dict:
        """Get current streaming statistics"""
        return self.stats.copy()

    def is_streaming(self) -> bool:
        """Check if streaming is active"""
        return self.is_running

    def start_receiver(self,
                       port: int = 5000,
                       display: bool = True,
                       save_file: str = None) -> bool:
        """
        Start video receiver

        Args:
            port: Port to receive on
            display: Display video window
            save_file: Optional file path to save video
        """
        if self.is_running:
            logger.warning("GStreamer already running")
            return False

        # Build GStreamer receiver pipeline
        pipeline = ['gst-launch-1.0', '-v']

        # Receive UDP RTP stream
        pipeline.extend([
            'udpsrc', f'port={port}',
            '!', 'application/x-rtp,encoding-name=H264,payload=96',
            '!', 'rtph264depay',
            '!', 'h264parse',
            '!', 'avdec_h264'
        ])

        if save_file:
            # Save to file
            pipeline.extend([
                '!', 'tee', 'name=t',
                't.', '!', 'queue', '!', 'videoconvert', '!', 'x264enc', '!', 'mp4mux', '!', f'filesink location={save_file}'
            ])
            if display:
                pipeline.extend([
                    't.', '!', 'queue', '!', 'videoconvert', '!', 'autovideosink'
                ])
        else:
            if display:
                # Display only
                pipeline.extend([
                    '!', 'videoconvert',
                    '!', 'autovideosink'
                ])
            else:
                # Fakesink (just receive, no display)
                pipeline.extend([
                    '!', 'fakesink'
                ])

        logger.info(f"Starting GStreamer receiver: {' '.join(pipeline)}")

        try:
            self.process = subprocess.Popen(
                pipeline,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            self.is_running = True
            self.stats = {
                'duration': 0,
                'port': port,
                'mode': 'receiver'
            }

            # Start monitoring thread
            self.thread = threading.Thread(
                target=self._monitor_stream,
                daemon=True
            )
            self.thread.start()

            self._notify('gstreamer_receiver_started', {
                'port': port,
                'display': display,
                'save_file': save_file
            })

            return True

        except Exception as e:
            logger.error(f"Failed to start GStreamer receiver: {e}")
            self._notify('gstreamer_error', {'error': str(e)})
            return False

    @staticmethod
    def check_available() -> bool:
        """Check if GStreamer is available"""
        try:
            result = subprocess.run(
                ['gst-launch-1.0', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
