---
name: project-setup
description: Self-healing project setup with environment probing, auto-fix, and verification. Use when setting up the project for the first time or troubleshooting environment issues.
---

# Project Setup

Self-healing project setup agent that probes the environment, diagnoses issues, auto-fixes what it can, and generates instructions for manual steps.

## Usage

```
/project-setup              # Full setup flow
/project-setup --probe      # Only probe, don't fix
/project-setup --resume     # Resume from checkpoint
/project-setup --verify     # Only run verification
/project-setup --dry-run    # Show fixes without applying
```

## Workflow

### 1. Probe Environment

Run the setup script to probe the environment:

```bash
python scripts/setup.py --probe
```

This checks:
- **Critical**: Python version (3.8-3.11), python3 executable
- **Core**: Virtual environment, installed packages
- **Config**: .env file, retailers.yaml, directories
- **Optional**: Node.js, Docker
- **Credentials**: Oxylabs, GCS

### 2. Review Diagnostic Report

The probe generates a diagnostic report showing:
- [PASS] - Check passed
- [FAIL] - Check failed (may be auto-fixable)
- [WARN] - Warning (optional item)
- [SKIP] - Skipped (optional, not installed)

### 3. Apply Auto-Fixes

If there are auto-fixable issues, run the full setup:

```bash
python scripts/setup.py
```

Auto-fixable items include:
- Virtual environment creation
- Package installation from requirements.txt
- .env file creation (copy from .env.example)
- Directory creation (data/, logs/, runs/)

### 4. Handle Human Actions

If the script pauses for human action, follow the displayed instructions:

```bash
# After completing manual steps, resume:
python scripts/setup.py --resume
```

Common manual actions:
- Installing correct Python version
- Configuring Oxylabs credentials
- Setting up GCS for cloud storage
- Installing Docker (optional)

### 5. Verification

The final phase runs verification tests:
- Core module imports
- Configuration validation
- Selected pytest tests
- CLI smoke test (`python run.py --status`)

## Quick Commands

```bash
# Full setup (recommended for first-time)
python scripts/setup.py

# Just check what's wrong
python scripts/setup.py --probe

# Just run verification
python scripts/setup.py --verify

# Resume after fixing manual items
python scripts/setup.py --resume

# See what would be fixed
python scripts/setup.py --dry-run

# Skip pytest tests (faster)
python scripts/setup.py --skip-tests
```

## Checkpoint System

Setup saves progress to `data/.setup_checkpoint.json`:
- Allows resuming after manual intervention
- Preserves fix results
- Tracks current phase

The checkpoint is automatically cleared on successful completion.

## Programmatic Usage

```python
from src.setup import run_setup, probe_environment

# Full setup
result = run_setup()
print(f"Status: {result.status}")

# Probe only
probe_result = probe_environment()
for check in probe_result.failed_checks:
    print(f"FAIL: {check.name} - {check.details}")
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Python version mismatch | Install Python 3.8-3.11 (see instructions) |
| Package install fails | Check pip, try: `pip install --upgrade pip` |
| Verification fails | Run `pytest tests/ -v` for detailed errors |
| Checkpoint stuck | Delete `data/.setup_checkpoint.json` |
