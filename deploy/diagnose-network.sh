#!/bin/bash
#
# Network Diagnostic Script for Dashboard Access
# Run this on your dev server to diagnose why dashboard is not accessible
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "Dashboard Network Diagnostics"
echo "=========================================="
echo ""

# Check 1: Docker containers running
echo -e "${BLUE}[1/7] Checking Docker containers...${NC}"
if command -v docker &> /dev/null; then
    if docker compose ps | grep -q "dashboard"; then
        STATUS=$(docker compose ps | grep dashboard | awk '{print $7}')
        if [[ "$STATUS" == *"running"* ]] || [[ "$STATUS" == *"Up"* ]]; then
            echo -e "${GREEN}✓ Dashboard container is running${NC}"
        else
            echo -e "${RED}✗ Dashboard container is not running (Status: $STATUS)${NC}"
            echo "  Fix: docker compose up -d dashboard"
        fi
    else
        echo -e "${RED}✗ Dashboard container not found${NC}"
        echo "  Fix: docker compose up -d"
    fi

    # Show container details
    echo ""
    docker compose ps
else
    echo -e "${YELLOW}⚠ Docker not found, skipping container check${NC}"
fi

echo ""

# Check 2: Port listening
echo -e "${BLUE}[2/7] Checking if port 5001 is listening...${NC}"
if command -v netstat &> /dev/null; then
    if netstat -tuln | grep -q ":5001"; then
        echo -e "${GREEN}✓ Port 5001 is listening${NC}"
        netstat -tuln | grep ":5001"
    else
        echo -e "${RED}✗ Port 5001 is NOT listening${NC}"
        echo "  This means Flask/dashboard is not running"
    fi
elif command -v ss &> /dev/null; then
    if ss -tuln | grep -q ":5001"; then
        echo -e "${GREEN}✓ Port 5001 is listening${NC}"
        ss -tuln | grep ":5001"
    else
        echo -e "${RED}✗ Port 5001 is NOT listening${NC}"
        echo "  This means Flask/dashboard is not running"
    fi
else
    echo -e "${YELLOW}⚠ netstat/ss not found, skipping port check${NC}"
fi

echo ""

# Check 3: Local access
echo -e "${BLUE}[3/7] Testing local access (localhost:5001)...${NC}"
if command -v curl &> /dev/null; then
    if curl -s -f http://localhost:5001/api/status > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Dashboard accessible locally${NC}"
        echo "  Response: $(curl -s http://localhost:5001/api/status | head -c 100)..."
    else
        echo -e "${RED}✗ Dashboard NOT accessible locally${NC}"
        echo "  This suggests Flask is not running or crashed"
        echo "  Check logs: docker compose logs dashboard"
    fi
else
    echo -e "${YELLOW}⚠ curl not found, install with: apt-get install curl${NC}"
fi

echo ""

# Check 4: Docker port mapping
echo -e "${BLUE}[4/7] Checking Docker port mapping...${NC}"
if command -v docker &> /dev/null; then
    MAPPING=$(docker compose ps dashboard | grep "5001" | grep -oE '0.0.0.0:[0-9]+->[0-9]+' || echo "")
    if [ -n "$MAPPING" ]; then
        echo -e "${GREEN}✓ Port mapping configured: $MAPPING${NC}"
    else
        echo -e "${RED}✗ Port 5001 not mapped${NC}"
        echo "  Check docker-compose.yml ports section"
    fi
fi

echo ""

# Check 5: Firewall (ufw)
echo -e "${BLUE}[5/7] Checking firewall (ufw)...${NC}"
if command -v ufw &> /dev/null; then
    UFW_STATUS=$(sudo ufw status 2>/dev/null || echo "inactive")
    if [[ "$UFW_STATUS" == *"inactive"* ]]; then
        echo -e "${GREEN}✓ Firewall is inactive (no blocking)${NC}"
    else
        if echo "$UFW_STATUS" | grep -q "5001"; then
            echo -e "${GREEN}✓ Port 5001 is allowed in firewall${NC}"
        else
            echo -e "${RED}✗ Port 5001 is NOT allowed in firewall${NC}"
            echo "  Fix: sudo ufw allow 5001/tcp"
            echo "  Or: sudo ufw allow from 192.168.1.0/24 to any port 5001"
        fi
    fi
else
    echo -e "${YELLOW}⚠ ufw not found, checking iptables...${NC}"
    if command -v iptables &> /dev/null; then
        if sudo iptables -L -n | grep -q "5001"; then
            echo -e "${GREEN}✓ Found iptables rule for 5001${NC}"
        else
            echo -e "${YELLOW}⚠ No iptables rule found for 5001${NC}"
            echo "  May need to add firewall rule"
        fi
    fi
fi

echo ""

# Check 6: Network interfaces
echo -e "${BLUE}[6/7] Checking network interfaces...${NC}"
if command -v ip &> /dev/null; then
    echo "Available IP addresses:"
    ip addr show | grep "inet " | awk '{print "  " $2}'
elif command -v ifconfig &> /dev/null; then
    echo "Available IP addresses:"
    ifconfig | grep "inet " | awk '{print "  " $2}'
fi

echo ""

# Check 7: Dashboard logs
echo -e "${BLUE}[7/7] Checking dashboard logs (last 20 lines)...${NC}"
if command -v docker &> /dev/null; then
    echo "--- Dashboard Container Logs ---"
    docker compose logs --tail=20 dashboard 2>/dev/null || echo "Could not retrieve logs"
fi

echo ""
echo "=========================================="
echo "Diagnostic Summary"
echo "=========================================="
echo ""
echo "Common fixes:"
echo ""
echo "1. If container not running:"
echo "   docker compose up -d dashboard"
echo ""
echo "2. If firewall blocking:"
echo "   sudo ufw allow 5001/tcp"
echo "   # Or restrict to local network:"
echo "   sudo ufw allow from 192.168.1.0/24 to any port 5001"
echo ""
echo "3. If port not listening:"
echo "   Check logs: docker compose logs dashboard"
echo "   Restart: docker compose restart dashboard"
echo ""
echo "4. Test local access first:"
echo "   curl http://localhost:5001/api/status"
echo ""
echo "5. Then test from your workstation:"
echo "   curl http://192.168.1.80:5001/api/status"
echo "   # Or open browser: http://192.168.1.80:5001"
echo ""
