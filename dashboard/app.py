# pylint: disable=too-many-lines
#!/usr/bin/env python3
"""Simple Flask dashboard for monitoring scraper progress"""

import csv
import io
import json
import logging
import os
import secrets
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

from functools import wraps
from flask import Flask, jsonify, request, render_template, send_from_directory, send_file, Response, stream_with_context
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from src.shared import status, scraper_manager, run_tracker
from src.shared.export_service import ExportService, ExportFormat, sanitize_csv_value

app = Flask(__name__, static_folder='static', template_folder='templates')


def _get_secret_key() -> str:
    """Get or generate a persistent secret key for CSRF protection (#95).

    Priority:
    1. FLASK_SECRET_KEY environment variable (recommended for production)
    2. Persisted random secret in .flask_secret file (auto-generated)

    The file-based approach ensures sessions persist across restarts
    while using cryptographically secure random values.

    Returns:
        A 64-character hex string secret key
    """
    # First, check environment variable
    env_key = os.environ.get('FLASK_SECRET_KEY')
    if env_key:
        return env_key

    # Generate and persist a random secret to file
    secret_file = Path(__file__).parent.parent / '.flask_secret'

    if secret_file.exists():
        try:
            stored_secret = secret_file.read_text().strip()
            if stored_secret and len(stored_secret) >= 32:
                return stored_secret
        except (IOError, OSError) as e:
            logging.warning(f"Could not read .flask_secret file: {e}")

    # Generate new random secret
    new_secret = secrets.token_hex(32)
    try:
        secret_file.write_text(new_secret)
        # Restrict file permissions (owner read/write only)
        secret_file.chmod(0o600)
        logging.info("Generated new secret key and saved to .flask_secret")
    except (IOError, OSError) as e:
        logging.warning(
            f"Could not save secret to .flask_secret: {e}. "
            f"Sessions will not persist across restarts."
        )

    return new_secret


app.config['SECRET_KEY'] = _get_secret_key()
app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit on tokens

# Check if running in development mode (whitelist approach for security #98)
# Source files are only served when FLASK_ENV is explicitly set to 'development'
IS_DEVELOPMENT = os.environ.get('FLASK_ENV') == 'development'

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Initialize rate limiter (#93)
# Note: Rate limiting can be disabled by setting RATELIMIT_ENABLED=False in config
# This is automatically done in tests via conftest.py
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    storage_uri="memory://",
    enabled=lambda: app.config.get('RATELIMIT_ENABLED', True),
)


def require_api_key(f):
    """Decorator to require API key authentication for mutating endpoints (#92).

    API key authentication is OPTIONAL - if DASHBOARD_API_KEY is not set,
    requests are allowed without authentication. This maintains backwards
    compatibility while enabling security for production deployments.

    Set DASHBOARD_API_KEY environment variable to enable authentication.
    Clients must include X-API-Key header with the correct key.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key_configured = os.environ.get('DASHBOARD_API_KEY')
        if not api_key_configured:
            # No API key configured - allow request (backwards compatible)
            return f(*args, **kwargs)

        # API key is configured - require it
        provided_key = request.headers.get('X-API-Key')
        if not provided_key:
            return jsonify({'error': 'Missing X-API-Key header'}), 401
        # Use constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(provided_key, api_key_configured):
            return jsonify({'error': 'Invalid API key'}), 401

        return f(*args, **kwargs)
    return decorated


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

    SECURITY: This endpoint is only enabled when FLASK_ENV=development (#98)
    Uses whitelist approach - disabled by default unless explicitly enabled.
    """
    # Only enable in development mode (whitelist approach)
    if not IS_DEVELOPMENT:
        return jsonify({"error": "Not found"}), 404

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
        
        # Get real stats from run tracker (#72)
        duration_text = "—"
        requests_text = "—"
        latest_run = run_tracker.get_latest_run(retailer_id)
        if latest_run:
            run_stats = latest_run.get("stats", {})
            duration_secs = run_stats.get("duration_seconds", 0)
            if duration_secs > 0:
                if duration_secs < 60:
                    duration_text = f"{duration_secs}s"
                elif duration_secs < 3600:
                    duration_text = f"{duration_secs // 60}m {duration_secs % 60}s"
                else:
                    hours = duration_secs // 3600
                    mins = (duration_secs % 3600) // 60
                    duration_text = f"{hours}h {mins}m"

            requests_made = run_stats.get("requests_made", 0)
            if requests_made > 0:
                requests_text = formatNumber(requests_made)

        stats = {
            "stat1_value": formatNumber(completed) if total > 0 else "—",
            "stat1_label": "Stores",
            "stat2_value": duration_text,
            "stat2_label": "Duration",
            "stat3_value": requests_text,
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


# Maximum allowed limit for stores per scrape
MAX_SCRAPER_LIMIT = 100000

# Valid proxy modes
VALID_PROXY_MODES = {'direct', 'residential', 'web_scraper_api', None}


def _validate_scraper_options(data: dict) -> tuple:
    """Validate scraper start options.

    Returns:
        Tuple of (is_valid, error_message_or_options)
    """
    retailer = data.get('retailer')

    if not retailer:
        return False, "Missing required field: retailer"

    if not isinstance(retailer, str):
        return False, "Field 'retailer' must be a string"

    # Validate retailer name format (allow 'all' as special case)
    if retailer != 'all' and not re.match(r'^[a-z][a-z0-9_]*$', retailer):
        return False, f"Invalid retailer name format: '{retailer}'"

    # Validate limit (#58)
    limit = data.get('limit')
    if limit is not None:
        # Explicitly exclude booleans since bool is a subclass of int in Python
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            return False, "Field 'limit' must be a positive integer"
        if limit > MAX_SCRAPER_LIMIT:
            return False, f"Field 'limit' exceeds maximum allowed value ({MAX_SCRAPER_LIMIT})"

    # Validate proxy mode (#58)
    proxy = data.get('proxy')
    if proxy is not None and proxy not in VALID_PROXY_MODES:
        return False, f"Invalid proxy mode '{proxy}'. Must be one of: direct, residential, web_scraper_api"

    # Validate boolean fields
    for field in ['resume', 'incremental', 'test', 'render_js', 'verbose']:
        value = data.get(field)
        if value is not None and not isinstance(value, bool):
            return False, f"Field '{field}' must be a boolean"

    # Validate proxy_country format
    proxy_country = data.get('proxy_country', 'us')
    if not isinstance(proxy_country, str) or not re.match(r'^[a-z]{2}$', proxy_country.lower()):
        return False, "Field 'proxy_country' must be a 2-letter country code"

    # Validate render_js requires web_scraper_api proxy mode (#7 review feedback)
    render_js = data.get('render_js', False)
    if render_js and proxy != 'web_scraper_api':
        return False, "--render-js requires proxy mode 'web_scraper_api'"

    # Validate test + limit conflict (matches CLI validation)
    test = data.get('test', False)
    if test and limit is not None:
        return False, "Cannot use 'test' with 'limit' (test mode already sets limit to 10)"

    # Build validated options
    options = {
        'resume': bool(data.get('resume', False)),
        'incremental': bool(data.get('incremental', False)),
        'limit': limit,
        'test': bool(data.get('test', False)),
        'proxy': proxy,
        'render_js': bool(data.get('render_js', False)),
        'proxy_country': proxy_country.lower(),
        'verbose': bool(data.get('verbose', False))
    }

    return True, options


@app.route('/api/scraper/start', methods=['POST'])
@limiter.limit("5 per minute")  # Rate limit scraper starts (#93)
@require_api_key  # API key auth for mutating endpoints (#92)
@require_json
def api_scraper_start():
    """Start scraper(s)

    Request body:
    {
        "retailer": "verizon",  # Required: retailer name or "all"
        "resume": true,         # Optional: resume from checkpoint (default: false)
        "incremental": false,   # Optional: incremental mode (default: false)
        "limit": null,          # Optional: limit number of stores (default: null, max: 100000)
        "test": false,          # Optional: test mode with 10 stores (default: false)
        "proxy": "direct",      # Optional: proxy mode (direct/residential/web_scraper_api)
        "render_js": false,     # Optional: enable JS rendering (default: false)
        "proxy_country": "us",  # Optional: proxy country code (default: "us")
        "verbose": false        # Optional: verbose logging (default: false)
    }
    """
    try:
        data = request.get_json() or {}

        # Validate all options (#58)
        is_valid, result = _validate_scraper_options(data)
        if not is_valid:
            return jsonify({"error": result}), 400

        retailer = data.get('retailer')
        options = result
        
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
@limiter.limit("10 per minute")  # Rate limit scraper stops (#93)
@require_api_key  # API key auth for mutating endpoints (#92)
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
        
        # Validate timeout is a proper integer, not a boolean
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
            return jsonify({"error": "Field 'timeout' must be a positive integer"}), 400
        
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
@limiter.limit("5 per minute")  # Rate limit scraper restarts (#93)
@require_api_key  # API key auth for mutating endpoints (#92)
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
        
        # Validate timeout is a proper integer, not a boolean
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
            return jsonify({"error": "Field 'timeout' must be a positive integer"}), 400
        
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


# Maximum allowed limit for run history queries
MAX_RUN_HISTORY_LIMIT = 100


@app.route('/api/runs/<retailer>')
def api_run_history(retailer):
    """Get historical runs for a retailer

    Query params:
        limit: Number of runs to return (default: 10, max: 100)
    """
    try:
        # Validate retailer name format
        if not re.match(r'^[a-z][a-z0-9_]*$', retailer):
            return jsonify({"error": "Invalid retailer name format"}), 400

        config = status.load_retailers_config()
        if retailer not in config:
            return jsonify({"error": f"Unknown retailer: {retailer}"}), 404

        # Bound the limit parameter (#99)
        limit = request.args.get('limit', 10, type=int)
        limit = max(limit, 1)
        limit = min(limit, MAX_RUN_HISTORY_LIMIT)

        runs = run_tracker.get_run_history(retailer, limit=limit)

        return jsonify({
            "retailer": retailer,
            "runs": runs,
            "count": len(runs)
        })
    except Exception as e:
        return safe_error_response(e, "API request")


# Maximum allowed values for log API parameters
MAX_LOG_TAIL = 10000
MAX_LOG_OFFSET = 1000000  # 1 million lines


def read_log_tail(filepath: Path, lines: int = 200) -> tuple:
    """Read last N lines efficiently without loading entire file (#70).

    Args:
        filepath: Path to log file
        lines: Number of lines to read from end

    Returns:
        Tuple of (list of lines, total line count estimate)
    """
    with open(filepath, 'rb') as f:
        # Get file size
        f.seek(0, 2)
        file_size = f.tell()

        if file_size == 0:
            return [], 0

        # Read in blocks from the end
        block_size = 8192
        blocks = []
        remaining_size = file_size

        # Estimate: read enough to get requested lines (assuming ~100 bytes/line avg)
        bytes_needed = lines * 200

        while remaining_size > 0 and sum(len(b) for b in blocks) < bytes_needed:
            read_size = min(block_size, remaining_size)
            remaining_size -= read_size
            f.seek(remaining_size)
            blocks.append(f.read(read_size))

        # Combine and decode
        content = b''.join(reversed(blocks)).decode('utf-8', errors='replace')
        all_lines = content.splitlines(keepends=True)

        # Estimate total lines (rough approximation based on file size / avg line length)
        avg_line_len = len(content) / max(len(all_lines), 1) if all_lines else 100
        estimated_total = int(file_size / avg_line_len)

        # Return last N lines
        return all_lines[-lines:], estimated_total


@app.route('/api/logs/<retailer>/<run_id>')
def api_get_logs(retailer, run_id):
    """Get logs for a specific run

    Query params:
        tail: Number of lines to return from end (default: all, max: 10000)
        offset: Line number to start from for incremental fetching (default: 0, max: 1000000)

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

        # Bound tail and offset parameters (#100)
        tail = request.args.get('tail', type=int)
        offset = request.args.get('offset', type=int, default=0)

        # Apply bounds
        if tail is not None:
            tail = max(tail, 1)
            tail = min(tail, MAX_LOG_TAIL)

        offset = max(offset, 0)
        offset = min(offset, MAX_LOG_OFFSET)

        # Use efficient tail reading when offset is 0 and tail is specified (#70)
        if offset == 0 and tail is not None:
            lines, total_lines = read_log_tail(log_file, tail)
        else:
            # Fall back to full read for offset-based queries
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


@app.route('/api/changes/<retailer>')
def api_get_changes(retailer):
    """Get latest change report for a retailer (#79)

    Returns the most recent change detection report if available.

    Path params:
        retailer: Retailer ID (verizon, att, target, etc.)

    Response:
        {
            "retailer": "verizon",
            "has_changes": true,
            "report": { ... change report data ... }
        }
    """
    try:
        # Validate retailer name format
        if not re.match(r'^[a-z][a-z0-9_]*$', retailer):
            return jsonify({"error": "Invalid retailer name format"}), 400

        config = status.load_retailers_config()
        if retailer not in config:
            return jsonify({"error": f"Unknown retailer: {retailer}"}), 404

        history_dir = Path(f'data/{retailer}/history')
        if not history_dir.exists():
            return jsonify({
                "retailer": retailer,
                "has_changes": False,
                "report": None,
                "message": "No change history available"
            })

        # Find the latest change report
        change_files = list(history_dir.glob('changes_*.json'))
        if not change_files:
            return jsonify({
                "retailer": retailer,
                "has_changes": False,
                "report": None,
                "message": "No change reports found"
            })

        # Get most recent by modification time
        latest = max(change_files, key=lambda p: p.stat().st_mtime)

        with open(latest, 'r', encoding='utf-8') as f:
            report = json.load(f)

        has_changes = (
            len(report.get('new_stores', [])) > 0 or
            len(report.get('closed_stores', [])) > 0 or
            len(report.get('modified_stores', [])) > 0
        )

        return jsonify({
            "retailer": retailer,
            "has_changes": has_changes,
            "report": report,
            "report_file": latest.name
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
@limiter.limit("10 per minute")  # Rate limit config updates (#93)
@require_api_key  # API key auth for mutating endpoints (#92)
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

            # Return success with restart notice (#83)
            return jsonify({
                "message": "Configuration saved. Restart running scrapers to apply changes.",
                "backup": str(backup_path),
                "requires_restart": True
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

# Threshold for using streaming exports (50MB file size) (#74)
STREAMING_THRESHOLD = 50 * 1024 * 1024


def generate_csv_stream(stores_file: Path, fieldnames: list = None):
    """Generate CSV content as a stream for large files (#74).

    Uses ijson for memory-efficient streaming of large JSON files.

    Args:
        stores_file: Path to JSON file containing stores
        fieldnames: Optional list of fields to include

    Yields:
        CSV lines as strings
    """
    import csv
    import io
    import ijson

    # Get fieldnames from config or use streaming discovery with limits
    if not fieldnames:
        # Only read first item for fieldnames, don't load all
        with open(stores_file, 'rb') as f:
            for first_item in ijson.items(f, 'item'):
                fieldnames = list(first_item.keys())
                break  # Stop after first item
        if not fieldnames:
            return  # Empty file

    # Yield header
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    yield output.getvalue()

    # Stream items using ijson (memory-efficient)
    chunk = []
    chunk_size = 100
    with open(stores_file, 'rb') as f:
        for store in ijson.items(f, 'item'):
            # Sanitize CSV values using shared sanitizer to prevent formula injection
            sanitized = {k: sanitize_csv_value(v) for k, v in store.items()}
            chunk.append(sanitized)

            if len(chunk) >= chunk_size:
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
                writer.writerows(chunk)
                yield output.getvalue()
                chunk = []

    # Yield remaining items
    if chunk:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writerows(chunk)
        yield output.getvalue()


def generate_json_stream(stores_file: Path):
    """Generate JSON content as a stream for large files.

    Uses ijson for memory-efficient streaming of large JSON files.

    Args:
        stores_file: Path to JSON file containing stores

    Yields:
        JSON chunks as strings
    """
    import ijson

    yield '[\n'
    
    first_item = True
    with open(stores_file, 'rb') as f:
        for store in ijson.items(f, 'item'):
            if not first_item:
                yield ',\n'
            else:
                first_item = False
            yield json.dumps(store, indent=2, ensure_ascii=False)
    
    yield '\n]'


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

        # Get retailer config for field mapping
        retailer_config = config.get(retailer, {})

        # Generate filename
        timestamp = datetime.now().strftime("%Y-%m-%d")
        ext = FILE_EXTENSIONS.get(export_format, export_format)
        filename = f"{retailer}_stores_{timestamp}.{ext}"

        # Check file size for streaming decision (#74)
        file_size = stores_file.stat().st_size

        # Use streaming for large files (#74)
        if file_size > STREAMING_THRESHOLD:
            if export_format == 'csv':
                fieldnames = retailer_config.get('output_fields')
                return Response(
                    stream_with_context(generate_csv_stream(stores_file, fieldnames)),
                    mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={filename}'}
                )
            elif export_format == 'json':
                return Response(
                    stream_with_context(generate_json_stream(stores_file)),
                    mimetype='application/json',
                    headers={'Content-Disposition': f'attachment; filename={filename}'}
                )
            # Note: Excel and GeoJSON formats require full dataset in memory
            # (Excel workbook generation, GeoJSON wrapping). Fall through to in-memory export.

        # Standard in-memory export for smaller files or Excel/GeoJSON
        with open(stores_file, 'r', encoding='utf-8') as f:
            stores = json.load(f)

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
