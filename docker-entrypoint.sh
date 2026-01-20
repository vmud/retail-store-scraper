#!/bin/bash
set -e

# Docker entrypoint script for retail-store-scraper
# Ensures proper permissions and directory structure on container startup

echo "🔧 Verifying directories..."

# Attempt to create missing directories (fails silently if no permissions)
# Directories are pre-created in Dockerfile; this handles edge cases
mkdir -p /app/data/{att,verizon,target,tmobile,walmart,bestbuy}/{output,checkpoints,runs,history} 2>/dev/null || true
mkdir -p /app/logs 2>/dev/null || true
mkdir -p /app/dashboard 2>/dev/null || true
touch /app/.flask_secret 2>/dev/null || true

# If running as root (user override), fix permissions
if [ "$(id -u)" = "0" ]; then
    echo "📝 Running as root - fixing permissions..."
    chown -R 1000:1000 /app/data /app/logs /app/.flask_secret 2>/dev/null || true
    chmod -R 755 /app/data /app/logs 2>/dev/null || true
    chmod 644 /app/.flask_secret 2>/dev/null || true
fi

# Display directory structure
echo "✅ Directory setup complete:"
ls -la /app/data/ 2>/dev/null || echo "  (data directory will be created)"

# Execute the main command
exec "$@"
