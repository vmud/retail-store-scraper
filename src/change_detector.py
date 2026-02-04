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
from typing import List, Dict, Optional, Any, Iterator

from src.shared.constants import STREAMING

try:
    import ijson
    IJSON_AVAILABLE = True
except ImportError:
    IJSON_AVAILABLE = False
    logging.debug("ijson not available, will use standard JSON loading")


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

    # Fields used for address-based key disambiguation (stable identity)
    # These define a store's core identity - location + primary contact
    # Phone is included because stores at the same address with different
    # phones are genuinely different stores (e.g., multi-service locations)
    ADDRESS_IDENTITY_FIELDS = ['name', 'street_address', 'city', 'state', 'zip', 'phone']

    # Fields used to detect modifications (excluding address identity)
    # These are attributes that can change without changing store identity
    COMPARISON_FIELDS = [
        'country', 'latitude', 'longitude',
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

    def _get_store_key(self, store: Dict[str, Any], identity_suffix: str = "") -> str:
        """Generate a unique key for a store based on identity fields.

        Args:
            store: Store dictionary
            identity_suffix: Optional identity hash suffix for stable disambiguation

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

        # Fall back to address-based key with identity hash for cross-run stability (#57)
        # Always include identity hash suffix for address-based keys to ensure the same
        # store has the same key across runs, even when comparison fields change
        addr_parts = [
            store.get('name', ''),
            store.get('street_address', ''),
            store.get('city', ''),
            store.get('state', ''),
            store.get('zip', ''),  # Include zip for better uniqueness
        ]
        base_key = f"addr:{'-'.join(p.lower().strip() for p in addr_parts if p)}"

        # Always use identity hash (NOT full fingerprint) for address-based keys
        # This prevents keys from changing when comparison fields (phone, status, etc.) change
        # while still allowing disambiguation of stores at the same address
        if identity_suffix:
            return f"{base_key}::{identity_suffix}"
        # If no identity hash provided, generate it now for stability
        return f"{base_key}::{self.compute_identity_hash(store)[:8]}"

    def _build_store_index(
        self,
        stores: List[Dict[str, Any]]
    ) -> tuple:
        """Build store index and fingerprint maps with collision handling (#148).

        Uses deterministic identity-hash-based keys that remain stable across runs,
        even when comparison fields change. All address-based stores use the consistent
        format 'base_key::col:{hash}' for stability. When multiple stores have the same
        key (multi-tenant or data issues), stores get deterministic suffixes based on a
        hash of ALL fields to prevent data loss and ensure order-independence.

        Returns:
            Tuple of (stores_by_key dict, fingerprints_by_key dict, collision_count)
        """
        # First pass: detect all collisions
        base_key_groups = {}  # Map base_key -> list of (index, store)

        for idx, store in enumerate(stores):
            # Compute identity hash for stable key generation (address-based stores only)
            identity_hash = self.compute_identity_hash(store)
            # Keys use identity hash to remain stable when comparison fields change
            base_key = self._get_store_key(store, identity_hash[:8])

            if base_key not in base_key_groups:
                base_key_groups[base_key] = []
            base_key_groups[base_key].append((idx, store))

        # Second pass: assign keys with deterministic suffixes for collisions
        stores_by_key = {}
        fingerprints_by_key = {}
        collision_count = 0

        for base_key, group_stores in base_key_groups.items():
            # Check if this is an address-based key (needs consistent collision format)
            is_address_based = base_key.startswith('addr:')
            has_collision = len(group_stores) > 1

            if has_collision:
                collision_count += len(group_stores) - 1

            # Track duplicate keys within this group for true duplicates
            seen_keys = {}

            for _, store in group_stores:
                if is_address_based:
                    if has_collision:
                        # Collision: use full_hash for disambiguation
                        full_hash = self._get_deterministic_store_hash(store)
                        key = f"{base_key}::col:{full_hash}"
                    else:
                        # Single address-based store: use identity_hash for stable keys
                        # This ensures keys remain stable when comparison fields change
                        identity_hash = self.compute_identity_hash(store)
                        key = f"{base_key}::col:{identity_hash}"

                    # Handle true duplicates (identical stores) by adding counter suffix
                    # Use counter instead of original index for order-independence
                    if key in stores_by_key:
                        count = seen_keys.get(key, 0) + 1
                        seen_keys[key] = count
                        key = f"{key}::{count}"
                        logging.debug(f"True duplicate detected, using counter suffix: '{key}'")
                elif has_collision:
                    # ID/URL-based stores with collision (edge case): use full_hash
                    full_hash = self._get_deterministic_store_hash(store)
                    key = f"{base_key}::col:{full_hash}"

                    if key in stores_by_key:
                        count = seen_keys.get(key, 0) + 1
                        seen_keys[key] = count
                        key = f"{key}::{count}"
                        logging.debug(f"True duplicate detected, using counter suffix: '{key}'")
                else:
                    # Single ID/URL-based store - use base_key directly (already unique)
                    key = base_key

                fingerprint = self.compute_fingerprint(store)

                stores_by_key[key] = store
                fingerprints_by_key[key] = fingerprint

            if has_collision:
                logging.debug(f"Key collision resolved with deterministic suffixes for base_key: '{base_key}'")

        if collision_count > 0:
            logging.warning(
                f"[{self.retailer}] {collision_count} key collision(s) resolved with suffixes. "
                f"This may indicate duplicate data or stores with identical identity fields."
            )

        return stores_by_key, fingerprints_by_key, collision_count

    def _get_deterministic_store_hash(self, store: Dict[str, Any]) -> str:
        """Generate a deterministic hash unique to this store instance.

        Uses all available fields to ensure two different stores
        always get different hashes, even if identity fields are identical.
        This provides stable disambiguation for true collisions.

        Args:
            store: Store dictionary

        Returns:
            Full SHA256 hash string (64 hex characters)
        """
        # json.dumps with sort_keys=True handles key ordering
        json_str = json.dumps(store, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def compute_identity_hash(self, store: Dict[str, Any]) -> str:
        """Compute a hash of ONLY identity fields for stable key generation.

        This hash is used for address-based key suffixes and remains stable
        when comparison fields (phone, status, etc.) change. This prevents
        false positives in change detection.

        Args:
            store: Store dictionary

        Returns:
            SHA256 hash of identity fields only
        """
        # Only use address identity fields for stable keys
        # Normalize postal code field (some scrapers use 'zip', others 'postal_code')
        data = {}
        for k in self.ADDRESS_IDENTITY_FIELDS:
            if k == 'zip':
                data[k] = store.get('zip') or store.get('postal_code', '')
            elif k in store:
                data[k] = store.get(k, '')

        # Sort keys for consistent hashing
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def compute_fingerprint(self, store: Dict[str, Any]) -> str:
        """Compute a fingerprint hash of a store's key attributes.
        
        This includes both identity and comparison fields, so it changes
        when any important field changes. Used for detecting modifications.
        
        Args:
            store: Store dictionary
            
        Returns:
            SHA256 hash of all relevant fields (identity + comparison)
        """
        # Include basic identity fields, address identity fields, and comparison fields
        # This ensures fingerprint captures ALL important store attributes
        fields_to_hash = self.IDENTITY_FIELDS + self.ADDRESS_IDENTITY_FIELDS + self.COMPARISON_FIELDS
        # Remove duplicates while preserving order
        seen = set()
        unique_fields = []
        for field in fields_to_hash:
            if field not in seen:
                seen.add(field)
                unique_fields.append(field)
        
        # Normalize postal code field (some scrapers use 'zip', others 'postal_code')
        data = {}
        for k in unique_fields:
            if k == 'zip':
                data[k] = store.get('zip') or store.get('postal_code', '')
            elif k in store:
                data[k] = store.get(k, '')

        # Sort keys for consistent hashing
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def rotate_previous(self) -> bool:
        """Rotate stores_latest.json to stores_previous.json BEFORE change detection (#122).

        This ensures change detection compares against Run N-1 (not N-2).
        Must be called before detect_changes() for correct comparison.

        Returns:
            True if rotation occurred, False if no latest file exists
        """
        latest_path = self.output_dir / "stores_latest.json"
        previous_path = self.output_dir / "stores_previous.json"

        if latest_path.exists():
            shutil.copy2(latest_path, previous_path)
            logging.debug(f"[{self.retailer}] Rotated stores_latest.json → stores_previous.json")
            return True
        return False

    def _load_stores_streaming(self, filepath: Path) -> Iterator[Dict[str, Any]]:
        """Load stores incrementally using ijson for memory efficiency (#65).

        Args:
            filepath: Path to JSON file containing array of stores

        Yields:
            Store dictionaries one at a time
        """
        if not IJSON_AVAILABLE:
            # Fallback to standard loading if ijson not available
            with open(filepath, 'r', encoding='utf-8') as f:
                stores = json.load(f)
            yield from stores
            return

        with open(filepath, 'rb') as f:
            yield from ijson.items(f, 'item')

    def load_previous_data(self) -> Optional[List[Dict[str, Any]]]:
        """Load previous run's store data.

        For files larger than 50MB, uses streaming parser if available (#65).
        """
        previous_path = self.output_dir / "stores_previous.json"
        if not previous_path.exists():
            return None

        try:
            file_size = previous_path.stat().st_size
            # Use streaming for large files (>50MB) if ijson is available
            if file_size > STREAMING.LARGE_FILE_THRESHOLD_BYTES and IJSON_AVAILABLE:
                logging.info(f"[{self.retailer}] Loading previous data with streaming parser (file size: {file_size / 1024 / 1024:.1f}MB)")
                return list(self._load_stores_streaming(previous_path))

            # Standard loading for smaller files
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

    def save_latest(self, stores: List[Dict[str, Any]]) -> None:
        """Save stores to stores_latest.json without rotation (#122).

        Use this after calling rotate_previous() + detect_changes() to avoid
        double rotation.

        Args:
            stores: List of store dictionaries to save
        """
        latest_path = self.output_dir / "stores_latest.json"
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(stores, f, indent=2, ensure_ascii=False)
        logging.info(f"[{self.retailer}] Saved {len(stores)} stores to {latest_path}")

    def save_version(self, stores: List[Dict[str, Any]]) -> None:
        """
        Save current data and rotate previous version.

        - stores_latest.json -> stores_previous.json
        - Write new stores_latest.json

        Note: If you called rotate_previous() before detect_changes(),
        use save_latest() instead to avoid double rotation (#122).
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
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        filename = f"changes_{self.retailer}_{timestamp}.json"
        filepath = self.history_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)

        logging.info(f"Saved change report to {filepath}")
        return str(filepath)

    def save_fingerprints(self, stores: List[Dict[str, Any]]) -> None:
        """Save fingerprints for current stores.

        Uses _build_store_index for consistent collision handling (#2 review feedback).
        This ensures fingerprints use the same keys as change detection.
        """
        # Use _build_store_index for consistent collision handling
        _, fingerprints, _ = self._build_store_index(stores)

        with open(self.fingerprints_path, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'count': len(fingerprints),
                'fingerprints': fingerprints
            }, f, indent=2)

        logging.info(f"Saved {len(fingerprints)} fingerprints for {self.retailer}")
