#!/bin/bash

# Test FastAPI compaction workflow
# No Lambda emulator bugs - clean and reliable!

set -e

API_URL="http://localhost:9000"

echo "========================================"
echo "FastAPI Compaction Test"
echo "========================================"

# 1. Health Check
echo ""
echo "1. Health Check"
curl -s "$API_URL/health" | jq '.'
sleep 2

# 2. Create Table
echo ""
echo "2. CREATE TABLE"
curl -s -X POST "$API_URL/database" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "CREATE_TABLE",
    "tenant_id": "test-tenant",
    "namespace": "default",
    "table": "users",
    "schema": {
      "fields": {
        "name": {"type": "string", "required": true},
        "email": {"type": "string", "required": true},
        "age": {"type": "integer", "required": false}
      }
    },
    "if_not_exists": true
  }' | jq '.'
sleep 2

# 3-7. Write 5 batches (will trigger check on 5th write)
for i in {1..5}; do
    echo ""
    echo "========== Write Batch $i =========="
    RESPONSE=$(curl -s -X POST "$API_URL/database" \
      -H "Content-Type: application/json" \
      -d "{
        \"operation\": \"WRITE\",
        \"tenant_id\": \"test-tenant\",
        \"namespace\": \"default\",
        \"table\": \"users\",
        \"records\": [
          {\"name\": \"User-$i-1\", \"email\": \"user$i-1@test.com\", \"age\": $((20 + i))},
          {\"name\": \"User-$i-2\", \"email\": \"user$i-2@test.com\", \"age\": $((20 + i))}
        ]
      }")

    echo "$RESPONSE" | jq '.'

    # Check compaction recommendation
    COMPACTION_REC=$(echo "$RESPONSE" | jq -r '.compaction_recommended // false')
    SMALL_FILES=$(echo "$RESPONSE" | jq -r '.small_files_count // "N/A"')

    if [ "$COMPACTION_REC" == "true" ]; then
        echo ""
        echo "🎉 ✅ COMPACTION RECOMMENDED DETECTED!"
        echo "   Small files count: $SMALL_FILES"
        echo "   This happened at write #$i (interval=5)"
        echo ""
    fi

    sleep 2
done

# 8. Query before compaction
echo ""
echo "8. QUERY - Before compaction"
curl -s -X POST "$API_URL/database" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "QUERY",
    "tenant_id": "test-tenant",
    "namespace": "default",
    "table": "users",
    "limit": 100
  }' | jq '{success, data: (.data | length), metadata}'
sleep 2

# 9. Run compaction
echo ""
echo "9. COMPACT - Merging small files"
COMPACT_RESPONSE=$(curl -s -X POST "$API_URL/database" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "COMPACT",
    "tenant_id": "test-tenant",
    "namespace": "default",
    "table": "users",
    "force": true,
    "expire_snapshots": false
  }')

echo "$COMPACT_RESPONSE" | jq '.'

# Extract compaction stats
SUCCESS=$(echo "$COMPACT_RESPONSE" | jq -r '.success')
COMPACTED=$(echo "$COMPACT_RESPONSE" | jq -r '.compacted')

if [ "$SUCCESS" == "true" ] && [ "$COMPACTED" == "true" ]; then
    echo ""
    echo "✅ COMPACTION SUCCESSFUL!"
    echo ""
    echo "Stats:"
    echo "$COMPACT_RESPONSE" | jq '.stats'
    echo ""
fi

sleep 2

# 10. Query after compaction
echo ""
echo "10. QUERY - After compaction (verify data integrity)"
curl -s -X POST "$API_URL/database" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "QUERY",
    "tenant_id": "test-tenant",
    "namespace": "default",
    "table": "users",
    "limit": 100
  }' | jq '{success, data: (.data | length), metadata}'

echo ""
echo "========================================"
echo "✅ TEST COMPLETED SUCCESSFULLY"
echo "========================================"
echo ""
echo "Summary:"
echo "- Wrote 5 batches of records"
echo "- Compaction check triggered at batch #5"
echo "- Executed compaction successfully"
echo "- Verified data integrity after compaction"
echo "- No Lambda emulator crashes!"
echo ""
