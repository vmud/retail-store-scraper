"""
Change Detection System for Store Data

Detects new, closed, and modified stores between runs by comparing
fingerprints of store data.
"""

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any


@dataclass
class ChangeReport:
    """Report of changes detected between runs"""
    retailer: str
    timestamp: str
    previous_run: Optional[str]
    current_run: str
    total_previous: int
    total_current: int
    new_stores: List[Dict[str, Any]]
    closed_stores: List[Dict[str, Any]]
    modified_stores: List[Dict[str, Any]]
    unchanged_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def has_changes(self) -> bool:
        return len(self.new_stores) > 0 or len(self.closed_stores) > 0 or len(self.modified_stores) > 0

    def summary(self) -> str:
        return (
            f"Changes for {self.retailer}: "
            f"+{len(self.new_stores)} new, "
            f"-{len(self.closed_stores)} closed, "
            f"~{len(self.modified_stores)} modified, "
            f"={self.unchanged_count} unchanged"
        )


class ChangeDetector:
    """Detects changes in store data between runs"""

    # Fields used to identify a store uniquely
    IDENTITY_FIELDS = ['store_id', 'url', 'name', 'street_address']

    # Fields used to detect modifications (excluding identity and timestamp)
    COMPARISON_FIELDS = [
        'city', 'state', 'zip', 'country',
        'latitude', 'longitude', 'phone',
        'store_type', 'status'
    ]

    def __init__(self, retailer: str, data_dir: str = "data"):
        self.retailer = retailer
        self.data_dir = Path(data_dir) / retailer
        self.output_dir = self.data_dir / "output"
        self.history_dir = self.data_dir / "history"
        self.fingerprints_path = self.data_dir / "fingerprints.json"

        # Ensure directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _get_store_key(self, store: Dict[str, Any], index: int = 0) -> str:
        """Generate a unique key for a store based on identity fields.

        Args:
            store: Store dictionary
            index: Optional index to disambiguate stores with same identity fields

        Returns:
            A unique string key for the store
        """
        # For Best Buy, prioritize URL over store_id (multi-service locations share IDs)
        if self.retailer == 'bestbuy':
            if store.get('url'):
                return f"url:{store['url']}"
            if store.get('store_id'):
                return f"id:{store['store_id']}"
        else:
            # For other retailers, try store_id first
            if store.get('store_id'):
                return f"id:{store['store_id']}"
            if store.get('url'):
                return f"url:{store['url']}"

        # Fall back to address-based key with more fields for uniqueness (#57)
        addr_parts = [
            store.get('name', ''),
            store.get('street_address', ''),
            store.get('city', ''),
            store.get('state', ''),
            store.get('zip', ''),  # Include zip for better uniqueness
        ]
        base_key = f"addr:{'-'.join(p.lower().strip() for p in addr_parts if p)}"

        # If index > 0, this is a collision disambiguation
        if index > 0:
            return f"{base_key}::{index}"
        return base_key

    def _build_store_index(
        self,
        stores: List[Dict[str, Any]]
    ) -> tuple:
        """Build store index and fingerprint maps, handling key collisions (#57).

        Returns:
            Tuple of (stores_by_key dict, fingerprints_by_key dict, collision_count)
        """
        stores_by_key = {}
        fingerprints_by_key = {}
        collision_count = 0
        key_occurrence_count = {}

        for store in stores:
            base_key = self._get_store_key(store)

            # Check for collision
            if base_key in stores_by_key:
                # Increment occurrence count
                key_occurrence_count[base_key] = key_occurrence_count.get(base_key, 1) + 1
                collision_count += 1

                # Generate new unique key with disambiguation index
                unique_key = self._get_store_key(store, key_occurrence_count[base_key])
                logging.debug(f"Key collision detected for '{base_key}', using '{unique_key}'")
            else:
                unique_key = base_key
                key_occurrence_count[base_key] = 1

            stores_by_key[unique_key] = store
            fingerprints_by_key[unique_key] = self.compute_fingerprint(store)

        if collision_count > 0:
            logging.warning(
                f"[{self.retailer}] {collision_count} key collision(s) detected and resolved. "
                f"Consider adding unique identifiers to store data."
            )

        return stores_by_key, fingerprints_by_key, collision_count

    def compute_fingerprint(self, store: Dict[str, Any]) -> str:
        """Compute a fingerprint hash of a store's key attributes"""
        # Include identity and comparison fields
        fields_to_hash = self.IDENTITY_FIELDS + self.COMPARISON_FIELDS
        data = {k: store.get(k, '') for k in fields_to_hash if k in store}

        # Sort keys for consistent hashing
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def load_previous_data(self) -> Optional[List[Dict[str, Any]]]:
        """Load previous run's store data"""
        previous_path = self.output_dir / "stores_previous.json"
        if not previous_path.exists():
            return None

        try:
            with open(previous_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading previous data: {e}")
            return None

    def load_current_data(self) -> Optional[List[Dict[str, Any]]]:
        """Load current run's store data"""
        current_path = self.output_dir / "stores_latest.json"
        if not current_path.exists():
            return None

        try:
            with open(current_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading current data: {e}")
            return None

    def detect_changes(self, current_stores: List[Dict[str, Any]]) -> ChangeReport:
        """
        Detect changes between current stores and previous run.

        Args:
            current_stores: List of store dictionaries from current run

        Returns:
            ChangeReport with lists of new, closed, and modified stores
        """
        previous_stores = self.load_previous_data()
        timestamp = datetime.now().isoformat()

        if previous_stores is None:
            # First run - all stores are "new"
            logging.info(f"No previous data found for {self.retailer} - treating as first run")
            return ChangeReport(
                retailer=self.retailer,
                timestamp=timestamp,
                previous_run=None,
                current_run=timestamp,
                total_previous=0,
                total_current=len(current_stores),
                new_stores=current_stores,
                closed_stores=[],
                modified_stores=[],
                unchanged_count=0
            )

        # Build lookup maps with collision handling (#57)
        previous_by_key, previous_fingerprints, prev_collisions = self._build_store_index(previous_stores)
        current_by_key, current_fingerprints, curr_collisions = self._build_store_index(current_stores)

        # Detect changes
        new_stores = []
        closed_stores = []
        modified_stores = []
        unchanged_count = 0

        # Find new and modified stores
        for key, store in current_by_key.items():
            if key not in previous_by_key:
                new_stores.append(store)
            elif current_fingerprints[key] != previous_fingerprints.get(key):
                modified_stores.append({
                    'current': store,
                    'previous': previous_by_key[key],
                    'changes': self._get_field_changes(previous_by_key[key], store)
                })
            else:
                unchanged_count += 1

        # Find closed stores
        for key, store in previous_by_key.items():
            if key not in current_by_key:
                closed_stores.append(store)

        # Get previous run timestamp
        previous_run = None
        if previous_stores and previous_stores[0].get('scraped_at'):
            previous_run = previous_stores[0]['scraped_at']

        return ChangeReport(
            retailer=self.retailer,
            timestamp=timestamp,
            previous_run=previous_run,
            current_run=timestamp,
            total_previous=len(previous_stores),
            total_current=len(current_stores),
            new_stores=new_stores,
            closed_stores=closed_stores,
            modified_stores=modified_stores,
            unchanged_count=unchanged_count
        )

    def _get_field_changes(
        self,
        previous: Dict[str, Any],
        current: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Get dictionary of field changes between two stores"""
        changes = {}
        for field in self.COMPARISON_FIELDS:
            prev_val = previous.get(field)
            curr_val = current.get(field)
            if prev_val != curr_val:
                changes[field] = {
                    'previous': prev_val,
                    'current': curr_val
                }
        return changes

    def save_version(self, stores: List[Dict[str, Any]]) -> None:
        """
        Save current data and rotate previous version.

        - stores_latest.json -> stores_previous.json
        - Write new stores_latest.json
        """
        latest_path = self.output_dir / "stores_latest.json"
        previous_path = self.output_dir / "stores_previous.json"

        # Rotate: latest -> previous
        if latest_path.exists():
            shutil.copy2(latest_path, previous_path)
            logging.info(f"Rotated previous version for {self.retailer}")

        # Write new latest
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(stores, f, indent=2, ensure_ascii=False)
        logging.info(f"Saved {len(stores)} stores to {latest_path}")

    def save_change_report(self, report: ChangeReport) -> str:
        """Save change report to history directory"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"changes_{timestamp}.json"
        filepath = self.history_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

        logging.info(f"Saved change report to {filepath}")
        return str(filepath)

    def save_fingerprints(self, stores: List[Dict[str, Any]]) -> None:
        """Save fingerprints for current stores"""
        fingerprints = {
            self._get_store_key(s): self.compute_fingerprint(s)
            for s in stores
        }

        with open(self.fingerprints_path, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'count': len(fingerprints),
                'fingerprints': fingerprints
            }, f, indent=2)

        logging.info(f"Saved {len(fingerprints)} fingerprints for {self.retailer}")
