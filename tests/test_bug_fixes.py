#!/usr/bin/env python3
"""Test script to verify bug fixes in scraper infrastructure"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import pytest
from src.shared import get_scraper_manager


def test_bug1_stale_process_cleanup():
    """
    Bug 1: Verify that start() properly detects and cleans up stale process entries

    When a scraper process exits (completes or crashes), the entry should be cleaned up
    automatically when attempting to start again, rather than failing with
    "Scraper for {retailer} is already running"
    """
    print("\n" + "=" * 70)
    print("BUG 1: Stale Process Cleanup Test")
    print("=" * 70)

    manager = get_scraper_manager()

    # Step 1: Start a scraper with a very low limit so it finishes quickly
    print("\n[Step 1] Starting AT&T scraper with limit=1 (will finish quickly)...")
    result = manager.start(retailer="att", limit=1, verbose=False)
    pid = result['pid']
    print(f"  ✓ Started: PID={pid}")

    # Step 2: Wait for it to complete
    print("\n[Step 2] Waiting for scraper to complete...")
    max_wait = 30  # 30 seconds max
    for i in range(max_wait):
        time.sleep(1)
        if not manager.is_running("att"):
            print(f"  ✓ Scraper completed after {i+1} seconds")
            break
        if i == max_wait - 1:
            print(f"  ✗ Scraper still running after {max_wait} seconds, stopping...")
            manager.stop("att")
            pytest.fail("Scraper took too long to complete")

    # Step 3: Verify process is not running but might still be in _processes dict
    print("\n[Step 3] Verifying process state...")
    is_running = manager.is_running("att")
    print(f"  ✓ is_running('att') = {is_running} (should be False)")
    assert not is_running, "Process should not be running"

    # Step 4: Try to start again - this should NOT fail with "already running"
    # Bug 1 was causing this to fail. With the fix, stale entries are cleaned up.
    print("\n[Step 4] Attempting to start again (should succeed with bug fix)...")
    try:
        result2 = manager.start(retailer="att", limit=1, verbose=False)
        print(f"  ✓ Successfully started again: PID={result2['pid']}")
        print("  ✓ BUG 1 FIX VERIFIED: Stale process entries are properly cleaned up")

        # Clean up
        time.sleep(2)
        if manager.is_running("att"):
            manager.stop("att")

        return True

    except ValueError as e:
        if "already running" in str(e):
            print(f"  ✗ BUG 1 STILL EXISTS: {e}")
            print("  ✗ Stale process entry was not cleaned up")
            pytest.fail("Bug 1 not fixed: Stale process entries are not cleaned up")
        else:
            raise


if __name__ == '__main__':
    # Run tests directly
    try:
        test_bug1_stale_process_cleanup()
        print("\n✅ All tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
