#!/usr/bin/env python3
"""
Unified CLI for Multi-Retailer Store Scraper

Usage:
    python run.py --retailer verizon              # Single retailer
    python run.py --all                            # All retailers concurrently
    python run.py --all --exclude bestbuy          # All except specified
    python run.py --all --resume                   # Resume from checkpoints
    python run.py --status                         # Show all retailer progress
    python run.py --status --retailer verizon      # Single retailer status
"""

import argparse
import asyncio
import concurrent.futures
import functools
import logging
import sys
import os
import json
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import yaml

from src.shared.utils import (
    setup_logging,
    load_retailer_config,
    create_proxied_session,
    close_all_proxy_clients
)
from src.shared import init_proxy_from_yaml, get_proxy_client
from src.shared.constants import WORKERS
from src.shared.export_service import ExportService, ExportFormat, parse_format_list
from src.shared.cloud_storage import get_cloud_storage
from src.scrapers import get_available_retailers, get_enabled_retailers, get_scraper_module
from src.change_detector import ChangeDetector


# Valid US state abbreviations (50 states + DC) for CLI validation (#173)
VALID_STATE_ABBREVS = frozenset({
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL',
    'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME',
    'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH',
    'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI',
    'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
})


def validate_states(states_str: str) -> Optional[List[str]]:
    """Validate and parse comma-separated state abbreviations (#173).

    Args:
        states_str: Comma-separated state abbreviations (e.g., "MD,PA,RI")

    Returns:
        List of uppercase state abbreviations, or None if empty

    Raises:
        argparse.ArgumentTypeError: If any state abbreviation is invalid
    """
    if not states_str:
        return None

    states = [s.strip().upper() for s in states_str.split(',') if s.strip()]

    if not states:
        return None

    invalid = [s for s in states if s not in VALID_STATE_ABBREVS]
    if invalid:
        raise argparse.ArgumentTypeError(
            f"Invalid state abbreviation(s): {', '.join(invalid)}. "
            f"Use standard 2-letter US state codes (e.g., MD, PA, RI, DC)."
        )

    return states


def validate_config_on_startup(config_path: str = "config/retailers.yaml") -> List[str]:
    """Validate configuration file on startup (#67).

    Checks for common configuration errors before running scrapers.

    Args:
        config_path: Path to retailers.yaml config file (default: "config/retailers.yaml")

    Returns:
        List of validation errors (empty if config is valid)
    """
    errors = []

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        return [f"Configuration file not found: {config_path}"]
    except yaml.YAMLError as e:
        return [f"Invalid YAML syntax in config file: {e}"]

    if not config:
        return ["Configuration file is empty"]

    if not isinstance(config, dict):
        return ["Configuration must be a dictionary"]

    # Check for retailers section
    if 'retailers' not in config:
        errors.append("Missing required 'retailers' section")
        return errors

    retailers = config.get('retailers', {})
    if not isinstance(retailers, dict):
        errors.append("'retailers' must be a dictionary")
        return errors

    # Validate each retailer
    for retailer_name, retailer_config in retailers.items():
        prefix = f"Retailer '{retailer_name}'"

        if not isinstance(retailer_config, dict):
            errors.append(f"{prefix}: configuration must be a dictionary")
            continue

        # Check required fields
        if 'enabled' not in retailer_config:
            errors.append(f"{prefix}: missing 'enabled' field")

        if 'base_url' in retailer_config:
            base_url = retailer_config['base_url']
            if not isinstance(base_url, str) or not base_url.startswith(('http://', 'https://')):
                errors.append(f"{prefix}: 'base_url' must be a valid HTTP/HTTPS URL")

        # Validate numeric fields
        for field in ['min_delay', 'max_delay', 'timeout']:
            if field in retailer_config:
                value = retailer_config[field]
                if not isinstance(value, (int, float)) or value < 0:
                    errors.append(f"{prefix}: '{field}' must be a non-negative number")

        # Validate delay order only when both are explicitly set (#3 review feedback)
        # Using defaults causes false positives when only one delay is configured
        # Only compare if both values are numeric to avoid TypeError on invalid configs
        if 'min_delay' in retailer_config and 'max_delay' in retailer_config:
            min_delay = retailer_config['min_delay']
            max_delay = retailer_config['max_delay']
            if isinstance(min_delay, (int, float)) and isinstance(max_delay, (int, float)):
                if min_delay > max_delay:
                    errors.append(f"{prefix}: 'min_delay' ({min_delay}) cannot be greater than 'max_delay' ({max_delay})")

    # Validate proxy section if present
    if 'proxy' in config:
        proxy = config['proxy']
        if not isinstance(proxy, dict):
            errors.append("'proxy' section must be a dictionary")
        else:
            mode = proxy.get('mode', 'direct')
            valid_modes = {'direct', 'residential', 'web_scraper_api'}
            if mode not in valid_modes:
                errors.append(f"Invalid proxy mode '{mode}'. Must be one of: {', '.join(valid_modes)}")

    return errors


def setup_parser() -> argparse.ArgumentParser:
    """Setup command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Multi-Retailer Store Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Retailer selection
    retailer_group = parser.add_mutually_exclusive_group()
    retailer_group.add_argument(
        '--retailer', '-r',
        type=str,
        choices=get_enabled_retailers(),
        help='Run specific retailer scraper'
    )
    retailer_group.add_argument(
        '--all', '-a',
        action='store_true',
        help='Run all retailers concurrently'
    )

    # Exclusions (for --all mode)
    parser.add_argument(
        '--exclude', '-e',
        type=str,
        nargs='+',
        choices=get_enabled_retailers(),
        default=[],
        help='Exclude specific retailers when using --all'
    )

    # Execution options
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from checkpoints'
    )
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Only process new/changed stores (requires previous run)'
    )
    parser.add_argument(
        '--refresh-urls',
        action='store_true',
        help='Force URL re-discovery (ignore cached store URLs, mainly for Verizon)'
    )
    parser.add_argument(
        '--states',
        type=validate_states,
        default=None,
        metavar='STATES',
        help='Comma-separated list of state abbreviations to scrape (Verizon only). '
             'Example: --states MD,PA,RI. Runs targeted discovery for specified states '
             'and merges results with existing data.'
    )

    # Testing options
    parser.add_argument(
        '--test',
        action='store_true',
        help='Quick test mode (10 stores per retailer)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of stores to process per retailer'
    )

    # Status
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show progress without running'
    )

    # Proxy options (Oxylabs integration)
    proxy_group = parser.add_argument_group('proxy options', 'Oxylabs proxy integration')
    proxy_group.add_argument(
        '--proxy',
        type=str,
        choices=['direct', 'residential', 'web_scraper_api'],
        default=None,
        help='Proxy mode: direct (no proxy), residential (Oxylabs IPs), web_scraper_api (managed service)'
    )
    proxy_group.add_argument(
        '--render-js',
        action='store_true',
        help='Enable JavaScript rendering (web_scraper_api mode only)'
    )
    proxy_group.add_argument(
        '--proxy-country',
        type=str,
        default=None,
        help='Proxy country code for geo-targeting (default: us)'
    )
    proxy_group.add_argument(
        '--validate-proxy',
        action='store_true',
        help='Validate proxy credentials before starting (makes a test request)'
    )

    # Export options
    export_group = parser.add_argument_group('export options', 'Output format selection')
    export_group.add_argument(
        '--format', '-f',
        type=str,
        default='json,csv',
        help='Export formats (comma-separated): json,csv,excel,geojson (default: json,csv)'
    )

    # Cloud storage options
    cloud_group = parser.add_argument_group('cloud storage', 'GCS backup/sync options')
    cloud_mutex = cloud_group.add_mutually_exclusive_group()
    cloud_mutex.add_argument(
        '--cloud',
        action='store_true',
        default=None,
        help='Enable cloud storage sync (uploads to GCS after local export)'
    )
    cloud_mutex.add_argument(
        '--no-cloud',
        action='store_true',
        help='Disable cloud storage sync (overrides env/config)'
    )
    cloud_group.add_argument(
        '--gcs-bucket',
        type=str,
        default=None,
        help='Override GCS bucket name'
    )
    cloud_group.add_argument(
        '--gcs-history',
        action='store_true',
        help='Upload timestamped copies to history/ folder'
    )

    # Logging
    parser.add_argument(
        '--log-file',
        type=str,
        default='logs/scraper.log',
        help='Log file path (default: logs/scraper.log)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )

    return parser


def get_retailers_to_run(args) -> List[str]:
    """Determine which retailers to run based on arguments"""
    if args.retailer:
        return [args.retailer]
    if args.all:
        enabled_retailers = get_enabled_retailers()
        return [r for r in enabled_retailers if r not in args.exclude]
    return []


def show_status(retailers: Optional[List[str]] = None) -> None:
    """Show status for specified retailers (or all if None)"""
    if retailers is None:
        retailers = get_available_retailers()

    print("\n" + "=" * 60)
    print("RETAILER SCRAPER STATUS")
    print("=" * 60)

    for retailer in retailers:
        print(f"\n--- {retailer.upper()} ---")
        try:
            # Try to load checkpoint data for status
            checkpoint_dir = f"data/{retailer}/checkpoints"
            output_dir = f"data/{retailer}/output"

            # Check for checkpoint files
            if os.path.exists(checkpoint_dir):
                checkpoints = os.listdir(checkpoint_dir)
                if checkpoints:
                    print(f"  Checkpoints: {', '.join(checkpoints)}")
                else:
                    print("  Checkpoints: None")
            else:
                print("  Checkpoints: Directory not found")

            # Check for output files
            if os.path.exists(output_dir):
                outputs = os.listdir(output_dir)
                if outputs:
                    print(f"  Outputs: {', '.join(outputs)}")

                    # Try to count stores in latest output
                    for out_file in outputs:
                        if out_file.endswith('.json'):
                            filepath = os.path.join(output_dir, out_file)
                            try:
                                with open(filepath, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    if isinstance(data, list):
                                        print(f"    {out_file}: {len(data)} stores")
                            except Exception as e:
                                logging.warning(f"Could not read {out_file}: {e}")
                else:
                    print("  Outputs: None")
            else:
                print("  Outputs: Directory not found")

        except Exception as e:
            print(f"  Error getting status: {e}")

    print("\n" + "=" * 60)


# Thread pool executor for running synchronous scrapers without blocking the event loop
_scraper_executor = concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS.EXECUTOR_MAX_WORKERS, thread_name_prefix='scraper')


def _run_scraper_sync(retailer: str, retailer_config: dict, session, scraper_module, **kwargs) -> dict:
    """Synchronous wrapper that runs the scraper.

    This function is designed to be called via run_in_executor()
    so it doesn't block the async event loop.
    """
    logging.info(f"[{retailer}] Calling scraper run() function")
    return scraper_module.run(session, retailer_config, retailer=retailer, **kwargs)


async def run_retailer_async(
    retailer: str,
    cli_proxy_override: Optional[str] = None,
    cli_proxy_settings: Optional[dict] = None,
    export_formats: Optional[List[ExportFormat]] = None,
    cloud_manager=None,
    **kwargs
) -> dict:
    """Run a single retailer scraper asynchronously

    Uses ThreadPoolExecutor to run synchronous scrapers without
    blocking the event loop, enabling true concurrent execution.

    Args:
        retailer: Retailer name
        cli_proxy_override: Optional CLI proxy mode override from --proxy flag
        cli_proxy_settings: Optional CLI proxy settings (country_code, render_js)
        export_formats: List of formats to export (default: JSON, CSV)
        cloud_manager: Optional CloudStorageManager for uploading to GCS
        **kwargs: Additional arguments (resume, incremental, limit, etc.)
    """
    logging.info(f"[{retailer}] Starting scraper")

    # Default to JSON and CSV if no formats specified
    if export_formats is None:
        export_formats = [ExportFormat.JSON, ExportFormat.CSV]

    session = None
    try:
        # Pass CLI proxy settings through to retailer config (#52)
        retailer_config = load_retailer_config(
            retailer,
            cli_proxy_override,
            cli_proxy_settings
        )

        session = create_proxied_session(retailer_config)

        scraper_module = get_scraper_module(retailer)

        # Run synchronous scraper in thread pool to avoid blocking the event loop
        # This enables true concurrent execution when running multiple retailers
        loop = asyncio.get_running_loop()
        scraper_result = await loop.run_in_executor(
            _scraper_executor,
            functools.partial(
                _run_scraper_sync,
                retailer,
                retailer_config,
                session,
                scraper_module,
                **kwargs
            )
        )

        # Extract data from scraper result
        stores = scraper_result.get('stores', [])
        count = scraper_result.get('count', 0)
        checkpoints_used = scraper_result.get('checkpoints_used', False)

        logging.info(f"[{retailer}] Scraper completed: {count} stores")
        if checkpoints_used:
            logging.info(f"[{retailer}] Resumed from checkpoint")

        # Run change detection if incremental mode is enabled
        incremental = kwargs.get('incremental', False)
        if incremental and stores:
            logging.info(f"[{retailer}] Running change detection (incremental mode)")
            try:
                detector = ChangeDetector(retailer)

                # Fix #122: Rotate stores_latest → stores_previous BEFORE detection
                # This ensures we compare against Run N-1 (not N-2)
                detector.rotate_previous()

                change_report = detector.detect_changes(stores)

                if change_report.has_changes:
                    logging.info(f"[{retailer}] {change_report.summary()}")
                    # Save change report
                    report_path = detector.save_change_report(change_report)
                    logging.info(f"[{retailer}] Change report saved to {report_path}")
                else:
                    logging.info(f"[{retailer}] No changes detected")

                # Save fingerprints for next run comparison
                detector.save_fingerprints(stores)

                # Save new latest (rotation already done, so use save_latest not save_version)
                detector.save_latest(stores)
            except Exception as change_err:
                logging.warning(f"[{retailer}] Change detection failed: {change_err}")

        # Export to all requested formats
        output_dir = f"data/{retailer}/output"
        format_extensions = {
            ExportFormat.JSON: 'json',
            ExportFormat.CSV: 'csv',
            ExportFormat.EXCEL: 'xlsx',
            ExportFormat.GEOJSON: 'geojson'
        }

        successful_formats = []
        successful_extensions = []
        for fmt in export_formats:
            ext = format_extensions.get(fmt, fmt.value)
            output_path = f"{output_dir}/stores_latest.{ext}"
            try:
                ExportService.export_stores(stores, fmt, output_path, retailer_config)
            except Exception as export_err:
                logging.warning(f"[{retailer}] Failed to export {fmt.value}: {export_err}")
                continue

            successful_formats.append(fmt)
            successful_extensions.append(ext)

        # Upload to cloud storage if configured
        cloud_results = {}
        if cloud_manager:
            if successful_extensions:
                try:
                    cloud_results = cloud_manager.upload_retailer_data(
                        retailer=retailer,
                        output_dir=output_dir,
                        formats=successful_extensions
                    )
                    successful = sum(1 for v in cloud_results.values() if v)
                    total = len(cloud_results)
                    if successful == total:
                        logging.info(f"[{retailer}] Cloud upload complete: {successful} files")
                    elif successful > 0:
                        logging.warning(f"[{retailer}] Cloud upload partial: {successful}/{total} files")
                    else:
                        logging.error(f"[{retailer}] Cloud upload failed: 0/{total} files")
                except Exception as cloud_err:
                    logging.warning(f"[{retailer}] Cloud upload failed: {cloud_err}")
            else:
                logging.warning(f"[{retailer}] Cloud upload skipped: no successful exports")

        result = {
            'retailer': retailer,
            'status': 'completed',
            'stores': count,
            'formats': [f.value for f in successful_formats],
            'cloud_uploaded': bool(cloud_results and any(cloud_results.values())),
            'error': None
        }

        logging.info(f"[{retailer}] Completed scraper")
        return result

    except Exception as e:
        logging.error(f"[{retailer}] Error running scraper: {e}", exc_info=True)
        return {
            'retailer': retailer,
            'status': 'error',
            'stores': 0,
            'error': str(e)
        }
    finally:
        # Close session to prevent resource leak (#4 review feedback)
        if session is not None:
            try:
                session.close()
            except Exception as close_err:
                logging.debug(f"[{retailer}] Error closing session: {close_err}")


async def run_all_retailers(
    retailers: List[str],
    cli_proxy_override: Optional[str] = None,
    cli_proxy_settings: Optional[dict] = None,
    export_formats: Optional[List[ExportFormat]] = None,
    cloud_manager=None,
    **kwargs
) -> dict:
    """Run multiple retailers concurrently

    Args:
        retailers: List of retailer names to run
        cli_proxy_override: Optional CLI proxy mode override from --proxy flag
        cli_proxy_settings: Optional CLI proxy settings (country_code, render_js)
        export_formats: List of formats to export
        cloud_manager: Optional CloudStorageManager for uploading to GCS
        **kwargs: Additional arguments (resume, incremental, limit, etc.)
    """
    logging.info(f"Starting concurrent scrape for {len(retailers)} retailers: {retailers}")

    tasks = [
        run_retailer_async(
            retailer,
            cli_proxy_override=cli_proxy_override,
            cli_proxy_settings=cli_proxy_settings,
            export_formats=export_formats,
            cloud_manager=cloud_manager,
            **kwargs
        )
        for retailer in retailers
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    summary = {}
    for retailer, result in zip(retailers, results):
        if isinstance(result, Exception):
            # Log full traceback for debugging (#145)
            logging.error(f"[{retailer}] Scraper failed with exception:", exc_info=result)

            summary[retailer] = {
                'status': 'error',
                'error': str(result)
            }
        else:
            summary[retailer] = result

    return summary


def _get_yaml_proxy_mode(config: dict, retailer: Optional[str] = None) -> Optional[str]:
    """Resolve proxy mode from YAML config for a retailer or global."""
    if not config:
        return None
    global_mode = config.get('proxy', {}).get('mode')
    if retailer:
        retailer_proxy = config.get('retailers', {}).get(retailer, {}).get('proxy')
        if isinstance(retailer_proxy, dict):
            return retailer_proxy.get('mode', global_mode)
    return global_mode


def _get_target_retailers(args) -> List[str]:
    """Return retailers targeted by CLI args."""
    retailer = getattr(args, 'retailer', None)
    if retailer:
        return [retailer]
    if getattr(args, 'all', False):
        excluded = set(getattr(args, 'exclude', []) or [])
        return [name for name in get_enabled_retailers() if name not in excluded]
    return []


def validate_cli_options(args, config: dict = None) -> List[str]:
    """Validate CLI options for conflicts (#106).

    Args:
        args: Parsed command line arguments
        config: Loaded YAML configuration (optional, for proxy mode check)

    Returns:
        List of validation errors (empty if options are valid)
    """
    errors = []

    # Check for conflicting options
    if args.test and args.limit:
        errors.append("Cannot use --test with --limit (--test already sets limit to 10)")

    # --render-js requires web_scraper_api proxy mode (CLI or YAML config)
    if args.render_js:
        if args.proxy and args.proxy != 'web_scraper_api':
            errors.append("--render-js requires --proxy web_scraper_api (or proxy.mode: web_scraper_api in config for selected retailers)")
        else:
            yaml_proxy_modes = set()
            if config:
                target_retailers = _get_target_retailers(args)
                if target_retailers:
                    for retailer in target_retailers:
                        mode = _get_yaml_proxy_mode(config, retailer)
                        if mode:
                            yaml_proxy_modes.add(mode)
                else:
                    mode = _get_yaml_proxy_mode(config, None)
                    if mode:
                        yaml_proxy_modes.add(mode)
            # Allow if CLI specifies web_scraper_api OR YAML config has web_scraper_api
            if args.proxy != 'web_scraper_api' and 'web_scraper_api' not in yaml_proxy_modes:
                errors.append("--render-js requires --proxy web_scraper_api (or proxy.mode: web_scraper_api in config for selected retailers)")

    # Validate limit range
    if args.limit is not None and args.limit < 1:
        errors.append("--limit must be a positive integer")

    # Validate exclude requires --all
    if getattr(args, 'exclude', None) and not getattr(args, 'all', False):
        errors.append("--exclude can only be used with --all")

    return errors


def main():
    """Main entry point"""
    parser = setup_parser()
    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(args.log_file)
    logging.getLogger().setLevel(log_level)

    # Handle status command
    if args.status:
        retailers = [args.retailer] if args.retailer else None
        show_status(retailers)
        return 0

    # Validate configuration on startup (#67)
    config_errors = validate_config_on_startup()
    if config_errors:
        print("Configuration errors found:")
        for error in config_errors:
            print(f"  - {error}")
        return 1

    # Load config for CLI validation (need to check YAML proxy mode for --render-js)
    with open("config/retailers.yaml", 'r', encoding='utf-8') as f:
        loaded_config = yaml.safe_load(f) or {}

    # Validate CLI options (#106)
    cli_errors = validate_cli_options(args, loaded_config)
    if cli_errors:
        print("Invalid command line options:")
        for error in cli_errors:
            print(f"  - {error}")
        return 1

    # Initialize proxy client if specified via CLI
    if args.proxy:
        # Check for mode-specific credentials
        if args.proxy == 'residential':
            # Check for residential credentials (with fallback to legacy)
            res_user = os.getenv('OXYLABS_RESIDENTIAL_USERNAME') or os.getenv('OXYLABS_USERNAME')
            res_pass = os.getenv('OXYLABS_RESIDENTIAL_PASSWORD') or os.getenv('OXYLABS_PASSWORD')
            if not res_user or not res_pass:
                print("Error: Residential proxy credentials required")
                print("Set them with:")
                print("  export OXYLABS_RESIDENTIAL_USERNAME=your_username")
                print("  export OXYLABS_RESIDENTIAL_PASSWORD=your_password")
                print("Or use legacy variables:")
                print("  export OXYLABS_USERNAME=your_username")
                print("  export OXYLABS_PASSWORD=your_password")
                return 1
        elif args.proxy == 'web_scraper_api':
            # Check for Web Scraper API credentials (with fallback to legacy)
            api_user = os.getenv('OXYLABS_SCRAPER_API_USERNAME') or os.getenv('OXYLABS_USERNAME')
            api_pass = os.getenv('OXYLABS_SCRAPER_API_PASSWORD') or os.getenv('OXYLABS_PASSWORD')
            if not api_user or not api_pass:
                print("Error: Web Scraper API credentials required")
                print("Set them with:")
                print("  export OXYLABS_SCRAPER_API_USERNAME=your_username")
                print("  export OXYLABS_SCRAPER_API_PASSWORD=your_password")
                print("Or use legacy variables:")
                print("  export OXYLABS_USERNAME=your_username")
                print("  export OXYLABS_PASSWORD=your_password")
                return 1

        # Build proxy config from CLI args
        proxy_config = {
            'mode': args.proxy,
            'render_js': args.render_js,
        }
        if args.proxy_country:
            proxy_config['country_code'] = args.proxy_country

        get_proxy_client(proxy_config)
        proxy_country = args.proxy_country or "us"
        logging.info(f"Proxy mode: {args.proxy} (country: {proxy_country})")
        if args.render_js:
            logging.info("JavaScript rendering enabled")
    else:
        # Try to load from YAML config
        try:
            init_proxy_from_yaml()
        except Exception as e:
            logging.debug(f"Using default proxy config: {e}")

    # Validate proxy credentials if requested (#107)
    if args.validate_proxy:
        proxy_client = get_proxy_client()
        if proxy_client:
            print("Validating proxy credentials...")
            success, message = proxy_client.validate_credentials()
            if success:
                print(f"  ✓ {message}")
            else:
                print(f"  ✗ {message}")
                return 1
        else:
            print("No proxy configured, skipping validation")

    # Get retailers to run
    retailers = get_retailers_to_run(args)

    if not retailers:
        print("No retailers specified. Use --retailer <name> or --all")
        print(f"Available retailers: {', '.join(get_enabled_retailers())}")
        return 1

    # Set limit for test mode
    limit = args.limit
    if args.test and limit is None:
        limit = 10

    # Parse export formats
    export_formats = parse_format_list(args.format)
    if not export_formats:
        print(f"No valid export formats specified. Valid formats: json, csv, excel, geojson")
        return 1

    logging.info(f"Running scrapers for: {retailers}")
    logging.info(f"Export formats: {', '.join(f.value for f in export_formats)}")
    if limit:
        logging.info(f"Limit: {limit} stores per retailer")
    if args.resume:
        logging.info("Resume mode enabled")
    if args.incremental:
        logging.info("Incremental mode enabled")
    if getattr(args, 'refresh_urls', False):
        logging.info("Refresh URLs mode enabled (will re-discover all store URLs)")
    if args.states:
        logging.info(f"Targeted states mode: {args.states}")

    # Get CLI proxy override and settings (#52)
    cli_proxy_override = args.proxy if args.proxy else None
    # Pass proxy settings if CLI override OR if render_js is set (can use YAML proxy)
    cli_proxy_settings = {}
    if args.proxy_country:
        cli_proxy_settings['country_code'] = args.proxy_country
    if args.render_js:
        cli_proxy_settings['render_js'] = True
    if not cli_proxy_settings and not cli_proxy_override:
        cli_proxy_settings = None

    # Initialize cloud storage if enabled
    # Priority: --no-cloud (disable) > --cloud (enable) > config/env
    cloud_manager = None
    if getattr(args, 'no_cloud', False):
        logging.debug("Cloud storage disabled via --no-cloud")
    else:
        cloud_enabled = getattr(args, 'cloud', False) or loaded_config.get('cloud_storage', {}).get('enabled', False)
        if cloud_enabled or args.gcs_bucket:
            cloud_manager = get_cloud_storage(
                bucket_override=args.gcs_bucket,
                enable_history=True if args.gcs_history else None,
                config=loaded_config
            )
            if cloud_manager:
                logging.info(f"Cloud storage enabled: {cloud_manager.provider_name}")
            elif cloud_enabled or args.gcs_bucket:
                logging.warning("Cloud storage requested but not configured (check GCS_* env vars)")

    # Run scrapers
    try:
        # Get refresh_urls flag (convert hyphen to underscore for attribute access)
        refresh_urls = getattr(args, 'refresh_urls', False)
        # States are already validated and parsed by validate_states() (#173)
        target_states = args.states

        if len(retailers) == 1:
            # Single retailer - run directly
            result = asyncio.run(run_retailer_async(
                retailers[0],
                cli_proxy_override=cli_proxy_override,
                cli_proxy_settings=cli_proxy_settings,
                export_formats=export_formats,
                cloud_manager=cloud_manager,
                resume=args.resume,
                incremental=args.incremental,
                limit=limit,
                refresh_urls=refresh_urls,
                target_states=target_states
            ))
            print(f"\nResult for {retailers[0]}: {result['status']}")
            if result.get('formats'):
                print(f"  Exported: {', '.join(result['formats'])}")
            if result.get('cloud_uploaded'):
                print(f"  Cloud: uploaded to {cloud_manager.provider_name}")
        else:
            # Multiple retailers - run concurrently
            results = asyncio.run(run_all_retailers(
                retailers,
                cli_proxy_override=cli_proxy_override,
                cli_proxy_settings=cli_proxy_settings,
                export_formats=export_formats,
                cloud_manager=cloud_manager,
                resume=args.resume,
                incremental=args.incremental,
                limit=limit,
                refresh_urls=refresh_urls,
                target_states=target_states
            ))

            print("\n" + "=" * 40)
            print("SCRAPING RESULTS")
            print("=" * 40)
            for retailer, result in results.items():
                status = result.get('status', 'unknown')
                stores = result.get('stores', 0)
                error = result.get('error', '')
                cloud_status = " [cloud]" if result.get('cloud_uploaded') else ""
                print(f"  {retailer}: {status} ({stores} stores){cloud_status}")
                if error:
                    print(f"    Error: {error}")

        return 0

    except KeyboardInterrupt:
        logging.info("Scraping interrupted by user")
        return 130
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
        return 1
    finally:
        # Cleanup all proxy clients
        close_all_proxy_clients()
        # Shutdown thread pool executor
        _scraper_executor.shutdown(wait=False)


if __name__ == '__main__':
    sys.exit(main())
