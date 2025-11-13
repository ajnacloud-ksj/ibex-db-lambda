# Quick Start Guide - S3 ACID Database

## Full Iceberg Integration
- **PyIceberg**: Table creation and writes with ACID transactions
- **DuckDB + iceberg_scan**: Fast queries directly from Iceberg metadata
- **Polars + PyArrow**: Data transformation and type handling
- **REST Catalog**: Iceberg metadata management (easily replaceable with AWS Glue)

## Prerequisites
- Docker and Docker Compose
- Postman (for API testing)

## One-Command Setup

Start everything with a single command:

```bash
docker compose up -d
```

This automatically:
- ✅ Starts MinIO (S3-compatible storage)
- ✅ Creates buckets: `test-bucket` and `iceberg-warehouse`
- ✅ Starts Iceberg REST Catalog
- ✅ Deploys Lambda API with full Iceberg support

Wait ~15 seconds for all services to be healthy.

## Check Health

```bash
curl -X POST http://localhost:8080/2015-03-31/functions/function/invocations \
  -H "Content-Type: application/json" \
  -d '{"httpMethod":"GET","path":"/health"}' | jq .
```

Expected response:
```json
{
  "statusCode": 200,
  "body": "{\"status\": \"healthy\", \"service\": \"S3 ACID Database\", \"version\": \"1.0.0\"}"
}
```

## Using Postman

1. Import the collection: `S3_ACID_Database.postman_collection.json`
2. Run requests in order:
   1. **Health Check** - Verify API is running
   2. **CREATE TABLE** - Create users table with schema
   3. **WRITE** - Insert 3 users (Alice, Bob, Charlie)
   4. **QUERY - Get all users** - Retrieve all records
   5. **QUERY - Filter by name** - Find Alice
   6. **QUERY - Filter by age** - Find users age > 28
   7. **QUERY - With sorting** - Sort by age descending
   8. **UPDATE** - Change Alice's age to 31
   9. **DELETE** - Soft delete Charlie
   10. **LIST TABLES** - Show all tables
   11. **DESCRIBE TABLE** - Get schema info

## Filter Syntax

Filters use this format:
```json
{
  "filter": {
    "field_name": {
      "operator": "value"
    }
  }
}
```

### Supported Operators
- `eq`: Equal (=)
- `ne`: Not equal (!=)
- `gt`: Greater than (>)
- `gte`: Greater than or equal (>=)
- `lt`: Less than (<)
- `lte`: Less than or equal (<=)
- `in`: In list
- `like`: Pattern matching

### Examples

**Filter by exact match:**
```json
{"name": {"eq": "Alice"}}
```

**Filter by range:**
```json
{"age": {"gt": 25}}
```

**Filter by multiple conditions (AND):**
```json
{
  "and": [
    {"age": {"gt": 25}},
    {"name": {"like": "Al%"}}
  ]
}
```

## Architecture

### Write Path (PyIceberg)
1. Client → Lambda → PyIceberg
2. PyIceberg creates Iceberg metadata + Parquet files
3. Files stored in S3 (MinIO)
4. Metadata registered in REST Catalog

### Read Path (DuckDB)
1. Client → Lambda → PyIceberg (load table metadata)
2. Get metadata file location from catalog
3. DuckDB's `iceberg_scan` reads metadata + Parquet files
4. Query results returned to client

### Update Path (Hybrid)
1. Query existing records (DuckDB)
2. Modify records in memory
3. Write updated records (PyIceberg)
4. ACID guarantees via Iceberg transactions

## Viewing Data in MinIO

Access MinIO Console:
- URL: http://localhost:9006
- Username: `minioadmin`
- Password: `minioadmin`

Browse to:
- `test-bucket/iceberg-warehouse/test_tenant_default/users/`

You'll see:
- `data/` - Parquet files with actual data
- `metadata/` - Iceberg metadata files (.json, .avro)

## Stopping Services

```bash
docker compose down
```

To remove data volumes:
```bash
docker compose down -v
```

## Production Deployment

To use AWS Glue Catalog instead of REST Catalog:

1. Update `docker-compose.yml` environment:
```yaml
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

## Troubleshooting

**Lambda crashes on first request:**
- This is normal - Lambda Runtime Emulator initializes on first call
- Wait 2 seconds and retry

**No tables listed:**
- Ensure you ran CREATE TABLE first
- Check MinIO console for files

**Query returns empty:**
- Verify data was written (check WRITE response)
- Ensure filter syntax is correct
- Check tenant_id matches

## System Fields

Every record includes:
- `_tenant_id`: Multi-tenant isolation
- `_record_id`: Unique record identifier (MD5 hash)
- `_timestamp`: Record creation/update time
- `_version`: Optimistic locking version
- `_deleted`: Soft delete flag
- `_deleted_at`: Deletion timestamp

Queries automatically filter out deleted records (`_deleted = false`).
