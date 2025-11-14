# AWS Lambda Test Events

These are ready-to-use test events for testing your Lambda function directly from the AWS Lambda Console UI.

## 🧪 How to Use

### Step 1: Open Lambda Console
1. Go to [AWS Lambda Console](https://console.aws.amazon.com/lambda)
2. Select your function: **ibex-db-lambda**
3. Click the **Test** tab

### Step 2: Create Test Events

Click **Create new test event** and paste the JSON content from each file below:

#### Test Sequence (Run in Order):

1. **`01_health_check.json`** - Verify Lambda is running
   - Event name: `health-check`
   - Should return: `{"status": "healthy", "service": "S3 ACID Database"}`

2. **`02_create_table.json`** - Create users table
   - Event name: `create-table-users`
   - Creates table with schema: name (string), email (string), age (integer)

3. **`03_write_users.json`** - Insert 3 users
   - Event name: `write-users`
   - Inserts: Alice, Bob, Charlie

4. **`04_query_all_users.json`** - Query all users
   - Event name: `query-all-users`
   - Should return all 3 users

5. **`05_query_filter_by_name.json`** - Query with filter
   - Event name: `query-filter-alice`
   - Should return only Alice

6. **`06_update_user.json`** - Update Alice's age
   - Event name: `update-alice-age`
   - Updates Alice's age to 31

7. **`07_delete_user.json`** - Soft delete Charlie
   - Event name: `delete-charlie`
   - Marks Charlie as deleted

8. **`08_list_tables.json`** - List all tables
   - Event name: `list-tables`
   - Should show "users" table

9. **`09_describe_table.json`** - Get table schema
   - Event name: `describe-table`
   - Returns schema and statistics

10. **`10_compact_table.json`** - Compact table files
    - Event name: `compact-users`
    - Merges small files for better performance

## 📝 Quick Start

### Create and Run First Test:

1. **Click "Test" tab** in Lambda console
2. **Click "Create new event"**
3. **Name it:** `health-check`
4. **Paste this:**
   ```json
   {
     "httpMethod": "GET",
     "path": "/health"
   }
   ```
5. **Click "Save"**
6. **Click "Test"** button

**Expected Response:**
```json
{
  "statusCode": 200,
  "headers": {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*"
  },
  "body": "{\"status\": \"healthy\", \"service\": \"S3 ACID Database\", \"version\": \"1.0.0\"}"
}
```

## 🔧 Important Configuration

### Before Testing, Ensure:

1. **Lambda IAM Role** has permissions for:
   - S3: `s3:GetObject`, `s3:PutObject`, `s3:ListBucket`
   - Glue (if using Glue Catalog): `glue:*`
   - DynamoDB (if using DynamoDB catalog): `dynamodb:*`

2. **Environment Variables** are set:
   ```
   ENVIRONMENT = production  # or staging, development
   AWS_REGION = us-east-1    # your region
   BUCKET_NAME = your-bucket-name
   ```

3. **Lambda Configuration:**
   - Memory: At least **3008 MB** (recommended)
   - Timeout: **900 seconds** (15 minutes)
   - Runtime: **Python 3.12**

4. **VPC Configuration** (if needed):
   - If your S3/Glue is in VPC, configure VPC settings
   - Add NAT Gateway for internet access

## 🎯 Test Results

### Success Response Example:
```json
{
  "statusCode": 200,
  "body": "{\"success\": true, \"message\": \"...\", \"data\": {...}}"
}
```

### Error Response Example:
```json
{
  "statusCode": 400,
  "body": "{\"success\": false, \"error\": \"Validation error: ...\"}"
}
```

## 🐛 Troubleshooting

### Error: "Task timed out after 3.00 seconds"
**Solution:** Increase Lambda timeout to 900 seconds (Configuration → General → Timeout)

### Error: "An error occurred (AccessDeniedException)"
**Solution:** Add S3/Glue permissions to Lambda IAM role

### Error: "Unable to import module 'src.lambda_handler'"
**Solution:** 
- Check Dockerfile CMD is: `["src.lambda_handler.lambda_handler"]`
- Verify container image was built successfully
- Check CloudWatch Logs for import errors

### Error: "GLIBC version not found"
**Solution:** Use Python 3.12 base image (you've already done this!)

### Error: "Table does not exist"
**Solution:** Run `02_create_table.json` first before querying

## 📊 Monitoring

### View Logs:
1. Go to **Monitor** tab in Lambda console
2. Click **View CloudWatch logs**
3. Check latest log stream for errors

### Useful Log Searches:
```
# Find errors
"ERROR" OR "Exception" OR "Traceback"

# Find specific operations
"operation": "QUERY"
"operation": "WRITE"

# Check execution time
"Duration:" OR "Billed Duration:"
```

## 🚀 Production Checklist

Before going to production:

- [ ] Lambda has sufficient memory (3008+ MB)
- [ ] Timeout is set to 900 seconds
- [ ] IAM role has all required permissions
- [ ] Environment variables are configured
- [ ] S3 bucket exists and is accessible
- [ ] Glue catalog is configured (or REST catalog for dev)
- [ ] VPC/Security groups configured (if needed)
- [ ] CloudWatch alarms set up
- [ ] Cost monitoring enabled
- [ ] Tested all operations successfully

## 📚 Next Steps

After testing in Lambda console:

1. **Set up API Gateway** for HTTP access
2. **Configure Lambda Function URL** for simpler access
3. **Import Postman collection** for comprehensive testing
4. **Set up CI/CD pipeline** with CodeBuild/CodePipeline
5. **Configure monitoring** with CloudWatch dashboards

## 💡 Tips

- **Save frequently used tests** with descriptive names
- **Test with production-like data** volume
- **Monitor execution time** and memory usage
- **Check CloudWatch logs** for any warnings
- **Test error cases** (invalid data, missing fields)
- **Use different tenant_id** for test vs production data

## 📖 Related Documentation

- [Main README](../README.md)
- [Configuration Guide](../docs/CONFIG.md)
- [API Documentation](../docs/DOCUMENTATION.md)
- [Postman Collection Guide](../postman/COLLECTION_GUIDE.md)

---

**Happy Testing! 🎉**

If you encounter any issues, check CloudWatch Logs first - they contain detailed error messages and stack traces.

