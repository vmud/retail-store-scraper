#!/usr/bin/env python3
"""Test script for scraper manager"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import logging
from src.shared.scraper_manager import get_scraper_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    manager = get_scraper_manager()

    print("\n" + "=" * 60)
    print("SCRAPER MANAGER VERIFICATION")
    print("=" * 60)

    # Test 1: Start a scraper
    print("\n[Test 1] Starting Verizon scraper with test mode (limit 5)...")
    try:
        result = manager.start(
            retailer="verizon",
            test=False,
            limit=5,
            verbose=True
        )
        print(f"✓ Started: PID={result['pid']}, Run ID={result['run_id']}")
        print(f"  Log file: {result['log_file']}")
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1

    # Test 2: Check status
    print("\n[Test 2] Checking scraper status...")
    time.sleep(2)
    status = manager.get_status("verizon")
    if status:
        print(f"✓ Running: PID={status['pid']}, Start time={status['start_time']}")
    else:
        print("✗ Not running")

    # Test 3: Get all status
    print("\n[Test 3] Getting all scrapers status...")
    all_status = manager.get_all_status()
    print(f"✓ Running scrapers: {list(all_status.keys())}")

    # Test 4: Check is_running
    print("\n[Test 4] Checking if Verizon scraper is running...")
    is_running = manager.is_running("verizon")
    print(f"✓ is_running('verizon') = {is_running}")

    # Test 5: Let it run for a bit
    print("\n[Test 5] Letting scraper run for 10 seconds...")
    for i in range(10):
        time.sleep(1)
        if not manager.is_running("verizon"):
            print(f"  Scraper exited after {i+1} seconds")
            break
        print(f"  {i+1}s - Still running...")

    # Test 6: Stop scraper (if still running)
    if manager.is_running("verizon"):
        print("\n[Test 6] Stopping Verizon scraper...")
        try:
            result = manager.stop("verizon", timeout=10)
            print(f"✓ Stopped: Exit code={result['exit_code']}, Status={result['status']}")
        except Exception as e:
            print(f"✗ Error: {e}")
    else:
        print("\n[Test 6] Scraper already exited, skipping stop test")

    # Test 7: Verify stopped
    print("\n[Test 7] Verifying scraper is stopped...")
    is_running = manager.is_running("verizon")
    print(f"✓ is_running('verizon') = {is_running}")

    # Test 8: Restart with resume
    print("\n[Test 8] Testing restart with resume...")
    try:
        result = manager.restart(
            retailer="verizon",
            resume=True,
            limit=5,
            verbose=True
        )
        print(f"✓ Restarted: PID={result['pid']}, Run ID={result['run_id']}")

        time.sleep(3)

        result = manager.stop("verizon", timeout=10)
        print(f"✓ Stopped after restart: Exit code={result['exit_code']}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 9: Test error handling - invalid retailer
    print("\n[Test 9] Testing error handling with invalid retailer...")
    try:
        manager.start(retailer="invalid_retailer")
        print("✗ Should have raised ValueError")
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")

    # Test 10: Test error handling - disabled retailer
    print("\n[Test 10] Testing error handling with disabled retailer...")
    try:
        manager.start(retailer="bestbuy")
        print("✗ Should have raised ValueError for disabled retailer")
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")

    # Test 11: Test error handling - already running
    print("\n[Test 11] Testing error handling with already running scraper...")
    try:
        manager.start(retailer="verizon", limit=5)
        time.sleep(1)
        manager.start(retailer="verizon", limit=5)
        print("✗ Should have raised ValueError for already running")
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
    finally:
        if manager.is_running("verizon"):
            manager.stop("verizon")

    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
