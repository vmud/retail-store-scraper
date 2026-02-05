"""Scraper process lifecycle management and control system"""

import os
import sys
import subprocess
import signal
import logging
import time
import atexit
import platform
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .run_tracker import RunTracker, get_active_run
from .status import load_retailers_config


__all__ = [
    'ScraperManager',
    'get_scraper_manager',
]


logger = logging.getLogger(__name__)


class ScraperManager:
    """Manage scraper process lifecycle (start, stop, restart)

    Thread-safe process manager with automatic cleanup and state recovery.
    """

    def __init__(self):
        """Initialize scraper manager"""
        self._processes: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

        self._run_py_path = self._find_run_py()

        self._recover_running_processes()

        atexit.register(self._cleanup_on_exit)

    def _find_run_py(self) -> str:
        """Find run.py script path"""
        run_py = Path("run.py")
        if run_py.exists():
            return str(run_py.absolute())

        run_py = Path(__file__).parent.parent.parent / "run.py"
        if run_py.exists():
            return str(run_py.absolute())

        raise FileNotFoundError("Could not find run.py script")

    def _get_log_file(self, retailer: str, run_id: str) -> str:
        """Get log file path for retailer

        Args:
            retailer: Retailer name
            run_id: Run ID for this scraper run

        Returns:
            Path to log file (data/{retailer}/logs/{run_id}.log)
        """
        log_dir = Path(f"data/{retailer}/logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        return str(log_dir / f"{run_id}.log")

    def _verify_process_is_scraper(self, pid: int, retailer: str) -> bool:
        """Verify that a PID belongs to our scraper process (#56).

        PID recycling can cause os.kill(pid, 0) to succeed for a different
        process that has reused the PID. This method verifies the process
        command line contains expected scraper identifiers.

        Safety: When verification tools fail or are unavailable, we fall back
        to trusting the PID check (return True) rather than incorrectly marking
        valid processes as failed.

        Args:
            pid: Process ID to verify
            retailer: Expected retailer name in command line

        Returns:
            True if the process appears to be our scraper or if verification fails,
            False only if we can confirm it's NOT our scraper
        """
        try:
            if platform.system() == 'Darwin' or platform.system() == 'Linux':
                # Use ps to get command line on Unix-like systems
                result = subprocess.run(
                    ['ps', '-p', str(pid), '-o', 'command='],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False
                )
                if result.returncode != 0:
                    # ps failed - could be PID doesn't exist OR tool error
                    # Check if output suggests "no such process" vs other errors
                    stderr_output = result.stderr if hasattr(result, 'stderr') else ""
                    if not result.stdout.strip() and not stderr_output:
                        # No output typically means PID doesn't exist
                        return False
                    # Other error - fall back to trusting PID check
                    logger.warning(
                        f"ps returned non-zero for PID {pid} but unclear if process "
                        f"missing or tool error - falling back to PID check"
                    )
                    return True

                cmdline = result.stdout.strip()
                if not cmdline:
                    # Empty output means process doesn't exist
                    return False

                # Verify it looks like our scraper command
                if 'run.py' in cmdline and retailer in cmdline:
                    return True
                # Also check for python process with our module
                if 'python' in cmdline.lower() and retailer in cmdline:
                    return True
                # Process exists but isn't our scraper
                return False

            elif platform.system() == 'Windows':
                # Use wmic on Windows
                result = subprocess.run(
                    ['wmic', 'process', 'where', f'ProcessId={pid}', 'get', 'CommandLine'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False
                )
                if result.returncode != 0:
                    # wmic failed - fall back to trusting PID check to be safe
                    logger.warning(
                        f"wmic returned non-zero for PID {pid} - unclear if process "
                        f"missing or tool error - falling back to PID check"
                    )
                    return True

                cmdline = result.stdout.strip()
                # WMIC returns headers even for non-existent PIDs, check for data
                lines = [line.strip() for line in cmdline.split('\n') if line.strip()]
                if len(lines) <= 1:  # Only header, no data
                    return False

                if 'run.py' in cmdline and retailer in cmdline:
                    return True
                # Process exists but isn't our scraper
                return False

            else:
                # Unknown platform - fall back to PID-only check
                logger.debug(f"Unknown platform {platform.system()} - falling back to PID-only check")
                return True

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            logger.warning(f"Could not verify process {pid}: {e} - falling back to PID-only check")
            # Fall back to PID-only check - assume process is valid if PID exists
            # We can't determine either way, so trust the existing PID check
            return True

    def _recover_running_processes(self) -> None:
        """Recover running processes from RunTracker metadata on startup

        This allows the manager to track scrapers that were started before
        a restart/crash of the dashboard application.

        Uses process verification (#56) to avoid misidentifying recycled PIDs.
        """
        config = load_retailers_config()

        for retailer in config.keys():
            active_run = get_active_run(retailer)
            if not active_run:
                continue

            pid = active_run.get('config', {}).get('pid')
            if not pid:
                continue

            try:
                # First check if PID exists
                os.kill(pid, 0)

                # Then verify it's actually our scraper process (#56)
                if not self._verify_process_is_scraper(pid, retailer):
                    logger.info(
                        f"PID {pid} exists but is not our scraper for {retailer} "
                        f"(likely PID recycling)"
                    )
                    tracker = RunTracker(retailer, run_id=active_run['run_id'])
                    tracker.fail("Process not found on recovery (PID recycled)")
                    continue

                logger.info(f"Recovered running scraper for {retailer} (PID: {pid})")

                self._processes[retailer] = {
                    "pid": pid,
                    "process": None,
                    "start_time": active_run.get('started_at'),
                    "log_file": self._get_log_file(retailer, active_run['run_id']),
                    "run_id": active_run['run_id'],
                    "command": f"Recovered from PID {pid}",
                    "recovered": True
                }
            except (OSError, ProcessLookupError):
                logger.info(f"Stale run metadata for {retailer} (PID {pid} not running)")

                tracker = RunTracker(retailer, run_id=active_run['run_id'])
                tracker.fail("Process not found on recovery (likely crashed)")

    def _cleanup_on_exit(self) -> None:
        """Cleanup handler called on exit"""
        logger.info("ScraperManager shutting down, stopping all scrapers...")
        try:
            self.stop_all(timeout=10)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def _is_process_running_unsafe(self, retailer: str) -> bool:
        """Check if process is running without acquiring lock (internal use only)

        Args:
            retailer: Retailer name

        Returns:
            True if running, False otherwise

        Note:
            This method assumes the caller already holds self._lock
        """
        if retailer not in self._processes:
            return False

        process_info = self._processes[retailer]
        process = process_info.get("process")
        pid = process_info["pid"]

        if process:
            # Check subprocess.Popen object
            return process.poll() is None
        else:
            # Check PID for recovered processes
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False

    def _cleanup_process_unsafe(self, retailer: str) -> None:
        """Clean up exited process without acquiring lock (internal use only)

        Args:
            retailer: Retailer name

        Note:
            This method assumes the caller already holds self._lock
        """
        if retailer not in self._processes:
            return

        process_info = self._processes[retailer]
        process = process_info.get("process")
        pid = process_info["pid"]
        run_id = process_info["run_id"]

        exit_code = None
        if process:
            exit_code = process.returncode

        logger.info(f"Cleaning up exited scraper for {retailer} (PID: {pid}, exit code: {exit_code})")

        # Update run tracker
        tracker = RunTracker(retailer, run_id=run_id)
        if exit_code == 0:
            tracker.complete()
        else:
            tracker.fail(f"Process exited with code {exit_code or 'unknown'}")

        # Remove from tracking
        del self._processes[retailer]

    def _build_command(
        self,
        retailer: str,
        log_file: str,
        resume: bool = False,
        incremental: bool = False,
        limit: Optional[int] = None,
        test: bool = False,
        proxy: Optional[str] = None,
        render_js: bool = False,
        proxy_country: str = "us",
        verbose: bool = False
    ) -> List[str]:
        """Build command to run scraper

        Args:
            retailer: Retailer name
            log_file: Path to log file
            resume: Resume from checkpoint
            incremental: Incremental mode
            limit: Limit number of stores
            test: Test mode (10 stores)
            proxy: Proxy mode (direct, residential, web_scraper_api)
            render_js: Enable JS rendering
            proxy_country: Proxy country code
            verbose: Verbose logging

        Returns:
            Command as list of strings
        """
        cmd = [sys.executable, self._run_py_path, "--retailer", retailer]

        if resume:
            cmd.append("--resume")

        if incremental:
            cmd.append("--incremental")

        if test:
            cmd.append("--test")
        elif limit is not None:
            cmd.extend(["--limit", str(limit)])

        if proxy:
            cmd.extend(["--proxy", proxy])
            if proxy_country:
                cmd.extend(["--proxy-country", proxy_country])
            if render_js:
                cmd.append("--render-js")

        if verbose:
            cmd.append("--verbose")

        cmd.extend(["--log-file", log_file])

        return cmd

    def start(
        self,
        retailer: str,
        resume: bool = False,
        incremental: bool = False,
        limit: Optional[int] = None,
        test: bool = False,
        proxy: Optional[str] = None,
        render_js: bool = False,
        proxy_country: str = "us",
        verbose: bool = False
    ) -> Dict[str, Any]:
        """Start a scraper process

        Args:
            retailer: Retailer name
            resume: Resume from checkpoint
            incremental: Incremental mode
            limit: Limit number of stores
            test: Test mode (10 stores)
            proxy: Proxy mode (direct, residential, web_scraper_api)
            render_js: Enable JS rendering
            proxy_country: Proxy country code
            verbose: Verbose logging

        Returns:
            Process info dict with pid, start_time, log_file

        Raises:
            ValueError: If retailer not found or already running
        """
        with self._lock:
            config = load_retailers_config()
            if retailer not in config:
                raise ValueError(f"Unknown retailer: {retailer}")

            # Check if process is actually still running (not just in tracking dict)
            if retailer in self._processes:
                if self._is_process_running_unsafe(retailer):
                    raise ValueError(f"Scraper for {retailer} is already running")
                else:
                    # Process has exited, clean it up before proceeding
                    logger.info(f"Cleaning up stale process entry for {retailer} before starting")
                    self._cleanup_process_unsafe(retailer)

            if not config[retailer].get('enabled', False):
                raise ValueError(f"Retailer {retailer} is disabled in config")

            run_tracker = RunTracker(retailer)
            run_tracker.update_config({
                "resume": resume,
                "incremental": incremental,
                "limit": limit,
                "test": test,
                "proxy": proxy,
                "render_js": render_js,
                "proxy_country": proxy_country,
            })

            log_file = self._get_log_file(retailer, run_tracker.run_id)

            cmd = self._build_command(
                retailer=retailer,
                log_file=log_file,
                resume=resume,
                incremental=incremental,
                limit=limit,
                test=test,
                proxy=proxy,
                render_js=render_js,
                proxy_country=proxy_country,
                verbose=verbose
            )

            try:
                with open(log_file, 'w') as log_f:
                    process = subprocess.Popen(
                        cmd,
                        stdout=log_f,
                        stderr=subprocess.STDOUT,
                        start_new_session=True
                    )

                run_tracker.update_config({"pid": process.pid})

                process_info = {
                    "pid": process.pid,
                    "process": process,
                    "start_time": datetime.now().isoformat(),
                    "log_file": log_file,
                    "run_id": run_tracker.run_id,
                    "command": " ".join(cmd),
                    "recovered": False
                }

                self._processes[retailer] = process_info

                logger.info(f"Started scraper for {retailer} (PID: {process.pid})")

                return {
                    "retailer": retailer,
                    "pid": process.pid,
                    "start_time": process_info["start_time"],
                    "log_file": log_file,
                    "run_id": run_tracker.run_id,
                    "status": "started"
                }

            except Exception as e:
                logger.error(f"Failed to start scraper for {retailer}: {e}")
                run_tracker.fail(f"Failed to start: {e}")
                raise

    def stop(self, retailer: str, timeout: int = 30) -> Dict[str, Any]:
        """Stop a scraper process gracefully

        Args:
            retailer: Retailer name
            timeout: Seconds to wait for graceful shutdown before force kill

        Returns:
            Process info with exit status

        Raises:
            ValueError: If scraper not running
        """
        with self._lock:
            if retailer not in self._processes:
                raise ValueError(f"No running scraper for {retailer}")

            process_info = self._processes[retailer]
            process = process_info.get("process")
            pid = process_info["pid"]
            run_id = process_info["run_id"]

            logger.info(f"Stopping scraper for {retailer} (PID: {pid})")

            try:
                if process:
                    if platform.system() == 'Windows':
                        process.terminate()
                    else:
                        process.send_signal(signal.SIGTERM)

                    try:
                        exit_code = process.wait(timeout=timeout)
                        logger.info(f"Scraper for {retailer} stopped gracefully (exit code: {exit_code})")
                        status = "stopped"
                    except subprocess.TimeoutExpired:
                        logger.warning(f"Scraper for {retailer} did not stop gracefully, sending SIGKILL")
                        process.kill()
                        exit_code = process.wait()
                        status = "killed"
                else:
                    try:
                        if platform.system() == 'Windows':
                            os.kill(pid, signal.SIGTERM)
                        else:
                            os.kill(pid, signal.SIGTERM)
                        exit_code = 0
                        status = "stopped"
                    except (OSError, ProcessLookupError):
                        exit_code = -1
                        status = "already_stopped"

                # User manually stopped the scraper - mark as canceled, not failed
                tracker = RunTracker(retailer, run_id=run_id)
                tracker.cancel()

                del self._processes[retailer]

                return {
                    "retailer": retailer,
                    "pid": pid,
                    "exit_code": exit_code,
                    "status": status
                }

            except Exception as e:
                logger.error(f"Error stopping scraper for {retailer}: {e}")
                raise

    def restart(
        self,
        retailer: str,
        resume: bool = True,
        timeout: int = 30,
        restart_delay: float = 0.5,
        **kwargs
    ) -> Dict[str, Any]:
        """Restart a scraper (stop then start)

        Args:
            retailer: Retailer name
            resume: Resume from checkpoint (default: True)
            timeout: Seconds to wait for stop
            restart_delay: Seconds to wait between stop and start (default: 0.5)
            **kwargs: Additional arguments for start()

        Returns:
            Process info from start()
        """
        if retailer in self._processes:
            logger.info(f"Restarting scraper for {retailer}")
            self.stop(retailer, timeout=timeout)
            if restart_delay > 0:
                time.sleep(restart_delay)
        else:
            logger.info(f"Starting scraper for {retailer} (not currently running)")

        return self.start(retailer, resume=resume, **kwargs)

    def is_running(self, retailer: str) -> bool:
        """Check if scraper is running

        Args:
            retailer: Retailer name

        Returns:
            True if running, False otherwise
        """
        with self._lock:
            if retailer not in self._processes:
                return False

            process_info = self._processes[retailer]
            process = process_info.get("process")
            pid = process_info["pid"]
            run_id = process_info["run_id"]

            if process:
                if process.poll() is None:
                    return True

                exit_code = process.returncode
                logger.info(f"Scraper for {retailer} has exited (exit code: {exit_code})")

                tracker = RunTracker(retailer, run_id=run_id)
                if exit_code == 0:
                    tracker.complete()
                else:
                    tracker.fail(f"Process exited with code {exit_code}")

                del self._processes[retailer]
                return False
            else:
                try:
                    os.kill(pid, 0)
                    return True
                except (OSError, ProcessLookupError):
                    logger.info(f"Recovered process for {retailer} (PID {pid}) has exited")

                    tracker = RunTracker(retailer, run_id=run_id)
                    tracker.fail("Process exited (recovered process, exit code unknown)")

                    del self._processes[retailer]
                    return False

    def get_status(self, retailer: str) -> Optional[Dict[str, Any]]:
        """Get status of running scraper

        Args:
            retailer: Retailer name

        Returns:
            Process info dict or None if not running
        """
        if not self.is_running(retailer):
            return None

        with self._lock:
            if retailer not in self._processes:
                return None

            process_info = self._processes[retailer]

            return {
                "retailer": retailer,
                "pid": process_info["pid"],
                "start_time": process_info["start_time"],
                "log_file": process_info["log_file"],
                "run_id": process_info["run_id"],
                "status": "running",
                "recovered": process_info.get("recovered", False)
            }

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all running scrapers

        Returns:
            Dictionary mapping retailer to process info
        """
        status = {}

        for retailer in list(self._processes.keys()):
            if self.is_running(retailer):
                status[retailer] = self.get_status(retailer)

        return status

    def stop_all(self, timeout: int = 30) -> Dict[str, Dict[str, Any]]:
        """Stop all running scrapers

        Args:
            timeout: Seconds to wait for each scraper

        Returns:
            Dictionary mapping retailer to stop results
        """
        results = {}

        for retailer in list(self._processes.keys()):
            try:
                results[retailer] = self.stop(retailer, timeout=timeout)
            except Exception as e:
                logger.error(f"Error stopping {retailer}: {e}")
                results[retailer] = {"error": str(e)}

        return results

    def cleanup_exited(self) -> List[str]:
        """Clean up exited processes from tracking

        Updates RunTracker status for exited processes.

        Returns:
            List of retailers that were cleaned up
        """
        cleaned = []

        with self._lock:
            for retailer in list(self._processes.keys()):
                process_info = self._processes[retailer]
                process = process_info.get("process")
                pid = process_info["pid"]
                run_id = process_info["run_id"]

                exited = False
                exit_code = None

                if process:
                    if process.poll() is not None:
                        exited = True
                        exit_code = process.returncode
                else:
                    try:
                        os.kill(pid, 0)
                    except (OSError, ProcessLookupError):
                        exited = True
                        exit_code = -1

                if exited:
                    logger.info(f"Cleaning up exited scraper for {retailer} (exit code: {exit_code})")

                    tracker = RunTracker(retailer, run_id=run_id)
                    if exit_code == 0:
                        tracker.complete()
                    else:
                        tracker.fail(f"Process exited with code {exit_code}")

                    del self._processes[retailer]
                    cleaned.append(retailer)

        return cleaned


_manager_instance = None


def get_scraper_manager() -> ScraperManager:
    """Get global scraper manager instance (singleton)

    Returns:
        ScraperManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ScraperManager()
    return _manager_instance
