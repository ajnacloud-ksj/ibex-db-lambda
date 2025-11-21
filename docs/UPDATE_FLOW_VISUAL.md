# Update Flow - Visual Guide

## Quick Summary

**Q: When I update a record, what happens?**  
**A: A new version of the record is appended to the table. The old version remains for audit/time-travel.**

---

## Visual Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         UPDATE OPERATION FLOW                         │
└──────────────────────────────────────────────────────────────────────┘

1. CLIENT REQUEST
   ↓
   {
     "operation": "UPDATE",
     "table": "products",
     "filters": [{"field": "product_id", "operator": "eq", "value": 1}],
     "updates": {"price": 799.99}
   }

2. FIND LATEST VERSION (SQL Window Function)
   ↓
   WITH ranked_records AS (
       SELECT *, ROW_NUMBER() OVER (PARTITION BY _record_id ORDER BY _version DESC) as rn
       FROM iceberg_scan('metadata.json')
       WHERE product_id = 1 AND _deleted IS NOT TRUE
   )
   SELECT * FROM ranked_records WHERE rn = 1
   
   ↓
   
   Result: ONE record (latest version only)
   {
     "_record_id": "abc123",
     "product_id": 1,
     "name": "Laptop",
     "price": 899.99,
     "_version": 2,
     "_deleted": false
   }

3. CREATE NEW VERSION
   ↓
   new_version = {
     "_record_id": "abc123",        # Same (identifies the record)
     "product_id": 1,               # Same
     "name": "Laptop",              # Same
     "price": 799.99,               # ← UPDATED
     "_version": 3,                 # ← INCREMENTED
     "_timestamp": "2024-11-21T...", # ← NEW
     "_deleted": false              # Same
   }

4. APPEND TO ICEBERG TABLE
   ↓
   table.append([new_version])  # PyIceberg append operation
   
   ↓
   
   ┌─────────────────────────────────────────────────────┐
   │ S3 Bucket                                           │
   ├─────────────────────────────────────────────────────┤
   │ file1.parquet (old)                                 │
   │   - version 1: price=999.99                         │
   │   - version 2: price=899.99                         │
   │                                                     │
   │ file2.parquet (NEW)                                 │
   │   - version 3: price=799.99  ← JUST ADDED          │
   └─────────────────────────────────────────────────────┘

5. RETURN SUCCESS
   ↓
   {
     "success": true,
     "data": {
       "records_updated": 1
     }
   }
```

---

## Timeline View: Multiple Updates

```
TIME →

t0: WRITE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Records in table:
┌─────────┬────────┬───────┬─────────┐
│ id      │ price  │ stock │ version │
├─────────┼────────┼───────┼─────────┤
│ 1       │ 999.99 │ 50    │ 1       │  ← v1
└─────────┴────────┴───────┴─────────┘


t1: UPDATE (price=899.99)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Records in table:
┌─────────┬────────┬───────┬─────────┐
│ id      │ price  │ stock │ version │
├─────────┼────────┼───────┼─────────┤
│ 1       │ 999.99 │ 50    │ 1       │  ← v1 (old)
│ 1       │ 899.99 │ 50    │ 2       │  ← v2 (latest)
└─────────┴────────┴───────┴─────────┘


t2: UPDATE (stock=100)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Records in table:
┌─────────┬────────┬───────┬─────────┐
│ id      │ price  │ stock │ version │
├─────────┼────────┼───────┼─────────┤
│ 1       │ 999.99 │ 50    │ 1       │  ← v1 (old)
│ 1       │ 899.99 │ 50    │ 2       │  ← v2 (old)
│ 1       │ 899.99 │ 100   │ 3       │  ← v3 (latest)
└─────────┴────────┴───────┴─────────┘


t3: UPDATE (price=799.99)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Records in table:
┌─────────┬────────┬───────┬─────────┐
│ id      │ price  │ stock │ version │
├─────────┼────────┼───────┼─────────┤
│ 1       │ 999.99 │ 50    │ 1       │  ← v1 (old)
│ 1       │ 899.99 │ 50    │ 2       │  ← v2 (old)
│ 1       │ 899.99 │ 100   │ 3       │  ← v3 (old)
│ 1       │ 799.99 │ 100   │ 4       │  ← v4 (latest) ★
└─────────┴────────┴───────┴─────────┘


QUERY (without version filter):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Returns ONLY v4 (latest):
┌─────────┬────────┬───────┬─────────┐
│ id      │ price  │ stock │ version │
├─────────┼────────┼───────┼─────────┤
│ 1       │ 799.99 │ 100   │ 4       │  ← v4 (latest)
└─────────┴────────┴───────┴─────────┘


AUDIT QUERY (all versions):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Returns ALL versions:
┌─────────┬────────┬───────┬─────────┬─────────────────────┐
│ id      │ price  │ stock │ version │ timestamp           │
├─────────┼────────┼───────┼─────────┼─────────────────────┤
│ 1       │ 999.99 │ 50    │ 1       │ 2024-11-21 10:00:00 │
│ 1       │ 899.99 │ 50    │ 2       │ 2024-11-21 11:00:00 │
│ 1       │ 899.99 │ 100   │ 3       │ 2024-11-21 12:00:00 │
│ 1       │ 799.99 │ 100   │ 4       │ 2024-11-21 13:00:00 │
└─────────┴────────┴───────┴─────────┴─────────────────────┘
```

---

## The Bug (Before Fix)

```
UPDATE FLOW - BUGGY VERSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current state:
┌─────────┬────────┬─────────┐
│ id      │ price  │ version │
├─────────┼────────┼─────────┤
│ 1       │ 999.99 │ 1       │  ← v1
│ 1       │ 899.99 │ 2       │  ← v2
│ 1       │ 799.99 │ 3       │  ← v3 (latest)
└─────────┴────────┴─────────┘

User: UPDATE id=1 SET stock=100

BUGGY CODE:
  1. Query: "SELECT * WHERE id=1"
     ↓
     Returns: v1, v2, v3 (ALL versions!) ❌
  
  2. For EACH version, create new version:
     ↓
     v1 → v4 (price=999.99, stock=100)
     v2 → v5 (price=899.99, stock=100)
     v3 → v6 (price=799.99, stock=100)
  
  3. Append all 3 new versions ❌

Result (BAD):
┌─────────┬────────┬───────┬─────────┐
│ id      │ price  │ stock │ version │
├─────────┼────────┼───────┼─────────┤
│ 1       │ 999.99 │ 50    │ 1       │  ← v1 (old)
│ 1       │ 899.99 │ 50    │ 2       │  ← v2 (old)
│ 1       │ 799.99 │ 100   │ 3       │  ← v3 (old)
│ 1       │ 999.99 │ 100   │ 4       │  ← v4 (duplicate!) ❌
│ 1       │ 899.99 │ 100   │ 5       │  ← v5 (duplicate!) ❌
│ 1       │ 799.99 │ 100   │ 6       │  ← v6 (latest)
└─────────┴────────┴───────┴─────────┘

Problem: Created 3 new versions instead of 1!
```

---

## The Fix

```
UPDATE FLOW - FIXED VERSION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current state:
┌─────────┬────────┬─────────┐
│ id      │ price  │ version │
├─────────┼────────┼─────────┤
│ 1       │ 999.99 │ 1       │  ← v1
│ 1       │ 899.99 │ 2       │  ← v2
│ 1       │ 799.99 │ 3       │  ← v3 (latest)
└─────────┴────────┴─────────┘

User: UPDATE id=1 SET stock=100

FIXED CODE:
  1. Query with window function:
     ↓
     WITH ranked AS (
       SELECT *, ROW_NUMBER() OVER (PARTITION BY _record_id 
                                    ORDER BY _version DESC) as rn
       FROM table WHERE id=1
     )
     SELECT * FROM ranked WHERE rn = 1
     ↓
     Returns: v3 ONLY (latest version) ✅
  
  2. Create new version from v3:
     ↓
     v3 → v4 (price=799.99, stock=100)
  
  3. Append 1 new version ✅

Result (GOOD):
┌─────────┬────────┬───────┬─────────┐
│ id      │ price  │ stock │ version │
├─────────┼────────┼───────┼─────────┤
│ 1       │ 999.99 │ 50    │ 1       │  ← v1 (old)
│ 1       │ 899.99 │ 50    │ 2       │  ← v2 (old)
│ 1       │ 799.99 │ 100   │ 3       │  ← v3 (old)
│ 1       │ 799.99 │ 100   │ 4       │  ← v4 (latest) ✅
└─────────┴────────┴───────┴─────────┘

Success: Created 1 new version as expected!
```

---

## Storage Layout (S3)

```
s3://bucket/warehouse/tenant_id_namespace/products/
│
├── metadata/
│   ├── v1.metadata.json      ← Snapshot 1 (initial write)
│   ├── v2.metadata.json      ← Snapshot 2 (after update 1)
│   ├── v3.metadata.json      ← Snapshot 3 (after update 2)
│   └── v4.metadata.json      ← Snapshot 4 (after update 3)
│
└── data/
    ├── 00001-abc.parquet     ← Contains v1
    ├── 00002-def.parquet     ← Contains v2
    ├── 00003-ghi.parquet     ← Contains v3
    └── 00004-jkl.parquet     ← Contains v4 (latest)

Each metadata file points to relevant data files:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v1.metadata.json → data/00001-abc.parquet
v2.metadata.json → data/00001-abc.parquet, data/00002-def.parquet
v3.metadata.json → data/00001-abc.parquet, data/00002-def.parquet, data/00003-ghi.parquet
v4.metadata.json → data/00001-abc.parquet, ..., data/00004-jkl.parquet (ALL files)
```

---

## Key Takeaways

### What Happens on Update

1. ✅ **Find**: Locate latest version of matching records
2. ✅ **Clone**: Copy all fields from latest version
3. ✅ **Modify**: Apply requested updates
4. ✅ **Version**: Increment `_version`, update `_timestamp`
5. ✅ **Append**: Write new version to new Parquet file
6. ✅ **Keep**: Old versions remain (for audit/time-travel)

### What Does NOT Happen

1. ❌ Old records are NOT deleted
2. ❌ Files are NOT modified in-place
3. ❌ Old versions are NOT replaced

### Why This Approach

- ✅ **Audit trail**: See complete history
- ✅ **Time travel**: Query data at any point
- ✅ **Compliance**: Meet regulatory requirements
- ✅ **Recovery**: Undo mistakes
- ✅ **ACID**: Full transactional guarantees

### Trade-off

- ⚠️ **Storage**: More versions = more storage
- ✅ **Solution**: Use COMPACT operation to clean up old versions

---

## Test It Yourself

```bash
# 1. Create table
cat lambda_test_events/02_create_table.json

# 2. Write initial record
cat lambda_test_events/03_write_users.json

# 3. Update record
cat lambda_test_events/06_update_user.json

# 4. Query to see current state (returns latest version)
cat lambda_test_events/04_query_all_users.json

# 5. Audit query to see all versions
# Add to your query:
{
  "projection": ["_version", "_timestamp", "name", "email"],
  "sort": [{"field": "_version", "order": "asc"}]
}
```

---

## Further Reading

- `docs/HOW_UPDATES_WORK.md` - Detailed explanation
- `docs/UPDATE_BUG_FIX.md` - Bug fix details
- [Apache Iceberg Docs](https://iceberg.apache.org/docs/latest/)

