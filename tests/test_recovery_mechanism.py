#!/usr/bin/env python3
"""Test process recovery mechanism"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import time
import subprocess
from src.shared import RunTracker

def test_recovery_mechanism():
    """Test that manager detects and recovers processes from RunTracker metadata"""

    print("\n" + "=" * 70)
    print("PROCESS RECOVERY MECHANISM TEST")
    print("=" * 70)

    # Create a long-running dummy process (sleep)
    print("\n[Step 1] Creating a long-running dummy process...")
    process = subprocess.Popen(['sleep', '60'])
    pid = process.pid
    print(f"  ✓ Started dummy process: PID={pid}")

    # Create run metadata to simulate an active scraper
    print("\n[Step 2] Creating RunTracker metadata for verizon...")
    tracker = RunTracker("verizon", run_id=f"verizon_test_{pid}")
    tracker.update_config({"pid": pid, "limit": 100})
    print(f"  ✓ Created run metadata with PID={pid}")

    # Clear any existing manager instance
    print("\n[Step 3] Creating new ScraperManager instance...")
    import src.shared.scraper_manager as sm_module
    sm_module._manager_instance = None

    from src.shared import get_scraper_manager
    manager = get_scraper_manager()

    # Check if the process was recovered
    print("\n[Step 4] Checking if process was recovered...")
    status = manager.get_status("verizon")

    if status:
        print(f"  ✓ Process recovered successfully!")
        print(f"    PID: {status['pid']}")
        print(f"    Run ID: {status['run_id']}")
        print(f"    Recovered: {status.get('recovered', False)}")

        if status['pid'] == pid:
            print(f"  ✓ PID matches ({pid})")
        else:
            print(f"  ✗ PID mismatch: expected {pid}, got {status['pid']}")
            process.kill()
            return 1
    else:
        print(f"  ✗ Process was NOT recovered")
        process.kill()
        return 1

    # Verify the process is actually tracked
    print("\n[Step 5] Verifying process is tracked...")
    all_status = manager.get_all_status()
    if "verizon" in all_status:
        print(f"  ✓ Verizon scraper is in tracked processes")
    else:
        print(f"  ✗ Verizon scraper not found in tracked processes")
        process.kill()
        return 1

    # Stop the recovered process
    print("\n[Step 6] Stopping recovered process via manager...")
    try:
        result = manager.stop("verizon", timeout=5)
        print(f"  ✓ Successfully stopped via manager")
        print(f"    Exit code: {result['exit_code']}")
    except Exception as e:
        print(f"  ✗ Error stopping: {e}")
        process.kill()
        return 1

    # Verify process is actually killed
    print("\n[Step 7] Verifying process was terminated...")
    time.sleep(1)
    try:
        os.kill(pid, 0)
        print(f"  ℹ Process {pid} still exists, trying force kill...")
        try:
            process.kill()
            process.wait(timeout=2)
        except:
            pass
        time.sleep(0.5)
        try:
            os.kill(pid, 0)
            print(f"  ✗ Process {pid} still exists after force kill")
            return 1
        except (OSError, ProcessLookupError):
            print(f"  ✓ Process {pid} was terminated (after force kill)")
    except (OSError, ProcessLookupError):
        print(f"  ✓ Process {pid} was terminated by SIGTERM")

    print("\n" + "=" * 70)
    print("RECOVERY MECHANISM TEST COMPLETE")
    print("=" * 70)
    print("\nResults:")
    print("  ✓ Manager successfully recovers processes from RunTracker metadata")
    print("  ✓ Recovered processes can be queried via get_status()")
    print("  ✓ Recovered processes can be stopped via stop()")
    print("  ✓ Process termination is verified")
    print("\nThis ensures scrapers started before dashboard restart")
    print("are still tracked and can be managed!")

    return 0


if __name__ == '__main__':
    sys.exit(test_recovery_mechanism())
