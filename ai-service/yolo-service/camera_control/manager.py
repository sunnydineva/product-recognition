import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from detection.preview import clear_preview


SERVICE_DIR = Path(__file__).resolve().parent.parent
CAMERA_SCRIPT = SERVICE_DIR / "run_live_camera.py"
PID_FILE = SERVICE_DIR / "camera.pid"


class CameraManager:
    """
    Manage the lifecycle of the live camera worker.

    The worker runs in a separate Python process and performs
    camera capture, YOLO tracking, and DINOv2 recognition.

    A PID file allows FastAPI to find the worker after a restart.
    """

    def __init__(self):
        """
        Initialize process management.

        The lock prevents concurrent start/stop operations within
        the current FastAPI process.
        """
        self.lock = threading.Lock()

    def _find_process(self):
        """
        Find the camera worker recorded in the PID file.

        Verify both the process ID and its command line to avoid
        accidentally controlling an unrelated process.

        Returns:
            A psutil.Process instance, or None if no valid worker exists.
        """
        if not PID_FILE.exists():
            return None

        try:
            pid = int(PID_FILE.read_text().strip())
            process = psutil.Process(pid)

            if not process.is_running():
                return None

            if process.status() == psutil.STATUS_ZOMBIE:
                return None

            command = process.cmdline()

            if str(CAMERA_SCRIPT) not in command:
                return None

            return process

        except (ValueError, psutil.Error, OSError):
            return None

    def status(self) -> dict:
        """
        Return the current camera worker status.

        Returns:
            A dictionary with the worker state and PID, if running.
        """
        with self.lock:
            process = self._find_process()

            if process is None:
                return {"status": "stopped"}

            return {
                "status": "running",
                "pid": process.pid,
            }

    def start(self) -> dict:
        """
        Start the camera worker if it is not already running.

        Prevent duplicate starts by checking the existing PID file.

        Returns:
            The worker startup state and PID.
        """
        with self.lock:
            process = self._find_process()

            if process is not None:
                return {
                    "status": "running",
                    "pid": process.pid,
                    "message": "Camera already running",
                }

            clear_preview()

            process = subprocess.Popen(
                [sys.executable, str(CAMERA_SCRIPT)],
                cwd=SERVICE_DIR,
                env=os.environ.copy(),
                start_new_session=True,
            )

            PID_FILE.write_text(str(process.pid))

            return {
                "status": "starting",
                "pid": process.pid,
            }

    def stop(self) -> dict:
        """
        Stop the camera worker using its saved process ID.

        First request a graceful shutdown with SIGTERM.
        If the process does not exit within 20 seconds, force
        termination with SIGKILL.

        Returns:
            A dictionary containing the stopped state.
        """
        with self.lock:
            process = self._find_process()

            if process is None:
                PID_FILE.unlink(missing_ok=True)
                clear_preview()
                return {"status": "stopped"}

            try:
                os.killpg(process.pid, signal.SIGTERM)

                try:
                    process.wait(timeout=20)
                except psutil.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)

            except (ProcessLookupError, psutil.NoSuchProcess):
                pass

            PID_FILE.unlink(missing_ok=True)
            clear_preview()

            return {"status": "stopped"}


camera_manager = CameraManager()
