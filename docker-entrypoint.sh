#!/bin/bash
set -e

# Docker entrypoint script for retail-store-scraper
# Ensures proper permissions and directory structure on container startup

echo "🔧 Setting up directories..."

# Create all necessary data directories
mkdir -p /app/data/{att,verizon,target,tmobile,walmart,bestbuy}/{output,checkpoints,runs,history}
mkdir -p /app/logs

# Create Flask secret file directory
mkdir -p /app/dashboard
touch /app/.flask_secret 2>/dev/null || true

# Fix permissions if running as root (for initial setup)
if [ "$(id -u)" = "0" ]; then
    echo "📝 Fixing permissions (running as root)..."
    chown -R 1000:1000 /app/data /app/logs /app/.flask_secret 2>/dev/null || true
    chmod -R 755 /app/data /app/logs 2>/dev/null || true
    chmod 644 /app/.flask_secret 2>/dev/null || true
else
    echo "📝 Running as non-root user ($(id -u):$(id -g))"
fi

# Display directory structure
echo "✅ Directory setup complete:"
ls -la /app/data/ 2>/dev/null || echo "  (data directory will be created)"

# Execute the main command
exec "$@"
