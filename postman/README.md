# Postman Collections & Environments

Complete Postman setup for testing Ibex DB API across different environments.

## 📦 Quick Start

### 1. Import Files

Import these files into Postman:

**Collections:**
- `collections/Ibex_DB_AWS.postman_collection.json` - AWS API Gateway (Production)
- `collections/Ibex_DB_FastAPI.postman_collection.json` - FastAPI (Local Development)

**Environments:**
- `environments/Production_CustomDomain.postman_environment.json` - ⭐ **Production (Clean URL)**
- `environments/AWS_API_Gateway.postman_environment.json` - Direct API Gateway URL
- `environments/FastAPI_Local.postman_environment.json` - Local development

### 2. Select Environment

Choose an environment based on your needs:

| Environment | When to Use | API Key Required |
|------------|-------------|------------------|
| **Production - Custom Domain** ⭐ | Production testing with clean URL | ✅ Yes |
| **AWS - API Gateway Direct** | Direct API Gateway access | ✅ Yes |
| **FastAPI - Local Development** | Local development & debugging | ❌ No |

---

## 🌐 Environments

### Production - Custom Domain ⭐ (RECOMMENDED)

**URL:** `https://smartlink.ajna.cloud/ibexdb`

**Variables:**
```json
{
  "baseUrl": "https://smartlink.ajna.cloud/ibexdb",
  "api_key": "McuMsuWDXo1g9zqLBBzVy3uXsIKDklGT8GbIhpyl",
  "tenant_id": "test-tenant",
  "namespace": "default"
}
```

**When to use:**
- ✅ Production testing
- ✅ Clean, professional URL
- ✅ Client demos
- ✅ External integrations

**Status:** ✅ Live and working

---

### AWS - API Gateway Direct

**URL:** `https://gcmdpajl1d.execute-api.ap-south-1.amazonaws.com/dev`

**Variables:**
```json
{
  "baseUrl": "https://gcmdpajl1d.execute-api.ap-south-1.amazonaws.com/dev",
  "api_key": "McuMsuWDXo1g9zqLBBzVy3uXsIKDklGT8GbIhpyl",
  "tenant_id": "test-tenant",
  "namespace": "default"
}
```

**When to use:**
- Direct AWS endpoint access
- Troubleshooting
- Custom domain unavailable

**Status:** ✅ Working

---

### FastAPI - Local Development

**URL:** `http://localhost:9000`

**Variables:**
```json
{
  "baseUrl": "http://localhost:9000",
  "tenant_id": "test-tenant",
  "namespace": "default"
}
```

**When to use:**
- Local development
- Testing changes before deployment
- Debugging
- No AWS costs

**Status:** Requires `docker-compose up -d fastapi`

**Setup:**
```bash
cd docker
docker-compose up -d fastapi minio
# Wait 5 seconds for services to start
```

---

## 📚 Collections

### Ibex_DB_AWS.postman_collection.json

Complete test suite for AWS API Gateway (production).

**Included Requests:**
1. **Table Management**
   - LIST_TABLES
   - CREATE_TABLE (products, users)
   - DROP_TABLE

2. **Data Operations**
   - WRITE (Insert records)
   - QUERY (Simple & filtered)
   - UPDATE (Single & bulk)
   - DELETE (Soft delete)

3. **Advanced Queries**
   - Filtering (eq, gt, gte, lt, lte, in, like)
   - Sorting (ASC, DESC)
   - Pagination (limit, offset)
   - Projections (select specific fields)

4. **Aggregations**
   - Count records
   - Sum, Average, Min, Max
   - Group By operations
   - Multiple aggregations

5. **Auditing & Time Travel**
   - View version history
   - Query data as of timestamp
   - Track all changes
   - View deleted records

6. **Performance**
   - COMPACT tables
   - Expire old snapshots
   - Optimize file sizes

**Required Environment Variables:**
- `baseUrl` - API endpoint
- `api_key` - API key for authentication
- `tenant_id` - Tenant identifier
- `namespace` - Table namespace

---

### Ibex_DB_FastAPI.postman_collection.json

Complete test suite for local FastAPI development.

**Differences from AWS Collection:**
- No API key required
- Includes Health Check endpoint
- Uses `/database` path
- Includes Documentation endpoints

**Additional Requests:**
- Health Check: `GET {{baseUrl}}/health`
- API Docs: `GET {{baseUrl}}/docs`
- API Schema: `GET {{baseUrl}}/openapi.json`

---

## 🔑 API Key Setup

### Current API Key
```
McuMsuWDXo1g9zqLBBzVy3uXsIKDklGT8GbIhpyl
```

**Usage in Postman:**

All AWS requests include this header:
```
x-api-key: {{api_key}}
```

The `{{api_key}}` variable is automatically populated from the environment.

### Create New API Key (if needed)

```bash
# Create new API key
aws apigateway create-api-key \
  --name "your-key-name" \
  --enabled \
  --region ap-south-1

# Link to usage plan
aws apigateway create-usage-plan-key \
  --usage-plan-id s85lwg \
  --key-id <YOUR_KEY_ID> \
  --key-type API_KEY \
  --region ap-south-1
```

---

## 🧪 Testing Workflow

### 1. Setup (One-time)

1. Import collections and environments into Postman
2. Select `Production - Custom Domain` environment
3. Verify `api_key` variable is set

### 2. Basic Test Flow

```
1. LIST_TABLES           → See existing tables
2. CREATE TABLE          → Create products table
3. WRITE - Insert        → Add sample data
4. QUERY - Simple        → Retrieve data
5. UPDATE                → Modify records
6. QUERY - Filtered      → Verify updates
7. DELETE                → Soft delete records
8. COMPACT               → Optimize table
```

### 3. Advanced Testing

**Auditing:**
```
1. WRITE records
2. UPDATE some records
3. DELETE some records
4. QUERY - View all versions
5. QUERY - Time travel (as_of timestamp)
6. QUERY - View deleted records
```

**Aggregations:**
```
1. WRITE - Insert products
2. QUERY - Count by category
3. QUERY - Average price
4. QUERY - Sum stock by category
```

**Bulk Operations:**
```
1. WRITE - 1000 records
2. UPDATE - Bulk update with filter
3. QUERY - Verify changes
4. COMPACT - Optimize
```

---

## 🎯 Example Requests

### List Tables
```http
POST {{baseUrl}}
Content-Type: application/json
x-api-key: {{api_key}}

{
  "operation": "LIST_TABLES",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}"
}
```

### Query with Filter
```http
POST {{baseUrl}}
Content-Type: application/json
x-api-key: {{api_key}}

{
  "operation": "QUERY",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "products",
  "filter": {
    "price": {"gte": 100, "lte": 500},
    "category": {"in": ["electronics", "furniture"]}
  },
  "sort": [{"field": "price", "order": "DESC"}],
  "limit": 10
}
```

### Bulk Update
```http
POST {{baseUrl}}
Content-Type: application/json
x-api-key: {{api_key}}

{
  "operation": "UPDATE",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "products",
  "filter": {
    "category": {"eq": "electronics"}
  },
  "updates": {
    "discount": 10,
    "on_sale": true
  }
}
```

### Time Travel Query
```http
POST {{baseUrl}}
Content-Type: application/json
x-api-key: {{api_key}}

{
  "operation": "QUERY",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "users",
  "as_of": "2025-11-13T00:00:00Z",
  "limit": 10
}
```

---

## 📊 Response Format

### Successful Query
```json
{
  "success": true,
  "data": [
    {
      "_tenant_id": "test-tenant",
      "_record_id": "abc123",
      "_timestamp": "2025-11-14T21:00:00.000Z",
      "_version": 1,
      "_deleted": false,
      "_deleted_at": null,
      "product_id": 1,
      "name": "Laptop",
      "price": 999.99
    }
  ],
  "metadata": {
    "row_count": 1,
    "execution_time_ms": 95.5,
    "scanned_bytes": 1024,
    "scanned_rows": 1,
    "cache_hit": false,
    "query_id": "xyz-789"
  },
  "request_id": "req-123",
  "execution_time_ms": 102.3
}
```

### Error Response
```json
{
  "success": false,
  "error": "Table not found: products",
  "request_id": "req-456",
  "timestamp": "2025-11-14T21:00:00.000Z"
}
```

---

## 🐛 Troubleshooting

### API Key Issues

**Error:** `{"message":"Forbidden"}`

**Solution:**
1. Verify `api_key` variable is set in environment
2. Check header: `x-api-key: {{api_key}}`
3. Ensure API key is linked to usage plan

### Custom Domain Not Working

**Error:** `{"message":"Not Found"}`

**Solution:**
1. Switch to "AWS - API Gateway Direct" environment
2. Custom domain may be propagating (wait 5-10 minutes)
3. Verify base path mapping exists

### Local FastAPI Not Running

**Error:** Connection refused

**Solution:**
```bash
cd docker
docker-compose ps  # Check if fastapi is running
docker-compose up -d fastapi  # Start if not running
docker-compose logs -f fastapi  # Check logs
```

### Wrong Request Format

**Error:** `Validation error: schema - Input should be a valid dictionary`

**Solution:**
- Ensure `schema` has `fields` key:
```json
{
  "schema": {
    "fields": {
      "id": {"type": "long", "required": true}
    }
  }
}
```

---

## 📝 Schema Format Reference

### Correct Format
```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "test-tenant",
  "namespace": "default",
  "table": "users",
  "schema": {
    "fields": {
      "id": {"type": "long", "required": true},
      "name": {"type": "string", "required": true},
      "email": {"type": "string", "required": false},
      "age": {"type": "integer", "required": false}
    }
  }
}
```

### Supported Types
- `boolean`
- `integer` / `int`
- `long`
- `float`
- `double`
- `decimal(precision, scale)`
- `date`
- `time`
- `timestamp`
- `timestamptz`
- `string`
- `uuid`
- `fixed(length)`
- `binary`

---

## 🚀 Performance Tips

1. **Use Projections**: Only select fields you need
   ```json
   {"projection": ["id", "name", "price"]}
   ```

2. **Add Indexes**: Use filters on indexed fields
   ```json
   {"filter": {"_tenant_id": {"eq": "test-tenant"}}}
   ```

3. **Limit Results**: Always use pagination
   ```json
   {"limit": 100, "offset": 0}
   ```

4. **Compact Regularly**: Optimize table files
   ```json
   {"operation": "COMPACT", "force": true}
   ```

5. **Use Cache**: Metadata is cached for 5 minutes

---

## 📞 Support

- **Documentation**: See `README.md` in project root
- **API Reference**: See `API_ENDPOINTS.md`
- **Schemas**: See `SCHEMA_FORMAT.md`

---

## ✅ Validation Checklist

Before considering the API production-ready:

- [x] All requests work with Production environment
- [x] API key authentication is working
- [x] Custom domain is accessible
- [x] CRUD operations function correctly
- [x] Filters and sorting work as expected
- [x] Aggregations return correct results
- [x] Time travel queries work
- [x] Bulk updates handle multiple records
- [x] Error responses are clear and helpful
- [x] Performance is acceptable (<200ms for reads)
- [x] Compaction optimizes table files

**Status:** ✅ Production Ready!
