#!/usr/bin/env bash
# Load secrets from 1Password for local development
#
# Usage:
#   source scripts/load-secrets.sh
#   python run.py --retailer verizon --test
#
# Prerequisites:
#   - 1Password CLI installed: brew install 1password-cli
#   - Signed in: op signin (or use biometric unlock)
#   - Service account: export OP_SERVICE_ACCOUNT_TOKEN="..."
#
# The script supports both interactive (op signin) and service account modes.

set -e

VAULT="DEV"

echo "Loading secrets from 1Password vault: $VAULT"

# Check if 1Password CLI is installed
if ! command -v op &> /dev/null; then
    echo "Error: 1Password CLI not installed"
    echo "Install with: brew install 1password-cli"
    exit 1
fi

# Check authentication
if ! op whoami &> /dev/null; then
    if [ -n "$OP_SERVICE_ACCOUNT_TOKEN" ]; then
        echo "Using service account authentication"
    else
        echo "Not signed in. Please run: op signin"
        exit 1
    fi
fi

# Function to safely read a secret (returns empty string if not found)
read_secret() {
    local item="$1"
    local field="${2:-credential}"
    op read "op://$VAULT/$item/$field" 2>/dev/null || echo ""
}

# Load Sentry
export SENTRY_DSN=$(read_secret "SENTRY_DSN")
if [ -n "$SENTRY_DSN" ]; then
    echo "✓ SENTRY_DSN loaded"
else
    echo "⚠ SENTRY_DSN not found in 1Password (Sentry will be disabled)"
fi

# Set environment for local development
export SENTRY_ENVIRONMENT="${SENTRY_ENVIRONMENT:-development}"
echo "✓ SENTRY_ENVIRONMENT=$SENTRY_ENVIRONMENT"

# Optionally load Oxylabs credentials
export OXYLABS_RESIDENTIAL_USERNAME=$(read_secret "OXYLABS_RESIDENTIAL" "username")
export OXYLABS_RESIDENTIAL_PASSWORD=$(read_secret "OXYLABS_RESIDENTIAL" "credential")
if [ -n "$OXYLABS_RESIDENTIAL_USERNAME" ]; then
    echo "✓ OXYLABS_RESIDENTIAL credentials loaded"
fi

export OXYLABS_SCRAPER_API_USERNAME=$(read_secret "OXYLABS_SCRAPER_API" "username")
export OXYLABS_SCRAPER_API_PASSWORD=$(read_secret "OXYLABS_SCRAPER_API" "credential")
if [ -n "$OXYLABS_SCRAPER_API_USERNAME" ]; then
    echo "✓ OXYLABS_SCRAPER_API credentials loaded"
fi

echo ""
echo "Secrets loaded. You can now run:"
echo "  python run.py --retailer verizon --test"
echo ""
