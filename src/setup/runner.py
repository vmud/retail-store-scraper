"""Main orchestration for self-healing project setup with checkpoint support."""

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.setup.diagnose import (
    CheckCategory,
    CheckStatus,
    FixResult,
    FixStatus,
    ProbeResult,
    SetupCheckpoint,
    SetupResult,
    SetupStatus,
)
from src.setup.fix import apply_fixes
from src.setup.instructions import generate_instructions
from src.setup.probe import probe_environment
from src.setup.verify import (
    VerificationSummary,
    print_verification_report,
    run_verification,
)


# Checkpoint file location
PROJECT_ROOT = Path.cwd()
CHECKPOINT_PATH = PROJECT_ROOT / 'data' / '.setup_checkpoint.json'


def _save_checkpoint(checkpoint: SetupCheckpoint) -> None:
    """Save checkpoint to disk using atomic write.

    Args:
        checkpoint: SetupCheckpoint to save
    """
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Write atomically via temp file
    temp_path = CHECKPOINT_PATH.with_suffix('.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        temp_path.replace(CHECKPOINT_PATH)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _load_checkpoint() -> Optional[SetupCheckpoint]:
    """Load checkpoint from disk.

    Returns:
        SetupCheckpoint or None if no checkpoint exists
    """
    if not CHECKPOINT_PATH.exists():
        return None

    try:
        with open(CHECKPOINT_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return SetupCheckpoint.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def _clear_checkpoint() -> None:
    """Remove checkpoint file."""
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()


def print_diagnostic_report(probe_result: ProbeResult) -> None:
    """Print formatted diagnostic report.

    Args:
        probe_result: Result from environment probe
    """
    print("\n" + "=" * 50)
    print("PROJECT SETUP - Diagnostic Report")
    print("=" * 50 + "\n")

    # Group checks by category
    categories = [
        (CheckCategory.CRITICAL, "Critical"),
        (CheckCategory.CORE, "Core"),
        (CheckCategory.CONFIG, "Configuration"),
        (CheckCategory.OPTIONAL_NODE, "Optional - Node.js"),
        (CheckCategory.OPTIONAL_DOCKER, "Optional - Docker"),
        (CheckCategory.CREDENTIALS, "Credentials"),
    ]

    for category, label in categories:
        checks = [c for c in probe_result.checks if c.category == category]
        if not checks:
            continue

        print(f"\n### {label}")
        for check in checks:
            status_map = {
                CheckStatus.PASS: "[PASS]",
                CheckStatus.FAIL: "[FAIL]",
                CheckStatus.WARNING: "[WARN]",
                CheckStatus.SKIPPED: "[SKIP]",
            }
            status_str = status_map.get(check.status, "[????]")

            # Add auto-fixable indicator
            suffix = ""
            if check.status == CheckStatus.FAIL and check.auto_fixable:
                suffix = " (auto-fixable)"

            print(f"  {status_str} {check.name}: {check.details}{suffix}")

    # Summary
    print("\n" + "-" * 50)
    print("Summary:")
    print(f"  - Passed: {len(probe_result.passed_checks)}")
    print(f"  - Failed: {len(probe_result.failed_checks)}")
    print(f"  - Warnings: {len(probe_result.warning_checks)}")
    print(f"  - Skipped: {len(probe_result.skipped_checks)}")

    auto_fixable = probe_result.auto_fixable_issues
    human_required = probe_result.human_required_issues

    if auto_fixable:
        print(f"  - Auto-fixable issues: {len(auto_fixable)}")
    if human_required:
        print(f"  - Issues requiring human action: {len(human_required)}")

    print("-" * 50)


def print_fix_results(fix_results: list) -> None:
    """Print formatted fix results.

    Args:
        fix_results: List of FixResult objects
    """
    if not fix_results:
        return

    print("\n" + "=" * 50)
    print("FIX RESULTS")
    print("=" * 50 + "\n")

    for result in fix_results:
        status_map = {
            FixStatus.FIXED: "[FIXED]",
            FixStatus.ALREADY_FIXED: "[OK]",
            FixStatus.ERROR: "[ERROR]",
            FixStatus.SKIPPED: "[SKIP]",
        }
        status_str = status_map.get(result.status, "[????]")
        print(f"  {status_str} {result.name}: {result.message}")


def run_setup(
    probe_only: bool = False,
    resume: bool = True,
    verify_only: bool = False,
    dry_run: bool = False,
    auto_fix: bool = True,
    skip_tests: bool = False,
) -> SetupResult:
    """Run the self-healing project setup.

    Args:
        probe_only: If True, only probe environment without fixing
        resume: If True, attempt to resume from checkpoint
        verify_only: If True, only run verification tests
        dry_run: If True, show what would be fixed without applying
        auto_fix: If True, automatically apply fixes (otherwise prompt)
        skip_tests: If True, skip pytest tests during verification

    Returns:
        SetupResult with final status and details
    """
    # Generate a run ID for this setup attempt
    run_id = str(uuid.uuid4())[:8]

    # Verify-only mode
    if verify_only:
        print("\nRunning verification only...\n")
        summary = run_verification(skip_tests=skip_tests)
        print_verification_report(summary)

        return SetupResult(
            status=SetupStatus.COMPLETE if summary.all_passed else SetupStatus.FAILED,
            verification_passed=summary.all_passed,
            verification_details=summary.to_dict(),
            message="Verification complete"
        )

    # Check for existing checkpoint
    checkpoint = None
    if resume:
        checkpoint = _load_checkpoint()
        if checkpoint:
            print(f"\nResuming from checkpoint (run: {checkpoint.run_id}, phase: {checkpoint.current_phase})")

            # If we were paused waiting for human action, re-probe to check if issues resolved
            if checkpoint.current_phase == 'paused':
                print("Re-probing environment after human intervention...")
                checkpoint = None  # Clear to trigger fresh probe
            else:
                run_id = checkpoint.run_id

    # Phase 1: Probe environment
    checkpoint = checkpoint or SetupCheckpoint(run_id=run_id, current_phase='probe')
    _save_checkpoint(checkpoint)

    print(f"\n[Phase 1/4] Probing environment...")
    probe_result = probe_environment()

    # Print diagnostic report
    print_diagnostic_report(probe_result)

    # Probe-only mode
    if probe_only:
        _clear_checkpoint()
        return SetupResult(
            status=SetupStatus.COMPLETE,
            probe_result=probe_result,
            message="Probe complete"
        )

    # Check for critical failures
    if probe_result.has_critical_failures:
        critical_failures = [
            c for c in probe_result.failed_checks
            if c.category == CheckCategory.CRITICAL
        ]

        print("\n⚠ CRITICAL ISSUES DETECTED")
        print("The following critical issues must be resolved before setup can continue:\n")

        # Generate and print instructions
        instructions = generate_instructions(probe_result)
        if instructions:
            print(instructions)

        # Save checkpoint for resume
        checkpoint.current_phase = 'paused'
        checkpoint.pending_human_actions = [c.name for c in critical_failures]
        _save_checkpoint(checkpoint)

        return SetupResult(
            status=SetupStatus.PAUSED,
            probe_result=probe_result,
            pending_human_actions=checkpoint.pending_human_actions,
            message="Setup paused - critical issues require human intervention"
        )

    # Phase 2: Apply auto-fixes
    fix_results = []
    auto_fixable = probe_result.auto_fixable_issues

    if auto_fixable and not dry_run:
        checkpoint.current_phase = 'fix'
        _save_checkpoint(checkpoint)

        print(f"\n[Phase 2/4] Applying {len(auto_fixable)} auto-fixes...")

        if auto_fix:
            fix_results = apply_fixes(probe_result, confirm=False, dry_run=False)
        else:
            # Interactive mode - ask for confirmation
            print("\nThe following issues can be automatically fixed:")
            for check in auto_fixable:
                print(f"  - {check.name}: {check.fix_command or 'auto-fix available'}")

            response = input("\nApply fixes? [Y/n]: ").strip().lower()
            if response in ('', 'y', 'yes'):
                fix_results = apply_fixes(probe_result, confirm=False, dry_run=False)
            else:
                print("Skipping auto-fixes.")
                fix_results = [
                    FixResult(
                        name=c.name,
                        status=FixStatus.SKIPPED,
                        message="User declined"
                    )
                    for c in auto_fixable
                ]

        print_fix_results(fix_results)

        # Update checkpoint with fix results
        checkpoint.fix_results = [
            {'name': r.name, 'status': r.status.value, 'message': r.message}
            for r in fix_results
        ]
        _save_checkpoint(checkpoint)

    elif auto_fixable and dry_run:
        print(f"\n[Phase 2/4] Dry run - would apply {len(auto_fixable)} fixes:")
        for check in auto_fixable:
            print(f"  - {check.name}: {check.fix_command or 'auto-fix available'}")

    else:
        print("\n[Phase 2/4] No auto-fixes needed.")

    # Phase 3: Check for remaining human-required issues
    # Re-probe after fixes to see current state
    if fix_results:
        print("\nRe-checking environment after fixes...")
        probe_result = probe_environment()

    human_required = probe_result.human_required_issues

    if human_required:
        checkpoint.current_phase = 'paused'
        checkpoint.pending_human_actions = [c.name for c in human_required]
        _save_checkpoint(checkpoint)

        print("\n[Phase 3/4] Human intervention required...")
        instructions = generate_instructions(probe_result)
        if instructions:
            print(instructions)

        return SetupResult(
            status=SetupStatus.PAUSED,
            probe_result=probe_result,
            fix_results=fix_results,
            pending_human_actions=checkpoint.pending_human_actions,
            message="Setup paused - some issues require human intervention"
        )
    else:
        print("\n[Phase 3/4] No human intervention required.")

    # Phase 4: Verification
    checkpoint.current_phase = 'verify'
    _save_checkpoint(checkpoint)

    print("\n[Phase 4/4] Running verification tests...")
    summary = run_verification(skip_tests=skip_tests)
    print_verification_report(summary)

    # Complete
    checkpoint.current_phase = 'complete'
    _save_checkpoint(checkpoint)

    if summary.all_passed:
        _clear_checkpoint()
        print("\n" + "=" * 50)
        print("✓ SETUP COMPLETE")
        print("=" * 50)
        print("\nYour environment is ready. You can now run:")
        print("  python run.py --status")
        print("  python run.py --retailer verizon --test")

        return SetupResult(
            status=SetupStatus.COMPLETE,
            probe_result=probe_result,
            fix_results=fix_results,
            verification_passed=True,
            verification_details=summary.to_dict(),
            message="Setup complete - all verification tests passed"
        )
    else:
        print("\n" + "=" * 50)
        print("✗ SETUP INCOMPLETE")
        print("=" * 50)
        print("\nSome verification tests failed. Please review and fix issues,")
        print("then run setup again:")
        print("  python scripts/setup.py --resume")

        return SetupResult(
            status=SetupStatus.FAILED,
            probe_result=probe_result,
            fix_results=fix_results,
            verification_passed=False,
            verification_details=summary.to_dict(),
            message="Setup incomplete - verification tests failed"
        )
