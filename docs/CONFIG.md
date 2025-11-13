# Configuration Guide

## Overview

All configuration is centralized in `config.json` with **NO hardcoded defaults or fallbacks**. This ensures clean, predictable behavior across environments.

## How It Works

1. **Environment Selection**: Set `ENVIRONMENT` variable to: `development`, `staging`, `production`, or `testing`
2. **Config Loading**: All settings load from `config.json` based on environment
3. **Variable Substitution**: Use `${VAR_NAME}` for dynamic values (production secrets)

## Configuration File Structure

```json
{
  "development": {
    "environment": "development",
    "s3": { ... },
    "catalog": { ... },
    "duckdb": { ... },
    "lambda": { ... },
    "performance": { ... }
  },
  "production": {
    ...
  }
}
```

## Environments

### Development (Local with MinIO + REST Catalog)

```yaml
# docker-compose.yml
environment:
  ENVIRONMENT: development
```

Configuration in `config.json`:
- S3: MinIO with hardcoded credentials
- Catalog: REST catalog at `http://iceberg-rest:8181`
- DuckDB: 2GB memory, 4 threads
- Performance: 5 retries, 30s timeout

### Staging (AWS S3 + Glue Catalog)

```yaml
# docker-compose.yml or Lambda environment
environment:
  ENVIRONMENT: staging
  BUCKET_NAME: my-staging-bucket
  AWS_REGION: us-east-1
  AWS_ACCOUNT_ID: "123456789012"
```

Configuration in `config.json`:
- S3: Real AWS S3 (uses IAM role)
- Catalog: AWS Glue
- DuckDB: 2GB memory, 4 threads
- Performance: 3 retries, 45s timeout

### Production (AWS S3 + Glue Catalog)

```yaml
# Lambda environment
environment:
  ENVIRONMENT: production
  BUCKET_NAME: my-production-bucket
  AWS_REGION: us-east-1
  AWS_ACCOUNT_ID: "123456789012"
```

Configuration in `config.json`:
- S3: Real AWS S3 with SSL (uses IAM role)
- Catalog: AWS Glue
- DuckDB: 4GB memory, 8 threads
- Performance: 3 retries, 60s timeout

### Testing (Local with MinIO + REST Catalog)

```yaml
# Test scripts
environment:
  ENVIRONMENT: testing
```

Configuration in `config.json`:
- S3: MinIO at `localhost:9005`
- Catalog: REST catalog at `localhost:8181`
- DuckDB: 1GB memory, 2 threads
- Performance: 3 retries, 10s timeout

## Configuration Sections

### S3 Configuration

```json
{
  "bucket_name": "test-bucket",           // S3 bucket name
  "warehouse_path": "iceberg-warehouse",   // Path within bucket
  "endpoint": "http://minio:9000",         // Optional: MinIO endpoint (dev only)
  "region": "us-east-1",                   // AWS region
  "access_key_id": "minioadmin",           // Optional: Credentials (dev only)
  "secret_access_key": "minioadmin",       // Optional: Credentials (dev only)
  "use_ssl": false,                        // SSL for S3 connections
  "path_style_access": true                // Path-style vs virtual-hosted style
}
```

**Production Note**: Omit `endpoint`, `access_key_id`, and `secret_access_key` in production. Use IAM roles instead.

### Catalog Configuration

```json
{
  "type": "rest",                          // "rest" or "glue"
  "name": "rest",                          // Catalog name
  "uri": "http://iceberg-rest:8181"        // For REST catalog
}
```

Or for Glue:

```json
{
  "type": "glue",
  "name": "glue",
  "account_id": "${AWS_ACCOUNT_ID}",       // Substituted from env var
  "region": "${AWS_REGION}"                // Substituted from env var
}
```

### DuckDB Configuration

```json
{
  "memory_limit": "2GB",                   // Memory limit for DuckDB
  "threads": 4                             // Number of threads
}
```

### Lambda Configuration

```json
{
  "timeout": 900,                          // Seconds
  "memory_size": 3008                      // MB
}
```

### Performance Configuration

```json
{
  "max_retries": 5,                        // Retry attempts
  "query_timeout_ms": 30000,               // Query timeout in milliseconds
  "batch_size": 1000                       // Batch size for operations
}
```

## Environment Variable Substitution

Use `${VAR_NAME}` in `config.json` for values that should come from environment variables:

```json
{
  "bucket_name": "${BUCKET_NAME}",
  "region": "${AWS_REGION}"
}
```

Required environment variables:
- **Production/Staging**: `BUCKET_NAME`, `AWS_REGION`, `AWS_ACCOUNT_ID`
- **Development/Testing**: None (all values in config.json)

## Usage in Code

### Get Config Instance

```python
from config import get_config

config = get_config()
```

### Access Configuration

```python
# Get S3 config
s3_config = config.s3
bucket = config.get('s3', 'bucket_name')

# Get catalog config
catalog_type = config.get('catalog', 'type')

# Get DuckDB config
duckdb_config = config.duckdb
memory = duckdb_config['memory_limit']
```

### Convenience Functions

```python
from config import get_s3_config, get_catalog_config, get_duckdb_config

s3 = get_s3_config()
catalog = get_catalog_config()
duckdb = get_duckdb_config()
```

## Switching Environments

### Local Development → Production

1. Update `ENVIRONMENT` variable:
   ```yaml
   environment:
     ENVIRONMENT: production
     BUCKET_NAME: my-prod-bucket
     AWS_REGION: us-east-1
     AWS_ACCOUNT_ID: "123456789012"
   ```

2. Ensure IAM role has permissions:
   - Glue: `glue:*` on catalog, databases, tables
   - S3: `s3:*` on bucket

3. Remove REST catalog container (not needed in production)

4. Deploy to AWS Lambda or ECS

That's it! No code changes required.

## Modifying Configuration

### Add New Setting

1. Add to `config.json` for each environment:
   ```json
   {
     "development": {
       "my_new_setting": "value"
     }
   }
   ```

2. Access in code:
   ```python
   value = config.get('my_new_setting')
   ```

### Change Environment-Specific Value

Edit the appropriate section in `config.json`:

```json
{
  "development": {
    "performance": {
      "query_timeout_ms": 60000  // Increased from 30000
    }
  }
}
```

Restart container to apply changes.

## Validation

The config loader validates:
- ✅ `ENVIRONMENT` variable is set
- ✅ Environment exists in `config.json`
- ✅ Required environment variables for substitution are present
- ✅ Config file exists and is valid JSON

If any validation fails, you'll get a clear error message:
```
ValueError: ENVIRONMENT not set. Must be one of: development, staging, production, testing
```

## Best Practices

1. **No Hardcoding**: Never add defaults or fallbacks in code
2. **Environment Variables**: Use for secrets in production only
3. **Config.json**: Use for all non-secret configuration
4. **Documentation**: Update this file when adding new settings
5. **Testing**: Test each environment before deploying

## Troubleshooting

### Error: "ENVIRONMENT not set"
- **Solution**: Set `ENVIRONMENT` variable in docker-compose.yml or Lambda config

### Error: "Environment 'xyz' not found in config.json"
- **Solution**: Check spelling of ENVIRONMENT value, must match config.json keys exactly

### Error: "Environment variable 'BUCKET_NAME' not set"
- **Solution**: Add required environment variable for production/staging

### Error: "Configuration file not found"
- **Solution**: Ensure `config.json` exists in project root

## Summary

✅ **Clean**: No hardcoded defaults or fallbacks
✅ **Simple**: One file to modify for all environments
✅ **Elegant**: Environment-based configuration with validation
✅ **Flexible**: Easy to add new environments or settings
✅ **Production-Ready**: Supports IAM roles and AWS Glue
