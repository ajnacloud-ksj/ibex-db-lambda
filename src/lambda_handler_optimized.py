#!/usr/bin/env python3
"""
Optimized Lambda Handler for IbexDB
Performance improvements for all users:
- In-memory caching (survives between invocations)
- Connection pooling for DuckDB
- Query optimization
- Batch operation support
"""

import json
import os
import time
import hashlib
import duckdb
import threading
from typing import Dict, Any, Optional, List
from collections import OrderedDict
from datetime import datetime
import boto3

# ===============================
# GLOBAL CACHE (Survives between Lambda invocations)
# ===============================
GLOBAL_CACHE = OrderedDict()
CACHE_STATS = {
    "hits": 0,
    "misses": 0,
    "evictions": 0,
    "total_requests": 0,
    "last_reset": time.time()
}
CACHE_LOCK = threading.Lock()

# Cache Configuration
MAX_CACHE_SIZE = int(os.environ.get('CACHE_MAX_SIZE', 500))  # Configurable via env
CACHE_TTL_SECONDS = int(os.environ.get('CACHE_TTL', 300))  # 5 minutes default
READ_CACHE_TTL = int(os.environ.get('READ_CACHE_TTL', 60))  # 1 minute for reads
ENABLE_CACHE = os.environ.get('ENABLE_CACHE', 'true').lower() == 'true'

# ===============================
# GLOBAL CONNECTION POOL
# ===============================
class DuckDBConnectionPool:
    """Singleton connection pool for DuckDB"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.connections = {}
                    cls._instance.prepared_statements = {}
        return cls._instance

    def get_connection(self, tenant_id: str, namespace: str = "default") -> duckdb.DuckDBPyConnection:
        """Get or create a connection for tenant/namespace"""
        conn_key = f"{tenant_id}:{namespace}"

        if conn_key not in self.connections:
            # Create new connection
            conn = duckdb.connect(':memory:')

            # Configure for performance
            conn.execute("""
                SET memory_limit='2GB';
                SET threads TO 2;
                SET enable_object_cache=true;
                SET force_compression='Uncompressed';
            """)

            # Install and load required extensions
            conn.execute("""
                INSTALL httpfs;
                LOAD httpfs;
                INSTALL parquet;
                LOAD parquet;
            """)

            # Configure S3 access
            if os.environ.get('AWS_ACCESS_KEY_ID'):
                conn.execute(f"""
                    SET s3_region='{os.environ.get('AWS_REGION', 'us-east-1')}';
                    SET s3_access_key_id='{os.environ['AWS_ACCESS_KEY_ID']}';
                    SET s3_secret_access_key='{os.environ['AWS_SECRET_ACCESS_KEY']}';
                """)

            # Attach Iceberg catalog if configured
            catalog_uri = os.environ.get('ICEBERG_CATALOG_URI')
            if catalog_uri:
                conn.execute(f"""
                    ATTACH DATABASE '{catalog_uri}' AS iceberg_catalog (TYPE ICEBERG);
                """)

            self.connections[conn_key] = conn
            print(f"Created new DuckDB connection for {conn_key}")

        return self.connections[conn_key]

    def prepare_statement(self, conn: duckdb.DuckDBPyConnection, name: str, query: str):
        """Prepare a statement for reuse"""
        stmt_key = f"{id(conn)}:{name}"
        if stmt_key not in self.prepared_statements:
            conn.execute(f"PREPARE {name} AS {query}")
            self.prepared_statements[stmt_key] = True

# Global connection pool instance
db_pool = DuckDBConnectionPool()

# ===============================
# CACHE FUNCTIONS
# ===============================
def get_cache_key(tenant_id: str, operation: str, **params) -> str:
    """Generate deterministic cache key"""
    key_data = {
        "tenant": tenant_id,
        "op": operation,
        **params
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()

def get_from_cache(cache_key: str) -> Optional[Dict]:
    """Get item from cache if valid"""
    if not ENABLE_CACHE:
        return None

    with CACHE_LOCK:
        if cache_key in GLOBAL_CACHE:
            entry = GLOBAL_CACHE[cache_key]

            # Check TTL
            if time.time() - entry["timestamp"] < entry["ttl"]:
                # Move to end (LRU)
                GLOBAL_CACHE.move_to_end(cache_key)
                CACHE_STATS["hits"] += 1

                # Return copy to prevent mutation
                import copy
                return copy.deepcopy(entry["data"])
            else:
                # Expired
                del GLOBAL_CACHE[cache_key]

        CACHE_STATS["misses"] += 1
        return None

def put_in_cache(cache_key: str, data: Dict, ttl: int = CACHE_TTL_SECONDS):
    """Store item in cache"""
    if not ENABLE_CACHE:
        return

    with CACHE_LOCK:
        # Evict if full
        while len(GLOBAL_CACHE) >= MAX_CACHE_SIZE:
            oldest_key = next(iter(GLOBAL_CACHE))
            del GLOBAL_CACHE[oldest_key]
            CACHE_STATS["evictions"] += 1

        GLOBAL_CACHE[cache_key] = {
            "data": data,
            "timestamp": time.time(),
            "ttl": ttl
        }

def invalidate_cache_for_table(tenant_id: str, table: str):
    """Invalidate all cache entries for a table"""
    if not ENABLE_CACHE:
        return

    with CACHE_LOCK:
        pattern = f"{tenant_id}:QUERY:table:{table}"
        keys_to_delete = [
            key for key in GLOBAL_CACHE.keys()
            if pattern in key or table in key
        ]
        for key in keys_to_delete:
            del GLOBAL_CACHE[key]

# ===============================
# OPTIMIZED OPERATIONS
# ===============================
def execute_query_optimized(conn: duckdb.DuckDBPyConnection, tenant_id: str,
                            operation: str, payload: Dict) -> Dict:
    """Execute query with optimizations"""

    # Check cache for read operations
    if operation in ["QUERY", "DESCRIBE_TABLE", "LIST_TABLES"]:
        cache_key = get_cache_key(tenant_id, operation, **payload)
        cached = get_from_cache(cache_key)
        if cached:
            return cached

    # Execute the operation
    start_time = time.perf_counter()
    result = None

    try:
        if operation == "QUERY":
            table = payload.get("table")
            filters = payload.get("filters", [])
            limit = payload.get("limit", 100)
            offset = payload.get("offset", 0)
            sort = payload.get("sort", [])

            # Build optimized query
            query_parts = [f"SELECT * FROM {table}"]

            # Add filters
            if filters:
                where_clauses = []
                for filter_item in filters:
                    field = filter_item.get("field")
                    operator = filter_item.get("operator", "eq")
                    value = filter_item.get("value")

                    if operator == "eq":
                        where_clauses.append(f"{field} = '{value}'")
                    elif operator == "gt":
                        where_clauses.append(f"{field} > '{value}'")
                    elif operator == "lt":
                        where_clauses.append(f"{field} < '{value}'")
                    elif operator == "like":
                        where_clauses.append(f"{field} LIKE '%{value}%'")

                if where_clauses:
                    query_parts.append(f"WHERE {' AND '.join(where_clauses)}")

            # Add sorting
            if sort:
                order_parts = []
                for sort_item in sort:
                    field = sort_item.get("field")
                    order = sort_item.get("order", "asc").upper()
                    order_parts.append(f"{field} {order}")
                query_parts.append(f"ORDER BY {', '.join(order_parts)}")

            # Add pagination
            query_parts.append(f"LIMIT {limit} OFFSET {offset}")

            query = " ".join(query_parts)

            # Execute query
            query_result = conn.execute(query).fetchall()
            columns = [desc[0] for desc in conn.description]

            # Format results
            records = [dict(zip(columns, row)) for row in query_result]

            result = {
                "success": True,
                "data": {
                    "records": records,
                    "count": len(records)
                }
            }

        elif operation == "WRITE":
            table = payload.get("table")
            records = payload.get("records", [])

            if records:
                # Batch insert for better performance
                columns = list(records[0].keys())
                placeholders = ", ".join(["?" for _ in columns])
                insert_query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

                # Prepare statement for reuse
                stmt_name = f"insert_{table}"
                db_pool.prepare_statement(conn, stmt_name, insert_query)

                # Execute batch insert
                conn.executemany(insert_query, [tuple(r.get(col) for col in columns) for r in records])

                # Invalidate cache for this table
                invalidate_cache_for_table(tenant_id, table)

                result = {
                    "success": True,
                    "data": {
                        "records": records,
                        "count": len(records)
                    }
                }

        elif operation == "UPDATE":
            table = payload.get("table")
            filters = payload.get("filters", [])
            updates = payload.get("updates", {})

            if updates:
                # Build update query
                set_parts = [f"{k} = '{v}'" for k, v in updates.items()]
                where_parts = [f"{f['field']} = '{f['value']}'" for f in filters]

                update_query = f"UPDATE {table} SET {', '.join(set_parts)}"
                if where_parts:
                    update_query += f" WHERE {' AND '.join(where_parts)}"

                conn.execute(update_query)

                # Invalidate cache
                invalidate_cache_for_table(tenant_id, table)

                result = {"success": True}

        elif operation == "DELETE":
            table = payload.get("table")
            filters = payload.get("filters", [])

            where_parts = [f"{f['field']} = '{f['value']}'" for f in filters]
            delete_query = f"DELETE FROM {table}"
            if where_parts:
                delete_query += f" WHERE {' AND '.join(where_parts)}"

            conn.execute(delete_query)

            # Invalidate cache
            invalidate_cache_for_table(tenant_id, table)

            result = {"success": True}

        elif operation == "BATCH":
            # New: Batch operation support
            operations = payload.get("operations", [])
            results = []

            conn.execute("BEGIN TRANSACTION")
            try:
                for op in operations:
                    op_result = execute_query_optimized(conn, tenant_id, op["operation"], op)
                    results.append(op_result)

                conn.execute("COMMIT")
                result = {
                    "success": True,
                    "data": {"results": results}
                }
            except Exception as e:
                conn.execute("ROLLBACK")
                raise e

        else:
            # Fallback to original implementation
            from lambda_handler import execute_operation
            result = execute_operation(conn, operation, payload)

    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }

    # Measure execution time
    execution_time = (time.perf_counter() - start_time) * 1000

    # Add execution time to result
    if result:
        result["execution_time_ms"] = round(execution_time, 2)

        # Cache successful read operations
        if result.get("success") and operation in ["QUERY", "DESCRIBE_TABLE", "LIST_TABLES"]:
            cache_key = get_cache_key(tenant_id, operation, **payload)
            ttl = READ_CACHE_TTL if operation == "QUERY" else CACHE_TTL_SECONDS
            put_in_cache(cache_key, result, ttl)

    return result

# ===============================
# MAIN HANDLER
# ===============================
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Optimized Lambda handler with caching and connection pooling
    """
    # Track request
    CACHE_STATS["total_requests"] += 1

    # Parse event
    try:
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON"})
        }

    # Get tenant info
    tenant_id = body.get('tenant_id', 'default')
    namespace = body.get('namespace', 'default')
    operation = body.get('operation', '').upper()

    # Get or create connection from pool
    try:
        conn = db_pool.get_connection(tenant_id, namespace)
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Database connection failed: {str(e)}"})
        }

    # Execute operation with optimizations
    try:
        result = execute_query_optimized(conn, tenant_id, operation, body)

        # Add cache statistics to response (optional)
        if os.environ.get('INCLUDE_CACHE_STATS', 'false').lower() == 'true':
            result["cache_stats"] = {
                "hit_rate": CACHE_STATS["hits"] / max(CACHE_STATS["total_requests"], 1),
                "hits": CACHE_STATS["hits"],
                "misses": CACHE_STATS["misses"],
                "cache_size": len(GLOBAL_CACHE),
                "cache_enabled": ENABLE_CACHE
            }

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "X-Cache-Hit": str(result.get("from_cache", False))
            },
            "body": json.dumps(result)
        }

    except Exception as e:
        import traceback
        error_details = {
            "error": str(e),
            "traceback": traceback.format_exc() if os.environ.get('DEBUG') == 'true' else None
        }

        return {
            "statusCode": 500,
            "body": json.dumps(error_details)
        }

# ===============================
# WARMUP FUNCTION
# ===============================
def warmup_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Warmup handler to pre-initialize connections
    Can be called by CloudWatch Events to keep Lambda warm
    """
    tenants = event.get('tenants', ['default'])

    for tenant in tenants:
        try:
            conn = db_pool.get_connection(tenant)
            # Pre-load common tables
            tables = event.get('preload_tables', [])
            for table in tables:
                conn.execute(f"SELECT 1 FROM {table} LIMIT 1")
        except:
            pass

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Warmup complete",
            "connections": len(db_pool.connections),
            "cache_size": len(GLOBAL_CACHE)
        })
    }