# Auditing & Time Travel Guide

## 🔍 Automatic Audit Fields

Every record gets these 6 system fields automatically:

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `_tenant_id` | string | Multi-tenant isolation | "test-tenant" |
| `_record_id` | string | Unique ID (MD5 hash) | "a7a36f..." |
| `_timestamp` | timestamp | Version creation time | "2025-11-14 05:32:23" |
| `_version` | integer | Version number | 1, 2, 3... |
| `_deleted` | boolean | Soft delete flag | false |
| `_deleted_at` | timestamp | Deletion time | null or timestamp |

---

## 📜 Version History (Auditing)

### How It Works
- **INSERT** → Creates Version 1
- **UPDATE** → Creates Version 2 (Version 1 still exists!)
- **UPDATE** → Creates Version 3 (all versions preserved)
- **DELETE** → Soft delete (marks `_deleted=true`, data still exists)

### Use Cases
1. **Compliance**: Salary change history, data modification trails
2. **Debugging**: See what value was before the bug
3. **Analytics**: Trend analysis over time
4. **Recovery**: Restore accidentally changed data

---

## 🔍 Query Patterns

### 1. View Complete Audit Trail
See ALL versions of a record:

```json
{
  "operation": "QUERY",
  "tenant_id": "test-tenant",
  "table": "users",
  "filter": {"name": {"eq": "Alice"}},
  "projection": ["_version", "_timestamp", "name", "age"],
  "sort": [{"field": "_version", "order": "asc"}]
}
```

**Result:**
```json
[
  {"_version": 1, "_timestamp": "2025-11-14 05:32:23", "age": 30},
  {"_version": 2, "_timestamp": "2025-11-14 05:33:36", "age": 31}
]
```

---

### 2. Get Current State (Latest Version)
```json
{
  "operation": "QUERY",
  "tenant_id": "test-tenant",
  "table": "users",
  "filter": {"name": {"eq": "Alice"}},
  "sort": [{"field": "_version", "order": "desc"}],
  "limit": 1
}
```

---

### 3. Track Field Changes Over Time
```json
{
  "operation": "QUERY",
  "tenant_id": "test-tenant",
  "table": "employees",
  "filter": {"employee_id": {"eq": "E001"}},
  "projection": ["_timestamp", "salary", "_version"],
  "sort": [{"field": "_timestamp", "order": "asc"}]
}
```

---

### 4. Find Changes in Time Range
```json
{
  "operation": "QUERY",
  "tenant_id": "test-tenant",
  "table": "users",
  "filter": {
    "_timestamp": {
      "gte": "2025-11-14T00:00:00",
      "lte": "2025-11-14T23:59:59"
    }
  },
  "sort": [{"field": "_timestamp", "order": "desc"}]
}
```

---

### 5. Point-in-Time Query (Time Travel)
Query data **as it existed** at a specific timestamp:

```json
{
  "operation": "QUERY",
  "tenant_id": "test-tenant",
  "table": "users",
  "as_of": "2025-11-14T05:32:00.000000",
  "limit": 100
}
```

This uses Iceberg's snapshot isolation to return data from that exact point in time.

---

### 6. View Soft-Deleted Records
```json
{
  "operation": "QUERY",
  "tenant_id": "test-tenant",
  "table": "users",
  "include_deleted": true,
  "filter": {"_deleted": {"eq": true}},
  "projection": ["name", "_deleted_at", "_timestamp"]
}
```

---

### 7. Count Versions Per Record
```json
{
  "operation": "QUERY",
  "tenant_id": "test-tenant",
  "table": "users",
  "aggregations": [
    {"op": "count", "field": null, "alias": "version_count"}
  ],
  "group_by": ["_record_id", "name"]
}
```

---

## ⏰ Time Travel Features

### Iceberg Snapshot-Based Time Travel
- Query data as it existed at any timestamp
- Based on Iceberg table snapshots
- No performance penalty for old data access

### Application-Level Version Tracking
- Every UPDATE creates a new version
- All versions stored as separate rows
- Efficient queries using `_version` and `_timestamp` indexes

---

## 🎯 Best Practices

### Performance
1. **For current data**: Use `sort + limit 1` pattern
2. **For history**: Query with `_record_id` filter
3. **For time ranges**: Use `_timestamp` filters
4. **Run COMPACT**: Periodically optimize storage

### Storage Management
- Versions accumulate over time
- Use `COMPACT` operation to optimize files
- Use snapshot expiration to remove old snapshots
- Configure retention policies based on compliance needs

### Query Optimization
- Always filter by `_tenant_id` first (partition key)
- Use `_record_id` for single-record history
- Use `_timestamp` for time-range queries
- Add indexes on frequently queried fields

---

## 🔐 Compliance & Audit Use Cases

### Financial Services
- Track all salary changes with timestamps
- Audit trail for regulatory compliance
- Immutable history for auditors

### Healthcare
- Patient record change history (HIPAA compliance)
- Track who changed what and when
- Point-in-time recovery for data corrections

### E-commerce
- Price change history
- Inventory adjustments audit trail
- Order modification tracking

### SaaS Applications
- User permission changes
- Configuration audit logs
- Subscription/billing history

---

## 🚀 Quick Start Examples

### See what Alice's salary was 6 months ago:
```json
{
  "operation": "QUERY",
  "table": "employees",
  "filter": {
    "name": {"eq": "Alice"},
    "_timestamp": {"lte": "2024-06-01T00:00:00"}
  },
  "sort": [{"field": "_timestamp", "order": "desc"}],
  "limit": 1
}
```

### Track price changes for Product X:
```json
{
  "operation": "QUERY",
  "table": "products",
  "filter": {"product_id": {"eq": "X"}},
  "projection": ["_timestamp", "price", "_version"],
  "sort": [{"field": "_timestamp", "order": "asc"}]
}
```

### Count total updates per user:
```json
{
  "operation": "QUERY",
  "table": "users",
  "aggregations": [
    {"op": "count", "field": null, "alias": "updates"}
  ],
  "group_by": ["name"],
  "sort": [{"field": "updates", "order": "desc"}]
}
```

---

## 💡 Key Takeaways

✅ **Automatic**: All audit fields added automatically  
✅ **Immutable**: Previous versions never deleted (until COMPACT)  
✅ **Performant**: Queries optimized with indexes  
✅ **Compliant**: Full audit trail for regulations  
✅ **Time Travel**: Query any point in history  
✅ **Soft Deletes**: Data never truly lost

---

## 📚 Additional Resources

- Apache Iceberg Time Travel: https://iceberg.apache.org/docs/latest/spark-queries/#time-travel
- DuckDB Temporal Queries: https://duckdb.org/docs/sql/query_syntax/from.html#temporal-queries
- ACID Compliance: Your data is always consistent and auditable

