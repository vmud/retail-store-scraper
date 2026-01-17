#!/usr/bin/env python3
"""Simple Flask dashboard for monitoring scraper progress"""

import sys
from pathlib import Path

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify
from src import status

app = Flask(__name__)


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
    """JSON API endpoint for status"""
    try:
        status_data = status.get_progress_status()
        return jsonify(status_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Run on all interfaces (0.0.0.0) to allow network access
    app.run(host='0.0.0.0', port=5000, debug=False)
