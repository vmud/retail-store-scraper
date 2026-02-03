"""Self-healing project setup module.

This module provides automated environment detection, diagnosis, and fixing
for project setup issues.

Example usage:
    from src.setup import run_setup, probe_environment

    # Full setup with auto-fix
    result = run_setup()

    # Probe only (no fixes)
    result = run_setup(probe_only=True)

    # Resume from checkpoint after human intervention
    result = run_setup(resume=True)

    # Verification only
    result = run_setup(verify_only=True)
"""

from src.setup.diagnose import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    FixResult,
    FixStatus,
    ProbeResult,
    SetupCheckpoint,
    SetupResult,
    SetupStatus,
)
from src.setup.fix import (
    apply_fixes,
    apply_single_fix,
    fix_directories,
    fix_env_file,
    fix_packages,
    fix_virtual_env,
)
from src.setup.instructions import (
    generate_instructions,
    generate_single_instruction,
    get_instruction,
)
from src.setup.probe import (
    check_credentials,
    check_directories,
    check_docker,
    check_docker_compose,
    check_docker_running,
    check_env_file,
    check_nodejs,
    check_npm,
    check_packages,
    check_python_executable,
    check_python_version,
    check_retailers_yaml,
    check_virtual_env,
    probe_environment,
)
from src.setup.runner import (
    print_diagnostic_report,
    print_fix_results,
    run_setup,
)
from src.setup.verify import (
    VerificationResult,
    VerificationSummary,
    print_verification_report,
    run_verification,
    verify_cli_status,
    verify_config,
    verify_imports,
    verify_pytest,
)

__all__ = [
    # Data structures
    "CheckCategory",
    "CheckResult",
    "CheckStatus",
    "FixResult",
    "FixStatus",
    "ProbeResult",
    "SetupCheckpoint",
    "SetupResult",
    "SetupStatus",
    "VerificationResult",
    "VerificationSummary",
    # Probe functions
    "probe_environment",
    "check_python_version",
    "check_python_executable",
    "check_virtual_env",
    "check_packages",
    "check_env_file",
    "check_retailers_yaml",
    "check_directories",
    "check_nodejs",
    "check_npm",
    "check_docker",
    "check_docker_running",
    "check_docker_compose",
    "check_credentials",
    # Fix functions
    "fix_virtual_env",
    "fix_packages",
    "fix_env_file",
    "fix_directories",
    "apply_fixes",
    "apply_single_fix",
    # Instructions
    "generate_instructions",
    "generate_single_instruction",
    "get_instruction",
    # Verification
    "verify_imports",
    "verify_config",
    "verify_pytest",
    "verify_cli_status",
    "run_verification",
    "print_verification_report",
    # Runner
    "run_setup",
    "print_diagnostic_report",
    "print_fix_results",
]
