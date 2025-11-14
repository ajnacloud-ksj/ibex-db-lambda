# Production Setup Guide - S3 + Glue Catalog

## 📋 Overview

This guide will help you deploy to AWS production with:
- ✅ **S3** for data storage
- ✅ **Glue Data Catalog** for metadata
- ✅ **IAM roles** for authentication (no access keys)
- ✅ **Production-grade** configuration

---

## 🔧 Configuration System Explained

### How It Works

1. **Environment Variable**: Lambda reads `ENVIRONMENT` variable
2. **Load Config**: System loads `config/config.json` and finds the matching section
3. **Variable Substitution**: Replaces `${BUCKET_NAME}` with actual environment variable values
4. **Ready**: Your Lambda is configured!

### Example Flow

```
ENVIRONMENT=production
         ↓
config.json["production"]
         ↓
"bucket_name": "${BUCKET_NAME}"  →  "my-production-bucket"
"region": "${AWS_REGION}"         →  "us-east-1"
         ↓
✅ Config Ready!
```

---

## 🚀 Step-by-Step Production Setup

### Step 1: Create S3 Bucket

```bash
# Create bucket for Iceberg data
aws s3 mb s3://your-iceberg-data-bucket --region us-east-1

# Enable versioning (recommended for data safety)
aws s3api put-bucket-versioning \
  --bucket your-iceberg-data-bucket \
  --versioning-configuration Status=Enabled

# Optional: Enable encryption
aws s3api put-bucket-encryption \
  --bucket your-iceberg-data-bucket \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

### Step 2: Create Glue Database

```bash
# Create Glue database for your tables
aws glue create-database \
  --database-input '{
    "Name": "iceberg_db",
    "Description": "Iceberg tables managed by Lambda"
  }' \
  --region us-east-1
```

### Step 3: Configure Lambda Environment Variables

**Go to AWS Console:**
1. Lambda → `ibex-db-lambda`
2. Configuration → Environment variables
3. Click **Edit**
4. Add these variables:

```bash
ENVIRONMENT = production
AWS_REGION = us-east-1
BUCKET_NAME = your-iceberg-data-bucket
AWS_ACCOUNT_ID = 123456789012
```

**How to get your AWS Account ID:**
```bash
aws sts get-caller-identity --query Account --output text
```

### Step 4: Update Lambda IAM Role

Your Lambda needs permissions for S3 and Glue.

**Create inline policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetObjectVersion",
        "s3:ListBucketVersions"
      ],
      "Resource": [
        "arn:aws:s3:::your-iceberg-data-bucket/*",
        "arn:aws:s3:::your-iceberg-data-bucket"
      ]
    },
    {
      "Sid": "GlueAccess",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:CreateDatabase",
        "glue:GetTable",
        "glue:GetTables",
        "glue:CreateTable",
        "glue:UpdateTable",
        "glue:DeleteTable",
        "glue:GetPartition",
        "glue:GetPartitions",
        "glue:BatchGetPartition",
        "glue:CreatePartition",
        "glue:UpdatePartition",
        "glue:DeletePartition"
      ],
      "Resource": [
        "arn:aws:glue:us-east-1:123456789012:catalog",
        "arn:aws:glue:us-east-1:123456789012:database/*",
        "arn:aws:glue:us-east-1:123456789012:table/*/*"
      ]
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

**Apply via AWS Console:**
1. Lambda → ibex-db-lambda → Configuration → Permissions
2. Click on the execution role name
3. Add permissions → Create inline policy
4. Paste the JSON above
5. Name it: `IcebergDatabasePolicy`
6. Save

### Step 5: Update Lambda Configuration

**Memory and Timeout:**
1. Configuration → General configuration → Edit
2. Memory: **3008 MB** (or higher for production)
3. Timeout: **900 seconds** (15 minutes)
4. Save

---

## 📝 Configuration Reference

### Production Config (from config.json)

```json
{
  "environment": "production",
  "s3": {
    "bucket_name": "${BUCKET_NAME}",           // ← from env var
    "warehouse_path": "iceberg-warehouse",     // ← folder in bucket
    "region": "${AWS_REGION}",                 // ← from env var
    "use_ssl": true,
    "path_style_access": false
  },
  "catalog": {
    "type": "glue",                            // ← uses Glue!
    "name": "glue",
    "account_id": "${AWS_ACCOUNT_ID}",         // ← from env var
    "region": "${AWS_REGION}"                  // ← from env var
  },
  "duckdb": {
    "memory_limit": "4GB",
    "threads": 8
  },
  "lambda": {
    "timeout": 900,
    "memory_size": 10240                       // 10GB recommended
  },
  "performance": {
    "max_retries": 3,
    "query_timeout_ms": 60000,
    "batch_size": 5000
  },
  "iceberg": {
    "write": {
      "target_file_size_mb": 256,
      "compression_codec": "zstd",
      "parquet_row_group_size": 16384
    },
    "compaction": {
      "enabled": true,
      "small_file_threshold_mb": 128,
      "min_files_to_compact": 20
    }
  }
}
```

### Key Differences: Development vs Production

| Feature | Development | Production |
|---------|-------------|------------|
| Storage | MinIO (local) | S3 |
| Catalog | REST Catalog | Glue Catalog |
| Auth | Access keys | IAM roles |
| Endpoint | http://minio:9000 | AWS S3 endpoints |
| SSL | false | true |
| Memory | 2GB | 4-10GB |

---

## ✅ Verification Steps

### 1. Test Environment Variables

Create test event: `test_config.json`

```json
{
  "httpMethod": "GET",
  "path": "/health"
}
```

**Expected Response:**
```json
{
  "statusCode": 200,
  "body": "{\"status\": \"healthy\", \"service\": \"S3 ACID Database\", \"version\": \"1.0.0\"}"
}
```

### 2. Test Table Creation

Use test event: `02_create_table.json`

**Expected in CloudWatch Logs:**
```
✓ Configuration loaded for environment: production
✓ Using Glue catalog
✓ Connecting to S3: s3://your-bucket/iceberg-warehouse/
✓ Table created: test-tenant.default.users
```

### 3. Verify S3 Data

```bash
# List tables in S3
aws s3 ls s3://your-iceberg-data-bucket/iceberg-warehouse/test-tenant/default/

# Should see:
# users/
```

### 4. Verify Glue Catalog

```bash
# List tables in Glue
aws glue get-tables \
  --database-name iceberg_db \
  --region us-east-1

# Should see your table metadata
```

---

## 🔒 Security Best Practices

### ✅ Use IAM Roles (Not Access Keys)
- Lambda automatically uses its execution role
- No hardcoded credentials
- Credentials rotate automatically

### ✅ Enable S3 Encryption
```bash
aws s3api put-bucket-encryption \
  --bucket your-bucket \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

### ✅ Enable S3 Versioning
```bash
aws s3api put-bucket-versioning \
  --bucket your-bucket \
  --versioning-configuration Status=Enabled
```

### ✅ Restrict S3 Access
- Use bucket policies to restrict access
- Enable S3 Block Public Access
- Use VPC endpoints for private access

### ✅ Use Secrets Manager (Optional)
For sensitive config values:
```bash
# Store secret
aws secretsmanager create-secret \
  --name iceberg-db-config \
  --secret-string '{"api_key":"xxx"}'

# Lambda reads it
import boto3
client = boto3.client('secretsmanager')
secret = client.get_secret_value(SecretId='iceberg-db-config')
```

---

## 🐛 Troubleshooting

### Error: "ENVIRONMENT not set"

**Cause:** Lambda environment variable not configured

**Fix:**
1. Lambda → Configuration → Environment variables
2. Add: `ENVIRONMENT = production`
3. Save and test again

### Error: "AccessDeniedException" (S3)

**Cause:** Lambda IAM role missing S3 permissions

**Fix:**
1. Lambda → Configuration → Permissions
2. Click execution role
3. Add S3 permissions (see Step 4 above)

### Error: "AccessDeniedException" (Glue)

**Cause:** Lambda IAM role missing Glue permissions

**Fix:**
1. Add Glue permissions to execution role
2. Ensure Glue database exists:
   ```bash
   aws glue create-database --database-input '{"Name":"iceberg_db"}'
   ```

### Error: "No such bucket"

**Cause:** S3 bucket doesn't exist or name mismatch

**Fix:**
1. Create bucket:
   ```bash
   aws s3 mb s3://your-bucket
   ```
2. Verify `BUCKET_NAME` environment variable matches

### Error: "Init timeout"

**Cause:** Lambda memory too low

**Fix:**
1. Configuration → General → Memory
2. Set to **3008 MB minimum**
3. For production: **10240 MB** recommended

---

## 📊 Monitoring Production

### CloudWatch Metrics

**Key metrics to monitor:**
- `Duration` - Query/write performance
- `Errors` - Failed operations
- `Throttles` - Concurrent execution limits
- `IteratorAge` - For streaming (if applicable)

### CloudWatch Alarms

**Create alarms for:**

```bash
# High error rate
aws cloudwatch put-metric-alarm \
  --alarm-name ibex-db-high-errors \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold

# Long duration
aws cloudwatch put-metric-alarm \
  --alarm-name ibex-db-slow-queries \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 5000 \
  --comparison-operator GreaterThanThreshold
```

### Cost Optimization

**Monitor:**
- Lambda invocations and duration
- S3 storage and requests
- Glue API calls
- Data transfer

**Tips:**
- Run compaction regularly to reduce small files
- Use provisioned concurrency only if needed
- Enable S3 Intelligent-Tiering for old data
- Set lifecycle policies for old snapshots

---

## 🎯 Quick Reference

### Required Environment Variables

```bash
ENVIRONMENT=production
AWS_REGION=us-east-1
BUCKET_NAME=your-iceberg-data-bucket
AWS_ACCOUNT_ID=123456789012
```

### Required IAM Permissions

- S3: `GetObject`, `PutObject`, `DeleteObject`, `ListBucket`
- Glue: `GetTable`, `CreateTable`, `UpdateTable`, `DeleteTable`
- CloudWatch: `PutLogEvents`

### Lambda Configuration

- Memory: **3008+ MB**
- Timeout: **900 seconds**
- Runtime: **Python 3.12**

### Data Location

```
s3://your-bucket/iceberg-warehouse/
  ├── {tenant_id}/
  │   ├── {namespace}/
  │   │   ├── {table_name}/
  │   │   │   ├── metadata/
  │   │   │   └── data/
```

---

## 📚 Next Steps

1. ✅ Set environment variables
2. ✅ Configure IAM permissions
3. ✅ Test with Lambda console
4. ✅ Set up API Gateway (optional)
5. ✅ Configure monitoring and alarms
6. ✅ Test with real workload
7. ✅ Set up CI/CD pipeline

---

## 💡 Tips

- **Start small**: Test with small dataset first
- **Monitor costs**: Enable cost allocation tags
- **Use CloudWatch Insights**: Query logs for patterns
- **Backup important data**: Use S3 versioning
- **Test disaster recovery**: Practice restoring from backup

---

## 📞 Support

If you encounter issues:
1. Check CloudWatch Logs
2. Verify environment variables
3. Confirm IAM permissions
4. Review this guide
5. Check AWS service health dashboard

---

**You're now ready for production! 🚀**

