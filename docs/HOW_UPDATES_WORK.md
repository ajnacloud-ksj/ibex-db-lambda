# How Updates Work in Apache Iceberg

## Overview

Apache Iceberg is designed for **immutable data files** - once a Parquet file is written, it's never modified. So how do we handle updates? The answer involves **metadata updates** and **new file creation**.

## Iceberg's Native Update Model

### 1. Immutable Data Files

Iceberg follows the principle of **immutable storage**:
- ✅ **Write**: Create new Parquet files
- ✅ **Append**: Add new Parquet files
- ❌ **In-place modification**: Never happens!

### 2. How Iceberg Handles Updates

When you "update" a record in Iceberg:

```
┌─────────────────────────────────────────────────┐
│ BEFORE UPDATE                                   │
├─────────────────────────────────────────────────┤
│ file1.parquet                                   │
│   - record1 (id=1, price=999)                   │
│   - record2 (id=2, price=500)                   │
│   - record3 (id=3, price=200)                   │
└─────────────────────────────────────────────────┘

UPDATE id=1 SET price=799
↓↓↓

┌─────────────────────────────────────────────────┐
│ AFTER UPDATE                                    │
├─────────────────────────────────────────────────┤
│ file1.parquet (marked for deletion in metadata) │
│   - record1 (id=1, price=999) ← OLD             │
│   - record2 (id=2, price=500)                   │
│   - record3 (id=3, price=200)                   │
│                                                 │
│ file2.parquet (new file)                        │
│   - record1 (id=1, price=799) ← NEW             │
│   - record2 (id=2, price=500)                   │
│   - record3 (id=3, price=200)                   │
└─────────────────────────────────────────────────┘
```

**What happened**:
1. Read all records from file1.parquet
2. Modify the matching record(s)
3. Write ALL records to file2.parquet (including unchanged ones)
4. Update metadata to mark file1 for deletion and add file2
5. Old file gets deleted during compaction

This is called **Copy-On-Write (COW)** semantics.

### 3. Metadata Snapshots

Each update creates a new **snapshot** in the Iceberg metadata:

```
Snapshot 1 (Initial Write)
  ├─ file1.parquet [record1, record2, record3]
  └─ manifest: points to file1

Snapshot 2 (After Update)
  ├─ file1.parquet (deleted)
  ├─ file2.parquet [record1_updated, record2, record3]
  └─ manifest: points to file2
```

### Key Point: PyIceberg's Update API

PyIceberg (as of v0.7.1) provides:
- ✅ `table.append()` - Add new data
- ✅ `table.overwrite()` - Replace entire table
- ✅ `table.delete()` - Delete with filter
- ❌ `table.update()` - **NOT directly available!**

**This is why we implement updates ourselves!**

---

## Our Implementation: Versioned Updates

Since Iceberg doesn't provide a native `UPDATE` API (in PyIceberg), we implement our own **versioning system** on top of Iceberg's append-only model.

### Our Approach: Version Tracking

Instead of physically deleting old records, we:
1. Keep ALL versions of each record
2. Track version numbers in `_version` field
3. Queries return only the latest version (unless explicitly requested)

### Example: Product Update Flow

#### 1. Initial Write

```json
{
  "operation": "WRITE",
  "records": [
    {"product_id": 1, "name": "Laptop", "price": 999.99}
  ]
}
```

**What gets written to Iceberg**:
```
file1.parquet:
┌──────────────┬────────────┬──────┬───────┬──────────┬─────────┐
│ _record_id   │ product_id │ name │ price │ _version │ _deleted│
├──────────────┼────────────┼──────┼───────┼──────────┼─────────┤
│ abc123       │ 1          │Laptop│ 999.99│ 1        │ false   │
└──────────────┴────────────┴──────┴───────┴──────────┴─────────┘
```

- `_record_id`: Unique identifier (MD5 hash of original record)
- `_version`: Starts at 1
- `_deleted`: Soft delete flag

#### 2. First Update

```json
{
  "operation": "UPDATE",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}],
  "updates": {"price": 899.99}
}
```

**What happens**:

```python
# Step 1: Find latest version of matching records
SELECT * FROM iceberg_table 
WHERE product_id = 1 
  AND _version = (SELECT MAX(_version) FROM iceberg_table WHERE _record_id = abc123)

# Step 2: Create new version with updated values
new_record = old_record.copy()
new_record["_version"] = 2  # Increment version
new_record["_timestamp"] = now()
new_record["price"] = 899.99  # Apply update

# Step 3: Append new version to Iceberg table
table.append([new_record])
```

**Result in Iceberg**:
```
file1.parquet (original):
┌──────────────┬────────────┬──────┬───────┬──────────┬─────────┐
│ _record_id   │ product_id │ name │ price │ _version │ _deleted│
├──────────────┼────────────┼──────┼───────┼──────────┼─────────┤
│ abc123       │ 1          │Laptop│ 999.99│ 1        │ false   │
└──────────────┴────────────┴──────┴───────┴──────────┴─────────┘

file2.parquet (new version):
┌──────────────┬────────────┬──────┬───────┬──────────┬─────────┐
│ _record_id   │ product_id │ name │ price │ _version │ _deleted│
├──────────────┼────────────┼──────┼───────┼──────────┼─────────┤
│ abc123       │ 1          │Laptop│ 899.99│ 2        │ false   │
└──────────────┴────────────┴──────┴───────┴──────────┴─────────┘
```

**Note**: Both versions exist! We don't delete the old one.

#### 3. Query (Gets Latest Version)

```json
{
  "operation": "QUERY",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}]
}
```

**Query SQL** (before the fix):
```sql
SELECT * FROM iceberg_scan('metadata.json')
WHERE _tenant_id = 'tenant1'
  AND _deleted IS NOT TRUE
  AND product_id = 1
```

**Problem**: Returns BOTH versions! (v1 and v2)

**Query SQL** (after the fix):
```sql
WITH ranked_records AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY _record_id ORDER BY _version DESC) as rn
    FROM iceberg_scan('metadata.json')
    WHERE _tenant_id = 'tenant1'
      AND _deleted IS NOT TRUE
      AND product_id = 1
)
SELECT * FROM ranked_records WHERE rn = 1
```

**Result**: Returns ONLY v2 (latest version)

---

## The Bug I Just Fixed

### What Was Wrong

The UPDATE operation was querying records without filtering by latest version:

```python
# OLD CODE (BUGGY)
def update(self, request):
    # Query matching records - Gets ALL VERSIONS!
    query_result = self.query(QueryRequest(
        filters=request.filters  # No version filter!
    ))
    
    # Creates new version for EVERY record returned
    for record in query_result.data.records:  # Includes v1, v2, v3...
        record["_version"] += 1
        record.update(request.updates)
        updated_records.append(record)
    
    table.append(updated_records)  # Creates v4, v5, v6...
```

**Scenario**:
```
Initial: product_id=1, price=999.99, _version=1
Update 1: product_id=1, price=899.99, _version=2
Update 2: product_id=1, price=799.99, _version=3

Now run: UPDATE product_id=1 SET stock=100

BUGGY BEHAVIOR:
- Query returns 3 records (v1, v2, v3)
- Creates 3 new versions (v4, v5, v6)
- Now you have 6 versions!
- Queries return confusing results
```

### The Fix

Use SQL window function to get ONLY latest version:

```python
# NEW CODE (FIXED)
def update(self, request):
    # Query with window function - Gets ONLY LATEST VERSION!
    sql = """
        WITH ranked_records AS (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY _record_id ORDER BY _version DESC) as rn
            FROM iceberg_scan('metadata.json')
            WHERE filters...
        )
        SELECT * FROM ranked_records WHERE rn = 1
    """
    
    records = execute_query(sql)
    
    # Creates new version ONLY for latest records
    for record in records:  # Only v3
        record["_version"] += 1
        record.update(request.updates)
        updated_records.append(record)
    
    table.append(updated_records)  # Creates only v4
```

**Same scenario, fixed behavior**:
```
Initial: product_id=1, price=999.99, _version=1
Update 1: product_id=1, price=899.99, _version=2
Update 2: product_id=1, price=799.99, _version=3

Now run: UPDATE product_id=1 SET stock=100

FIXED BEHAVIOR:
- Query returns 1 record (v3 only)
- Creates 1 new version (v4)
- Now you have 4 versions (correct!)
- Queries return single, correct result
```

---

## Benefits of Our Versioning Approach

### 1. **Complete Audit Trail**
Every change is tracked:
```sql
SELECT _version, _timestamp, price 
FROM products 
WHERE product_id = 1
ORDER BY _version;

-- Returns:
-- v1: 2024-01-01 10:00:00, $999.99
-- v2: 2024-01-01 11:00:00, $899.99
-- v3: 2024-01-01 12:00:00, $799.99
```

### 2. **Time Travel**
Query data as it existed at any point:
```json
{
  "operation": "QUERY",
  "as_of": "2024-01-01T10:30:00Z",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}]
}
```
Returns version 1 (price=$999.99)

### 3. **Soft Deletes**
Deletes are just updates with `_deleted=true`:
```json
{
  "operation": "DELETE",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}]
}
```

Creates new version with `_deleted=true`, old versions remain queryable.

### 4. **Compliance & Recovery**
- Regulatory compliance (audit logs)
- Undo changes (restore previous version)
- Investigate incidents (what changed when?)

---

## Performance Implications

### Storage

**More versions = More storage**:
```
100 records × 10 updates each = 1,000 versions
If each record is 1KB = 1MB total storage
```

**Solution**: Use COMPACT operation to remove old versions:
```json
{
  "operation": "COMPACT",
  "table": "products",
  "expire_snapshots": true,
  "snapshot_retention_hours": 168
}
```

### Query Performance

**Latest version queries are fast** because:
1. DuckDB's window functions are optimized
2. Iceberg's file-level metadata filters out irrelevant files
3. Parquet's columnar format allows column pruning

**Version history queries are slower**:
- Must scan all versions
- Use sparingly or pre-aggregate

---

## Comparison: Other Databases

### Traditional Databases (PostgreSQL, MySQL)

```sql
UPDATE products SET price = 899.99 WHERE product_id = 1;
```

**What happens**:
1. Find the row in the data file
2. **Overwrite the row in-place** (if MVCC, old version in separate area)
3. Update indexes
4. Old data is lost (unless you have audit tables)

### Delta Lake (Similar to Iceberg)

Delta Lake also uses **Copy-On-Write**:
```python
deltaTable.update(
    condition = "product_id = 1",
    set = {"price": "899.99"}
)
```

Internally:
1. Reads affected files
2. Merges changes
3. Writes new files
4. Updates transaction log

### Apache Hudi (Optimized for Updates)

Hudi uses **Merge-On-Read (MOR)**:
- Updates written to delta logs
- Base files updated later during compaction
- Faster writes, slightly slower reads

---

## Best Practices

### 1. Batch Updates When Possible

**Bad** (Many small updates):
```python
for product in products:
    update(product_id=product.id, price=product.new_price)
# Creates 1000 new versions for 1000 products
```

**Good** (Bulk update):
```python
update(
    filters=[{"field": "category", "operator": "eq", "value": "Electronics"}],
    updates={"discount": 0.1}
)
# Creates N new versions (one per matching product) in single operation
```

### 2. Compact Regularly

```json
{
  "operation": "COMPACT",
  "force": false,
  "expire_snapshots": true,
  "snapshot_retention_hours": 168
}
```

Runs after many updates to:
- Merge small files into large files
- Remove old versions (after retention period)
- Improve query performance

### 3. Use Filters Wisely

**Efficient**:
```json
{"filters": [
  {"field": "product_id", "operator": "eq", "value": 1}
]}
```

**Inefficient**:
```json
{"filters": [
  {"field": "name", "operator": "like", "value": "%Laptop%"}
]}
```
(Full scan of all files)

### 4. Monitor Version Count

```sql
SELECT _record_id, COUNT(*) as version_count
FROM products
GROUP BY _record_id
ORDER BY version_count DESC
LIMIT 10;
```

If version_count is very high (>100), consider compaction.

---

## Summary

### Apache Iceberg's Update Model
- ✅ **Immutable files**: Never modify existing Parquet files
- ✅ **Copy-On-Write**: Read old file, write new file with changes
- ✅ **Metadata snapshots**: Each change creates new snapshot
- ❌ **No native UPDATE**: PyIceberg doesn't expose simple update API

### Our Implementation
- ✅ **Version tracking**: `_version` field increments on each update
- ✅ **Append-only**: New versions appended, old versions remain
- ✅ **Latest version queries**: Window function selects latest only
- ✅ **Audit trail**: Complete history of all changes
- ✅ **Time travel**: Query data at any point in time

### The Bug & Fix
- ❌ **Bug**: UPDATE queried ALL versions, created duplicates
- ✅ **Fix**: Use `ROW_NUMBER() OVER PARTITION BY` to get latest only
- ✅ **Result**: Updates now work correctly, one new version per record

### Trade-offs
- **Storage**: More versions = more storage (mitigated by compaction)
- **Performance**: Slightly slower updates (read + write), fast queries
- **Benefits**: Complete audit trail, time travel, soft deletes, compliance

---

## Further Reading

- [Apache Iceberg Update Strategy](https://iceberg.apache.org/docs/latest/performance/)
- [PyIceberg API Documentation](https://py.iceberg.apache.org/api/)
- [DuckDB Window Functions](https://duckdb.org/docs/sql/window_functions)
- Our docs: `docs/UPDATE_BUG_FIX.md`

