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

from src.shared.utils import (
    setup_logging,
    load_retailer_config,
    create_proxied_session,
    close_all_proxy_clients
)
from src.shared import init_proxy_from_yaml, get_proxy_client
from src.shared.export_service import ExportService, ExportFormat, parse_format_list
from src.scrapers import get_available_retailers, get_scraper_module
from src.change_detector import ChangeDetector


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
        choices=get_available_retailers(),
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
        choices=get_available_retailers(),
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
        default='us',
        help='Proxy country code for geo-targeting (default: us)'
    )

    # Export options
    export_group = parser.add_argument_group('export options', 'Output format selection')
    export_group.add_argument(
        '--format', '-f',
        type=str,
        default='json,csv',
        help='Export formats (comma-separated): json,csv,excel,geojson (default: json,csv)'
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
        all_retailers = get_available_retailers()
        return [r for r in all_retailers if r not in args.exclude]
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
                            except Exception:
                                pass
                else:
                    print("  Outputs: None")
            else:
                print("  Outputs: Directory not found")

        except Exception as e:
            print(f"  Error getting status: {e}")

    print("\n" + "=" * 60)


# Thread pool executor for running synchronous scrapers without blocking the event loop
_scraper_executor = concurrent.futures.ThreadPoolExecutor(max_workers=6, thread_name_prefix='scraper')


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
    export_formats: Optional[List[ExportFormat]] = None,
    **kwargs
) -> dict:
    """Run a single retailer scraper asynchronously

    Uses ThreadPoolExecutor to run synchronous scrapers without
    blocking the event loop, enabling true concurrent execution.

    Args:
        retailer: Retailer name
        cli_proxy_override: Optional CLI proxy mode override from --proxy flag
        export_formats: List of formats to export (default: JSON, CSV)
        **kwargs: Additional arguments (resume, incremental, limit, etc.)
    """
    logging.info(f"[{retailer}] Starting scraper")

    # Default to JSON and CSV if no formats specified
    if export_formats is None:
        export_formats = [ExportFormat.JSON, ExportFormat.CSV]

    try:
        retailer_config = load_retailer_config(retailer, cli_proxy_override)

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

                # Rotate versions: stores_latest -> stores_previous
                detector.save_version(stores)
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

        for fmt in export_formats:
            try:
                ext = format_extensions.get(fmt, fmt.value)
                output_path = f"{output_dir}/stores_latest.{ext}"
                ExportService.export_stores(stores, fmt, output_path, retailer_config)
            except Exception as export_err:
                logging.warning(f"[{retailer}] Failed to export {fmt.value}: {export_err}")

        result = {
            'retailer': retailer,
            'status': 'completed',
            'stores': count,
            'formats': [f.value for f in export_formats],
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


async def run_all_retailers(
    retailers: List[str],
    cli_proxy_override: Optional[str] = None,
    export_formats: Optional[List[ExportFormat]] = None,
    **kwargs
) -> dict:
    """Run multiple retailers concurrently

    Args:
        retailers: List of retailer names to run
        cli_proxy_override: Optional CLI proxy mode override from --proxy flag
        export_formats: List of formats to export
        **kwargs: Additional arguments (resume, incremental, limit, etc.)
    """
    logging.info(f"Starting concurrent scrape for {len(retailers)} retailers: {retailers}")

    tasks = [
        run_retailer_async(
            retailer,
            cli_proxy_override=cli_proxy_override,
            export_formats=export_formats,
            **kwargs
        )
        for retailer in retailers
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    summary = {}
    for retailer, result in zip(retailers, results):
        if isinstance(result, Exception):
            summary[retailer] = {
                'status': 'error',
                'error': str(result)
            }
        else:
            summary[retailer] = result

    return summary


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
            'country_code': args.proxy_country,
            'render_js': args.render_js,
        }

        get_proxy_client(proxy_config)
        logging.info(f"Proxy mode: {args.proxy} (country: {args.proxy_country})")
        if args.render_js:
            logging.info("JavaScript rendering enabled")
    else:
        # Try to load from YAML config
        try:
            init_proxy_from_yaml()
        except Exception as e:
            logging.debug(f"Using default proxy config: {e}")

    # Get retailers to run
    retailers = get_retailers_to_run(args)

    if not retailers:
        print("No retailers specified. Use --retailer <name> or --all")
        print(f"Available retailers: {', '.join(get_available_retailers())}")
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

    # Get CLI proxy override
    cli_proxy_override = args.proxy if args.proxy else None

    # Run scrapers
    try:
        if len(retailers) == 1:
            # Single retailer - run directly
            result = asyncio.run(run_retailer_async(
                retailers[0],
                cli_proxy_override=cli_proxy_override,
                export_formats=export_formats,
                resume=args.resume,
                incremental=args.incremental,
                limit=limit
            ))
            print(f"\nResult for {retailers[0]}: {result['status']}")
            if result.get('formats'):
                print(f"  Exported: {', '.join(result['formats'])}")
        else:
            # Multiple retailers - run concurrently
            results = asyncio.run(run_all_retailers(
                retailers,
                cli_proxy_override=cli_proxy_override,
                export_formats=export_formats,
                resume=args.resume,
                incremental=args.incremental,
                limit=limit
            ))

            print("\n" + "=" * 40)
            print("SCRAPING RESULTS")
            print("=" * 40)
            for retailer, result in results.items():
                status = result.get('status', 'unknown')
                stores = result.get('stores', 0)
                error = result.get('error', '')
                print(f"  {retailer}: {status} ({stores} stores)")
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
