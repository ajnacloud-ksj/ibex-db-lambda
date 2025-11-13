# S3 ACID Database - Complete Setup Guide

## ✅ Fully Automated Setup

Everything is configured to work out-of-the-box with **zero manual setup required**!

## Quick Start (One Command)

```bash
docker compose up -d
```

Wait ~20 seconds for services to initialize, then you're ready to go!

### What Happens Automatically:

1. **MinIO** starts (S3-compatible storage)
2. **minio-init** container automatically:
   - Creates `test-bucket` bucket
   - Creates `iceberg-warehouse` bucket
   - Sets public access policies
   - Exits when done ✓
3. **Iceberg REST Catalog** starts
4. **Lambda API** starts with full Iceberg support

## Verify Setup

```bash
curl -X POST http://localhost:8080/2015-03-31/functions/function/invocations \
  -H "Content-Type: application/json" \
  -d '{"httpMethod":"GET","path":"/health"}' | jq .
```

Expected output:
```json
{
  "statusCode": 200,
  "body": "{\"status\": \"healthy\", \"service\": \"S3 ACID Database\", \"version\": \"1.0.0\"}"
}
```

## Using Postman

### Import Collection
1. Open Postman
2. Import → Upload Files
3. Select: `S3_ACID_Database.postman_collection.json`

### Run Requests in Order
The collection contains 11 ready-to-use requests:

1. **Health Check** - Verify API is running ✓
2. **CREATE TABLE** - Create users table with schema
3. **WRITE** - Insert 3 users (Alice, Bob, Charlie)
4. **QUERY - Get all users** - Retrieve all records
5. **QUERY - Filter by name** - Find Alice specifically
6. **QUERY - Filter by age** - Find users where age > 28
7. **QUERY - With sorting** - Sort by age descending
8. **UPDATE** - Change Alice's age from 30 to 31
9. **DELETE** - Soft delete Charlie (_deleted=true)
10. **LIST TABLES** - Show all tables in namespace
11. **DESCRIBE TABLE** - Get schema and statistics

**Important:** Wait 1-2 seconds between CREATE_TABLE and WRITE for table metadata to sync.

## Architecture Overview

```
┌─────────────┐
│   Client    │
│  (Postman)  │
└──────┬──────┘
       │
       v
┌─────────────────────┐
│  Lambda Container   │
│  (Port 8080)        │
├─────────────────────┤
│ • PyIceberg (Write) │
│ • DuckDB (Read)     │
│ • Polars (Convert)  │
└──────┬──────┬───────┘
       │      │
       v      v
┌──────────┐ ┌──────────────┐
│  MinIO   │ │ REST Catalog │
│ (S3 API) │ │  (Metadata)  │
│ Port 9005│ │   Port 8181  │
└──────────┘ └──────────────┘
```

### Write Path
```
Client → Lambda → PyIceberg → REST Catalog (register metadata)
                            → MinIO (write Parquet + metadata)
```

### Read Path
```
Client → Lambda → PyIceberg (get metadata location)
               → DuckDB iceberg_scan(metadata) → MinIO (read Parquet)
```

## Filter Syntax

All filters use this format:
```json
{
  "filter": {
    "field_name": {"operator": "value"}
  }
}
```

### Examples

**Equal:**
```json
{"name": {"eq": "Alice"}}
```

**Greater than:**
```json
{"age": {"gt": 25}}
```

**Range:**
```json
{"age": {"between": [25, 35]}}
```

**Pattern matching:**
```json
{"email": {"like": "%example.com"}}
```

**Multiple conditions (AND):**
```json
{
  "and": [
    {"age": {"gte": 25}},
    {"name": {"like": "A%"}}
  ]
}
```

**Multiple conditions (OR):**
```json
{
  "or": [
    {"age": {"lt": 30}},
    {"age": {"gt": 40}}
  ]
}
```

## Services & Ports

| Service | Port | URL | Credentials |
|---------|------|-----|-------------|
| Lambda API | 8080 | http://localhost:8080 | - |
| MinIO Console | 9006 | http://localhost:9006 | minioadmin / minioadmin |
| MinIO API | 9005 | http://localhost:9005 | - |
| REST Catalog | 8181 | http://localhost:8181 | - |

## Viewing Data

### MinIO Console
1. Open: http://localhost:9006
2. Login: `minioadmin` / `minioadmin`
3. Navigate to: `test-bucket` → `iceberg-warehouse` → `test_tenant_default` → `users`

You'll see:
- `data/` - Parquet files with actual records
- `metadata/` - Iceberg metadata (.json, .avro files)

### Docker Logs
```bash
# View Lambda logs
docker compose logs -f lambda-api

# View MinIO logs
docker compose logs -f minio

# View REST Catalog logs
docker compose logs -f iceberg-rest

# View init container logs (buckets creation)
docker compose logs minio-init
```

## System Fields

Every record automatically includes:

| Field | Type | Description |
|-------|------|-------------|
| `_tenant_id` | string | Multi-tenant isolation |
| `_record_id` | string | Unique MD5 hash of record |
| `_timestamp` | timestamp | Creation/update time |
| `_version` | int | Optimistic locking version |
| `_deleted` | boolean | Soft delete flag |
| `_deleted_at` | timestamp | Deletion time (null if not deleted) |

Queries automatically exclude deleted records (`WHERE _deleted IS NOT TRUE`).

## Common Operations

### Fresh Start
```bash
docker compose down -v  # Remove volumes
docker compose up -d    # Start fresh
```

### View Status
```bash
docker compose ps
```

### Stop Services
```bash
docker compose down
```

### Restart Lambda (if crashed)
```bash
docker compose restart lambda-api
```

## Troubleshooting

### Lambda doesn't respond
**Solution:** Wait 15-20 seconds after `docker compose up -d` for Lambda to initialize.

### "Empty reply from server"
**Solution:** Lambda Runtime Emulator initializes on first request. Wait 2 seconds and retry.

### CREATE TABLE works but WRITE fails
**Solution:** Wait 1-2 seconds between CREATE_TABLE and WRITE for metadata sync.

### Query returns 0 results
**Checklist:**
- ✓ Did WRITE return `records_written: N`?
- ✓ Is `tenant_id` correct in query?
- ✓ Is filter syntax correct? (e.g., `{"name": {"eq": "value"}}`)

### MinIO Console shows no files
**Solution:**
```bash
docker compose logs minio-init  # Verify buckets created
```

## Production Deployment

### Switch to AWS Glue Catalog

1. Update `docker-compose.yml`:
```yaml
environment:
  CATALOG_TYPE: glue
  AWS_ACCOUNT_ID: your-account-id
```

2. Update `src/operations_full_iceberg.py`:
```python
from pyiceberg.catalog.glue import GlueCatalog

catalog = GlueCatalog(
    name="glue",
    **{
        "region_name": AWS_REGION,
        "s3.region": AWS_REGION,
        "warehouse": f"s3://{BUCKET_NAME}/iceberg-warehouse"
    }
)
```

3. Replace MinIO with real S3:
```yaml
environment:
  BUCKET_NAME: your-real-bucket
  # Remove S3_ENDPOINT (use real AWS S3)
```

## Testing

Run automated test suite:
```bash
chmod +x test_workflow.sh
./test_workflow.sh
```

This validates:
- ✓ CREATE TABLE
- ✓ WRITE (3 records)
- ✓ QUERY (all records)
- ✓ QUERY (with filter)
- ✓ UPDATE (modify record)
- ✓ DELETE (soft delete)
- ✓ LIST TABLES
- ✓ DESCRIBE TABLE

## File Structure

```
s3-acid-database/
├── docker-compose.yml                          # Service orchestration
├── Dockerfile                                   # Lambda container
├── S3_ACID_Database.postman_collection.json    # ✓ Ready-to-use API tests
├── QUICKSTART.md                                # Quick reference
├── README_SETUP.md                              # This file
├── test_workflow.sh                             # Automated tests
├── src/
│   ├── lambda_handler.py                        # API Gateway handler
│   ├── operations_full_iceberg.py               # ✓ PyIceberg + DuckDB
│   ├── models.py                                # Type-safe Pydantic models
│   ├── query_builder.py                         # SQL query builder
│   └── config.py                                # Configuration
└── pyproject.toml                               # Dependencies
```

## Dependencies

Automatically installed in Docker container:
- **pyiceberg** - Iceberg table operations
- **duckdb** - Query engine with iceberg_scan
- **polars** - Data transformation
- **pyarrow** - Columnar data format
- **pydantic** - Type validation
- **boto3** - S3 operations

## Next Steps

1. ✓ `docker compose up -d`
2. ✓ Import Postman collection
3. ✓ Run "Health Check" request
4. ✓ Run "CREATE TABLE" request
5. ✓ Run "WRITE" request
6. ✓ Run "QUERY" requests
7. ✓ Experiment with filters and updates
8. ✓ View data in MinIO Console

**Everything is ready to use! No manual setup required.**

## Support

For issues:
1. Check `docker compose logs lambda-api`
2. Verify `docker compose ps` shows all services as healthy
3. Ensure ports 8080, 9005, 9006, 8181 are available

**The system is fully automated and production-ready!** 🚀
