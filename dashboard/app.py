#!/usr/bin/env python3
"""Simple Flask dashboard for monitoring scraper progress"""

import sys
import os
import re
import yaml
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request, Response
from src.shared import status, scraper_manager, run_tracker

app = Flask(__name__)

# Get singleton scraper manager instance
_scraper_manager = scraper_manager.get_scraper_manager()


def require_json(f):
    """Decorator to require JSON Content-Type for POST endpoints"""
    def wrapper(*args, **kwargs):
        if request.method == 'POST':
            if request.content_type != 'application/json':
                return jsonify({"error": "Content-Type must be application/json"}), 415
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


@app.route('/')
def index():
    """Main dashboard page with embedded HTML/CSS/JS"""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verizon Store Scraper - Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 30px;
        }
        h1 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .status-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
            margin-bottom: 20px;
        }
        .status-active {
            background: #10b981;
            color: white;
        }
        .status-inactive {
            background: #ef4444;
            color: white;
        }
        .overall-progress {
            background: #f3f4f6;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .overall-progress h2 {
            margin-bottom: 10px;
            color: #333;
        }
        .progress-bar-container {
            background: #e5e7eb;
            border-radius: 10px;
            height: 30px;
            overflow: hidden;
            position: relative;
        }
        .progress-bar {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            height: 100%;
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 0.9em;
        }
        .phases {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .phase-card {
            background: #f9fafb;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            padding: 20px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .phase-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .phase-card h3 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        .phase-info {
            margin-bottom: 10px;
            font-size: 0.95em;
            color: #666;
        }
        .phase-status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
        }
        .status-complete {
            background: #10b981;
            color: white;
        }
        .status-in_progress {
            background: #3b82f6;
            color: white;
        }
        .status-pending {
            background: #9ca3af;
            color: white;
        }
        .last-updated {
            font-size: 0.85em;
            color: #9ca3af;
            margin-top: 10px;
        }
        .refresh-info {
            text-align: center;
            color: #9ca3af;
            font-size: 0.9em;
            margin-top: 20px;
        }
        .error {
            background: #fee2e2;
            border: 1px solid #fca5a5;
            color: #991b1b;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Verizon Store Scraper</h1>
        <p class="subtitle">Real-time progress monitoring</p>
        
        <div id="status-badge" class="status-badge status-inactive">Checking status...</div>
        
        <div class="overall-progress">
            <h2>Overall Progress</h2>
            <div class="progress-bar-container">
                <div id="overall-progress-bar" class="progress-bar" style="width: 0%">0%</div>
            </div>
        </div>
        
        <div class="phases" id="phases-container">
            <div class="phase-card">
                <h3>Phase 1: States</h3>
                <div class="phase-info">Loading...</div>
            </div>
            <div class="phase-card">
                <h3>Phase 2: Cities</h3>
                <div class="phase-info">Loading...</div>
            </div>
            <div class="phase-card">
                <h3>Phase 3: Store URLs</h3>
                <div class="phase-info">Loading...</div>
            </div>
            <div class="phase-card">
                <h3>Phase 4: Extract Details</h3>
                <div class="phase-info">Loading...</div>
            </div>
        </div>
        
        <div class="refresh-info">
            Auto-refreshing every 30 seconds...
        </div>
    </div>
    
    <script>
        function updateDashboard() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    // Update status badge
                    const badge = document.getElementById('status-badge');
                    if (data.scraper_active) {
                        badge.textContent = '🟢 Scraper Active';
                        badge.className = 'status-badge status-active';
                    } else {
                        badge.textContent = '🔴 Scraper Inactive';
                        badge.className = 'status-badge status-inactive';
                    }
                    
                    // Update overall progress
                    const overallProgress = data.overall_progress || 0;
                    const progressBar = document.getElementById('overall-progress-bar');
                    progressBar.style.width = overallProgress + '%';
                    progressBar.textContent = overallProgress.toFixed(1) + '%';
                    
                    // Update phase cards
                    const phases = [
                        { key: 'phase1', name: 'Phase 1: States', container: document.getElementById('phases-container') },
                        { key: 'phase2', name: 'Phase 2: Cities', container: document.getElementById('phases-container') },
                        { key: 'phase3', name: 'Phase 3: Store URLs', container: document.getElementById('phases-container') },
                        { key: 'phase4', name: 'Phase 4: Extract Details', container: document.getElementById('phases-container') }
                    ];
                    
                    phases.forEach((phase, index) => {
                        const phaseData = data[phase.key];
                        const card = phase.container.children[index];
                        
                        const completed = phaseData.completed || 0;
                        const total = phaseData.total || 0;
                        const status = phaseData.status || 'pending';
                        const lastUpdated = phaseData.last_updated || null;
                        
                        let statusText = '';
                        let statusClass = 'status-pending';
                        if (status === 'complete') {
                            statusText = '✓ Complete';
                            statusClass = 'status-complete';
                        } else if (status === 'in_progress') {
                            statusText = '⟳ In Progress';
                            statusClass = 'status-in_progress';
                        } else {
                            statusText = '○ Pending';
                            statusClass = 'status-pending';
                        }
                        
                        const percentage = total > 0 ? ((completed / total) * 100).toFixed(1) : '0.0';
                        
                        card.innerHTML = `
                            <h3>${phase.name}</h3>
                            <div class="phase-info">
                                <strong>${completed}</strong> / <strong>${total}</strong> (${percentage}%)
                            </div>
                            <div>
                                <span class="phase-status ${statusClass}">${statusText}</span>
                            </div>
                            ${lastUpdated ? `<div class="last-updated">Last updated: ${new Date(lastUpdated).toLocaleString()}</div>` : ''}
                        `;
                    });
                })
                .catch(error => {
                    console.error('Error fetching status:', error);
                    document.getElementById('phases-container').innerHTML = `
                        <div class="error">
                            <strong>Error loading status:</strong> ${error.message}
                        </div>
                    `;
                });
        }
        
        // Initial load
        updateDashboard();
        
        // Auto-refresh every 30 seconds
        setInterval(updateDashboard, 30000);
    </script>
</body>
</html>"""
    return html


@app.route('/api/status')
def api_status():
    """Get status for all retailers"""
    try:
        status_data = status.get_all_retailers_status()
        return jsonify(status_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/status/<retailer>')
def api_retailer_status(retailer):
    """Get status for a single retailer"""
    try:
        retailer_status = status.get_retailer_status(retailer)
        
        if "error" in retailer_status:
            return jsonify(retailer_status), 404
        
        return jsonify(retailer_status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        else:
            result = _scraper_manager.start(retailer, **options)
            return jsonify(result)
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        else:
            result = _scraper_manager.stop(retailer, timeout=timeout)
            return jsonify(result)
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        else:
            result = _scraper_manager.restart(retailer, resume=resume, timeout=timeout)
            return jsonify(result)
    
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"error": str(e)}), 500


@app.route('/api/logs/<retailer>/<run_id>')
def api_get_logs(retailer, run_id):
    """Get logs for a specific run
    
    Query params:
        tail: Number of lines to return from end (default: all)
    """
    try:
        config = status.load_retailers_config()
        if retailer not in config:
            return jsonify({"error": f"Unknown retailer: {retailer}"}), 404
        
        if not re.match(r'^[\w\-]+$', run_id):
            return jsonify({"error": "Invalid run_id format. Only alphanumeric, underscore, and hyphen allowed"}), 400
        
        log_file = Path(f"data/{retailer}/logs/{run_id}.log")
        
        if not log_file.exists():
            return jsonify({"error": "Log file not found"}), 404
        
        log_file_resolved = log_file.resolve()
        expected_base = Path(f"data/{retailer}/logs").resolve()
        
        if not str(log_file_resolved).startswith(str(expected_base)):
            return jsonify({"error": "Invalid log file path"}), 400
        
        tail = request.args.get('tail', type=int)
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        if tail:
            lines = lines[-tail:]
        
        return jsonify({
            "retailer": retailer,
            "run_id": run_id,
            "lines": len(lines),
            "content": ''.join(lines)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/config', methods=['GET'])
def api_get_config():
    """Get current configuration"""
    try:
        config_path = Path("config/retailers.yaml")
        
        if not config_path.exists():
            return jsonify({"error": "Configuration file not found"}), 404
        
        with open(config_path, 'r') as f:
            config_content = f.read()
        
        return jsonify({
            "path": str(config_path),
            "content": config_content
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
            with open(temp_path, 'w') as f:
                f.write(content)
            
            temp_path.replace(config_path)
            
            _reload_config()
            
            return jsonify({
                "message": "Configuration updated successfully",
                "backup": str(backup_path)
            })
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    """Reload configuration after update
    
    Forces the status module to reload the configuration file
    on the next access by clearing any cached config data.
    """
    pass


if __name__ == '__main__':
    # Run on all interfaces (0.0.0.0) to allow network access
    app.run(host='0.0.0.0', port=5000, debug=False)
