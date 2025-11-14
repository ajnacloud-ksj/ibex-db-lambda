# Postman Collections & Environments

Clean, simple Postman setup for testing Ibex DB Lambda.

## 📦 What's Included

### Collections (2)
1. **Ibex_DB_FastAPI.postman_collection.json** - For local FastAPI development
2. **Ibex_DB_AWS.postman_collection.json** - For AWS API Gateway production

### Environments (2)
1. **FastAPI_Local.postman_environment.json** - Local development (`http://localhost:9000`)
2. **AWS_API_Gateway.postman_environment.json** - Production (`https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda`)

---

## 🚀 Quick Start

### For Local Development (FastAPI)

**Step 1: Start FastAPI**
```bash
cd docker
docker-compose up -d fastapi
```

**Step 2: Import to Postman**
1. Open Postman
2. Import:
   - `collections/Ibex_DB_FastAPI.postman_collection.json`
   - `environments/FastAPI_Local.postman_environment.json`
3. Select environment: **FastAPI - Local Development**
4. Run requests in order!

**URL**: `http://localhost:9000/database`

---

### For AWS Production (API Gateway)

**Step 1: Import to Postman**
1. Open Postman
2. Import:
   - `collections/Ibex_DB_AWS.postman_collection.json`
   - `environments/AWS_API_Gateway.postman_environment.json`
3. Select environment: **AWS - API Gateway Production**
4. Run requests!

**URL**: `https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda`

---

## 📋 Collection Contents

### FastAPI Collection (10 requests)
1. Health Check
2. CREATE TABLE - users
3. WRITE - Insert users
4. QUERY - All users
5. QUERY - With filter
6. UPDATE - Update user
7. DELETE - Soft delete
8. LIST_TABLES
9. DESCRIBE_TABLE
10. COMPACT - Optimize files

### AWS Collection (10 requests)
1. LIST_TABLES
2. CREATE TABLE - products
3. WRITE - Insert products
4. QUERY - All products
5. QUERY - With filter
6. UPDATE - Update price
7. DELETE - Soft delete
8. DESCRIBE_TABLE
9. COMPACT - Optimize files
10. Query existing - users table

---

## ⚙️ Environment Variables

Both environments use these variables:

| Variable | FastAPI | AWS |
|----------|---------|-----|
| `baseUrl` | `http://localhost:9000` | `https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda` |
| `tenant_id` | `test-tenant` | `test-tenant` |
| `namespace` | `default` | `default` |

**To change tenant:**
1. Click **Environments** in Postman
2. Select your environment
3. Change `tenant_id` value
4. Save

---

## 🔧 How Requests Work

### FastAPI Format
```http
POST http://localhost:9000/database
Content-Type: application/json

{
  "operation": "QUERY",
  "tenant_id": "test-tenant",
  "namespace": "default",
  "table": "users"
}
```

### AWS API Gateway Format
```http
POST https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda
Content-Type: application/json

{
  "operation": "QUERY",
  "tenant_id": "test-tenant",
  "namespace": "default",
  "table": "users"
}
```

**Key Difference**: 
- FastAPI uses `/database` path
- API Gateway uses base URL directly (no `/database` path)

---

## 🧪 Test Scenarios

### Scenario 1: Complete CRUD Flow (FastAPI)

1. Health Check → Verify server is running
2. CREATE TABLE → Create `users` table
3. WRITE → Insert 3 users (Alice, Bob, Charlie)
4. QUERY All → See all users
5. UPDATE → Update Alice's age
6. QUERY Filter → Query users by age
7. DELETE → Soft delete Charlie
8. QUERY All → See remaining users (Charlie marked deleted)
9. LIST_TABLES → Verify table exists
10. COMPACT → Optimize files

### Scenario 2: Production Test (AWS)

1. LIST_TABLES → See existing tables
2. CREATE TABLE → Create `products` table
3. WRITE → Insert 3 products
4. QUERY All → See all products
5. QUERY Filter → Find cheap products
6. UPDATE → Update laptop price
7. DESCRIBE → Check table schema
8. Query existing → Test `users` table (if exists)

---

## 📊 Expected Responses

### Success Response
```json
{
  "success": true,
  "data": [...],
  "metadata": {
    "row_count": 3,
    "execution_time_ms": 123.45
  },
  "request_id": "abc-123-def",
  "execution_time_ms": 123.45
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error message",
  "request_id": "abc-123-def",
  "timestamp": "2025-11-14T12:34:56.789Z"
}
```

---

## 🐛 Troubleshooting

### FastAPI: "Could not send request"
**Solution:**
```bash
# Check if FastAPI is running
docker-compose ps

# Start if not running
docker-compose up -d fastapi

# Check logs
docker-compose logs fastapi
```

### AWS: "Could not get any response"
**Solution:**
1. Verify API Gateway URL is correct
2. Test with curl:
   ```bash
   curl -X POST "https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda" \
     -H "Content-Type: application/json" \
     -d '{"operation":"LIST_TABLES","tenant_id":"test-tenant","namespace":"default"}'
   ```
3. Check Lambda logs in CloudWatch

### Variables not replacing (showing as `{{baseUrl}}`)
**Solution:**
1. Make sure environment is selected (top-right dropdown)
2. Variables should turn orange when hovering
3. Re-import environment if needed

---

## 📝 Tips

### 1. Run Collection Automatically
1. Click collection name → **Run**
2. Select environment
3. Click **Run Collection**
4. All requests run in sequence!

### 2. Save Responses
Right-click on request → **Save as Example**

### 3. Test Different Tenants
Change `tenant_id` in environment:
- `test-tenant` → Your data
- `customer-123` → Different tenant
- `demo-tenant` → Demo data

Data is isolated per tenant!

### 4. View Request Details
Click **Console** (bottom) to see:
- Full request/response
- Headers
- Timing
- Errors

---

## 🎯 Common Operations

### Create New Table
```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "test-tenant",
  "namespace": "default",
  "table": "orders",
  "schema": [
    {"name": "order_id", "type": "long", "nullable": false},
    {"name": "customer_name", "type": "string", "nullable": false},
    {"name": "total", "type": "double", "nullable": false}
  ]
}
```

### Query with Aggregations
```json
{
  "operation": "QUERY",
  "tenant_id": "test-tenant",
  "table": "orders",
  "aggregations": [
    {"op": "sum", "field": "total", "alias": "total_revenue"},
    {"op": "count", "field": null, "alias": "order_count"}
  ],
  "group_by": ["customer_name"]
}
```

### Hard Delete (Physical)
```json
{
  "operation": "DELETE",
  "tenant_id": "test-tenant",
  "table": "users",
  "filter": {"id": {"eq": 1}},
  "hard_delete": true
}
```

---

## 📚 Additional Resources

- **Main README**: `../../README.md`
- **API Documentation**: Start FastAPI and visit `http://localhost:9000/documentation`
- **Swagger UI**: `http://localhost:9000/docs` (FastAPI only)
- **Lambda Test Events**: `../lambda_test_events/`
- **Test Script**: `../../test_local.sh`

---

## 🔐 Security Notes

### Local Development
- ✅ No authentication needed
- ✅ Accessible only on localhost
- ✅ Use test data only

### AWS Production
- ⚠️ **Currently no authentication** (be careful!)
- 🔒 Recommended: Enable IAM authentication
- 🔒 Recommended: Add API key
- 🔒 Recommended: Enable throttling

**To add API key:**
1. AWS Console → API Gateway
2. Create API Key
3. Create Usage Plan
4. In Postman, add header: `x-api-key: YOUR_KEY`

---

## ✅ Checklist Before Production

- [ ] Enable IAM authentication on API Gateway
- [ ] Add API key and usage plan
- [ ] Enable CloudWatch logging
- [ ] Set up throttling (100 req/s recommended)
- [ ] Test with production tenant ID
- [ ] Run compaction after bulk loads
- [ ] Set up monitoring alerts
- [ ] Document API for your team

---

**Happy Testing! 🚀**

Questions? Check the main [README.md](../../README.md) or logs:
```bash
# FastAPI logs
docker-compose logs fastapi

# AWS Lambda logs
aws logs tail /aws/lambda/ibex-db-lambda --follow --region ap-south-1
```

