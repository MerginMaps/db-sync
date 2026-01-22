"""
Subprocess management for the sync daemon.
"""

import os
import pathlib
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Optional

from . import config_manager


class SyncManager:
    """Manages the dbsync_daemon subprocess."""

    def __init__(self, max_log_lines: int = 1000):
        self.process: Optional[subprocess.Popen] = None
        self.log_buffer: deque = deque(maxlen=max_log_lines)
        self._log_lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_reader = threading.Event()

    @property
    def is_running(self) -> bool:
        """Check if the sync daemon is currently running."""
        if self.process is None:
            return False
        return self.process.poll() is None

    def get_status(self) -> dict:
        """Get current sync daemon status."""
        if self.process is None:
            return {
                "running": False,
                "status": "stopped",
                "pid": None
            }

        poll_result = self.process.poll()
        if poll_result is None:
            return {
                "running": True,
                "status": "running",
                "pid": self.process.pid
            }
        else:
            return {
                "running": False,
                "status": "stopped",
                "pid": None,
                "exit_code": poll_result
            }

    def start(self, force_init: bool = False) -> dict:
        """
        Start the sync daemon subprocess.

        Args:
            force_init: If True, pass --force-init flag to reinitialize

        Returns:
            dict with 'success' boolean and status or 'error' string
        """
        if self.is_running:
            return {
                "success": False,
                "error": "Sync daemon is already running"
            }

        config_path = config_manager.get_config_path()
        if not config_path.exists():
            return {
                "success": False,
                "error": "Configuration file not found. Please complete the setup wizard first."
            }

        # Build command
        project_root = pathlib.Path(__file__).parent.parent
        daemon_script = project_root / "dbsync_daemon.py"

        cmd = [sys.executable, str(daemon_script), str(config_path)]
        if force_init:
            cmd.append("--force-init")

        try:
            # Clear log buffer
            with self._log_lock:
                self.log_buffer.clear()

            # Start process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=str(project_root)
            )

            # Start log reader thread
            self._stop_reader.clear()
            self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self._reader_thread.start()

            return {
                "success": True,
                "status": "started",
                "pid": self.process.pid
            }

        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Daemon script not found: {daemon_script}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to start daemon: {str(e)}"
            }

    def stop(self) -> dict:
        """
        Stop the sync daemon subprocess.

        Returns:
            dict with 'success' boolean and status or 'error' string
        """
        if not self.is_running:
            return {
                "success": False,
                "error": "Sync daemon is not running"
            }

        try:
            # Signal reader thread to stop
            self._stop_reader.set()

            # Terminate process
            self.process.terminate()

            # Wait for process to end (with timeout)
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't respond
                self.process.kill()
                self.process.wait(timeout=5)

            exit_code = self.process.returncode

            # Add stop message to log
            with self._log_lock:
                self.log_buffer.append(f"[Web UI] Sync daemon stopped (exit code: {exit_code})")

            return {
                "success": True,
                "status": "stopped",
                "exit_code": exit_code
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to stop daemon: {str(e)}"
            }

    def _read_output(self):
        """Read output from subprocess in a separate thread."""
        try:
            while not self._stop_reader.is_set() and self.process and self.process.stdout:
                line = self.process.stdout.readline()
                if line:
                    with self._log_lock:
                        self.log_buffer.append(line.rstrip())
                elif self.process.poll() is not None:
                    # Process ended
                    break
        except Exception:
            pass

    def get_logs(self, last_n: int = 100) -> list:
        """
        Get recent log lines.

        Args:
            last_n: Number of recent lines to return

        Returns:
            list of log lines
        """
        with self._log_lock:
            logs = list(self.log_buffer)
            if last_n and len(logs) > last_n:
                return logs[-last_n:]
            return logs

    def get_new_logs_since(self, index: int) -> dict:
        """
        Get log lines since a given index.

        Args:
            index: Starting index

        Returns:
            dict with 'logs' list and 'next_index' int
        """
        with self._log_lock:
            logs = list(self.log_buffer)
            if index >= len(logs):
                return {"logs": [], "next_index": len(logs)}
            return {
                "logs": logs[index:],
                "next_index": len(logs)
            }


# Global instance
_sync_manager: Optional[SyncManager] = None


def get_sync_manager() -> SyncManager:
    """Get the global SyncManager instance."""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = SyncManager()
    return _sync_manager
