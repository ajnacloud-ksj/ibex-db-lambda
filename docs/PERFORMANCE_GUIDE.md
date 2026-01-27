# Performance Optimization Guide 🚀

This database runs on **AWS Lambda** using **DuckDB** and **S3 (Iceberg)**. Performance is determined by the interaction between compute (Lambda), storage (S3), and query efficiency (DuckDB/Iceberg).

Here is how to maximize performance:

## 1. Infrastructure Tuning (Lambda)

### Memory = CPU
DuckDB is an in-memory OLAP engine. It thrives on memory and CPU. In AWS Lambda, **CPU power is proportional to memory**.
- **Recommendation**: Allocate at least **1769 MB** (1 vCPU).
- **Sweet Spot**: **2048 MB - 4096 MB**.
- **Why**: 
    - Simpler queries run faster with more CPU.
    - Complex queries (joins, aggregations) need memory to avoid spilling to disk (which is slow /tmp on Lambda).
    - Faster execution = lower billing duration.

### Concurrency
Ensure your Lambda function has enough reserved concurrency if you expect burst traffic, to avoid cold starts.

## 2. Storage Optimization (S3)

### Use S3 Express One Zone (Directory Buckets)
This is the **single biggest performance upgrade**.
- **Standard S3**: ~50-100ms latency per request.
- **S3 Express**: ~5-10ms latency (single digit).
- **Impact**: DuckDB makes many metadata requests. Reducing latency by 10x drastically speeds up planning and execution.
- **Status**: The codebase already supports this automatically if your bucket name ends in `--x-s3`.

### Compaction (The "Small Files" Problem)
Streaming data often creates thousands of tiny Parquet files.
- **Problem**: Reading 1,000 small files takes much longer than reading 1 large file.
- **Solution**: Run the `COMPACT` operation regularly (e.g., daily or hourly via EventBridge).
    ```json
    {
      "operation": "COMPACT",
      "table": "my_table",
      "target_file_size_mb": 64
    }
    ```

## 3. Application Tuning (Codebase)

### Metadata Caching (Enabled)
Iceberg requires reading `metadata.json` to plan queries.
- **Optimization**: We cache the S3 location of metadata for **5 seconds**.
- **Benefit**: "Hot" queries don't need to re-fetch the table location from the catalog (Glue/REST), saving ~200-500ms per query.

### Connection Reuse
DuckDB connections are re-used across Lambda invocations (warm starts).
- **Benefit**: Avoids the ~500ms startup cost of initializing DuckDB and loading extensions.

### Partitioning
For large tables (millions of rows), **Partitioning** is critical.
- **Strategy**: Partition by a queryable field like `date(timestamp)` or `tenant_id`.
- **Why**: Allows DuckDB to skip reading entire S3 folders/files that don't match the filter (Partition Pruning).

## 4. Advanced Tuning

### Switch to ARM64 (Graviton2)
AWS Lambda offers an ARM64 architecture option.
### Switch to ARM64 (Graviton2)
AWS Lambda offers an ARM64 architecture option.
- **Benefit**: Typically **20% cheaper** and often faster for compute-intensive workloads like DuckDB.
- **How to Migrate**:

**1. Update Docker Build**
You must build the container for ARM64.
```bash
docker buildx build --platform linux/arm64 -t ibex-db-lambda:arm64 .
```

**2. Update Lambda Architecture**
- **AWS Console**: Go to Function -> Runtime settings -> Edit -> Change Architecture from `x86_64` to `arm64`.
- **AWS SAM / CloudFormation**:
    ```yaml
    Resources:
      IbexFunction:
        Type: AWS::Serverless::Function
        Properties:
          Architectures: [arm64]
    ```
- **Serverless Framework**:
    ```yaml
    provider:
      architecture: arm64
    ```

### Provisioned Concurrency

### Provisioned Concurrency
If you have "bursty" traffic and need consistently low latency:
- **Problem**: "Cold starts" (loading container + DuckDB) take 1-3 seconds.
- **Solution**: Enable **Provisioned Concurrency** for your Lambda.
- **Benefit**: Maintains initialized environments ready to respond in milliseconds.

### Optimized Writes
- **Batching**: Write multiple records in a single `WRITE` request rather than one at a time. This reduces S3 PUT costs and commit overhead.
- **Async Processing**: If writes don't need immediate confirmation, use SQS to decouple the API from the Lambda, allowing the Lambda to process batches of writes.

## 5. Query Best Practices

- **Select Specific Columns**: Avoid `SELECT *`. Parquet is columnar; selecting fewer columns means reading less data from S3.
- **Always Filter**: Use `WHERE` clauses (especially on partition columns) to minimize data scanned.
- **Use the Latest Endpoints**: The new `QUERY` logic is optimized to filter versions efficiently using window functions.

## Summary Checklist

- [ ] **Lambda Memory**: Set to 2GB+
- [ ] **Bucket**: Use S3 Express (`...--x-s3`)
- [ ] **Maintenance**: Schedule periodic `COMPACT` calls
- [ ] **Schema**: Use Partitioning for large tables

# 🎯 Web Application Strategy (Replacing RDS)

If you are using this as a primary database for a User Interface (OLTP workload), traditional Data Warehouse rules don't apply. You need low latency and consistency.

## 1. Latency & Consistency (The "UI Lag" Problem)
- **The Challenge**: Users expect to update a profile and see it change instantly. "Eventual consistency" (SQS) can feel broken.
- **The Solution (Hybrid Approach)**:
    - **Synchronous Writes**: For user-initiated actions (Save, Submit, Edit), use the direct `POST` endpoint. Do NOT use SQS.
    - **Optimistic UI**: If you MUST use SQS for speed, update the React state *immediately* before the API confirms. Rollback if it fails.

## 2. Mandatory Configuration
For a snappy UI experience, you **MUST** use:
1.  **S3 Express Directory Bucket**: Reduces read latency from 100ms → 10ms.
2.  **Provisioned Concurrency**: Keeps Lambda warm to avoid the 2-second "Cold Start" on the first request.
3.  **Metadata Caching**: The codebase now caches metadata for 5s but invalidates it instantly on Write. This gives you Read-Your-Writes consistency within the same Lambda container.

## 3. Workload Separation
Don't let analytics queries slow down the UI.
- **UI Queries**: Simple lookups (WHERE id = X), recent history. Small, fast.
- **Background Jobs**: Heavy aggregations, reports. Run these asynchronously or on a separate Lambda function alias/version to avoid starving the UI of compute.

