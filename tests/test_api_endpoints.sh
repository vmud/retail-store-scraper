#!/bin/bash

# Test script for API endpoints
# Usage: ./test_api_endpoints.sh [base_url]
# Example: ./test_api_endpoints.sh http://localhost:5000

BASE_URL="${1:-http://localhost:5000}"

echo "Testing API endpoints at $BASE_URL"
echo "======================================"
echo ""

echo "1. Testing GET /api/status (all retailers status)"
curl -s "$BASE_URL/api/status" | python -m json.tool | head -20
echo ""

echo "2. Testing GET /api/status/verizon (single retailer status)"
curl -s "$BASE_URL/api/status/verizon" | python -m json.tool | head -20
echo ""

echo "3. Testing GET /api/status/invalid (invalid retailer - should return 404)"
curl -s "$BASE_URL/api/status/invalid_retailer" | python -m json.tool
echo ""

echo "4. Testing POST /api/scraper/start (missing retailer - should return 400)"
curl -s -X POST "$BASE_URL/api/scraper/start" \
  -H "Content-Type: application/json" \
  -d '{}' | python -m json.tool
echo ""

echo "5. Testing POST /api/scraper/start (invalid retailer - should return 400)"
curl -s -X POST "$BASE_URL/api/scraper/start" \
  -H "Content-Type: application/json" \
  -d '{"retailer": "invalid"}' | python -m json.tool
echo ""

echo "6. Testing POST /api/scraper/stop (not running - should return 400)"
curl -s -X POST "$BASE_URL/api/scraper/stop" \
  -H "Content-Type: application/json" \
  -d '{"retailer": "verizon"}' | python -m json.tool
echo ""

echo "7. Testing GET /api/runs/verizon (run history)"
curl -s "$BASE_URL/api/runs/verizon?limit=3" | python -m json.tool | head -30
echo ""

echo "8. Testing GET /api/config (get configuration)"
curl -s "$BASE_URL/api/config" | python -m json.tool | head -10
echo ""

echo "9. Testing POST /api/config (invalid YAML - should return 400)"
curl -s -X POST "$BASE_URL/api/config" \
  -H "Content-Type: application/json" \
  -d '{"content": "invalid: yaml: : syntax"}' | python -m json.tool
echo ""

echo "10. Testing POST /api/config (missing required fields - should return 400)"
curl -s -X POST "$BASE_URL/api/config" \
  -H "Content-Type: application/json" \
  -d '{"content": "retailers:\n  test:\n    name: Test"}' | python -m json.tool
echo ""

echo "======================================"
echo "All endpoint tests completed!"
