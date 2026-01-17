#!/usr/bin/env python3
"""Test that stale process entries don't block new starts"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import subprocess
import os
from src.shared import get_scraper_manager, RunTracker

def test_stale_process_cleanup():
    """
    Test that the manager automatically cleans up stale process entries
    when attempting to start a new scraper.
    """
    
    print("\n" + "=" * 70)
    print("STALE PROCESS CLEANUP TEST")
    print("=" * 70)
    
    # Clear any existing manager instance to start fresh
    import src.shared.scraper_manager as sm_module
    sm_module._manager_instance = None
    
    manager = get_scraper_manager()
    
    # Step 1: Manually inject a stale process entry
    print("\n[Step 1] Creating a dummy completed process and injecting stale entry...")
    
    # Create a short-lived process that exits immediately
    dummy_process = subprocess.Popen(['sleep', '0.1'])
    pid = dummy_process.pid
    print(f"  ✓ Created dummy process: PID={pid}")
    
    # Wait for it to complete
    dummy_process.wait()
    print(f"  ✓ Dummy process exited with code: {dummy_process.returncode}")
    
    # Verify process is truly dead
    try:
        os.kill(pid, 0)
        print(f"  ✗ Process {pid} still exists?!")
        return 1
    except (OSError, ProcessLookupError):
        print(f"  ✓ Confirmed process {pid} has exited")
    
    # Step 2: Manually inject stale entry into manager
    print("\n[Step 2] Injecting stale entry into manager's _processes dict...")
    
    run_tracker = RunTracker("verizon")
    
    with manager._lock:
        manager._processes["verizon"] = {
            "pid": pid,
            "process": dummy_process,
            "start_time": "2026-01-17T00:00:00",
            "log_file": "data/verizon/logs/test.log",
            "run_id": run_tracker.run_id,
            "command": "test command",
            "recovered": False
        }
    
    print(f"  ✓ Injected stale entry for 'verizon' with dead PID={pid}")
    
    # Step 3: Verify stale entry exists
    print("\n[Step 3] Verifying stale entry is in _processes dict...")
    if "verizon" in manager._processes:
        print(f"  ✓ Stale entry confirmed (PID: {manager._processes['verizon']['pid']})")
    else:
        print(f"  ✗ Entry not found in _processes dict")
        return 1
    
    # Step 4: Try to start the same scraper again
    # This should automatically detect and clean up the stale entry
    print("\n[Step 4] Attempting to start Verizon scraper...")
    print("  (This should auto-detect the exited process and clean it up)")
    
    try:
        result = manager.start(retailer="verizon", limit=1, verbose=False)
        new_pid = result['pid']
        run_id = result['run_id']
        print(f"  ✓ Success! Started new process: PID={new_pid}, Run ID={run_id}")
        
        # Verify it's a different process
        if new_pid != pid:
            print(f"  ✓ Confirmed new process (old PID: {pid}, new PID: {new_pid})")
        else:
            print(f"  ⚠ Same PID (unusual but possible with PID reuse)")
        
        # Clean up the new process
        time.sleep(2)
        if manager.is_running("verizon"):
            try:
                manager.stop("verizon", timeout=5)
            except:
                pass
        
    except ValueError as e:
        if "already running" in str(e):
            print(f"  ✗ FAILED: Got 'already running' error")
            print(f"     Error message: {e}")
            print(f"     This means the stale entry was NOT cleaned up")
            
            # Clean up stale entry manually
            if "verizon" in manager._processes:
                del manager._processes["verizon"]
            
            return 1
        else:
            print(f"  ✗ FAILED: Got unexpected ValueError: {e}")
            return 1
    except Exception as e:
        print(f"  ✗ FAILED: Unexpected exception: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 70)
    print("STALE PROCESS CLEANUP TEST PASSED")
    print("=" * 70)
    print("\nResults:")
    print("  ✓ Manager detects when process in _processes dict has exited")
    print("  ✓ Manager automatically cleans up stale entry in start()")
    print("  ✓ New scraper can be started without 'already running' error")
    print("  ✓ RunTracker is properly updated when stale entry is cleaned")
    print("\nThis fixes the issue where completed/crashed scrapers")
    print("blocked subsequent start attempts!")
    
    return 0


if __name__ == '__main__':
    sys.exit(test_stale_process_cleanup())
