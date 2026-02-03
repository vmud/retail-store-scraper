"""Auto-fix implementations for setup issues.

All fixes are idempotent - safe to run multiple times.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List

from src.setup.diagnose import (
    CheckResult,
    FixResult,
    FixStatus,
    ProbeResult,
)


# Project root (assumes we're run from project directory)
PROJECT_ROOT = Path.cwd()


def fix_virtual_env() -> FixResult:
    """Create virtual environment if it doesn't exist.

    Idempotent: safe to run multiple times.
    """
    venv_path = PROJECT_ROOT / 'venv'
    venv_python = venv_path / 'bin' / 'python'
    venv_python_win = venv_path / 'Scripts' / 'python.exe'

    # Already fixed?
    if venv_python.exists() or venv_python_win.exists():
        return FixResult(
            name="Virtual environment",
            status=FixStatus.ALREADY_FIXED,
            message="venv already exists"
        )

    try:
        subprocess.run(
            [sys.executable, '-m', 'venv', str(venv_path)],
            check=True,
            capture_output=True,
            timeout=120
        )
        return FixResult(
            name="Virtual environment",
            status=FixStatus.FIXED,
            message=f"Created virtual environment at {venv_path}"
        )
    except subprocess.CalledProcessError as e:
        return FixResult(
            name="Virtual environment",
            status=FixStatus.ERROR,
            message=f"Failed to create venv: {e.stderr.decode()[:100] if e.stderr else str(e)}"
        )
    except subprocess.TimeoutExpired:
        return FixResult(
            name="Virtual environment",
            status=FixStatus.ERROR,
            message="Timeout creating virtual environment"
        )


def fix_packages() -> FixResult:
    """Install required packages from requirements.txt.

    Idempotent: pip install handles already-installed packages gracefully.
    """
    requirements_path = PROJECT_ROOT / 'requirements.txt'

    if not requirements_path.exists():
        return FixResult(
            name="Install packages",
            status=FixStatus.ERROR,
            message="requirements.txt not found"
        )

    # Use venv python if available, otherwise system python
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
            [python_exe, '-m', 'pip', 'install', '-r', str(requirements_path)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes for package installation
        )

        if result.returncode == 0:
            # Check if anything was actually installed
            if 'Requirement already satisfied' in result.stdout and \
               'Installing collected packages' not in result.stdout:
                return FixResult(
                    name="Install packages",
                    status=FixStatus.ALREADY_FIXED,
                    message="All packages already installed"
                )
            else:
                return FixResult(
                    name="Install packages",
                    status=FixStatus.FIXED,
                    message="Packages installed successfully"
                )
        else:
            return FixResult(
                name="Install packages",
                status=FixStatus.ERROR,
                message=f"pip install failed: {result.stderr[:200]}"
            )
    except subprocess.TimeoutExpired:
        return FixResult(
            name="Install packages",
            status=FixStatus.ERROR,
            message="Timeout installing packages (>10 minutes)"
        )
    except subprocess.SubprocessError as e:
        return FixResult(
            name="Install packages",
            status=FixStatus.ERROR,
            message=f"Failed to run pip: {str(e)[:100]}"
        )


def fix_env_file() -> FixResult:
    """Copy .env.example to .env if it doesn't exist.

    Idempotent: only copies if .env doesn't exist.
    """
    env_path = PROJECT_ROOT / '.env'
    env_example = PROJECT_ROOT / '.env.example'

    # Already fixed?
    if env_path.exists():
        return FixResult(
            name=".env file",
            status=FixStatus.ALREADY_FIXED,
            message=".env already exists"
        )

    if not env_example.exists():
        return FixResult(
            name=".env file",
            status=FixStatus.ERROR,
            message=".env.example not found to copy from"
        )

    try:
        shutil.copy2(env_example, env_path)
        return FixResult(
            name=".env file",
            status=FixStatus.FIXED,
            message="Copied .env.example to .env"
        )
    except (IOError, OSError) as e:
        return FixResult(
            name=".env file",
            status=FixStatus.ERROR,
            message=f"Failed to copy .env.example: {str(e)[:100]}"
        )


def fix_directories() -> FixResult:
    """Create required directories if they don't exist.

    Idempotent: mkdir with exist_ok=True handles existing directories.
    """
    required_dirs = ['data', 'logs', 'runs']
    created = []
    errors = []

    for dir_name in required_dirs:
        dir_path = PROJECT_ROOT / dir_name
        try:
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                created.append(dir_name)
        except (IOError, OSError) as e:
            errors.append(f"{dir_name}: {str(e)[:30]}")

    if errors:
        return FixResult(
            name="Required directories",
            status=FixStatus.ERROR,
            message=f"Failed to create some directories: {', '.join(errors)}"
        )
    elif created:
        return FixResult(
            name="Required directories",
            status=FixStatus.FIXED,
            message=f"Created directories: {', '.join(created)}"
        )
    else:
        return FixResult(
            name="Required directories",
            status=FixStatus.ALREADY_FIXED,
            message="All required directories already exist"
        )


# Mapping from check names to fix functions
FIX_FUNCTIONS: Dict[str, Callable[[], FixResult]] = {
    "Virtual environment": fix_virtual_env,
    "Missing packages": fix_packages,
    "Package version mismatches": fix_packages,
    ".env file": fix_env_file,
    "Required directories": fix_directories,
}


def get_fix_function(check_name: str) -> Callable[[], FixResult]:
    """Get the fix function for a given check name.

    Args:
        check_name: Name of the check to fix

    Returns:
        Fix function or None if no fix available

    Raises:
        KeyError: If no fix function exists for the check
    """
    if check_name not in FIX_FUNCTIONS:
        raise KeyError(f"No fix function for check: {check_name}")
    return FIX_FUNCTIONS[check_name]


def apply_fixes(
    probe_result: ProbeResult,
    confirm: bool = True,
    dry_run: bool = False
) -> List[FixResult]:
    """Apply all auto-fixable fixes.

    Args:
        probe_result: Result from environment probe
        confirm: If True, prompt user for confirmation (ignored in dry_run)
        dry_run: If True, show what would be fixed without actually fixing

    Returns:
        List of FixResult objects
    """
    fixable = probe_result.auto_fixable_issues

    if not fixable:
        return []

    results = []

    for check in fixable:
        if check.name not in FIX_FUNCTIONS:
            results.append(FixResult(
                name=check.name,
                status=FixStatus.SKIPPED,
                message=f"No fix function implemented for: {check.name}"
            ))
            continue

        if dry_run:
            results.append(FixResult(
                name=check.name,
                status=FixStatus.SKIPPED,
                message=f"Would fix: {check.fix_command or check.name}"
            ))
            continue

        try:
            fix_func = FIX_FUNCTIONS[check.name]
            result = fix_func()
            results.append(result)
        except Exception as e:
            results.append(FixResult(
                name=check.name,
                status=FixStatus.ERROR,
                message=f"Unexpected error: {str(e)[:100]}"
            ))

    return results


def apply_single_fix(check_name: str, dry_run: bool = False) -> FixResult:
    """Apply a single fix by check name.

    Args:
        check_name: Name of the check to fix
        dry_run: If True, show what would be fixed without actually fixing

    Returns:
        FixResult object
    """
    if check_name not in FIX_FUNCTIONS:
        return FixResult(
            name=check_name,
            status=FixStatus.SKIPPED,
            message=f"No fix function implemented for: {check_name}"
        )

    if dry_run:
        return FixResult(
            name=check_name,
            status=FixStatus.SKIPPED,
            message=f"Would fix: {check_name}"
        )

    try:
        fix_func = FIX_FUNCTIONS[check_name]
        return fix_func()
    except Exception as e:
        return FixResult(
            name=check_name,
            status=FixStatus.ERROR,
            message=f"Unexpected error: {str(e)[:100]}"
        )
