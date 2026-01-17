#!/usr/bin/env python3
"""Test script to verify Bug 1 and Bug 2 fixes"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import subprocess
import pytest
from src.shared import get_scraper_manager, RunTracker


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


def test_bug2_content_type_with_charset():
    """
    Bug 2: Verify that require_json decorator accepts Content-Type with charset
    
    The decorator should accept both:
    - "application/json"
    - "application/json; charset=utf-8"
    
    Previously it only accepted exact match "application/json"
    """
    print("\n" + "=" * 70)
    print("BUG 2: Content-Type with Charset Test")
    print("=" * 70)
    
    from dashboard.app import app
    
    with app.test_client() as client:
        # Test 1: Standard Content-Type (should always work)
        print("\n[Test 1] Testing with 'application/json'...")
        response = client.post(
            '/api/scraper/start',
            json={'retailer': 'invalid_test'},
            content_type='application/json'
        )
        print(f"  Status code: {response.status_code}")
        assert response.status_code != 415, "Should not return 415 for standard application/json"
        print("  ✓ Accepted application/json")
        
        # Test 2: Content-Type with charset (this was failing before)
        print("\n[Test 2] Testing with 'application/json; charset=utf-8'...")
        response = client.post(
            '/api/scraper/start',
            json={'retailer': 'invalid_test'},
            content_type='application/json; charset=utf-8'
        )
        print(f"  Status code: {response.status_code}")
        
        if response.status_code == 415:
            print("  ✗ BUG 2 STILL EXISTS: Rejected Content-Type with charset")
            pytest.fail("Bug 2 not fixed: Content-Type with charset is rejected")
        else:
            print("  ✓ Accepted application/json; charset=utf-8")
            print("  ✓ BUG 2 FIX VERIFIED: Content-Type with charset is properly handled")
        
        # Test 3: Invalid Content-Type (should still be rejected)
        print("\n[Test 3] Testing with 'text/plain' (should be rejected)...")
        response = client.post(
            '/api/scraper/start',
            data='{"retailer": "test"}',
            content_type='text/plain'
        )
        print(f"  Status code: {response.status_code}")
        assert response.status_code == 415, "Should return 415 for non-JSON Content-Type"
        print("  ✓ Correctly rejected text/plain")
        
        return True


def test_both_bugs():
    """Run both bug tests"""
    print("\n" + "=" * 70)
    print("TESTING BOTH BUG FIXES")
    print("=" * 70)
    
    # Test Bug 1
    test_bug1_stale_process_cleanup()
    
    # Test Bug 2
    test_bug2_content_type_with_charset()
    
    print("\n" + "=" * 70)
    print("ALL BUG FIXES VERIFIED")
    print("=" * 70)
    print("\n✓ Bug 1: Stale process cleanup - FIXED")
    print("✓ Bug 2: Content-Type with charset - FIXED")


if __name__ == '__main__':
    # Run tests directly
    try:
        test_both_bugs()
        print("\n✅ All tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
