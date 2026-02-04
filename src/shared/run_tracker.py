"""Run metadata tracking for multi-retailer scraper"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .utils import save_checkpoint, load_checkpoint
from src.shared.constants import RUN_HISTORY


class RunTracker:
    """Track metadata for scraping runs"""
    
    def __init__(self, retailer: str, run_id: Optional[str] = None):
        """Initialize run tracker
        
        Args:
            retailer: Retailer name (verizon, att, etc.)
            run_id: Optional run ID, will be auto-generated if not provided
                   If run_id is provided and file exists, will load existing data
        """
        self.retailer = retailer
        self.run_id = run_id or self._generate_run_id()
        self.run_dir = Path(f"data/{retailer}/runs")
        self.run_file = self.run_dir / f"{self.run_id}.json"
        
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        if run_id and self.run_file.exists():
            existing_data = load_checkpoint(str(self.run_file))
            if existing_data:
                self.metadata = existing_data
            else:
                self.metadata = self._create_fresh_metadata()
                self._save()
        else:
            self.metadata = self._create_fresh_metadata()
            self._save()
    
    def _create_fresh_metadata(self) -> Dict[str, Any]:
        """Create fresh metadata dictionary for new run
        
        Returns:
            Fresh metadata dict
        """
        return {
            "run_id": self.run_id,
            "retailer": self.retailer,
            "status": "running",
            "started_at": datetime.utcnow().isoformat() + "Z",
            "completed_at": None,
            "config": {},
            "stats": {
                "stores_scraped": 0,
                "requests_made": 0,
                "errors": 0,
                "duration_seconds": 0
            },
            "phases": {},
            "errors": []
        }
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID based on timestamp"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{self.retailer}_{timestamp}"
    
    def _save(self) -> None:
        """Save metadata to disk using checkpoint utility"""
        save_checkpoint(self.metadata, str(self.run_file))
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update run configuration
        
        Args:
            config: Configuration dict (resume, incremental, limit, proxy_mode, etc.)
        """
        self.metadata["config"].update(config)
        self._save()
    
    def update_status(self, status: str) -> None:
        """Update run status

        Args:
            status: One of: running, paused, complete, failed, canceled
        """
        self.metadata["status"] = status
        if status in ["complete", "failed", "canceled"]:
            self.metadata["completed_at"] = datetime.utcnow().isoformat() + "Z"
        self._save()
    
    def update_stats(self, **stats) -> None:
        """Update statistics
        
        Args:
            **stats: Keyword arguments for stats (stores_scraped, requests_made, errors, etc.)
        """
        self.metadata["stats"].update(stats)
        self._save()
    
    def increment_stat(self, stat_name: str, amount: int = 1) -> None:
        """Increment a statistic counter
        
        Args:
            stat_name: Name of the stat (stores_scraped, requests_made, errors)
            amount: Amount to increment by (default: 1)
        """
        if stat_name in self.metadata["stats"]:
            self.metadata["stats"][stat_name] += amount
        else:
            self.metadata["stats"][stat_name] = amount
        self._save()
    
    def update_phases(self, phases: Dict[str, Any]) -> None:
        """Update phase information
        
        Args:
            phases: Dictionary of phase data (from status module)
        """
        self.metadata["phases"] = phases
        self._save()
    
    def add_error(self, error_msg: str, url: Optional[str] = None, **extra) -> None:
        """Add error to error log
        
        Args:
            error_msg: Error message
            url: Optional URL where error occurred
            **extra: Additional error context
        """
        error_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": error_msg,
        }
        if url:
            error_entry["url"] = url
        error_entry.update(extra)
        
        self.metadata["errors"].append(error_entry)
        self.increment_stat("errors")
    
    def calculate_duration(self) -> int:
        """Calculate run duration in seconds
        
        Returns:
            Duration in seconds
        """
        try:
            start_dt = datetime.fromisoformat(self.metadata["started_at"].replace("Z", ""))
            
            if self.metadata["completed_at"]:
                end_dt = datetime.fromisoformat(self.metadata["completed_at"].replace("Z", ""))
            else:
                end_dt = datetime.utcnow()
            
            duration = int((end_dt - start_dt).total_seconds())
            self.metadata["stats"]["duration_seconds"] = duration
            self._save()
            return duration
        except Exception:
            return 0
    
    def complete(self) -> None:
        """Mark run as complete"""
        self.calculate_duration()
        self.update_status("complete")
    
    def fail(self, error_msg: Optional[str] = None) -> None:
        """Mark run as failed

        Args:
            error_msg: Optional error message
        """
        if error_msg:
            self.add_error(error_msg)
        self.calculate_duration()
        self.update_status("failed")

    def cancel(self) -> None:
        """Mark run as canceled (user manually stopped)"""
        self.calculate_duration()
        self.update_status("canceled")

    def get_metadata(self) -> Dict[str, Any]:
        """Get current metadata
        
        Returns:
            Metadata dictionary
        """
        self.calculate_duration()
        return self.metadata.copy()


def get_run_history(retailer: str, limit: int = RUN_HISTORY.HISTORY_LIMIT) -> List[Dict[str, Any]]:
    """Get historical runs for a retailer
    
    Args:
        retailer: Retailer name
        limit: Maximum number of runs to return (most recent first)
    
    Returns:
        List of run metadata dictionaries
    """
    run_dir = Path(f"data/{retailer}/runs")
    if not run_dir.exists():
        return []
    
    run_files = sorted(
        run_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )[:limit]
    
    runs = []
    for run_file in run_files:
        try:
            metadata = load_checkpoint(str(run_file))
            if metadata:
                runs.append(metadata)
        except Exception:
            pass
    
    return runs


def get_latest_run(retailer: str) -> Optional[Dict[str, Any]]:
    """Get latest run for a retailer
    
    Args:
        retailer: Retailer name
    
    Returns:
        Run metadata or None if no runs exist
    """
    history = get_run_history(retailer, limit=1)
    return history[0] if history else None


def get_active_run(retailer: str) -> Optional[Dict[str, Any]]:
    """Get currently active run for a retailer (#69)

    Returns the NEWEST running run by file mtime to avoid returning
    stale "running" entries from crashed/abandoned runs.

    Args:
        retailer: Retailer name

    Returns:
        Active run metadata or None
    """
    run_dir = Path(f"data/{retailer}/runs")
    if not run_dir.exists():
        return None

    # Collect all running runs with their mtime
    running_runs = []
    for run_file in run_dir.glob("*.json"):
        try:
            metadata = load_checkpoint(str(run_file))
            if metadata and metadata.get("status") == "running":
                running_runs.append((run_file.stat().st_mtime, metadata))
        except Exception:
            pass

    if not running_runs:
        return None

    # Return newest by mtime (#69)
    running_runs.sort(key=lambda x: x[0], reverse=True)
    return running_runs[0][1]


def cleanup_old_runs(retailer: str, keep: int = RUN_HISTORY.CLEANUP_KEEP) -> int:
    """Clean up old run files, keeping only the most recent
    
    Args:
        retailer: Retailer name
        keep: Number of runs to keep (default: 20)
    
    Returns:
        Number of files deleted
    """
    run_dir = Path(f"data/{retailer}/runs")
    if not run_dir.exists():
        return 0
    
    run_files = sorted(
        run_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    deleted = 0
    for run_file in run_files[keep:]:
        try:
            run_file.unlink()
            deleted += 1
        except Exception:
            pass
    
    return deleted
