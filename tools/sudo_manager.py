#!/usr/bin/env python3
"""
Sudo Password Manager
Secure management of sudo passwords for privileged operations
"""

import logging
import subprocess
import time
from typing import Optional
import hashlib
import secrets

logger = logging.getLogger(__name__)


class SudoManager:
    """Manages sudo password with security considerations"""

    def __init__(self, session_timeout: int = 900):
        """
        Initialize sudo manager

        Args:
            session_timeout: Session timeout in seconds (default 15 minutes)
        """
        self.session_timeout = session_timeout
        self._password = None
        self._password_hash = None
        self._last_use_time = None
        self._session_token = None
        self._verified = False

    def set_password(self, password: str) -> tuple[bool, str]:
        """
        Set and verify sudo password

        Args:
            password: Sudo password to verify

        Returns:
            Tuple of (success, message)
        """
        try:
            # Verify password by running a simple sudo command
            process = subprocess.Popen(
                ['sudo', '-S', 'echo', 'test'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate(input=password + '\n', timeout=5)

            if process.returncode == 0:
                # Password is correct
                self._password = password
                self._password_hash = hashlib.sha256(password.encode()).hexdigest()
                self._last_use_time = time.time()
                self._session_token = secrets.token_hex(16)
                self._verified = True

                logger.info("Sudo password verified and stored")
                return True, "Password verified successfully"
            else:
                logger.warning("Failed to verify sudo password")
                return False, "Incorrect password or sudo not configured"

        except subprocess.TimeoutExpired:
            logger.error("Sudo password verification timed out")
            return False, "Verification timed out"
        except Exception as e:
            logger.error(f"Error verifying sudo password: {e}")
            return False, f"Verification error: {str(e)}"

    def get_password(self) -> Optional[str]:
        """
        Get stored sudo password if session is still valid

        Returns:
            Password if valid session, None otherwise
        """
        if not self._verified or self._password is None:
            return None

        # Check session timeout
        if self._last_use_time is not None:
            elapsed = time.time() - self._last_use_time
            if elapsed > self.session_timeout:
                logger.info("Sudo session expired")
                self.clear_password()
                return None

        # Update last use time
        self._last_use_time = time.time()
        return self._password

    def clear_password(self):
        """Clear stored password from memory"""
        self._password = None
        self._password_hash = None
        self._session_token = None
        self._verified = False
        logger.info("Sudo password cleared from memory")

    def is_valid_session(self) -> bool:
        """Check if current session is still valid"""
        if not self._verified or self._password is None:
            return False

        if self._last_use_time is not None:
            elapsed = time.time() - self._last_use_time
            if elapsed > self.session_timeout:
                return False

        return True

    def get_session_token(self) -> Optional[str]:
        """Get current session token"""
        if self.is_valid_session():
            return self._session_token
        return None

    def execute_sudo_command(self, command: list[str], timeout: int = 30) -> tuple[bool, str, str]:
        """
        Execute a command with sudo privileges

        Args:
            command: Command to execute as list (e.g., ['ip', 'link', 'set', 'eth0', 'up'])
            timeout: Command timeout in seconds

        Returns:
            Tuple of (success, stdout, stderr)
        """
        password = self.get_password()
        if password is None:
            return False, "", "No valid sudo session. Please authenticate."

        try:
            # Prepare sudo command
            sudo_cmd = ['sudo', '-S'] + command

            process = subprocess.Popen(
                sudo_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout, stderr = process.communicate(input=password + '\n', timeout=timeout)

            if process.returncode == 0:
                logger.info(f"Sudo command executed successfully: {' '.join(command)}")
                return True, stdout, stderr
            else:
                logger.warning(f"Sudo command failed: {' '.join(command)}")
                return False, stdout, stderr

        except subprocess.TimeoutExpired:
            logger.error(f"Sudo command timed out: {' '.join(command)}")
            return False, "", "Command timed out"
        except Exception as e:
            logger.error(f"Error executing sudo command: {e}")
            return False, "", str(e)

    def check_sudo_available(self) -> bool:
        """
        Check if sudo is available on the system

        Returns:
            True if sudo is available
        """
        try:
            result = subprocess.run(
                ['which', 'sudo'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_session_info(self) -> dict:
        """
        Get current session information

        Returns:
            Dictionary with session details
        """
        if not self.is_valid_session():
            return {
                "active": False,
                "remaining_time": 0
            }

        elapsed = time.time() - self._last_use_time if self._last_use_time else 0
        remaining = max(0, self.session_timeout - elapsed)

        return {
            "active": True,
            "remaining_time": int(remaining),
            "last_use": int(elapsed)
        }


# Global instance
sudo_manager = SudoManager()


if __name__ == "__main__":
    # Test sudo manager
    logging.basicConfig(level=logging.INFO)

    print("Sudo Manager Test")
    print("=" * 50)

    if not sudo_manager.check_sudo_available():
        print("ERROR: sudo is not available on this system")
        exit(1)

    print("Sudo is available")
    print("\nEnter sudo password to test:")

    import getpass
    password = getpass.getpass()

    success, message = sudo_manager.set_password(password)
    print(f"\nVerification: {message}")

    if success:
        print(f"Session active: {sudo_manager.is_valid_session()}")
        print(f"Session token: {sudo_manager.get_session_token()}")

        # Test command
        print("\nTesting sudo command (echo test)...")
        success, stdout, stderr = sudo_manager.execute_sudo_command(['echo', 'test'])
        print(f"Success: {success}")
        print(f"Output: {stdout}")

        # Get session info
        info = sudo_manager.get_session_info()
        print(f"\nSession info: {info}")
