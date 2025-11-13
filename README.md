# S3 ACID Database

A production-ready, serverless ACID database built on **Apache Iceberg**, **DuckDB**, and **S3** with full PyIceberg integration.

## Features

- ✅ **Full ACID Transactions** - Apache Iceberg with PyIceberg for writes
- ✅ **Fast Queries** - DuckDB with native Iceberg support
- ✅ **Type-Safe API** - Complete Pydantic validation
- ✅ **Centralized Config** - Single `config.json` for all environments
- ✅ **Multi-Tenant** - Built-in tenant isolation
- ✅ **Production Ready** - Supports AWS Glue Catalog + S3
- ✅ **Zero Manual Setup** - Automated initialization with Docker Compose
- ✅ **REST Catalog (Dev)** - Easy local development
- ✅ **Glue Catalog (Prod)** - Seamless AWS integration

## Architecture

**Write Path:**
```
Client → Lambda → PyIceberg → REST Catalog/Glue
                             → S3 (Parquet + Metadata)
```

**Read Path:**
```
Client → Lambda → PyIceberg (get metadata location)
               → DuckDB iceberg_scan → S3 (read Parquet)
```

## 📁 Project Structure

```
s3-acid-database/
├── src/                          # Python source code
├── tests/e2e/                    # End-to-end tests
├── docker/                       # Docker files
│   ├── Dockerfile                # Lambda runtime
│   ├── Dockerfile.fastapi        # FastAPI runtime
│   └── docker-compose.yml        # Service orchestration
├── docs/                         # Documentation
├── postman/                      # API collections & environments
├── config/                       # Configuration files
├── fastapi_app.py               # FastAPI entry point
└── README.md                    # This file
```

## Quick Start

### Option 1: FastAPI (Recommended for Development)

```bash
# Start FastAPI service
cd docker
docker compose up -d fastapi

# Wait 10 seconds, then check health
curl http://localhost:9000/health

# Run comprehensive test suite
cd ..
bash tests/e2e/test_fastapi_compaction.sh
```

### Option 2: Lambda Runtime (For Production Testing)

```bash
# Start Lambda service
cd docker
docker compose up -d lambda

# Test via Lambda Runtime Interface
curl -X POST http://localhost:8080/2015-03-31/functions/function/invocations \
  -H "Content-Type: application/json" \
  -d '{"httpMethod":"GET","path":"/health"}' | jq .
```

### Using Postman

1. **Import Collection**: `postman/collections/S3_ACID_Database_FastAPI.postman_collection.json`
2. **Import Environment**: Choose from `postman/environments/` directory:
   - `FastAPI.postman_environment.json` - Local FastAPI testing
   - `Development.postman_environment.json` - Local Lambda testing
   - `Staging.postman_environment.json` - AWS staging
   - `Production.postman_environment.json` - AWS production
3. **Select Environment**: Use the dropdown in top-right corner
4. **Run Requests**: Execute the requests in order

The collection uses environment variables, making it easy to switch between dev/staging/production.

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for detailed API examples.

## Configuration

All settings are in `config/config.json` with **no hardcoding or fallbacks**.

**Development:**
```yaml
environment:
  ENVIRONMENT: development
# All other settings loaded from config/config.json
```

**Production:**
```yaml
environment:
  ENVIRONMENT: production
  BUCKET_NAME: your-prod-bucket
  AWS_REGION: us-east-1
  AWS_ACCOUNT_ID: "123456789012"
```

See [docs/CONFIG.md](docs/CONFIG.md) for complete configuration guide.

## API Operations

| Operation | Description |
|-----------|-------------|
| **CREATE_TABLE** | Create Iceberg table with schema |
| **WRITE** | Insert records (ACID transaction) |
| **QUERY** | Query with filters, sorting, limits (`include_deleted` parameter) |
| **UPDATE** | Update records by filter |
| **DELETE** | Soft delete records (sets `_deleted=true`) |
| **HARD_DELETE** | Permanent deletion (requires `confirm=true`) |
| **LIST_TABLES** | List all tables in namespace |
| **DESCRIBE_TABLE** | Get table schema and stats |
| **COMPACT** | Merge small files for better performance |

### Filter Syntax

```json
{
  "filter": {
    "name": {"eq": "Alice"},
    "age": {"gt": 25}
  }
}
```

Supported operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `like`, `between`

## System Fields

Every record automatically includes:

- `_tenant_id` - Multi-tenant isolation
- `_record_id` - Unique record ID (MD5 hash)
- `_timestamp` - Creation/update timestamp
- `_version` - Optimistic locking version
- `_deleted` - Soft delete flag
- `_deleted_at` - Deletion timestamp

## Services

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| **FastAPI** | 9000 | http://localhost:9000 | Recommended for development |
| Lambda API | 8080 | http://localhost:8080 | Production testing |
| MinIO Console | 9006 | http://localhost:9006 | View S3 data |
| MinIO API | 9005 | http://localhost:9005 | S3-compatible storage |
| REST Catalog | 8181 | http://localhost:8181 | Iceberg metadata (dev only) |

## Testing

Run comprehensive end-to-end test suite:
```bash
# Test with FastAPI (recommended)
bash tests/e2e/test_fastapi_compaction.sh
```

Tests all operations: CREATE → WRITE → QUERY → UPDATE → DELETE → HARD_DELETE → COMPACT

## Production Deployment

### Switch to AWS Glue Catalog

1. Update environment:
   ```yaml
   ENVIRONMENT: production
   BUCKET_NAME: your-bucket
   AWS_REGION: us-east-1
   AWS_ACCOUNT_ID: "123456789012"
   ```

2. Deploy to AWS Lambda or ECS

3. Ensure IAM role has:
   - Glue permissions: `glue:*`
   - S3 permissions: `s3:*`

No code changes required - just environment variables!

See [docs/CONFIG.md](docs/CONFIG.md) for detailed production deployment guide.

## Tech Stack

- **Apache Iceberg** - ACID table format
- **PyIceberg** - Python library for Iceberg operations
- **DuckDB** - Fast SQL query engine with Iceberg support
- **Polars** - High-performance DataFrame library
- **PyArrow** - Columnar data format
- **Pydantic** - Type-safe data validation
- **MinIO** - S3-compatible storage (local dev)
- **Tabular.io REST Catalog** - Iceberg metadata service (local dev)
- **AWS Glue** - Managed Iceberg catalog (production)

## Key Design Principles

✅ **No Hardcoding** - All config in `config.json`
✅ **No Fallbacks** - Explicit configuration required
✅ **Simple & Clean** - One file controls everything
✅ **Production Ready** - Easy AWS deployment
✅ **Type Safe** - Full Pydantic validation

## Documentation

- [docs/QUICKSTART.md](docs/QUICKSTART.md) - Quick reference guide
- [docs/README_SETUP.md](docs/README_SETUP.md) - Complete setup guide with troubleshooting
- [docs/CONFIG.md](docs/CONFIG.md) - Configuration system guide
- [postman/README.md](postman/README.md) - Postman collection guide

## Requirements

- Docker & Docker Compose
- Postman (optional, for API testing)

## License

MIT

---

**Built with Apache Iceberg, DuckDB, and S3 for production-grade ACID transactions on object storage.**
