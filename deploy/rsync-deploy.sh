#!/bin/bash
#
# rsync Deployment Script
# Syncs files from workstation to remote dev server
#
# Usage: ./deploy/rsync-deploy.sh user@dev-server-ip [destination-path]
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# Parse arguments
if [ $# -lt 1 ]; then
    echo -e "${RED}Error: Missing required argument${NC}"
    echo "Usage: $0 user@dev-server-ip [destination-path]"
    echo ""
    echo "Examples:"
    echo "  $0 ubuntu@192.168.1.100"
    echo "  $0 ubuntu@192.168.1.100 /opt/retail-store-scraper"
    exit 1
fi

REMOTE_HOST="$1"
REMOTE_PATH="${2:-/opt/retail-store-scraper}"

echo "=========================================="
echo "rsync Deployment Script"
echo "=========================================="
echo ""
echo "Source:      $REPO_DIR"
echo "Destination: $REMOTE_HOST:$REMOTE_PATH"
echo ""

# Confirm before proceeding
read -p "Continue with deployment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# Test SSH connection
echo -e "${YELLOW}Testing SSH connection...${NC}"
if ssh -o ConnectTimeout=5 "$REMOTE_HOST" "echo 'SSH connection successful'" 2>/dev/null; then
    echo -e "${GREEN}✓ SSH connection OK${NC}"
else
    echo -e "${RED}✗ SSH connection failed${NC}"
    echo "Please check:"
    echo "  - SSH server is running on $REMOTE_HOST"
    echo "  - Your SSH credentials are correct"
    echo "  - Network connectivity to the server"
    exit 1
fi

# Create remote directory if it doesn't exist
echo -e "${YELLOW}Creating remote directory...${NC}"
ssh "$REMOTE_HOST" "sudo mkdir -p $REMOTE_PATH && sudo chown $USER:$USER $REMOTE_PATH" || {
    echo -e "${RED}✗ Failed to create remote directory${NC}"
    exit 1
}
echo -e "${GREEN}✓ Remote directory ready${NC}"

# Sync files
echo -e "${YELLOW}Syncing files...${NC}"
rsync -avz --progress \
    --exclude 'venv/' \
    --exclude 'data/' \
    --exclude 'logs/' \
    --exclude '.git/' \
    --exclude 'node_modules/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache/' \
    --exclude '.coverage' \
    --exclude 'htmlcov/' \
    --exclude '.env' \
    --exclude '.DS_Store' \
    --exclude '*.log' \
    --exclude 'dist/' \
    --exclude 'build/' \
    --exclude '*.egg-info/' \
    "$REPO_DIR/" \
    "$REMOTE_HOST:$REMOTE_PATH/" || {
    echo -e "${RED}✗ rsync failed${NC}"
    exit 1
}

echo -e "${GREEN}✓ Files synced successfully${NC}"

# Set permissions
echo -e "${YELLOW}Setting permissions...${NC}"
ssh "$REMOTE_HOST" "chmod -R 755 $REMOTE_PATH" || {
    echo -e "${YELLOW}⚠ Warning: Failed to set permissions (non-critical)${NC}"
}

echo ""
echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. SSH into the server:"
echo "   ssh $REMOTE_HOST"
echo ""
echo "2. Configure environment:"
echo "   cd $REMOTE_PATH"
echo "   cp .env.example .env"
echo "   nano .env  # Add your credentials"
echo ""
echo "3. Deploy using Docker:"
echo "   docker compose build"
echo "   docker compose up -d"
echo ""
echo "4. Or deploy using Python:"
echo "   python3.11 -m venv venv"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo "   python run.py --all --test"
echo ""
echo "5. Access dashboard:"
echo "   http://$REMOTE_HOST:5001"
echo ""
echo "For detailed instructions, see DEPLOYMENT.md"
echo ""
