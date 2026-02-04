"""Logging configuration and setup.

This module provides thread-safe logging configuration with file rotation
and console output.
"""

import logging
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.shared.constants import LOGGING

__all__ = [
    'setup_logging',
]


# Thread lock for setup_logging to prevent duplicate handlers (#163)
_logging_lock = threading.Lock()


def setup_logging(log_file: str = "logs/scraper.log", max_bytes: int = LOGGING.MAX_BYTES, backup_count: int = LOGGING.BACKUP_COUNT) -> None:
    """Setup logging configuration with rotation (#118).

    This function is idempotent and thread-safe - calling it multiple times
    or from multiple threads will not add duplicate handlers (#143, #163).

    Args:
        log_file: Path to log file
        max_bytes: Maximum file size before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
    """
    # Thread-safe handler setup (#163)
    with _logging_lock:
        root_logger = logging.getLogger()
        log_path = Path(log_file)

        # Idempotency check for file handler: skip if handler exists with matching configuration
        has_file_handler = False
        for handler in root_logger.handlers[:]:  # Copy list to allow modification during iteration
            if isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(log_path.absolute()):
                # Check if configuration matches
                if handler.maxBytes == max_bytes and handler.backupCount == backup_count:
                    has_file_handler = True
                    break
                # Configuration mismatch - remove old handler to reconfigure
                root_logger.removeHandler(handler)
                handler.close()

        # Idempotency check for console handler (#143): skip if one already exists
        # Use FileHandler (not RotatingFileHandler) to exclude ALL file-based handlers
        # since FileHandler is the base class for all file handlers including RotatingFileHandler
        has_console_handler = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in root_logger.handlers
        )

        # Return early if both handlers already exist
        if has_file_handler and has_console_handler:
            return

        # Ensure log directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        root_logger.setLevel(logging.INFO)

        # Add file handler if needed
        if not has_file_handler:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        # Add console handler if needed (#143)
        if not has_console_handler:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
