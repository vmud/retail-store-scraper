"""Status calculation module for multi-retailer progress tracking."""

import csv
import json
import yaml
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from src.shared.constants import STATUS


__all__ = [
    'CONFIG_PATH',
    'get_all_retailers_status',
    'get_checkpoint_path',
    'get_progress_status',
    'get_retailer_status',
    'load_retailers_config',
]



CONFIG_PATH = "config/retailers.yaml"


def load_retailers_config() -> Dict[str, Any]:
    """Load retailers configuration from YAML.

    Returns:
        Dictionary of retailer configurations, empty dict if load fails.
    """
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config.get('retailers', {})
    except Exception:
        return {}


def get_checkpoint_path(retailer: str, checkpoint_type: str) -> Path:
    """Get checkpoint file path for a retailer (#68).

    Uses new naming convention (stores_latest.*) with fallback to legacy names
    for backwards compatibility with existing data.

    Args:
        retailer: Retailer name (verizon, att, etc.)
        checkpoint_type: Type of checkpoint (states, cities, store_urls, sitemap_urls, output_csv, output_json)

    Returns:
        Path to checkpoint file.
    """
    base_path = Path(f"data/{retailer}")

    if checkpoint_type == "output_csv":
        # Try new filename first, fall back to legacy (#68)
        new_path = base_path / "output" / "stores_latest.csv"
        if new_path.exists():
            return new_path
        return base_path / "output" / f"{retailer}_stores.csv"
    if checkpoint_type == "output_json":
        # Try new filename first, fall back to legacy (#68)
        new_path = base_path / "output" / "stores_latest.json"
        if new_path.exists():
            return new_path
        return base_path / "output" / f"{retailer}_stores.json"
    return base_path / "checkpoints" / f"{checkpoint_type}.json"


def get_retailer_status(retailer: str) -> Dict[str, Any]:
    """Get status for a single retailer.

    Args:
        retailer: Retailer name (e.g., 'verizon', 'att', 'target'). See `config/retailers.yaml` for a full list.

    Returns:
        Status dictionary with phases, progress, and metadata.
    """
    config = load_retailers_config()
    retailer_config = config.get(retailer, {})
    
    if not retailer_config:
        return {
            "retailer": retailer,
            "enabled": False,
            "error": "Retailer not found in configuration"
        }
    
    discovery_method = retailer_config.get('discovery_method', 'sitemap')
    enabled = retailer_config.get('enabled', False)
    
    status = {
        "retailer": retailer,
        "name": retailer_config.get('name', retailer.title()),
        "enabled": enabled,
        "discovery_method": discovery_method,
        "phases": {},
        "overall_progress": 0.0,
        "scraper_active": False,
        "last_updated": None,
    }
    
    # Calculate status based on discovery method
    if discovery_method == "html_crawl":
        # Verizon-style 4-phase discovery
        status["phases"] = _get_html_crawl_status(retailer)
    else:
        # Sitemap-based 2-phase discovery (att, target, tmobile, walmart, bestbuy)
        status["phases"] = _get_sitemap_status(retailer)
    
    # Calculate overall progress
    status["overall_progress"] = _calculate_overall_progress(status["phases"])
    
    # Check if scraper is active
    status["scraper_active"] = _check_scraper_active(retailer, status["phases"])
    
    # Get last updated timestamp
    status["last_updated"] = _get_last_updated(retailer, status["phases"])
    
    return status


def _get_html_crawl_status(retailer: str) -> Dict[str, Any]:
    """Get status for HTML crawl method (Verizon 4-phase).

    Phases:
    1. States - Discover all states
    2. Cities - Discover cities per state
    3. Store URLs - Discover store URLs per city
    4. Extract - Extract store details

    Args:
        retailer: Retailer name (e.g., 'verizon')

    Returns:
        Dictionary with status of all four phases.
    """
    phases = {
        "phase1_states": {"name": "States", "total": 0, "completed": 0, "status": "pending", "last_updated": None},
        "phase2_cities": {"name": "Cities", "total": 0, "completed": 0, "status": "pending", "last_updated": None},
        "phase3_urls": {"name": "Store URLs", "total": 0, "completed": 0, "status": "pending", "last_updated": None},
        "phase4_extract": {"name": "Extract Details", "total": 0, "completed": 0, "status": "pending", "last_updated": None},
    }
    
    # Phase 1: States
    states_path = get_checkpoint_path(retailer, "states")
    if states_path.exists():
        try:
            with open(states_path, 'r', encoding='utf-8') as f:
                states = json.load(f)
            if isinstance(states, list) and len(states) > 0:
                phases["phase1_states"]["total"] = len(states)
                phases["phase1_states"]["completed"] = len(states)
                phases["phase1_states"]["status"] = "complete"
                phases["phase1_states"]["last_updated"] = datetime.fromtimestamp(
                    states_path.stat().st_mtime
                ).isoformat()
        except Exception:
            pass
    
    # Phase 2: Cities
    cities_path = get_checkpoint_path(retailer, "cities")
    if cities_path.exists():
        try:
            with open(cities_path, 'r', encoding='utf-8') as f:
                cities_data = json.load(f)
            if isinstance(cities_data, dict):
                completed_states = cities_data.get('completed_states', [])
                phases["phase2_cities"]["completed"] = len(completed_states)
                phases["phase2_cities"]["status"] = "in_progress" if completed_states else "pending"
                phases["phase2_cities"]["last_updated"] = datetime.fromtimestamp(
                    cities_path.stat().st_mtime
                ).isoformat()
                
                if phases["phase1_states"]["total"] > 0:
                    phases["phase2_cities"]["total"] = phases["phase1_states"]["total"]
                    if len(completed_states) >= phases["phase1_states"]["total"]:
                        phases["phase2_cities"]["status"] = "complete"
        except Exception:
            pass
    
    # Phase 3: Store URLs
    stores_path = get_checkpoint_path(retailer, "store_urls")
    if stores_path.exists():
        try:
            with open(stores_path, 'r', encoding='utf-8') as f:
                stores_data = json.load(f)
            if isinstance(stores_data, dict):
                stores = stores_data.get('stores', [])
                completed_cities = stores_data.get('completed_cities', [])
                phases["phase3_urls"]["total"] = len(stores) if stores else 0
                phases["phase3_urls"]["completed"] = len(completed_cities)
                phases["phase3_urls"]["status"] = "in_progress" if completed_cities else "pending"
                phases["phase3_urls"]["last_updated"] = datetime.fromtimestamp(
                    stores_path.stat().st_mtime
                ).isoformat()
                
                if len(stores) > 0 and len(completed_cities) >= len(stores):
                    phases["phase3_urls"]["status"] = "complete"
        except Exception:
            pass
    
    # Phase 4: Store extraction
    output_path = get_checkpoint_path(retailer, "output_csv")
    if output_path.exists():
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = sum(1 for _ in reader)
            phases["phase4_extract"]["completed"] = count
            phases["phase4_extract"]["status"] = "in_progress" if count > 0 else "pending"
            phases["phase4_extract"]["last_updated"] = datetime.fromtimestamp(
                output_path.stat().st_mtime
            ).isoformat()
            
            if phases["phase3_urls"]["total"] > 0:
                phases["phase4_extract"]["total"] = phases["phase3_urls"]["total"]
                if count >= phases["phase3_urls"]["total"]:
                    phases["phase4_extract"]["status"] = "complete"
        except Exception:
            pass
    
    return phases


def _get_sitemap_status(retailer: str) -> Dict[str, Any]:
    """Get status for sitemap-based method (AT&T, Target, T-Mobile, Walmart, Best Buy).

    Phases:
    1. Sitemap URLs - Discover all store URLs from sitemap(s)
    2. Extract - Extract store details from each URL

    Args:
        retailer: Retailer name (e.g., 'target', 'walmart')

    Returns:
        Dictionary with status of both phases.
    """
    phases = {
        "phase1_sitemap": {"name": "Sitemap Discovery", "total": 0, "completed": 0, "status": "pending", "last_updated": None},
        "phase2_extract": {"name": "Extract Details", "total": 0, "completed": 0, "status": "pending", "last_updated": None},
    }
    
    # Phase 1: Sitemap URLs
    sitemap_path = get_checkpoint_path(retailer, "sitemap_urls")
    if sitemap_path.exists():
        try:
            with open(sitemap_path, 'r', encoding='utf-8') as f:
                sitemap_data = json.load(f)
            
            if isinstance(sitemap_data, dict):
                urls = sitemap_data.get('urls', [])
                phases["phase1_sitemap"]["total"] = len(urls)
                phases["phase1_sitemap"]["completed"] = len(urls)
                phases["phase1_sitemap"]["status"] = "complete" if urls else "pending"
                phases["phase1_sitemap"]["last_updated"] = datetime.fromtimestamp(
                    sitemap_path.stat().st_mtime
                ).isoformat()
            elif isinstance(sitemap_data, list):
                phases["phase1_sitemap"]["total"] = len(sitemap_data)
                phases["phase1_sitemap"]["completed"] = len(sitemap_data)
                phases["phase1_sitemap"]["status"] = "complete" if sitemap_data else "pending"
                phases["phase1_sitemap"]["last_updated"] = datetime.fromtimestamp(
                    sitemap_path.stat().st_mtime
                ).isoformat()
        except Exception:
            pass
    
    # Phase 2: Store extraction
    output_path = get_checkpoint_path(retailer, "output_csv")
    if output_path.exists():
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = sum(1 for _ in reader)
            phases["phase2_extract"]["completed"] = count
            phases["phase2_extract"]["status"] = "in_progress" if count > 0 else "pending"
            phases["phase2_extract"]["last_updated"] = datetime.fromtimestamp(
                output_path.stat().st_mtime
            ).isoformat()
            
            if phases["phase1_sitemap"]["total"] > 0:
                phases["phase2_extract"]["total"] = phases["phase1_sitemap"]["total"]
                if count >= phases["phase1_sitemap"]["total"]:
                    phases["phase2_extract"]["status"] = "complete"
        except Exception:
            pass
    
    return phases


def _calculate_overall_progress(phases: Dict[str, Any]) -> float:
    """Calculate overall progress percentage from phases.

    Args:
        phases: Dictionary of phase statuses with total/completed counts

    Returns:
        Overall progress percentage (0.0 to 100.0).
    """
    total_weight = 0
    weighted_sum = 0
    
    for _phase_key, phase_data in phases.items():
        if phase_data["total"] > 0:
            weight = 1.0
            total_weight += weight
            weighted_sum += (phase_data["completed"] / phase_data["total"]) * weight
    
    if total_weight > 0:
        return round((weighted_sum / total_weight) * 100, 1)
    return 0.0


def _check_scraper_active(retailer: str, phases: Dict[str, Any]) -> bool:
    """Check if scraper is currently active (any checkpoint updated in last 5 minutes).

    Args:
        retailer: Retailer name
        phases: Dictionary of phase statuses with last_updated timestamps

    Returns:
        True if scraper is active, False otherwise.
    """
    current_time = time.time()
    active_threshold = STATUS.ACTIVE_THRESHOLD_SECONDS  # 5 minutes
    
    for phase_data in phases.values():
        last_updated = phase_data.get("last_updated")
        if last_updated:
            try:
                last_updated_dt = datetime.fromisoformat(last_updated)
                last_updated_ts = last_updated_dt.timestamp()
                if (current_time - last_updated_ts) < active_threshold:
                    return True
            except Exception:
                pass
    
    return False


def _get_last_updated(retailer: str, phases: Dict[str, Any]) -> Optional[str]:
    """Get most recent update timestamp across all phases.

    Args:
        retailer: Retailer name
        phases: Dictionary of phase statuses with last_updated timestamps

    Returns:
        ISO format timestamp of most recent update, None if no updates found.
    """
    latest = None
    latest_ts = 0
    
    for phase_data in phases.values():
        last_updated = phase_data.get("last_updated")
        if last_updated:
            try:
                last_updated_dt = datetime.fromisoformat(last_updated)
                last_updated_ts = last_updated_dt.timestamp()
                if last_updated_ts > latest_ts:
                    latest_ts = last_updated_ts
                    latest = last_updated
            except Exception:
                pass
    
    return latest


def get_all_retailers_status() -> Dict[str, Any]:
    """Get status for all retailers.

    Returns:
        Dictionary with global stats and per-retailer status.
    """
    config = load_retailers_config()
    retailers = list(config.keys())
    
    global_stats = {
        "total_retailers": len(retailers),
        "active_scrapers": 0,
        "enabled_retailers": 0,
        "total_stores": 0,
        "overall_progress": 0.0,
        "last_updated": None,
    }
    
    retailers_status = {}
    
    for retailer in retailers:
        status = get_retailer_status(retailer)
        retailers_status[retailer] = status
        
        if status["enabled"]:
            global_stats["enabled_retailers"] += 1
        
        if status["scraper_active"]:
            global_stats["active_scrapers"] += 1
        
        # Count stores from final extraction phase
        for phase_key, phase_data in status["phases"].items():
            if "extract" in phase_key.lower():
                global_stats["total_stores"] += phase_data["completed"]
        
        # Track latest update across all retailers
        if status["last_updated"]:
            if not global_stats["last_updated"] or status["last_updated"] > global_stats["last_updated"]:
                global_stats["last_updated"] = status["last_updated"]
    
    # Calculate average progress across enabled retailers
    if global_stats["enabled_retailers"] > 0:
        total_progress = sum(
            status["overall_progress"] 
            for status in retailers_status.values() 
            if status["enabled"]
        )
        global_stats["overall_progress"] = round(
            total_progress / global_stats["enabled_retailers"], 1
        )
    
    return {
        "global": global_stats,
        "retailers": retailers_status
    }


def get_progress_status() -> Dict[str, Any]:
    """Legacy function - get Verizon-only status for backward compatibility.

    Returns:
        Status dictionary for Verizon retailer.
    """
    return get_retailer_status("verizon")
