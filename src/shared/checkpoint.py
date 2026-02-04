"""Checkpoint management for resumable scraping.

This module provides functions to save and load checkpoint data,
allowing scrapers to resume from where they left off if interrupted.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

__all__ = [
    'load_checkpoint',
    'save_checkpoint',
]


def save_checkpoint(data: Any, filepath: str) -> None:
    """Save progress to allow resuming using atomic write (temp file + rename).

    This function uses atomic file operations to prevent corruption if the
    process is interrupted during write. It creates a temporary file, writes
    the data, then atomically renames it to the target path.

    Args:
        data: Data to save (will be JSON serialized)
        filepath: Path where checkpoint should be saved

    Raises:
        IOError: If checkpoint cannot be saved
        OSError: If filesystem operations fail
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file first, then rename atomically
    # This prevents corruption if interrupted during write
    try:
        # Create temp file in same directory to ensure atomic rename works
        temp_fd, temp_path = tempfile.mkstemp(
            suffix='.tmp',
            dir=path.parent,
            prefix=path.name + '.'
        )

        try:
            # Write JSON to temp file using os.fdopen to properly manage the fd
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            # Atomic rename: os.replace is atomic on POSIX and Windows
            # shutil.move is not guaranteed atomic on all filesystems
            os.replace(temp_path, str(path))
            logging.info(f"Checkpoint saved: {filepath}")

        except Exception as e:
            # Close the fd if fdopen failed and it's still open
            try:
                os.close(temp_fd)
            except OSError:
                pass
            # Clean up temp file on error
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass
            raise e

    except (IOError, OSError) as e:
        logging.error(f"Failed to save checkpoint {filepath}: {e}")
        raise


def load_checkpoint(filepath: str) -> Optional[Any]:
    """Load previous progress from checkpoint file.

    Args:
        filepath: Path to checkpoint file

    Returns:
        Loaded checkpoint data, or None if file doesn't exist or is invalid
    """
    path = Path(filepath)
    if not path.exists():
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logging.info(f"Checkpoint loaded: {filepath}")
        return data
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.warning(f"Failed to load checkpoint {filepath}: {e}")
        return None
