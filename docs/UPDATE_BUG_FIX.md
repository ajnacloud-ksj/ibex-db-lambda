# Update Operation Bug Fix

## Issue Description

**Problem**: UPDATE operations were not working correctly. Updates appeared to succeed but records were not actually updated.

**Root Cause**: The update operation was querying ALL historical versions of matching records (not just the latest version), then creating new versions for ALL of them. This caused:
1. Multiple duplicate updates instead of a single update
2. Ambiguous "latest" version
3. Queries returning duplicate records
4. Updates appearing to have no effect

## Example of the Bug

### Setup
1. Create product with id=1, price=999.99 (version 1)
2. Update product price to 899.99 (version 2)
3. Update product price to 799.99 (version 3)

### Bug Behavior (BEFORE FIX)
When you run:
```json
{
  "operation": "UPDATE",
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}],
  "updates": {"stock": 100}
}
```

**What happened**:
- Query returned ALL 3 versions (v1, v2, v3)
- Created 3 new versions (v4, v5, v6) - one for each historical version
- Result: 6 versions total instead of 4
- Queries would return confusing/duplicate results

### Fixed Behavior (AFTER FIX)
**What happens now**:
- Query returns ONLY the latest version (v3)
- Creates 1 new version (v4) with updated stock
- Result: 4 versions total (as expected)
- Queries return correct, single record

## Technical Details

### Before (Broken)

```python
def update(self, request: UpdateRequest):
    # Query without version filtering - GETS ALL VERSIONS
    query_req = QueryRequest(
        tenant_id=request.tenant_id,
        namespace=request.namespace,
        table=request.table,
        filters=request.filters  # Only user filters, no version filter!
    )
    query_result = self.query(query_req)
    
    # Creates new version for EVERY record returned (including old versions!)
    for record in query_result.data.records:
        record["_version"] = int(record.get("_version", 1)) + 1
        record.update(request.updates)
        updated_records.append(record)
```

**Problem**: `query_result.data.records` contains ALL versions, not just latest!

### After (Fixed)

```python
def update(self, request: UpdateRequest):
    # Use SQL window function to get ONLY latest version
    sql = f"""
        WITH ranked_records AS (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY _record_id ORDER BY _version DESC) as rn
            FROM iceberg_scan('{metadata_path}')
            WHERE _tenant_id = '{request.tenant_id}'
              AND _deleted IS NOT TRUE
              AND ({filter_sql})
        )
        SELECT * FROM ranked_records WHERE rn = 1
    """
    
    # Now records contains ONLY the latest version of each record
    records = result_df.to_dict(orient='records')
    
    # Creates new version only for latest records
    for record in records:
        record["_version"] = int(record.get("_version", 1)) + 1
        record.update(request.updates)
        updated_records.append(record)
```

**Solution**: Use `ROW_NUMBER() OVER (PARTITION BY _record_id ORDER BY _version DESC)` to rank versions and select only `rn = 1` (latest version).

## SQL Window Function Explanation

```sql
WITH ranked_records AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY _record_id ORDER BY _version DESC) as rn
    FROM iceberg_scan('{metadata_path}')
    WHERE _tenant_id = '{tenant_id}'
      AND _deleted IS NOT TRUE
      AND (user_filters)
)
SELECT * FROM ranked_records WHERE rn = 1
```

- `PARTITION BY _record_id`: Group rows by unique record identifier
- `ORDER BY _version DESC`: Order versions from newest to oldest
- `ROW_NUMBER()`: Assign sequential number (1, 2, 3...) within each partition
- `WHERE rn = 1`: Select only the first row (latest version) from each partition

### Visual Example

**Records in table**:
| _record_id | product_id | price | _version | rn (after window function) |
|------------|------------|-------|----------|----------------------------|
| abc123     | 1          | 999.99| 1        | 3                          |
| abc123     | 1          | 899.99| 2        | 2                          |
| abc123     | 1          | 799.99| 3        | 1  ← SELECTED              |

**Query returns only**: `_record_id=abc123, _version=3` (latest version)

## Impact

### Operations Affected
1. ✅ **UPDATE**: Now only updates latest version (primary fix)
2. ✅ **DELETE (soft)**: Uses UPDATE internally, so also fixed
3. ⚠️ **QUERY**: No change needed (already filters deleted records)
4. ⚠️ **WRITE**: No change needed (always creates version 1)

### Performance Impact
- **Slightly slower**: Window function adds minor overhead
- **Much more correct**: Eliminates duplicate version creation
- **Better storage**: Prevents version explosion from buggy updates

## Testing

### Test Case 1: Simple Update

```json
{
  "operation": "WRITE",
  "table": "products",
  "records": [
    {"product_id": 1, "name": "Laptop", "price": 999.99, "stock": 50}
  ]
}
```

```json
{
  "operation": "UPDATE",
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}],
  "updates": {"price": 899.99}
}
```

**Expected Result**: 
- 1 record updated
- Query returns price=899.99
- Total versions: 2 (original + update)

### Test Case 2: Update After Multiple Updates

```json
// Initial write
{"product_id": 1, "price": 999.99}  // v1

// Update 1
{"updates": {"price": 899.99}}  // v2

// Update 2
{"updates": {"price": 799.99}}  // v3

// Update 3
{"updates": {"stock": 100}}  // v4
```

**Expected Result**:
- Each update creates exactly 1 new version
- Query always returns latest version (v4)
- Total versions: 4 (not 10+ as with the bug)

### Test Case 3: Bulk Update

```json
{
  "operation": "UPDATE",
  "table": "products",
  "filters": [{"field": "category", "operator": "eq", "value": "Electronics"}],
  "updates": {"stock": 1000}
}
```

**Expected Result**:
- Updates latest version of ALL Electronics products
- Each product gets exactly 1 new version
- No duplicate versions created

## Verification Steps

1. **Create test table and data**:
```json
{
  "operation": "CREATE_TABLE",
  "table": "test_updates",
  "schema": {
    "fields": {
      "id": {"type": "long", "required": true},
      "value": {"type": "integer", "required": true}
    }
  }
}
```

2. **Write initial record**:
```json
{
  "operation": "WRITE",
  "table": "test_updates",
  "records": [{"id": 1, "value": 100}]
}
```

3. **Query to verify initial state**:
```json
{
  "operation": "QUERY",
  "table": "test_updates",
  "filters": [{"field": "id", "operator": "eq", "value": 1}]
}
```
Expected: 1 record, value=100, _version=1

4. **Update value**:
```json
{
  "operation": "UPDATE",
  "table": "test_updates",
  "filters": [{"field": "id", "operator": "eq", "value": 1}],
  "updates": {"value": 200}
}
```
Expected: records_updated=1

5. **Query to verify update**:
```json
{
  "operation": "QUERY",
  "table": "test_updates",
  "filters": [{"field": "id", "operator": "eq", "value": 1}]
}
```
Expected: 1 record (not 2!), value=200, _version=2

6. **Check version history**:
```json
{
  "operation": "QUERY",
  "table": "test_updates",
  "filters": [{"field": "id", "operator": "eq", "value": 1}],
  "projection": ["_version", "value", "_timestamp"],
  "sort": [{"field": "_version", "order": "asc"}]
}
```
Expected: 2 records total (v1 with value=100, v2 with value=200)

## Migration Notes

### For Existing Tables with Bug

If you have tables that were affected by this bug (multiple duplicate versions), you may want to:

1. **Identify affected tables**:
```sql
-- Count versions per record
SELECT _record_id, COUNT(*) as version_count
FROM iceberg_scan('table_metadata_path')
GROUP BY _record_id
HAVING COUNT(*) > expected_count
```

2. **Clean up duplicates** (if needed):
- Option A: Keep only latest version (use COMPACT operation)
- Option B: Query and rebuild table with correct versions
- Option C: Leave as-is (queries will still work correctly now)

3. **Verify fix is working**:
- Make a test update on affected table
- Verify only 1 new version is created
- Verify queries return correct results

## Related Operations

### DELETE Operation
DELETE uses UPDATE internally to set `_deleted=True`, so it also benefits from this fix:

```python
def delete(self, request: DeleteRequest):
    update_req = UpdateRequest(
        updates={"_deleted": True, "_deleted_at": datetime.utcnow()},
        filters=request.filters
    )
    return self.update(update_req)  # Uses fixed update method
```

## Changelog

### Version: 2024-11-21
- **Fixed**: UPDATE operation now only updates latest version of each record
- **Added**: SQL window function to select latest version (`ROW_NUMBER() OVER PARTITION BY`)
- **Impact**: Eliminates duplicate version creation bug
- **Backward Compatible**: Yes, existing tables work correctly

## Summary

✅ **Bug**: Updates created new versions for ALL historical versions, not just latest  
✅ **Fix**: Use SQL window function to select only latest version before updating  
✅ **Result**: Updates now work correctly, creating exactly 1 new version per record  
✅ **Testing**: Use test events in `lambda_test_events/17_test_update_fix.json`  
✅ **Impact**: DELETE also fixed (uses UPDATE internally)

