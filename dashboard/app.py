#!/usr/bin/env python3
"""Simple Flask dashboard for monitoring scraper progress"""

import csv
import io
import json
import logging
import os
import sys
import re
import uuid
import yaml
import shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file (look in parent directory)
load_dotenv(Path(__file__).parent.parent / '.env')

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request, render_template, send_from_directory, send_file
from flask_wtf.csrf import CSRFProtect, generate_csrf
from src.shared import status, scraper_manager, run_tracker
from src.shared.export_service import ExportService, ExportFormat

app = Flask(__name__, static_folder='static', template_folder='templates')

# Configure secret key for CSRF protection (use env var or generate random)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(32).hex())
app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit on tokens

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Get singleton scraper manager instance
_scraper_manager = scraper_manager.get_scraper_manager()


def safe_error_response(error: Exception, operation: str = "operation") -> tuple:
    """Generate a safe error response that doesn't leak sensitive information.

    Logs the full exception internally with a reference ID, then returns
    a generic error message to the client with that reference ID.

    Args:
        error: The caught exception
        operation: Description of the operation that failed (for logging)

    Returns:
        Tuple of (jsonify response, status code) suitable for Flask routes
    """
    # Generate a reference ID for correlation
    error_id = str(uuid.uuid4())[:8]

    # Log the full error internally for debugging
    logging.error(f"[{error_id}] Error during {operation}: {error}", exc_info=True)

    # Return a generic message to the client
    return jsonify({
        "error": f"An internal error occurred. Reference: {error_id}",
        "reference": error_id
    }), 500


def require_json(f):
    """Decorator to require JSON Content-Type for POST endpoints"""
    def wrapper(*args, **kwargs):
        if request.method == 'POST':
            # Use request.is_json which properly handles charset and other parameters
            # This accepts "application/json" and "application/json; charset=utf-8"
            if not request.is_json:
                return jsonify({"error": "Content-Type must be application/json"}), 415
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


@app.route('/')
def index():
    """Main dashboard page

    Serves the Vite-built frontend from static/dist/index.html if it exists,
    otherwise falls back to templates/index.html for development.
    """
    # Check if Vite-built index.html exists (production mode)
    vite_index = Path(__file__).parent / 'static' / 'dist' / 'index.html'
    if vite_index.exists():
        return send_from_directory(
            str(vite_index.parent),
            'index.html'
        )
    # Fallback to legacy template
    return render_template('index.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory(app.static_folder, filename)


@app.route('/src/<path:filename>')
def serve_src(filename):
    """Serve source files for Vite dev mode

    In development, Vite serves files directly. This route allows
    Flask to serve source files when running without Vite dev server.
    """
    src_folder = Path(__file__).parent / 'src'
    return send_from_directory(str(src_folder), filename)


def _transform_status_for_frontend(backend_data: dict) -> dict:
    """Transform backend status format to frontend-expected format"""
    global_stats = backend_data.get("global", {})
    retailers_data = backend_data.get("retailers", {})

    # Count actually running scrapers from ScraperManager (more accurate than file-based check)
    actual_active_count = 0
    for retailer_id in retailers_data.keys():
        if _scraper_manager.is_running(retailer_id):
            actual_active_count += 1

    summary = {
        "total_stores": global_stats.get("total_stores", 0),
        "active_retailers": global_stats.get("enabled_retailers", 0),
        "total_retailers": global_stats.get("total_retailers", 6),
        "overall_progress": global_stats.get("overall_progress", 0.0),
        "estimated_remaining_seconds": 0,
        "active_scrapers": actual_active_count,  # Use actual count from ScraperManager
    }

    retailers = {}

    for retailer_id, retailer_data in retailers_data.items():
        enabled = retailer_data.get("enabled", False)
        # Check BOTH file-based status AND ScraperManager process tracking
        # ScraperManager knows immediately when a process starts, while file-based
        # detection only works after checkpoint files are written
        scraper_active = retailer_data.get("scraper_active", False) or _scraper_manager.is_running(retailer_id)
        
        if not enabled:
            status_value = "disabled"
        elif scraper_active:
            status_value = "running"
        elif retailer_data.get("overall_progress", 0) >= 100:
            status_value = "complete"
        else:
            status_value = "pending"
        
        phases_dict = retailer_data.get("phases", {})
        phases_list = []
        for _phase_key, phase_data in phases_dict.items():
            phases_list.append({
                "name": phase_data.get("name", "Unknown"),
                "status": phase_data.get("status", "pending"),
                "completed": phase_data.get("completed", 0),
                "total": phase_data.get("total", 0),
            })
        
        total = 0
        completed = 0
        for phase in phases_list:
            if "extract" in phase["name"].lower():
                total = phase["total"]
                completed = phase["completed"]
                break
        
        if total == 0 and len(phases_list) > 0:
            last_phase = phases_list[-1]
            total = last_phase["total"]
            completed = last_phase["completed"]
        
        progress_pct = retailer_data.get("overall_progress", 0.0)
        progress_text = f"{completed:,} / {total:,} stores ({progress_pct:.1f}%)" if total > 0 else "No data"
        
        stats = {
            "stat1_value": formatNumber(completed) if total > 0 else "—",
            "stat1_label": "Stores",
            "stat2_value": "—",
            "stat2_label": "Duration",
            "stat3_value": "—",
            "stat3_label": "Requests",
        }
        
        retailers[retailer_id] = {
            "status": status_value,
            "progress": {
                "percentage": progress_pct,
                "text": progress_text,
            },
            "stats": stats,
            "phases": phases_list,
        }
    
    return {
        "summary": summary,
        "retailers": retailers,
    }


def formatNumber(num):
    """Format number with commas"""
    if num is None or num == 0:
        return "0"
    return f"{num:,}"


@app.route('/api/csrf-token')
def api_csrf_token():
    """Get CSRF token for subsequent POST requests"""
    return jsonify({"csrf_token": generate_csrf()})


@app.route('/api/status')
def api_status():
    """Get status for all retailers"""
    try:
        status_data = status.get_all_retailers_status()
        transformed = _transform_status_for_frontend(status_data)
        return jsonify(transformed)
    except Exception as e:
        return safe_error_response(e, "API request")


@app.route('/api/status/<retailer>')
def api_retailer_status(retailer):
    """Get status for a single retailer"""
    try:
        retailer_status = status.get_retailer_status(retailer)
        
        if "error" in retailer_status:
            return jsonify(retailer_status), 404
        
        return jsonify(retailer_status)
    except Exception as e:
        return safe_error_response(e, "API request")


@app.route('/api/scraper/start', methods=['POST'])
@require_json
def api_scraper_start():
    """Start scraper(s)
    
    Request body:
    {
        "retailer": "verizon",  # Required: retailer name or "all"
        "resume": true,         # Optional: resume from checkpoint (default: false)
        "incremental": false,   # Optional: incremental mode (default: false)
        "limit": null,          # Optional: limit number of stores (default: null)
        "test": false,          # Optional: test mode with 10 stores (default: false)
        "proxy": "direct",      # Optional: proxy mode (direct/residential/web_scraper_api)
        "render_js": false,     # Optional: enable JS rendering (default: false)
        "proxy_country": "us",  # Optional: proxy country code (default: "us")
        "verbose": false        # Optional: verbose logging (default: false)
    }
    """
    try:
        data = request.get_json() or {}
        retailer = data.get('retailer')
        
        if not retailer:
            return jsonify({"error": "Missing required field: retailer"}), 400
        
        options = {
            'resume': data.get('resume', False),
            'incremental': data.get('incremental', False),
            'limit': data.get('limit'),
            'test': data.get('test', False),
            'proxy': data.get('proxy'),
            'render_js': data.get('render_js', False),
            'proxy_country': data.get('proxy_country', 'us'),
            'verbose': data.get('verbose', False)
        }
        
        if retailer == 'all':
            config = status.load_retailers_config()
            results = []
            errors = []
            
            for ret in config.keys():
                if not config[ret].get('enabled', False):
                    continue
                
                try:
                    result = _scraper_manager.start(ret, **options)
                    results.append(result)
                except Exception as e:
                    errors.append({"retailer": ret, "error": str(e)})
            
            return jsonify({
                "message": f"Started {len(results)} scraper(s)",
                "started": results,
                "errors": errors
            })
        
        result = _scraper_manager.start(retailer, **options)
        return jsonify(result)
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return safe_error_response(e, "API request")


@app.route('/api/scraper/stop', methods=['POST'])
@require_json
def api_scraper_stop():
    """Stop scraper(s)
    
    Request body:
    {
        "retailer": "verizon",  # Required: retailer name or "all"
        "timeout": 30           # Optional: shutdown timeout in seconds (default: 30)
    }
    """
    try:
        data = request.get_json() or {}
        retailer = data.get('retailer')
        timeout = data.get('timeout', 30)
        
        if not retailer:
            return jsonify({"error": "Missing required field: retailer"}), 400
        
        if retailer == 'all':
            result = _scraper_manager.stop_all(timeout=timeout)
            return jsonify({
                "message": f"Stopped {len(result)} scraper(s)",
                "stopped": result
            })
        
        result = _scraper_manager.stop(retailer, timeout=timeout)
        return jsonify(result)
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return safe_error_response(e, "API request")


@app.route('/api/scraper/restart', methods=['POST'])
@require_json
def api_scraper_restart():
    """Restart scraper(s)
    
    Request body:
    {
        "retailer": "verizon",  # Required: retailer name or "all"
        "resume": true,         # Optional: resume from checkpoint (default: true)
        "timeout": 30           # Optional: shutdown timeout in seconds (default: 30)
    }
    """
    try:
        data = request.get_json() or {}
        retailer = data.get('retailer')
        
        if not retailer:
            return jsonify({"error": "Missing required field: retailer"}), 400
        
        resume = data.get('resume', True)
        timeout = data.get('timeout', 30)
        
        if retailer == 'all':
            config = status.load_retailers_config()
            results = []
            errors = []
            
            for ret in config.keys():
                if not config[ret].get('enabled', False):
                    continue
                
                try:
                    result = _scraper_manager.restart(ret, resume=resume, timeout=timeout)
                    results.append(result)
                except Exception as e:
                    errors.append({"retailer": ret, "error": str(e)})
            
            return jsonify({
                "message": f"Restarted {len(results)} scraper(s)",
                "restarted": results,
                "errors": errors
            })
        
        result = _scraper_manager.restart(retailer, resume=resume, timeout=timeout)
        return jsonify(result)
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return safe_error_response(e, "API request")


@app.route('/api/runs/<retailer>')
def api_run_history(retailer):
    """Get historical runs for a retailer
    
    Query params:
        limit: Number of runs to return (default: 10)
    """
    try:
        config = status.load_retailers_config()
        if retailer not in config:
            return jsonify({"error": f"Unknown retailer: {retailer}"}), 404
        
        limit = request.args.get('limit', 10, type=int)
        runs = run_tracker.get_run_history(retailer, limit=limit)
        
        return jsonify({
            "retailer": retailer,
            "runs": runs,
            "count": len(runs)
        })
    except Exception as e:
        return safe_error_response(e, "API request")


@app.route('/api/logs/<retailer>/<run_id>')
def api_get_logs(retailer, run_id):
    """Get logs for a specific run

    Query params:
        tail: Number of lines to return from end (default: all)
        offset: Line number to start from for incremental fetching (default: 0)

    Response includes:
        - total_lines: Total lines in log file
        - offset: The offset that was applied
        - is_active: Whether this run is currently active (scraper running)
    """
    try:
        # Validate retailer name format to prevent path traversal
        if not re.match(r'^[a-z][a-z0-9_]*$', retailer):
            return jsonify({"error": "Invalid retailer name format. Must start with lowercase letter and contain only lowercase, digits, and underscores"}), 400

        config = status.load_retailers_config()
        if retailer not in config:
            return jsonify({"error": f"Unknown retailer: {retailer}"}), 404

        if not re.match(r'^[\w\-]+$', run_id):
            return jsonify({"error": "Invalid run_id format. Only alphanumeric, underscore, and hyphen allowed"}), 400

        log_file = Path(f"data/{retailer}/logs/{run_id}.log")

        # SECURITY: Validate path BEFORE checking existence to prevent path traversal attacks
        # that could probe the filesystem for existence of arbitrary files
        log_file_resolved = log_file.resolve()
        expected_base = Path("data").resolve()

        if not str(log_file_resolved).startswith(str(expected_base)):
            return jsonify({"error": "Invalid log file path"}), 400

        if not log_file.exists():
            return jsonify({"error": "Log file not found"}), 404

        # Check if scraper is currently running for this run_id
        is_active = False
        if _scraper_manager.is_running(retailer):
            scraper_status = _scraper_manager.get_status(retailer)
            if scraper_status and scraper_status.get('run_id') == run_id:
                is_active = True

        tail = request.args.get('tail', type=int)
        offset = request.args.get('offset', type=int, default=0)

        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        total_lines = len(lines)

        # Apply offset first (for incremental fetching)
        if offset > 0:
            lines = lines[offset:]

        # Then apply tail (for initial load)
        if tail:
            lines = lines[-tail:]

        return jsonify({
            "retailer": retailer,
            "run_id": run_id,
            "lines": len(lines),
            "total_lines": total_lines,
            "offset": offset,
            "is_active": is_active,
            "content": ''.join(lines)
        })
    except Exception as e:
        return safe_error_response(e, "API request")


@app.route('/api/config', methods=['GET'])
def api_get_config():
    """Get current configuration"""
    try:
        config_path = Path("config/retailers.yaml")
        
        if not config_path.exists():
            return jsonify({"error": "Configuration file not found"}), 404
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()
        
        return jsonify({
            "path": str(config_path),
            "content": config_content
        })
    except Exception as e:
        return safe_error_response(e, "API request")


@app.route('/api/config', methods=['POST'])
@require_json
def api_update_config():
    """Update configuration with validation
    
    Request body:
    {
        "content": "YAML content as string"
    }
    
    Features:
    - Validates YAML syntax
    - Validates required fields and structure
    - Creates timestamped backup before update
    - Atomic write (temp file -> validate -> move)
    - Reloads configuration in memory
    """
    try:
        data = request.get_json() or {}
        content = data.get('content')
        
        if not content:
            return jsonify({"error": "Missing required field: content"}), 400
        
        config_path = Path("config/retailers.yaml")
        
        try:
            parsed_config = yaml.safe_load(content)
        except yaml.YAMLError as e:
            return jsonify({
                "error": "Invalid YAML syntax",
                "details": str(e)
            }), 400
        
        validation_result = _validate_config(parsed_config)
        if not validation_result["valid"]:
            return jsonify({
                "error": "Configuration validation failed",
                "details": validation_result["errors"]
            }), 400
        
        backup_path = _create_config_backup(config_path)
        
        temp_path = config_path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            temp_path.replace(config_path)
            
            _reload_config()
            
            return jsonify({
                "message": "Configuration updated successfully",
                "backup": str(backup_path)
            })
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    except Exception as e:
        return safe_error_response(e, "API request")


def _validate_config(config: dict) -> dict:
    """Validate configuration structure and required fields
    
    Args:
        config: Parsed YAML configuration
    
    Returns:
        Dict with 'valid' (bool) and 'errors' (list) keys
    """
    errors = []
    
    if not isinstance(config, dict):
        errors.append("Configuration must be a dictionary")
        return {"valid": False, "errors": errors}
    
    if 'retailers' not in config:
        errors.append("Missing required top-level key: 'retailers'")
    
    if 'retailers' in config:
        retailers = config['retailers']
        
        if not isinstance(retailers, dict):
            errors.append("'retailers' must be a dictionary")
        else:
            for retailer_name, retailer_config in retailers.items():
                # Validate retailer name format to prevent path traversal
                if not re.match(r'^[a-z][a-z0-9_]*$', retailer_name):
                    errors.append(
                        f"Invalid retailer name '{retailer_name}'. "
                        f"Must start with lowercase letter and contain only lowercase, digits, and underscores"
                    )
                    continue
                
                if not isinstance(retailer_config, dict):
                    errors.append(f"Retailer '{retailer_name}' config must be a dictionary")
                    continue
                
                required_fields = ['name', 'enabled', 'base_url', 'discovery_method']
                for field in required_fields:
                    if field not in retailer_config:
                        errors.append(f"Retailer '{retailer_name}' missing required field: '{field}'")
                
                if 'enabled' in retailer_config and not isinstance(retailer_config['enabled'], bool):
                    errors.append(f"Retailer '{retailer_name}' field 'enabled' must be boolean")
                
                if 'base_url' in retailer_config:
                    base_url = retailer_config['base_url']
                    if not isinstance(base_url, str) or not base_url.startswith(('http://', 'https://')):
                        errors.append(f"Retailer '{retailer_name}' field 'base_url' must be a valid HTTP/HTTPS URL")
                
                if 'discovery_method' in retailer_config:
                    valid_methods = ['html_crawl', 'sitemap', 'sitemap_gzip', 'sitemap_paginated']
                    if retailer_config['discovery_method'] not in valid_methods:
                        errors.append(
                            f"Retailer '{retailer_name}' has invalid discovery_method. "
                            f"Must be one of: {', '.join(valid_methods)}"
                        )
                
                numeric_fields = ['min_delay', 'max_delay', 'timeout', 'checkpoint_interval']
                for field in numeric_fields:
                    if field in retailer_config:
                        value = retailer_config[field]
                        if not isinstance(value, (int, float)) or value <= 0:
                            errors.append(
                                f"Retailer '{retailer_name}' field '{field}' must be a positive number"
                            )
    
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def _create_config_backup(config_path: Path) -> Path:
    """Create timestamped backup of configuration file
    
    Args:
        config_path: Path to config file
    
    Returns:
        Path to backup file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = config_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    backup_path = backup_dir / f"{config_path.stem}_{timestamp}{config_path.suffix}"
    shutil.copy2(config_path, backup_path)
    
    return backup_path


def _reload_config() -> None:
    """Reload configuration after update.

    Note: Full runtime config reload is not currently implemented.
    This function logs a notice that the app needs restart for
    configuration changes to take full effect.
    """
    logging.info("Config file updated. Restart app for changes to take full effect.")


# =============================================================================
# EXPORT API ENDPOINTS
# =============================================================================

VALID_EXPORT_FORMATS = {'json', 'csv', 'excel', 'geojson'}
CONTENT_TYPES = {
    'json': 'application/json',
    'csv': 'text/csv',
    'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'geojson': 'application/geo+json'
}
FILE_EXTENSIONS = {
    'json': 'json',
    'csv': 'csv',
    'excel': 'xlsx',
    'geojson': 'geojson'
}


@app.route('/api/export/<retailer>/<export_format>')
def api_export_retailer(retailer, export_format):
    """Export single retailer data in specified format

    Path params:
        retailer: Retailer ID (verizon, att, target, etc.)
        export_format: Export format (json|csv|excel|geojson)

    Returns:
        File download with appropriate Content-Type
    """
    try:
        # Validate format
        export_format = export_format.lower()
        if export_format not in VALID_EXPORT_FORMATS:
            return jsonify({
                "error": f"Invalid format '{export_format}'. Must be one of: {', '.join(VALID_EXPORT_FORMATS)}"
            }), 400

        # Validate retailer
        config = status.load_retailers_config()
        if retailer not in config:
            return jsonify({"error": f"Unknown retailer: {retailer}"}), 404

        # Load stores
        stores_file = Path(f"data/{retailer}/output/stores_latest.json")
        if not stores_file.exists():
            return jsonify({"error": f"No data found for {retailer}"}), 404

        with open(stores_file, 'r', encoding='utf-8') as f:
            stores = json.load(f)

        # Get retailer config for field mapping
        retailer_config = config.get(retailer, {})

        # Generate filename
        timestamp = datetime.now().strftime("%Y-%m-%d")
        ext = FILE_EXTENSIONS.get(export_format, export_format)
        filename = f"{retailer}_stores_{timestamp}.{ext}"

        # Generate export based on format
        if export_format == 'json':
            data = json.dumps(stores, indent=2, ensure_ascii=False).encode('utf-8')
        elif export_format == 'csv':
            fieldnames = retailer_config.get('output_fields')
            if not fieldnames and stores:
                fieldnames = list(stores[0].keys())
            data = ExportService.generate_csv_string(stores, fieldnames).encode('utf-8')
        elif export_format == 'excel':
            fieldnames = retailer_config.get('output_fields')
            data = ExportService.generate_excel_bytes(stores, retailer.title(), fieldnames)
        elif export_format == 'geojson':
            geojson_data = ExportService.generate_geojson(stores)
            data = json.dumps(geojson_data, indent=2, ensure_ascii=False).encode('utf-8')
        else:
            # Should not reach here due to format validation above
            return jsonify({"error": f"Unsupported format: {export_format}"}), 400

        return send_file(
            io.BytesIO(data),
            mimetype=CONTENT_TYPES[export_format],
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return safe_error_response(e, "API request")


@app.route('/api/export/multi', methods=['POST'])
@require_json
def api_export_multi():
    """Export multiple retailers combined

    Request body:
    {
        "retailers": ["verizon", "att", "target"],
        "format": "excel",
        "combine": true
    }

    Returns:
        File download (Excel: multi-sheet, others: merged arrays)
    """
    try:
        data = request.get_json() or {}
        retailers = data.get('retailers', [])
        export_format = data.get('format', 'excel').lower()
        # combine is accepted but always true for now

        # Validation
        if not retailers or not isinstance(retailers, list):
            return jsonify({"error": "Missing or invalid 'retailers' field"}), 400

        # Validate each retailer is a string
        for retailer in retailers:
            if not isinstance(retailer, str):
                return jsonify({
                    "error": f"Invalid retailer value. All retailers must be strings, got {type(retailer).__name__}"
                }), 400

        if len(retailers) > 10:
            return jsonify({"error": "Maximum 10 retailers allowed"}), 400

        # Validate retailer name format to prevent path traversal and type errors
        for retailer in retailers:
            if not re.match(r'^[a-z][a-z0-9_]*$', retailer):
                return jsonify({
                    "error": f"Invalid retailer name format: '{retailer}'. "
                            f"Must start with lowercase letter and contain only lowercase, digits, and underscores"
                }), 400

        if export_format not in VALID_EXPORT_FORMATS:
            return jsonify({
                "error": f"Invalid format. Must be one of: {', '.join(VALID_EXPORT_FORMATS)}"
            }), 400

        # Load stores for each retailer
        config = status.load_retailers_config()
        retailer_data = {}

        for retailer in retailers:
            if retailer not in config:
                return jsonify({"error": f"Unknown retailer: {retailer}"}), 404

            stores_file = Path(f"data/{retailer}/output/stores_latest.json")
            if not stores_file.exists():
                continue

            with open(stores_file, 'r', encoding='utf-8') as f:
                retailer_data[retailer] = json.load(f)

        if not retailer_data:
            return jsonify({"error": "No data found for any retailer"}), 404

        # Check if all retailers have empty store lists
        all_empty = all(not stores for stores in retailer_data.values())
        if all_empty:
            return jsonify({"error": "All retailers have empty data"}), 404

        # Generate filename
        timestamp = datetime.now().strftime("%Y-%m-%d")
        ext = FILE_EXTENSIONS.get(export_format, export_format)
        filename = f"stores_combined_{timestamp}.{ext}"

        if export_format == 'excel':
            # Multi-sheet Excel
            file_data = ExportService.generate_multi_sheet_excel(retailer_data, config)
        else:
            # Merge all stores into single array
            all_stores = []
            for retailer, stores in retailer_data.items():
                for store in stores:
                    store_copy = store.copy()
                    store_copy['retailer'] = retailer  # Add retailer identifier
                    all_stores.append(store_copy)

            if export_format == 'json':
                file_data = json.dumps(all_stores, indent=2, ensure_ascii=False).encode('utf-8')
            elif export_format == 'csv':
                # Get all unique fields across retailers
                all_fields = set()
                for store in all_stores:
                    all_fields.update(store.keys())
                fieldnames = sorted(all_fields)
                # Ensure 'retailer' is first
                if 'retailer' in fieldnames:
                    fieldnames.remove('retailer')
                    fieldnames = ['retailer'] + fieldnames
                file_data = ExportService.generate_csv_string(all_stores, fieldnames).encode('utf-8')
            elif export_format == 'geojson':
                geojson_data = ExportService.generate_geojson(all_stores)
                file_data = json.dumps(geojson_data, indent=2, ensure_ascii=False).encode('utf-8')
            else:
                # Should not reach here due to format validation above
                return jsonify({"error": f"Unsupported format: {export_format}"}), 400

        return send_file(
            io.BytesIO(file_data),
            mimetype=CONTENT_TYPES[export_format],
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return safe_error_response(e, "API request")


@app.route('/api/export/formats')
def api_export_formats():
    """Get list of available export formats

    Returns:
        List of format objects with id, name, extension, and description
    """
    formats = [
        {
            "id": "json",
            "name": "JSON",
            "extension": "json",
            "description": "JavaScript Object Notation - full data with all fields"
        },
        {
            "id": "csv",
            "name": "CSV",
            "extension": "csv",
            "description": "Comma-Separated Values - compatible with Excel, Google Sheets"
        },
        {
            "id": "excel",
            "name": "Excel",
            "extension": "xlsx",
            "description": "Microsoft Excel workbook with formatting"
        },
        {
            "id": "geojson",
            "name": "GeoJSON",
            "extension": "geojson",
            "description": "Geographic JSON - for mapping applications"
        }
    ]
    return jsonify({"formats": formats})


if __name__ == '__main__':
    # Run on all interfaces (0.0.0.0) to allow network access
    app.run(host='0.0.0.0', port=5001, debug=False)
