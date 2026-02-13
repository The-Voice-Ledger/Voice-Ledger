#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# test_api.sh — Quick smoke-test for the CRE Provenance API
#
# Usage:  cd /path/to/Voice-Ledger && bash chainlink/test/test_api.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

API="http://localhost:8100"
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo "═══════════════════════════════════════════"
echo "  Voice Ledger — CRE Provenance API Tests"
echo "═══════════════════════════════════════════"
echo ""

# Health check
echo "▸ Health check..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/health")
[ "$HTTP_CODE" = "200" ] && pass "GET /health → 200" || fail "GET /health → $HTTP_CODE"

# Trigger 1: Provenance metrics
echo "▸ Provenance metrics..."
RESP=$(curl -s "$API/api/provenance")
echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'totalFarmers' in d; assert 'lastUpdated' in d" 2>/dev/null \
  && pass "GET /api/provenance → valid JSON with expected fields" \
  || fail "GET /api/provenance → missing expected fields"
echo "  $RESP"

# Trigger 2: Batch details (will 404 if no batches exist — that's OK)
echo "▸ Batch details (expect 404 or 200)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/batch/TEST_BATCH_001")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "404" ]; then
  pass "GET /api/batch/TEST_BATCH_001 → $HTTP_CODE (expected)"
else
  fail "GET /api/batch/TEST_BATCH_001 → $HTTP_CODE (unexpected)"
fi

# Trigger 3: Deforestation check (will 404 if farm doesn't exist — that's OK)
echo "▸ Deforestation check (expect 404 or 200)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/deforestation/FARM-001")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "404" ] || [ "$HTTP_CODE" = "422" ]; then
  pass "GET /api/deforestation/FARM-001 → $HTTP_CODE (expected)"
else
  fail "GET /api/deforestation/FARM-001 → $HTTP_CODE (unexpected)"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "  All API smoke tests passed ✓"
echo "═══════════════════════════════════════════"
