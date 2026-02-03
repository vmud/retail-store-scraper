"""Verification tests for project setup."""

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# Project root
PROJECT_ROOT = Path.cwd()


@dataclass
class VerificationResult:
    """Result of a single verification test."""
    name: str
    passed: bool
    message: str
    details: Optional[str] = None


@dataclass
class VerificationSummary:
    """Summary of all verification tests."""
    results: List[VerificationResult] = field(default_factory=list)
    all_passed: bool = False
    passed_count: int = 0
    failed_count: int = 0

    def add_result(self, result: VerificationResult) -> None:
        """Add a verification result."""
        self.results.append(result)
        if result.passed:
            self.passed_count += 1
        else:
            self.failed_count += 1
        self.all_passed = self.failed_count == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'all_passed': self.all_passed,
            'passed_count': self.passed_count,
            'failed_count': self.failed_count,
            'results': [
                {
                    'name': r.name,
                    'passed': r.passed,
                    'message': r.message,
                    'details': r.details
                }
                for r in self.results
            ]
        }


def verify_imports() -> VerificationResult:
    """Verify that core modules can be imported.

    Tests:
        - src.shared.utils imports correctly
        - Key functions are available
    """
    try:
        from src.shared.utils import setup_logging, load_retailer_config
        from src.shared.proxy_client import ProxyClient, ProxyMode
        from src.scrapers import get_available_retailers

        return VerificationResult(
            name="Core imports",
            passed=True,
            message="All core modules import successfully"
        )
    except ImportError as e:
        return VerificationResult(
            name="Core imports",
            passed=False,
            message=f"Import failed: {str(e)[:100]}",
            details=str(e)
        )
    except Exception as e:
        return VerificationResult(
            name="Core imports",
            passed=False,
            message=f"Unexpected error: {str(e)[:100]}",
            details=str(e)
        )


def verify_config() -> VerificationResult:
    """Verify that retailers.yaml configuration is valid.

    Reuses the existing validate_config_on_startup() function.
    """
    try:
        # Import dynamically to avoid issues if module not ready
        from run import validate_config_on_startup

        errors = validate_config_on_startup()
        if errors:
            return VerificationResult(
                name="Config validation",
                passed=False,
                message=f"Configuration errors: {len(errors)} issues found",
                details="\n".join(errors[:5])
            )
        else:
            return VerificationResult(
                name="Config validation",
                passed=True,
                message="Configuration is valid"
            )
    except ImportError as e:
        return VerificationResult(
            name="Config validation",
            passed=False,
            message=f"Could not import validation function: {str(e)[:50]}"
        )
    except Exception as e:
        return VerificationResult(
            name="Config validation",
            passed=False,
            message=f"Validation error: {str(e)[:100]}",
            details=str(e)
        )


def verify_pytest(test_path: Optional[str] = None) -> VerificationResult:
    """Run pytest on critical test files.

    Args:
        test_path: Optional specific test file or directory

    Tests:
        - Basic test infrastructure works
        - Core functionality tests pass
    """
    # Determine which tests to run
    if test_path:
        test_args = [test_path]
    else:
        # Run a subset of quick, critical tests
        test_files = [
            'tests/test_change_detector.py',
            'tests/test_export_service.py',
        ]
        # Only include files that exist
        test_args = [f for f in test_files if (PROJECT_ROOT / f).exists()]

    if not test_args:
        return VerificationResult(
            name="Pytest",
            passed=True,
            message="No test files found to run (skipped)"
        )

    # Use venv python if available
    venv_python = PROJECT_ROOT / 'venv' / 'bin' / 'python'
    venv_python_win = PROJECT_ROOT / 'venv' / 'Scripts' / 'python.exe'

    if venv_python.exists():
        python_exe = str(venv_python)
    elif venv_python_win.exists():
        python_exe = str(venv_python_win)
    else:
        python_exe = sys.executable

    try:
        result = subprocess.run(
            [python_exe, '-m', 'pytest', '-v', '--tb=short', '-q'] + test_args,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes
            cwd=PROJECT_ROOT
        )

        if result.returncode == 0:
            # Extract summary line from output
            lines = result.stdout.strip().split('\n')
            summary = lines[-1] if lines else "Tests passed"
            return VerificationResult(
                name="Pytest",
                passed=True,
                message=summary
            )
        else:
            # Extract failure info
            stderr_excerpt = result.stderr[:200] if result.stderr else ""
            stdout_excerpt = result.stdout[-500:] if result.stdout else ""
            return VerificationResult(
                name="Pytest",
                passed=False,
                message=f"Tests failed (exit code {result.returncode})",
                details=f"stdout:\n{stdout_excerpt}\nstderr:\n{stderr_excerpt}"
            )
    except subprocess.TimeoutExpired:
        return VerificationResult(
            name="Pytest",
            passed=False,
            message="Tests timed out (>5 minutes)"
        )
    except FileNotFoundError:
        return VerificationResult(
            name="Pytest",
            passed=False,
            message="pytest not found - install with: pip install pytest"
        )
    except Exception as e:
        return VerificationResult(
            name="Pytest",
            passed=False,
            message=f"Error running tests: {str(e)[:100]}"
        )


def verify_cli_status() -> VerificationResult:
    """Verify CLI works by running --status command.

    This is a smoke test that validates:
        - CLI entry point works
        - Configuration loads
        - Basic scraper infrastructure initializes
    """
    # Use venv python if available
    venv_python = PROJECT_ROOT / 'venv' / 'bin' / 'python'
    venv_python_win = PROJECT_ROOT / 'venv' / 'Scripts' / 'python.exe'

    if venv_python.exists():
        python_exe = str(venv_python)
    elif venv_python_win.exists():
        python_exe = str(venv_python_win)
    else:
        python_exe = sys.executable

    run_script = PROJECT_ROOT / 'run.py'
    if not run_script.exists():
        return VerificationResult(
            name="CLI status",
            passed=False,
            message="run.py not found"
        )

    try:
        result = subprocess.run(
            [python_exe, str(run_script), '--status'],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=PROJECT_ROOT
        )

        if result.returncode == 0:
            return VerificationResult(
                name="CLI status",
                passed=True,
                message="CLI --status command works"
            )
        else:
            return VerificationResult(
                name="CLI status",
                passed=False,
                message=f"CLI failed (exit code {result.returncode})",
                details=result.stderr[:300] if result.stderr else result.stdout[:300]
            )
    except subprocess.TimeoutExpired:
        return VerificationResult(
            name="CLI status",
            passed=False,
            message="CLI command timed out"
        )
    except Exception as e:
        return VerificationResult(
            name="CLI status",
            passed=False,
            message=f"Error running CLI: {str(e)[:100]}"
        )


def run_verification(
    skip_tests: bool = False,
    test_path: Optional[str] = None
) -> VerificationSummary:
    """Run all verification tests.

    Args:
        skip_tests: If True, skip pytest tests
        test_path: Optional specific test file to run

    Returns:
        VerificationSummary with all results
    """
    summary = VerificationSummary()

    # Always run import test (fast)
    summary.add_result(verify_imports())

    # Always run config validation (fast)
    summary.add_result(verify_config())

    # Run pytest unless skipped
    if not skip_tests:
        summary.add_result(verify_pytest(test_path))

    # Run CLI smoke test
    summary.add_result(verify_cli_status())

    return summary


def print_verification_report(summary: VerificationSummary) -> None:
    """Print a formatted verification report.

    Args:
        summary: VerificationSummary to print
    """
    print("\n" + "=" * 50)
    print("VERIFICATION RESULTS")
    print("=" * 50 + "\n")

    for result in summary.results:
        status = "[PASS]" if result.passed else "[FAIL]"
        print(f"{status} {result.name}: {result.message}")
        if result.details and not result.passed:
            # Indent details
            for line in result.details.split('\n')[:5]:
                print(f"       {line}")

    print("\n" + "-" * 50)
    print(f"Total: {summary.passed_count} passed, {summary.failed_count} failed")

    if summary.all_passed:
        print("\n✓ All verification tests passed!")
    else:
        print("\n✗ Some verification tests failed. Please review and fix issues.")
