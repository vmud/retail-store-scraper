#!/bin/bash

# Security fixes verification test script
# Tests all critical security improvements

BASE_URL="${1:-http://localhost:5000}"
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "======================================"
echo "Security Fixes Verification"
echo "======================================"
echo ""

# Test 1: Content-Type Validation
echo "Test 1: Content-Type Validation on POST endpoints"
response=$(curl -s -X POST "$BASE_URL/api/scraper/start" \
  -d '{"retailer": "verizon"}')
if echo "$response" | grep -q "Content-Type must be application/json"; then
    echo -e "${GREEN}✓ PASS${NC}: Content-Type validation working"
else
    echo -e "${RED}✗ FAIL${NC}: Content-Type validation not working"
    echo "Response: $response"
fi
echo ""

# Test 2: Retailer Validation on /api/runs
echo "Test 2: Retailer validation on /api/runs endpoint"
response=$(curl -s "$BASE_URL/api/runs/invalid_retailer_xyz")
if echo "$response" | grep -q "Unknown retailer"; then
    echo -e "${GREEN}✓ PASS${NC}: Retailer validation working"
else
    echo -e "${RED}✗ FAIL${NC}: Retailer validation not working"
    echo "Response: $response"
fi
echo ""

# Test 3: Restart Endpoint Batch Support
echo "Test 3: Restart endpoint with 'all' retailers"
response=$(curl -s -X POST "$BASE_URL/api/scraper/restart" \
  -H "Content-Type: application/json" \
  -d '{"retailer": "all", "resume": false}')
if echo "$response" | grep -q "Restarted"; then
    echo -e "${GREEN}✓ PASS${NC}: Batch restart working"
    # Stop all scrapers immediately
    curl -s -X POST "$BASE_URL/api/scraper/stop" \
      -H "Content-Type: application/json" \
      -d '{"retailer": "all"}' > /dev/null 2>&1
else
    echo -e "${RED}✗ FAIL${NC}: Batch restart not working"
    echo "Response: $response"
fi
echo ""

# Test 4: Enhanced Config Validation - Invalid URL
echo "Test 4: Config validation rejects invalid URLs"
response=$(curl -s -X POST "$BASE_URL/api/config" \
  -H "Content-Type: application/json" \
  -d '{"content": "retailers:\n  test:\n    name: Test\n    enabled: true\n    base_url: not_a_url\n    discovery_method: sitemap"}')
if echo "$response" | grep -q "must be a valid HTTP/HTTPS URL"; then
    echo -e "${GREEN}✓ PASS${NC}: URL validation working"
else
    echo -e "${RED}✗ FAIL${NC}: URL validation not working"
    echo "Response: $response"
fi
echo ""

# Test 5: Enhanced Config Validation - Negative Numbers
echo "Test 5: Config validation rejects negative numbers"
response=$(curl -s -X POST "$BASE_URL/api/config" \
  -H "Content-Type: application/json" \
  -d '{"content": "retailers:\n  test:\n    name: Test\n    enabled: true\n    base_url: https://test.com\n    discovery_method: sitemap\n    min_delay: -5"}')
if echo "$response" | grep -q "must be a positive number"; then
    echo -e "${GREEN}✓ PASS${NC}: Numeric validation working"
else
    echo -e "${RED}✗ FAIL${NC}: Numeric validation not working"
    echo "Response: $response"
fi
echo ""

# Test 6: Enhanced Config Validation - Invalid Discovery Method
echo "Test 6: Config validation rejects invalid discovery_method"
response=$(curl -s -X POST "$BASE_URL/api/config" \
  -H "Content-Type: application/json" \
  -d '{"content": "retailers:\n  test:\n    name: Test\n    enabled: true\n    base_url: https://test.com\n    discovery_method: invalid_method"}')
if echo "$response" | grep -q "invalid discovery_method"; then
    echo -e "${GREEN}✓ PASS${NC}: Discovery method validation working"
else
    echo -e "${RED}✗ FAIL${NC}: Discovery method validation not working"
    echo "Response: $response"
fi
echo ""

# Test 7: Start Endpoint with Missing Retailer
echo "Test 7: Start endpoint rejects missing retailer"
response=$(curl -s -X POST "$BASE_URL/api/scraper/start" \
  -H "Content-Type: application/json" \
  -d '{"resume": true}')
if echo "$response" | grep -q "Missing required field: retailer"; then
    echo -e "${GREEN}✓ PASS${NC}: Missing field validation working"
else
    echo -e "${RED}✗ FAIL${NC}: Missing field validation not working"
    echo "Response: $response"
fi
echo ""

# Test 8: Start Endpoint with Invalid Retailer
echo "Test 8: Start endpoint rejects invalid retailer"
response=$(curl -s -X POST "$BASE_URL/api/scraper/start" \
  -H "Content-Type: application/json" \
  -d '{"retailer": "invalid_xyz"}')
if echo "$response" | grep -q "Unknown retailer"; then
    echo -e "${GREEN}✓ PASS${NC}: Invalid retailer rejected"
else
    echo -e "${RED}✗ FAIL${NC}: Invalid retailer not rejected"
    echo "Response: $response"
fi
echo ""

# Test 9: Batch Operations - Start All
echo "Test 9: Batch start with 'all' retailers"
response=$(curl -s -X POST "$BASE_URL/api/scraper/start" \
  -H "Content-Type: application/json" \
  -d '{"retailer": "all", "test": true}')
if echo "$response" | grep -q "Started"; then
    echo -e "${GREEN}✓ PASS${NC}: Batch start working"
    # Clean up
    curl -s -X POST "$BASE_URL/api/scraper/stop" \
      -H "Content-Type: application/json" \
      -d '{"retailer": "all"}' > /dev/null 2>&1
else
    echo -e "${RED}✗ FAIL${NC}: Batch start not working"
    echo "Response: $response"
fi
echo ""

echo "======================================"
echo "Security Tests Complete"
echo "======================================"
