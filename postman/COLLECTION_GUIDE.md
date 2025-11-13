# Postman Collection Guide

## 📦 Complete Collection - S3_ACID_Database_FastAPI_Complete

This is the comprehensive collection with **all features** organized into logical folders.

### 📋 Collection Structure

**Total Requests: 28** organized into 6 folders:

1. **00. Health Check** (1 request)
   - Basic health check endpoint

2. **01. Basic CRUD Operations** (7 requests)
   - CREATE_TABLE
   - WRITE
   - QUERY (all records)
   - UPDATE
   - DELETE (soft delete)
   - LIST_TABLES
   - DESCRIBE_TABLE

3. **02. Column Selection (Projection)** (3 requests)
   - Select specific columns
   - Select with system fields (_version, _timestamp)
   - Select with filter and sorting

4. **03. Aggregations & GROUP BY** (5 requests)
   - COUNT by department
   - Multiple aggregations (COUNT, SUM, AVG, MIN, MAX)
   - COUNT DISTINCT
   - GROUP BY with HAVING
   - Complex: WHERE + GROUP BY + HAVING

5. **04. Audit & Versioning** (4 requests)
   - View all versions of a record
   - Get latest version only
   - Track salary changes
   - Changes by department

6. **05. Soft Delete & Hard Delete** (4 requests)
   - Soft delete (sets _deleted=true)
   - Query without deleted records
   - Query including deleted records
   - Hard delete (permanent removal)

7. **06. Advanced Queries** (4 requests)
   - Complex filter conditions
   - LIKE pattern matching
   - Pagination example
   - COMPACT table

## 🚀 Quick Start

### 1. Import Collection

**File to import:**
```
postman/collections/S3_ACID_Database_FastAPI_Complete.postman_collection.json
```

### 2. Import Environment

**Choose environment:**
```
postman/environments/FastAPI.postman_environment.json  (Local FastAPI)
```

Or create a new environment with:
```json
{
  "baseUrl": "http://localhost:9000",
  "tenant_id": "test-tenant",
  "namespace": "default"
}
```

### 3. Run Collection

**Execute requests in order:**
1. Health Check → Verify service is running
2. Basic CRUD → Create table and insert data
3. Try other folders based on your needs

## 📊 Feature Examples

### Column Selection (Projection)

**Select specific columns:**
```json
{
  "operation": "QUERY",
  "tenant_id": "{{tenant_id}}",
  "table": "employees",
  "projection": ["name", "email", "department"]
}
```

**Result:** Only returns the 3 specified columns, reducing data transfer.

### Type-Safe Aggregations

**Clean aggregation syntax:**
```json
{
  "operation": "QUERY",
  "tenant_id": "{{tenant_id}}",
  "table": "employees",
  "projection": ["department"],
  "aggregations": [
    {"op": "count", "field": null, "alias": "headcount"},
    {"op": "avg", "field": "salary", "alias": "avg_salary"},
    {"op": "sum", "field": "salary", "alias": "total_payroll"}
  ],
  "group_by": ["department"]
}
```

**Available aggregation operations:**
- `count` - Count rows or distinct values
- `sum` - Sum of numeric values
- `avg` - Average
- `min` - Minimum value
- `max` - Maximum value
- `stddev` - Standard deviation
- `variance` - Variance
- `median` - Median value

### Audit & Versioning

**View complete change history:**
```json
{
  "operation": "QUERY",
  "tenant_id": "{{tenant_id}}",
  "table": "employees",
  "filter": {"employee_id": {"eq": "E001"}},
  "projection": ["_version", "_timestamp", "name", "department", "salary"],
  "sort": [{"field": "_version", "order": "asc"}]
}
```

**System fields for audit:**
- `_version` - Version number (increments on UPDATE)
- `_timestamp` - Timestamp of change
- `_record_id` - Unique record identifier
- `_deleted` - Soft delete flag
- `_deleted_at` - Deletion timestamp

### HAVING Clause

**Post-aggregation filtering:**
```json
{
  "operation": "QUERY",
  "tenant_id": "{{tenant_id}}",
  "table": "employees",
  "projection": ["department"],
  "aggregations": [
    {"op": "count", "field": null, "alias": "headcount"},
    {"op": "avg", "field": "salary", "alias": "avg_salary"}
  ],
  "group_by": ["department"],
  "having": {"headcount": {"gt": 2}}
}
```

**Result:** Only departments with more than 2 employees.

## 🎯 Common Use Cases

### 1. Employee Management
- Create employee table
- Add employees
- Update salaries/departments
- Track changes over time

### 2. Department Analytics
- Count employees per department
- Calculate average salary by department
- Find high-paying departments
- Identify departments needing more staff

### 3. Compliance & Audit
- View complete salary history
- Track department changes
- Monitor who made changes (via _timestamp)
- Verify data integrity

### 4. Data Cleanup
- Soft delete old records (recoverable)
- Hard delete PII data (GDPR compliance)
- View deleted records for recovery
- Compact tables for performance

## 📌 Important Notes

### Soft Delete vs Hard Delete

**Soft Delete:**
- Sets `_deleted=true` flag
- Record stays in storage
- Can be recovered
- Use for normal deletions

**Hard Delete:**
- Physically removes record
- IRREVERSIBLE
- Requires `confirm=true`
- Use for GDPR/PII compliance

### Versioning Behavior

**Every UPDATE creates a new version:**
- Version starts at 1
- Increments on each UPDATE
- All versions are preserved (ACID)
- Enables time-travel queries

**Example:**
1. INSERT record → version 1
2. UPDATE salary → version 2 (both v1 and v2 exist)
3. UPDATE department → version 3 (v1, v2, v3 exist)

### Performance Tips

1. **Use column selection** - Only fetch needed columns
2. **Run COMPACT** - After many writes, merge small files
3. **Use pagination** - For large result sets
4. **Create indexes** - On frequently filtered columns (future feature)

## 🔧 Troubleshooting

### Collection not working?

1. **Check service is running:**
   ```bash
   curl http://localhost:9000/health
   ```

2. **Verify environment variables:**
   - `baseUrl` should be `http://localhost:9000`
   - `tenant_id` can be any string (e.g., "test-tenant")
   - `namespace` defaults to "default"

3. **Check Docker services:**
   ```bash
   cd docker
   docker compose ps
   ```

### Common Errors

**"Table does not exist"**
- Run "CREATE TABLE" request first

**"Field required"**
- Check all required fields in request body
- Verify JSON syntax is correct

**"Validation error"**
- Check aggregation syntax (use `aggregations` field, not raw SQL)
- Verify filter operators (eq, gt, lt, etc.)

## 📚 Additional Resources

- [Main README](../README.md) - Project overview
- [Quick Start Guide](../docs/QUICKSTART.md) - Getting started
- [Configuration Guide](../docs/CONFIG.md) - Environment setup
- [API Documentation](../docs/API_REFERENCE.md) - Complete API reference

## 🎉 Ready to Use!

Import the collection and start exploring all the features. The requests are organized logically and include helpful descriptions.

**Happy Testing!** 🚀
