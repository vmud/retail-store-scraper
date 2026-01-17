"""Status calculation module for progress tracking"""

import csv
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Checkpoint file paths (matching main.py)
STATES_FILE = "data/checkpoints/states.json"
CITIES_FILE = "data/checkpoints/cities.json"
STORES_FILE = "data/checkpoints/store_urls.json"
OUTPUT_CSV = "data/output/verizon_stores.csv"
OUTPUT_JSON = "data/output/verizon_stores.json"


def get_progress_status() -> Dict[str, Any]:
    """Read all checkpoint files and calculate progress status"""

    status = {
        "phase1": {"total": 0, "completed": 0, "status": "pending", "last_updated": None},
        "phase2": {"total": 0, "completed": 0, "status": "pending", "last_updated": None},
        "phase3": {"total": 0, "completed": 0, "status": "pending", "last_updated": None},
        "phase4": {"total": 0, "completed": 0, "status": "pending", "last_updated": None},
        "overall_progress": 0.0,
        "estimated_time_remaining": None,
        "scraper_active": False,
    }

    # Phase 1: States
    states_path = Path(STATES_FILE)
    if states_path.exists():
        try:
            with open(states_path, 'r') as f:
                states = json.load(f)
            if isinstance(states, list) and len(states) > 0:
                status["phase1"]["total"] = len(states)
                status["phase1"]["completed"] = len(states)
                status["phase1"]["status"] = "complete"
                status["phase1"]["last_updated"] = datetime.fromtimestamp(
                    states_path.stat().st_mtime
                ).isoformat()
        except Exception:
            pass

    # Phase 2: Cities
    cities_path = Path(CITIES_FILE)
    if cities_path.exists():
        try:
            with open(cities_path, 'r') as f:
                cities_data = json.load(f)
            if isinstance(cities_data, dict):
                cities = cities_data.get('cities', [])
                completed_states = cities_data.get('completed_states', [])
                status["phase2"]["total"] = len(completed_states)  # Will be updated when we know total states
                status["phase2"]["completed"] = len(completed_states)
                status["phase2"]["status"] = "in_progress" if completed_states else "pending"
                status["phase2"]["last_updated"] = datetime.fromtimestamp(
                    cities_path.stat().st_mtime
                ).isoformat()

                # If we have states, calculate percentage
                if status["phase1"]["total"] > 0:
                    status["phase2"]["total"] = status["phase1"]["total"]
                    if len(completed_states) >= status["phase1"]["total"]:
                        status["phase2"]["status"] = "complete"
        except Exception:
            pass

    # Phase 3: Store URLs
    stores_path = Path(STORES_FILE)
    if stores_path.exists():
        try:
            with open(stores_path, 'r') as f:
                stores_data = json.load(f)
            if isinstance(stores_data, dict):
                stores = stores_data.get('stores', [])
                completed_cities = stores_data.get('completed_cities', [])
                status["phase3"]["total"] = len(completed_cities)  # Will be updated when we know total cities
                status["phase3"]["completed"] = len(completed_cities)
                status["phase3"]["status"] = "in_progress" if completed_cities else "pending"
                status["phase3"]["last_updated"] = datetime.fromtimestamp(
                    stores_path.stat().st_mtime
                ).isoformat()

                # If we have cities, calculate percentage
                if status["phase2"]["total"] > 0:
                    status["phase3"]["total"] = status["phase2"]["total"]
                    if len(completed_cities) >= status["phase2"]["total"]:
                        status["phase3"]["status"] = "complete"
        except Exception:
            pass

    # Phase 4: Store extraction
    output_path = Path(OUTPUT_CSV)
    if output_path.exists():
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = sum(1 for _ in reader)
            status["phase4"]["completed"] = count
            status["phase4"]["status"] = "in_progress" if count > 0 else "pending"
            status["phase4"]["last_updated"] = datetime.fromtimestamp(
                output_path.stat().st_mtime
            ).isoformat()

            # If we have store URLs, calculate percentage
            if status["phase3"]["total"] > 0:
                status["phase4"]["total"] = status["phase3"]["total"]
                if count >= status["phase3"]["total"]:
                    status["phase4"]["status"] = "complete"
        except Exception:
            pass

    # Calculate overall progress (weighted average)
    phases = [
        status["phase1"],
        status["phase2"],
        status["phase3"],
        status["phase4"]
    ]

    total_weight = 0
    weighted_sum = 0

    for i, phase in enumerate(phases, 1):
        if phase["total"] > 0:
            weight = 1.0 / (2 ** (i - 1))  # Phase 1 = 1.0, Phase 2 = 0.5, Phase 3 = 0.25, Phase 4 = 0.125
            total_weight += weight
            weighted_sum += (phase["completed"] / phase["total"]) * weight

    if total_weight > 0:
        status["overall_progress"] = round((weighted_sum / total_weight) * 100, 1)

    # Check if scraper is active (any checkpoint file updated in last 5 minutes)
    import time
    current_time = time.time()
    active_threshold = 300  # 5 minutes

    checkpoint_files = [states_path, cities_path, stores_path, output_path]
    for checkpoint_file in checkpoint_files:
        if checkpoint_file.exists():
            mtime = checkpoint_file.stat().st_mtime
            if (current_time - mtime) < active_threshold:
                status["scraper_active"] = True
                break

    return status
