#!/usr/bin/env python3
"""Standalone CLI entry point for self-healing project setup.

This script provides a CLI interface to the setup module, allowing
environment probing, auto-fixing, and verification outside of Claude Code.

Usage:
    python scripts/setup.py              # Full setup flow
    python scripts/setup.py --probe      # Only probe, don't fix
    python scripts/setup.py --resume     # Resume from checkpoint
    python scripts/setup.py --verify     # Only run verification
    python scripts/setup.py --dry-run    # Show fixes without applying
    python scripts/setup.py --skip-tests # Skip pytest during verification
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.setup import run_setup, SetupStatus


def main() -> int:
    """Main entry point for setup CLI.

    Returns:
        Exit code (0 for success, 1 for failure/incomplete)
    """
    parser = argparse.ArgumentParser(
        description='Self-healing project setup for retail-store-scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
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
        """
    )

    parser.add_argument(
        '--probe',
        action='store_true',
        help='Only probe environment without applying fixes'
    )

    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from previous checkpoint (default: True)'
    )

    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Start fresh, ignoring any existing checkpoint'
    )

    parser.add_argument(
        '--verify',
        action='store_true',
        help='Only run verification tests'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be fixed without actually applying fixes'
    )

    parser.add_argument(
        '--no-auto-fix',
        action='store_true',
        help='Prompt for confirmation before applying fixes'
    )

    parser.add_argument(
        '--skip-tests',
        action='store_true',
        help='Skip pytest tests during verification'
    )

    args = parser.parse_args()

    # Determine resume behavior
    resume = not args.no_resume

    try:
        result = run_setup(
            probe_only=args.probe,
            resume=resume,
            verify_only=args.verify,
            dry_run=args.dry_run,
            auto_fix=not args.no_auto_fix,
            skip_tests=args.skip_tests,
        )

        # Return appropriate exit code
        if result.status == SetupStatus.COMPLETE:
            return 0
        elif result.status == SetupStatus.PAUSED:
            # Paused for human action - not an error, but not complete
            return 2
        else:
            return 1

    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user.")
        print("Run 'python scripts/setup.py --resume' to continue later.")
        return 130

    except Exception as e:
        print(f"\n\nUnexpected error during setup: {e}")
        print("Please report this issue if it persists.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
