#!/usr/bin/env bash
# Automated verification for all 6 assignment steps.
# Usage: bash tests/test_orders.sh [BASE_URL]

set -euo pipefail

BASE=${1:-http://localhost:5000}
PASS=0
FAIL=0

check() {
  local label="$1" expected="$2" actual="$3"
  if [ "$actual" -eq "$expected" ]; then
    echo "  PASS  $label (HTTP $actual)"
    PASS=$((PASS+1))
  else
    echo "  FAIL  $label — expected $expected, got $actual"
    FAIL=$((FAIL+1))
  fi
}

echo "=== Step 1: Create order (expect 201) ==="
RESP1=$(curl -s -w "\n%{http_code}" -X POST "$BASE/orders" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-key-001" \
  -d '{"customer_id":"cust-1","item_id":"item-42","quantity":2}')
BODY1=$(echo "$RESP1" | sed '$d')
CODE1=$(echo "$RESP1" | tail -1)
check "Step 1" 201 "$CODE1"
ORDER_ID=$(echo "$BODY1" | python3 -c "import sys,json; print(json.load(sys.stdin)['order_id'])")
echo "  order_id=$ORDER_ID"

echo ""
echo "=== Step 2: Retry same key+payload (expect 201, same order_id) ==="
RESP2=$(curl -s -w "\n%{http_code}" -X POST "$BASE/orders" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-key-001" \
  -d '{"customer_id":"cust-1","item_id":"item-42","quantity":2}')
BODY2=$(echo "$RESP2" | sed '$d')
CODE2=$(echo "$RESP2" | tail -1)
check "Step 2 status" 201 "$CODE2"
ORDER_ID2=$(echo "$BODY2" | python3 -c "import sys,json; print(json.load(sys.stdin)['order_id'])")
if [ "$ORDER_ID" = "$ORDER_ID2" ]; then
  echo "  PASS  Same order_id returned"
  PASS=$((PASS+1))
else
  echo "  FAIL  Different order_id ($ORDER_ID vs $ORDER_ID2)"
  FAIL=$((FAIL+1))
fi

echo ""
echo "=== Step 3: Same key, different payload (expect 409) ==="
RESP3=$(curl -s -w "\n%{http_code}" -X POST "$BASE/orders" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-key-001" \
  -d '{"customer_id":"cust-1","item_id":"item-99","quantity":5}')
CODE3=$(echo "$RESP3" | tail -1)
check "Step 3" 409 "$CODE3"

echo ""
echo "=== Step 4: Simulated failure after commit (expect 500) ==="
RESP4=$(curl -s -w "\n%{http_code}" -X POST "$BASE/orders" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-key-fail-002" \
  -H "X-Debug-Fail-After-Commit: true" \
  -d '{"customer_id":"cust-2","item_id":"item-7","quantity":1}')
CODE4=$(echo "$RESP4" | tail -1)
check "Step 4" 500 "$CODE4"

echo ""
echo "=== Step 5: Retry after failure (expect 201, same order) ==="
RESP5=$(curl -s -w "\n%{http_code}" -X POST "$BASE/orders" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-key-fail-002" \
  -d '{"customer_id":"cust-2","item_id":"item-7","quantity":1}')
BODY5=$(echo "$RESP5" | sed '$d')
CODE5=$(echo "$RESP5" | tail -1)
check "Step 5" 201 "$CODE5"

echo ""
echo "=== Step 6: GET order by ID (expect 200) ==="
RESP6=$(curl -s -w "\n%{http_code}" "$BASE/orders/$ORDER_ID")
CODE6=$(echo "$RESP6" | tail -1)
check "Step 6" 200 "$CODE6"

echo ""
echo "=============================="
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && echo "ALL TESTS PASSED" || echo "SOME TESTS FAILED"
exit "$FAIL"
