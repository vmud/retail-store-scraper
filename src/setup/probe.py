"""Environment probing for project setup validation."""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

from src.setup.diagnose import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    ProbeResult,
)


# Required Python version range
MIN_PYTHON_VERSION = (3, 8)
MAX_PYTHON_VERSION = (3, 11)

# Project root (assumes we're run from project directory)
PROJECT_ROOT = Path.cwd()


def probe_environment() -> ProbeResult:
    """Probe the environment and return all check results.

    Returns:
        ProbeResult containing all check results
    """
    result = ProbeResult(platform=platform.system())

    # Critical checks (must pass)
    result.add_check(check_python_version())
    result.add_check(check_python_executable())

    # Core checks (essential for operation)
    result.add_check(check_virtual_env())
    missing_packages, version_mismatches = check_packages()
    if missing_packages:
        result.add_check(missing_packages)
    if version_mismatches:
        result.add_check(version_mismatches)
    # If both are None, packages are OK
    if not missing_packages and not version_mismatches:
        result.add_check(CheckResult(
            name="Required packages",
            category=CheckCategory.CORE,
            status=CheckStatus.PASS,
            details="All required packages installed with correct versions"
        ))

    # Configuration checks
    result.add_check(check_env_file())
    result.add_check(check_retailers_yaml())
    result.add_check(check_directories())

    # Optional - Node.js
    result.add_check(check_nodejs())
    result.add_check(check_npm())

    # Optional - Docker
    result.add_check(check_docker())
    result.add_check(check_docker_running())
    result.add_check(check_docker_compose())

    # Credentials (optional)
    oxylabs_check, gcs_check = check_credentials()
    result.add_check(oxylabs_check)
    result.add_check(gcs_check)

    return result


def check_python_version() -> CheckResult:
    """Check if Python version is within required range."""
    current = sys.version_info[:2]
    version_str = f"{current[0]}.{current[1]}"

    if MIN_PYTHON_VERSION <= current <= MAX_PYTHON_VERSION:
        return CheckResult(
            name="Python version",
            category=CheckCategory.CRITICAL,
            status=CheckStatus.PASS,
            details=f"Python {version_str} (within {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}-{MAX_PYTHON_VERSION[0]}.{MAX_PYTHON_VERSION[1]})"
        )
    else:
        return CheckResult(
            name="Python version",
            category=CheckCategory.CRITICAL,
            status=CheckStatus.FAIL,
            details=f"Python {version_str} not in range {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}-{MAX_PYTHON_VERSION[0]}.{MAX_PYTHON_VERSION[1]}",
            auto_fixable=False,
            human_instructions="install_python"
        )


def check_python_executable() -> CheckResult:
    """Check if python3 executable is available."""
    python_path = shutil.which('python3')
    if python_path:
        return CheckResult(
            name="Python executable",
            category=CheckCategory.CRITICAL,
            status=CheckStatus.PASS,
            details=f"Found at {python_path}"
        )
    else:
        return CheckResult(
            name="Python executable",
            category=CheckCategory.CRITICAL,
            status=CheckStatus.FAIL,
            details="python3 executable not found in PATH",
            auto_fixable=False,
            human_instructions="install_python"
        )


def check_virtual_env() -> CheckResult:
    """Check if virtual environment exists."""
    venv_python = PROJECT_ROOT / 'venv' / 'bin' / 'python'
    venv_python_win = PROJECT_ROOT / 'venv' / 'Scripts' / 'python.exe'

    if venv_python.exists() or venv_python_win.exists():
        return CheckResult(
            name="Virtual environment",
            category=CheckCategory.CORE,
            status=CheckStatus.PASS,
            details="venv/bin/python exists"
        )
    else:
        return CheckResult(
            name="Virtual environment",
            category=CheckCategory.CORE,
            status=CheckStatus.FAIL,
            details="Virtual environment not found at venv/",
            auto_fixable=True,
            fix_command="python3 -m venv venv"
        )


def _parse_requirements(requirements_path: Path) -> Dict[str, Optional[str]]:
    """Parse requirements.txt into package -> version dict.

    Returns:
        Dict mapping package name to version spec (or None if no version specified)
    """
    packages = {}
    if not requirements_path.exists():
        return packages

    with open(requirements_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#') or line.startswith('-'):
                continue

            # Handle various version specifiers
            for sep in ['==', '>=', '<=', '~=', '!=', '>', '<']:
                if sep in line:
                    name, version = line.split(sep, 1)
                    packages[name.strip().lower()] = version.strip()
                    break
            else:
                # No version specifier
                packages[line.lower()] = None

    return packages


def _get_installed_packages() -> Dict[str, str]:
    """Get installed packages via pip freeze.

    Returns:
        Dict mapping package name to installed version
    """
    packages = {}
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'freeze'],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if '==' in line:
                    name, version = line.split('==', 1)
                    packages[name.strip().lower()] = version.strip()
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass

    return packages


def check_packages() -> Tuple[Optional[CheckResult], Optional[CheckResult]]:
    """Check if required packages are installed.

    Returns:
        Tuple of (missing_packages_result, version_mismatch_result)
        Each can be None if no issues found
    """
    requirements_path = PROJECT_ROOT / 'requirements.txt'
    if not requirements_path.exists():
        return (
            CheckResult(
                name="Requirements file",
                category=CheckCategory.CORE,
                status=CheckStatus.FAIL,
                details="requirements.txt not found",
                auto_fixable=False
            ),
            None
        )

    required = _parse_requirements(requirements_path)
    installed = _get_installed_packages()

    missing = []
    mismatched = []

    for package, required_version in required.items():
        if package not in installed:
            missing.append(package)
        elif required_version and installed[package] != required_version:
            mismatched.append(f"{package} (have {installed[package]}, need {required_version})")

    missing_result = None
    mismatch_result = None

    if missing:
        missing_result = CheckResult(
            name="Missing packages",
            category=CheckCategory.CORE,
            status=CheckStatus.FAIL,
            details=f"Missing: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}",
            auto_fixable=True,
            fix_command="pip install -r requirements.txt"
        )

    if mismatched:
        mismatch_result = CheckResult(
            name="Package version mismatches",
            category=CheckCategory.CORE,
            status=CheckStatus.WARNING,
            details=f"Version mismatches: {', '.join(mismatched[:3])}{'...' if len(mismatched) > 3 else ''}",
            auto_fixable=True,
            fix_command="pip install -r requirements.txt"
        )

    return missing_result, mismatch_result


def check_env_file() -> CheckResult:
    """Check if .env file exists."""
    env_path = PROJECT_ROOT / '.env'
    env_example = PROJECT_ROOT / '.env.example'

    if env_path.exists():
        return CheckResult(
            name=".env file",
            category=CheckCategory.CONFIG,
            status=CheckStatus.PASS,
            details=".env file exists"
        )
    elif env_example.exists():
        return CheckResult(
            name=".env file",
            category=CheckCategory.CONFIG,
            status=CheckStatus.FAIL,
            details=".env file missing (can copy from .env.example)",
            auto_fixable=True,
            fix_command="cp .env.example .env"
        )
    else:
        return CheckResult(
            name=".env file",
            category=CheckCategory.CONFIG,
            status=CheckStatus.WARNING,
            details=".env file missing (no .env.example to copy from)",
            auto_fixable=False
        )


def check_retailers_yaml() -> CheckResult:
    """Check if retailers.yaml is valid."""
    config_path = PROJECT_ROOT / 'config' / 'retailers.yaml'

    if not config_path.exists():
        return CheckResult(
            name="retailers.yaml",
            category=CheckCategory.CONFIG,
            status=CheckStatus.FAIL,
            details="config/retailers.yaml not found",
            auto_fixable=False
        )

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if not config:
            return CheckResult(
                name="retailers.yaml",
                category=CheckCategory.CONFIG,
                status=CheckStatus.FAIL,
                details="config/retailers.yaml is empty"
            )

        if 'retailers' not in config:
            return CheckResult(
                name="retailers.yaml",
                category=CheckCategory.CONFIG,
                status=CheckStatus.FAIL,
                details="Missing 'retailers' section in config/retailers.yaml"
            )

        return CheckResult(
            name="retailers.yaml",
            category=CheckCategory.CONFIG,
            status=CheckStatus.PASS,
            details="Valid YAML with retailers section"
        )

    except yaml.YAMLError as e:
        return CheckResult(
            name="retailers.yaml",
            category=CheckCategory.CONFIG,
            status=CheckStatus.FAIL,
            details=f"Invalid YAML syntax: {str(e)[:50]}"
        )


def check_directories() -> CheckResult:
    """Check if required directories exist."""
    required_dirs = ['data', 'logs', 'runs']
    missing = []

    for dir_name in required_dirs:
        dir_path = PROJECT_ROOT / dir_name
        if not dir_path.exists():
            missing.append(dir_name)

    if not missing:
        return CheckResult(
            name="Required directories",
            category=CheckCategory.CONFIG,
            status=CheckStatus.PASS,
            details="data/, logs/, runs/ exist"
        )
    else:
        return CheckResult(
            name="Required directories",
            category=CheckCategory.CONFIG,
            status=CheckStatus.FAIL,
            details=f"Missing directories: {', '.join(missing)}",
            auto_fixable=True,
            fix_command=f"mkdir -p {' '.join(missing)}"
        )


def check_nodejs() -> CheckResult:
    """Check if Node.js is installed (optional)."""
    node_path = shutil.which('node')
    if node_path:
        try:
            result = subprocess.run(
                ['node', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            version = result.stdout.strip()
            return CheckResult(
                name="Node.js",
                category=CheckCategory.OPTIONAL_NODE,
                status=CheckStatus.PASS,
                details=f"Installed: {version}"
            )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return CheckResult(
                name="Node.js",
                category=CheckCategory.OPTIONAL_NODE,
                status=CheckStatus.WARNING,
                details="Found but version check failed"
            )
    else:
        return CheckResult(
            name="Node.js",
            category=CheckCategory.OPTIONAL_NODE,
            status=CheckStatus.SKIPPED,
            details="Not installed (optional)"
        )


def check_npm() -> CheckResult:
    """Check if npm is installed (optional)."""
    npm_path = shutil.which('npm')
    if npm_path:
        try:
            result = subprocess.run(
                ['npm', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            version = result.stdout.strip()
            return CheckResult(
                name="npm",
                category=CheckCategory.OPTIONAL_NODE,
                status=CheckStatus.PASS,
                details=f"Installed: {version}"
            )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return CheckResult(
                name="npm",
                category=CheckCategory.OPTIONAL_NODE,
                status=CheckStatus.WARNING,
                details="Found but version check failed"
            )
    else:
        return CheckResult(
            name="npm",
            category=CheckCategory.OPTIONAL_NODE,
            status=CheckStatus.SKIPPED,
            details="Not installed (optional)"
        )


def check_docker() -> CheckResult:
    """Check if Docker is installed (optional)."""
    docker_path = shutil.which('docker')
    if docker_path:
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            version = result.stdout.strip()
            return CheckResult(
                name="Docker",
                category=CheckCategory.OPTIONAL_DOCKER,
                status=CheckStatus.PASS,
                details=f"Installed: {version}"
            )
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return CheckResult(
                name="Docker",
                category=CheckCategory.OPTIONAL_DOCKER,
                status=CheckStatus.WARNING,
                details="Found but version check failed"
            )
    else:
        return CheckResult(
            name="Docker",
            category=CheckCategory.OPTIONAL_DOCKER,
            status=CheckStatus.SKIPPED,
            details="Not installed (optional)",
            human_instructions="install_docker"
        )


def check_docker_running() -> CheckResult:
    """Check if Docker daemon is running (optional)."""
    docker_path = shutil.which('docker')
    if not docker_path:
        return CheckResult(
            name="Docker daemon",
            category=CheckCategory.OPTIONAL_DOCKER,
            status=CheckStatus.SKIPPED,
            details="Docker not installed"
        )

    try:
        result = subprocess.run(
            ['docker', 'info'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return CheckResult(
                name="Docker daemon",
                category=CheckCategory.OPTIONAL_DOCKER,
                status=CheckStatus.PASS,
                details="Docker daemon is running"
            )
        else:
            return CheckResult(
                name="Docker daemon",
                category=CheckCategory.OPTIONAL_DOCKER,
                status=CheckStatus.WARNING,
                details="Docker installed but daemon not running"
            )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return CheckResult(
            name="Docker daemon",
            category=CheckCategory.OPTIONAL_DOCKER,
            status=CheckStatus.WARNING,
            details="Could not check Docker daemon status"
        )


def check_docker_compose() -> CheckResult:
    """Check if docker-compose.yaml is valid (optional)."""
    compose_path = PROJECT_ROOT / 'docker-compose.yml'
    if not compose_path.exists():
        compose_path = PROJECT_ROOT / 'docker-compose.yaml'

    if not compose_path.exists():
        return CheckResult(
            name="docker-compose",
            category=CheckCategory.OPTIONAL_DOCKER,
            status=CheckStatus.SKIPPED,
            details="No docker-compose.yml found"
        )

    docker_path = shutil.which('docker')
    if not docker_path:
        return CheckResult(
            name="docker-compose",
            category=CheckCategory.OPTIONAL_DOCKER,
            status=CheckStatus.SKIPPED,
            details="Docker not installed"
        )

    try:
        result = subprocess.run(
            ['docker', 'compose', 'config', '-q'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=PROJECT_ROOT
        )
        if result.returncode == 0:
            return CheckResult(
                name="docker-compose",
                category=CheckCategory.OPTIONAL_DOCKER,
                status=CheckStatus.PASS,
                details="docker-compose.yml is valid"
            )
        else:
            return CheckResult(
                name="docker-compose",
                category=CheckCategory.OPTIONAL_DOCKER,
                status=CheckStatus.WARNING,
                details=f"docker-compose.yml validation failed: {result.stderr[:50]}"
            )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        return CheckResult(
            name="docker-compose",
            category=CheckCategory.OPTIONAL_DOCKER,
            status=CheckStatus.WARNING,
            details=f"Could not validate docker-compose.yml: {str(e)[:30]}"
        )


def _parse_env_file() -> Dict[str, str]:
    """Parse .env file into dict.

    Returns:
        Dict of environment variable name to value
    """
    env_vars = {}
    env_path = PROJECT_ROOT / '.env'

    if not env_path.exists():
        return env_vars

    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip().strip('"\'')

    return env_vars


def check_credentials() -> Tuple[CheckResult, CheckResult]:
    """Check for optional credentials in .env.

    Returns:
        Tuple of (oxylabs_check, gcs_check)
    """
    env_vars = _parse_env_file()

    # Check Oxylabs credentials
    oxylabs_keys = [
        'OXYLABS_USERNAME', 'OXYLABS_PASSWORD',
        'OXYLABS_RESIDENTIAL_USERNAME', 'OXYLABS_RESIDENTIAL_PASSWORD'
    ]
    has_oxylabs = any(key in env_vars and env_vars[key] for key in oxylabs_keys)

    if has_oxylabs:
        oxylabs_result = CheckResult(
            name="Oxylabs credentials",
            category=CheckCategory.CREDENTIALS,
            status=CheckStatus.PASS,
            details="Oxylabs credentials configured"
        )
    else:
        oxylabs_result = CheckResult(
            name="Oxylabs credentials",
            category=CheckCategory.CREDENTIALS,
            status=CheckStatus.WARNING,
            details="Oxylabs credentials not configured (optional)",
            human_instructions="setup_oxylabs"
        )

    # Check GCS credentials
    gcs_keys = ['GCS_SERVICE_ACCOUNT_KEY', 'GCS_BUCKET_NAME']
    has_gcs = all(key in env_vars and env_vars[key] for key in gcs_keys)

    if has_gcs:
        # Also check if service account file exists
        sa_path = env_vars.get('GCS_SERVICE_ACCOUNT_KEY', '')
        if sa_path and Path(sa_path).exists():
            gcs_result = CheckResult(
                name="GCS credentials",
                category=CheckCategory.CREDENTIALS,
                status=CheckStatus.PASS,
                details="GCS credentials configured and service account file exists"
            )
        else:
            gcs_result = CheckResult(
                name="GCS credentials",
                category=CheckCategory.CREDENTIALS,
                status=CheckStatus.WARNING,
                details="GCS credentials configured but service account file not found",
                human_instructions="setup_gcs"
            )
    else:
        gcs_result = CheckResult(
            name="GCS credentials",
            category=CheckCategory.CREDENTIALS,
            status=CheckStatus.WARNING,
            details="GCS credentials not configured (optional)",
            human_instructions="setup_gcs"
        )

    return oxylabs_result, gcs_result
