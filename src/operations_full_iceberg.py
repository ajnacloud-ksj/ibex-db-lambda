"""
Full Iceberg implementation using PyIceberg for writes and DuckDB for reads.

This provides complete ACID transactions with Apache Iceberg:
- PyIceberg: Create tables, write data, manage catalog
- Polars: Data manipulation and Parquet conversion
- DuckDB: Query Iceberg tables using iceberg_scan
"""

import json
import hashlib
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union

import duckdb
import polars as pl
import pyarrow as pa
from pyiceberg.catalog import Catalog
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    NestedField, StringType, IntegerType, LongType,
    FloatType, DoubleType, BooleanType, TimestampType,
    DateType, ListType, MapType, StructType, DecimalType,
    BinaryType
)
from pyiceberg.table import Table

from .config import get_config
from .models import (
    WriteRequest, WriteResponse,
    UpdateRequest, UpdateResponse,
    DeleteRequest, DeleteResponse,
    HardDeleteRequest, HardDeleteResponse,
    CompactRequest, CompactResponse, CompactionStats,
    CreateTableRequest, CreateTableResponse,
    DescribeTableRequest, DescribeTableResponse, ListTablesRequest,
    TableDescription, ListTablesResponse,
    QueryRequest, QueryResponse,
    ErrorDetail, QueryMetadata,
    DropTableRequest, DropTableResponse, DropTableResponseData,
    DropNamespaceRequest, DropNamespaceResponse, DropNamespaceResponseData
)
from .query_builder import TypeSafeQueryBuilder


class FullIcebergOperations:
    """Full Iceberg operations using PyIceberg for writes and DuckDB for reads"""

    def __init__(self):
        """
        Initialize PyIceberg catalog and DuckDB connection
        
        Raises:
            RuntimeError: If initialization fails
        """
        try:
            print("Loading configuration...")
            self.config = get_config()
            print("✓ Configuration loaded")

            # Lazy initialize catalog - don't create until first use
            self.catalog = None
            print("✓ Catalog will be initialized on first use (lazy loading)")

            print("Initializing DuckDB...")
            self.conn = self._init_duckdb()
            
            # Initialize metadata cache for query performance
            self._metadata_cache = {}
            self._cache_ttl = 300  # 5 minutes cache - safe for read-heavy workloads

            # Initialize query result cache for repeated queries
            self._query_cache = {}
            self._query_cache_ttl = 60  # 1 minute for query results
            print(f"✓ Query cache initialized (TTL: {self._cache_ttl}s, Result cache: {self._query_cache_ttl}s)")

            # Initialize last compaction check time (for auto-compaction)
            self._last_compact_check = None
            
        except Exception as e:
            error_msg = f"FullIcebergOperations initialization failed: {e}"
            print(f"✗ {error_msg}")
            raise RuntimeError(error_msg) from e

    def _get_catalog(self):
        """Lazy initialize catalog on first use"""
        if self.catalog is None:
            print("Lazy-loading PyIceberg catalog on first use...")
            self.catalog = self._init_pyiceberg_catalog()
        return self.catalog

    def _init_pyiceberg_catalog(self) -> Catalog:
        """
        Initialize PyIceberg catalog (REST or Glue based on config)
        
        Returns:
            Configured Catalog instance
            
        Raises:
            ValueError: If catalog type is unsupported
            RuntimeError: If catalog initialization fails
        """
        try:
            catalog_config = self.config.catalog
            s3_config = self.config.s3

            catalog_type = catalog_config['type']
            catalog_name = catalog_config['name']

            # Build warehouse path
            warehouse = f"s3://{s3_config['bucket_name']}/{s3_config['warehouse_path']}/"
            print(f"Warehouse location: {warehouse}")

            if catalog_type == 'rest':
                # Development: REST Catalog
                catalog_params = {
                    "uri": catalog_config['uri'],
                    "s3.region": s3_config['region'],
                    "warehouse": warehouse,
                    "py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO",
                }

                # Add S3 endpoint if present (for MinIO)
                if 'endpoint' in s3_config:
                    catalog_params["s3.endpoint"] = s3_config['endpoint']

                # Add credentials if present
                if 'access_key_id' in s3_config:
                    catalog_params["s3.access-key-id"] = s3_config['access_key_id']
                    catalog_params["s3.secret-access-key"] = s3_config['secret_access_key']

                try:
                    catalog = RestCatalog(name=catalog_name, **catalog_params)
                    print(f"✓ PyIceberg REST catalog initialized at {catalog_config['uri']}")
                except Exception as e:
                    raise RuntimeError(f"Failed to initialize REST catalog: {e}") from e

            elif catalog_type == 'glue':
                # Production: AWS Glue Catalog (import only when needed)
                try:
                    from pyiceberg.catalog.glue import GlueCatalog

                    catalog_params = {
                        "region_name": catalog_config['region'],
                        "s3.region": s3_config['region'],
                        "warehouse": warehouse,
                        "py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO",
                    }

                    catalog = GlueCatalog(name=catalog_name, **catalog_params)
                    print(f"✓ PyIceberg Glue catalog initialized in {catalog_config['region']}")
                except Exception as e:
                    raise RuntimeError(f"Failed to initialize Glue catalog: {e}") from e

            else:
                raise ValueError(f"Unsupported catalog type: {catalog_type}")

            return catalog
            
        except ValueError:
            # Re-raise ValueError as-is
            raise
        except RuntimeError:
            # Re-raise RuntimeError as-is
            raise
        except Exception as e:
            error_msg = f"PyIceberg catalog initialization failed: {e}"
            print(f"✗ {error_msg}")
            raise RuntimeError(error_msg) from e

    def _init_duckdb(self) -> duckdb.DuckDBPyConnection:
        """
        Initialize DuckDB with Iceberg extension
        
        Returns:
            DuckDB connection
            
        Raises:
            RuntimeError: If DuckDB initialization fails
        """
        try:
            s3_config = self.config.s3
            duckdb_config = self.config.duckdb

            print("Connecting to DuckDB...")
            conn = duckdb.connect(':memory:')

            # Set home directory for extensions (fixes Lambda/Docker issue)
            # Extensions are pre-installed in /opt/duckdb_extensions during container build
            print("Setting DuckDB home directory to /opt/duckdb_extensions...")
            conn.execute("SET home_directory='/opt/duckdb_extensions';")

            # Load extensions (already pre-installed in Docker container)
            # Extensions are installed at container build time for faster cold starts
            print("Loading DuckDB extensions...")
            try:
                conn.execute("LOAD avro;")
                print("  ✓ avro extension loaded")
            except Exception as e:
                raise RuntimeError(f"Failed to load avro extension: {e}") from e
                
            try:
                conn.execute("LOAD iceberg;")
                print("  ✓ iceberg extension loaded")
            except Exception as e:
                raise RuntimeError(f"Failed to load iceberg extension: {e}") from e
                
            try:
                conn.execute("LOAD httpfs;")
                print("  ✓ httpfs extension loaded")
            except Exception as e:
                raise RuntimeError(f"Failed to load httpfs extension: {e}") from e

            # Configure DuckDB settings
            print("Configuring DuckDB settings...")
            # Optimize memory for 3008MB Lambda (leave buffer for Lambda runtime)
            conn.execute("SET memory_limit='2.5GB';")  # Optimized for 3008MB Lambda
            conn.execute(f"SET threads={duckdb_config['threads']};")

            # Performance optimizations
            conn.execute("SET enable_object_cache=true;")
            conn.execute("SET enable_http_metadata_cache=true;")
            conn.execute("SET force_compression='zstd';")
            conn.execute("SET preserve_insertion_order=false;")
            conn.execute("SET checkpoint_threshold='256MB';")  # Reduce checkpoint frequency
            conn.execute("SET temp_directory='/tmp';")  # Use local temp directory
            print("  ✓ Performance optimizations enabled")

            # Configure S3 - Handle S3 Express One Zone automatically
            print("Configuring S3 settings...")
            s3_commands = [
                f"SET s3_region='{s3_config['region']}';"
            ]
            
            # Check for S3 Express bucket (ends with --x-s3)
            bucket_name = s3_config.get('bucket_name', '')
            if bucket_name.endswith('--x-s3') and 'endpoint' not in s3_config:
                try:
                    # Extract Zone ID from bucket name: name--zoneid--x-s3
                    # Split by '--'
                    parts = bucket_name.split('--')
                    if len(parts) >= 3:
                        zone_id = parts[-2]
                        region = s3_config['region']
                        # Construct S3 Express endpoint
                        # Format: s3express-{zone_id}.{region}.amazonaws.com
                        endpoint = f"s3express-{zone_id}.{region}.amazonaws.com"
                        print(f"  ℹ S3 Express Mode: Enabled (Endpoint: {endpoint})")
                        s3_commands.append(f"SET s3_endpoint='{endpoint}';")
                except Exception as e:
                    print(f"Warning: Failed to derive S3 Express endpoint: {e}")

            # Add endpoint if present (for MinIO)
            if 'endpoint' in s3_config:
                endpoint = s3_config['endpoint'].replace('http://', '').replace('https://', '')
                s3_commands.append(f"SET s3_endpoint='{endpoint}';")
                s3_commands.append(f"SET s3_use_ssl={str(s3_config.get('use_ssl', False)).lower()};")
                s3_commands.append(f"SET s3_url_style='{'path' if s3_config.get('path_style_access', True) else 'vhost'}';")

            # Add credentials if present (for MinIO, not needed in production with IAM)
            if 'access_key_id' in s3_config:
                s3_commands.append(f"SET s3_access_key_id='{s3_config['access_key_id']}';")
                s3_commands.append(f"SET s3_secret_access_key='{s3_config['secret_access_key']}';")

            # Execute all S3 configuration commands
            for cmd in s3_commands:
                conn.execute(cmd)

            print(f"✓ DuckDB initialized with Iceberg extension (threads={duckdb_config['threads']}, memory={duckdb_config['memory_limit']})")
            return conn
            
        except Exception as e:
            error_msg = f"DuckDB initialization failed: {e}"
            print(f"✗ {error_msg}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(error_msg) from e

    def _get_metadata_path(self, table_identifier: str) -> str:
        """
        Get metadata path with caching to avoid repeated Glue calls
        
        Args:
            table_identifier: Full table identifier
            
        Returns:
            Metadata location path
            
        Raises:
            Exception: If table doesn't exist or can't be loaded
        """
        cache_key = table_identifier
        now = time.time()
        
        if cache_key in self._metadata_cache:
             cached_path, cached_time = self._metadata_cache[cache_key]
             if now - cached_time < self._cache_ttl:
                 # Cache hit
                 return cached_path
        
        # Cache miss - load from catalog (slow Glue call)
        table = self._get_catalog().load_table(table_identifier)
        metadata_path = table.metadata_location
        
        # Update cache
        self._metadata_cache[cache_key] = (metadata_path, now)
        
        return metadata_path

    def _get_namespace(self, tenant_id: str, namespace: str) -> str:
        """Get Iceberg namespace from tenant and namespace"""
        # Replace hyphens with underscores for valid SQL names
        return f"{tenant_id}_{namespace}".replace("-", "_")

    def _get_table_identifier(self, tenant_id: str, namespace: str, table: str) -> str:
        """Get full Iceberg table identifier"""
        ns = self._get_namespace(tenant_id, namespace)
        return f"{ns}.{table}"

    def _build_select_clause(self, projection: Optional[list], aggregations: Optional[list] = None) -> str:
        """
        Build SELECT clause from projection list and aggregations

        Args:
            projection: List of column names or ProjectionField objects
            aggregations: List of AggregateField objects

        Returns:
            SQL SELECT clause string
        """
        from src.models import ProjectionField, AggregateField

        select_parts = []

        # Handle regular projections (columns)
        if projection and projection != ["*"]:
            for proj in projection:
                if isinstance(proj, str):
                    # Simple column name
                    select_parts.append(proj)
                elif isinstance(proj, ProjectionField):
                    # Complex projection with alias/transformations
                    field = proj.field

                    # Apply transformations
                    if proj.upper:
                        field = f"UPPER({field})"
                    elif proj.lower:
                        field = f"LOWER({field})"

                    if proj.trim:
                        field = f"TRIM({field})"

                    if proj.cast:
                        field = f"CAST({field} AS {proj.cast})"

                    # Add alias if provided
                    if proj.alias:
                        field = f"{field} AS {proj.alias}"

                    select_parts.append(field)
                else:
                    # Fallback to string representation
                    select_parts.append(str(proj))

        # Handle aggregations
        if aggregations:
            for agg in aggregations:
                if isinstance(agg, AggregateField):
                    # Build aggregation function
                    func = agg.function.upper()

                    if agg.field:
                        # Aggregation on specific field
                        if agg.distinct:
                            agg_expr = f"{func}(DISTINCT {agg.field})"
                        else:
                            agg_expr = f"{func}({agg.field})"
                    else:
                        # COUNT(*) case
                        agg_expr = f"{func}(*)"

                    # Add alias
                    agg_expr = f"{agg_expr} AS {agg.alias}"
                    select_parts.append(agg_expr)

        # If no projections or aggregations specified, return all columns
        if not select_parts:
            return "*"

        return ", ".join(select_parts)

    def create_table(self, request: CreateTableRequest) -> CreateTableResponse:
        """Create Iceberg table using PyIceberg"""
        try:
            namespace = self._get_namespace(request.tenant_id, request.namespace)
            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )

            # Create namespace if it doesn't exist
            try:
                self._get_catalog().create_namespace(namespace)
                print(f"✓ Created namespace: {namespace}")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    print(f"Namespace creation note: {e}")

            # Check if table exists
            try:
                existing_table = self._get_catalog().load_table(table_identifier)
                if not request.if_not_exists:
                    from src.models import ResponseMetadata
                    return CreateTableResponse(
                        success=False,
                        data=None,
                        metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                        error=ErrorDetail(code="TABLE_EXISTS", message="Table already exists")
                    )
                from src.models import CreateTableResponseData, ResponseMetadata
                return CreateTableResponse(
                    success=True,
                    data=CreateTableResponseData(
                        table_created=False,
                        table_existed=True
                    ),
                    metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                    error=None
                )
            except:
                pass  # Table doesn't exist, create it

            # Build Iceberg schema
            field_id = 1
            fields = []

            # System fields
            fields.extend([
                NestedField(field_id, "_tenant_id", StringType(), required=True),
                NestedField(field_id + 1, "_record_id", StringType(), required=True),
                NestedField(field_id + 2, "_timestamp", TimestampType(), required=True),
                NestedField(field_id + 3, "_version", IntegerType(), required=True),
                NestedField(field_id + 4, "_deleted", BooleanType(), required=False),
                NestedField(field_id + 5, "_deleted_at", TimestampType(), required=False),
            ])
            field_id += 6

            # User-defined fields
            if request.table_schema and request.table_schema.fields:
                print(f"Processing {len(request.table_schema.fields)} user fields...")
                for field_name, field_def in request.table_schema.fields.items():
                    try:
                        # field_def is a FieldDefinition object
                        required = field_def.required if hasattr(field_def, 'required') else False
                        # Pass the entire field_def to support complex types (arrays, maps, structs)
                        iceberg_type = self._map_to_iceberg_type(field_def)
                        print(f"  Field {field_id}: {field_name} ({iceberg_type}) req={required}")
                        fields.append(
                            NestedField(field_id, field_name, iceberg_type, required=required)
                        )
                        field_id += 1
                    except Exception as fe:
                        print(f"ERROR processing field {field_name}: {fe}")
                        raise fe

            schema = Schema(*fields)
            print(f"Final Schema constructed with {len(fields)} fields")
            print(f"Schema: {schema}")

            # Create table (location is determined by catalog warehouse config)
            table = self._get_catalog().create_table(
                identifier=table_identifier,
                schema=schema
            )

            print(f"✓ Created Iceberg table: {table_identifier}")
            from src.models import CreateTableResponseData, ResponseMetadata
            return CreateTableResponse(
                success=True,
                data=CreateTableResponseData(
                    table_created=True,
                    table_existed=False
                ),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            from src.models import ResponseMetadata
            return CreateTableResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="CREATE_ERROR", message=str(e))
            )

    def write(self, request: WriteRequest) -> WriteResponse:
        """Write records to Iceberg table using PyIceberg and Polars"""
        try:
            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )

            # Load Iceberg table
            table = self._get_catalog().load_table(table_identifier)

            # Enrich records with system fields
            timestamp = datetime.utcnow()
            enriched_records = []

            for record in request.records:
                enriched = record.copy()
                enriched.update({
                    "_tenant_id": request.tenant_id,
                    "_record_id": hashlib.md5(
                        json.dumps(record, sort_keys=True).encode()
                    ).hexdigest(),
                    "_timestamp": timestamp,
                    "_version": 1,
                    "_deleted": False,
                    "_deleted_at": None
                })
                enriched_records.append(enriched)

            # Convert to Polars DataFrame with proper schema
            df = pl.DataFrame(enriched_records)

            # Ensure proper data types for system fields
            df = df.with_columns([
                pl.col("_tenant_id").cast(pl.Utf8),
                pl.col("_record_id").cast(pl.Utf8),
                pl.col("_timestamp").cast(pl.Datetime),
                pl.col("_version").cast(pl.Int32),
                pl.col("_deleted").cast(pl.Boolean),
                pl.col("_deleted_at").cast(pl.Datetime, strict=False)
            ])

            # Get Iceberg table schema first to check for missing columns
            iceberg_schema = table.schema().as_arrow()
            
            # CRITICAL FIX: Ensure all schema columns exist in DataFrame before conversion
            # Polars drops columns that are missing from input dicts, but PyArrow select() requires them
            missing_fields = []
            for field in iceberg_schema:
                if field.name not in df.columns:
                    missing_fields.append(pl.lit(None).alias(field.name))
                    print(f"  Gap-filling missing field: {field.name}")
            
            if missing_fields:
                df = df.with_columns(missing_fields)

            # Convert to PyArrow table
            arrow_table = df.to_arrow()

            # Reorder columns to match Iceberg schema field order
            field_names = [field.name for field in iceberg_schema]
            arrow_table = arrow_table.select(field_names)

            # Cast the arrow table to match Iceberg schema exactly
            # This ensures field types and nullability match
            arrow_table = arrow_table.cast(iceberg_schema)

            # Append to Iceberg table
            table.append(arrow_table)

            print(f"✓ Wrote {len(enriched_records)} records to {table_identifier}")

            # Invalidate metadata cache to ensure immediate consistency for this container
            if table_identifier in self._metadata_cache:
                del self._metadata_cache[table_identifier]


            # Opportunistic compaction check (non-blocking)
            compaction_recommended = False
            small_files_count = None

            try:
                # Get compaction config using nested keys
                compaction_config = self.config.get('iceberg', 'compaction')

                if compaction_config.get('enabled', True):
                    # Check every Nth write using snapshot count
                    check_interval = compaction_config.get('opportunistic_check_interval', 100)

                    # Reload table to get updated metadata
                    table = self._get_catalog().load_table(table_identifier)
                    snapshot_count = len(list(table.history()))

                    # Check if it's time to evaluate compaction
                    if snapshot_count % check_interval == 0:
                        # Quick file inspection
                        small_file_threshold_mb = compaction_config.get('small_file_threshold_mb', 64)
                        small_file_threshold_bytes = small_file_threshold_mb * 1024 * 1024
                        min_files_to_compact = compaction_config.get('min_files_to_compact', 10)

                        # Inspect files using scan().plan_files()
                        scan_tasks = list(table.scan().plan_files())
                        small_files = [
                            task for task in scan_tasks
                            if task.file.file_size_in_bytes < small_file_threshold_bytes
                        ]

                        small_files_count = len(small_files)

                        if len(small_files) >= min_files_to_compact:
                            compaction_recommended = True
                            print(f"⚠ Compaction recommended: {len(small_files)} small files detected")

            except Exception as e:
                # Don't fail write if compaction check fails
                print(f"Warning: Compaction check failed: {e}")

            # Auto-compaction check (runs asynchronously, doesn't block response)
            if self._last_compact_check is not None:
                time_since_check = time.time() - self._last_compact_check
                if time_since_check > 3600 and compaction_recommended:  # Check hourly AND if needed
                    self._trigger_async_compact(request.tenant_id, request.namespace, request.table)
                    self._last_compact_check = time.time()
            else:
                self._last_compact_check = time.time()

            from src.models import WriteResponseData, ResponseMetadata
            return WriteResponse(
                success=True,
                data=WriteResponseData(
                    records_written=len(enriched_records),
                    compaction_recommended=compaction_recommended,
                    small_files_count=small_files_count
                ),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            from src.models import ResponseMetadata
            return WriteResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="WRITE_ERROR", message=str(e))
            )

    def query(self, request: QueryRequest) -> QueryResponse:
        """Query Iceberg table using DuckDB's iceberg_scan with metadata caching"""
        import uuid
        query_start = time.time()
        query_id = str(uuid.uuid4())
        cache_hit = False

        # Create cache key from request parameters for query result caching
        cache_key_parts = [
            request.tenant_id,
            request.namespace,
            request.table,
            str(request.filters) if request.filters else "",
            str(request.projection) if request.projection else "*",
            str(request.aggregations) if request.aggregations else "",
            str(request.group_by) if request.group_by else "",
            str(request.having) if request.having else "",
            str(request.sort) if request.sort else "",
            str(request.limit) if request.limit else "",
            str(request.include_deleted)
        ]
        query_cache_key = hashlib.md5(":".join(cache_key_parts).encode()).hexdigest()

        # Check query result cache
        if query_cache_key in self._query_cache:
            cached_result, cached_time = self._query_cache[query_cache_key]
            if time.time() - cached_time < self._query_cache_ttl:
                # Update metadata to indicate cache hit
                cached_result['data']['query_metadata']['cache_hit'] = True
                cached_result['data']['query_metadata']['query_id'] = query_id
                from src.models import QueryResponse, QueryResponseData, QueryMetadata, ResponseMetadata
                return QueryResponse(**cached_result)

        try:
            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )

            # Get table metadata location from cache (fast) or catalog (slow)
            try:
                # Check if this will be a cache hit
                cache_key = table_identifier
                if cache_key in self._metadata_cache:
                    cached_path, cached_time = self._metadata_cache[cache_key]
                    if time.time() - cached_time < self._cache_ttl:
                        cache_hit = True
                
                metadata_path = self._get_metadata_path(table_identifier)
            except Exception as e:
                # Table doesn't exist
                from src.models import QueryResponseData, ResponseMetadata
                return QueryResponse(
                    success=True,
                    data=QueryResponseData(
                        records=[],
                        query_metadata=QueryMetadata(
                            row_count=0,
                            execution_time_ms=0,
                            cache_hit=False,
                            query_id=query_id
                        )
                    ),
                    metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                    error=None
                )

            # Build SELECT clause based on projection and aggregations
            select_clause = self._build_select_clause(request.projection, request.aggregations)

            # Build DuckDB query using iceberg_scan with metadata file
            # Use CTE to select only the latest version of each record
            # Then apply filters (including _deleted check) on the result
            deleted_filter = "" if request.include_deleted else "AND _deleted IS NOT TRUE"
            
            sql = f"""
                WITH ranked_records AS (
                    SELECT *,
                           ROW_NUMBER() OVER (PARTITION BY _record_id ORDER BY _version DESC) as rn
                    FROM iceberg_scan('{metadata_path}')
                    WHERE _tenant_id = '{request.tenant_id}'
                )
                SELECT {select_clause} FROM ranked_records
                WHERE rn = 1
                {deleted_filter}
            """

            # Add custom filters
            params = []
            if request.filters:
                builder = TypeSafeQueryBuilder()
                filter_sql, params = builder._build_filters(request.filters, "")
                if filter_sql:
                    sql += f" AND ({filter_sql})"

            # Add GROUP BY clause
            if request.group_by:
                group_fields = ', '.join(request.group_by)
                sql += f" GROUP BY {group_fields}"

            # Add HAVING clause (post-aggregation filter)
            if request.having:
                builder = TypeSafeQueryBuilder()
                having_sql, having_params = builder._build_filters(request.having, "")
                if having_sql:
                    sql += f" HAVING {having_sql}"
                    if having_params:
                        params.extend(having_params)

            # Add sorting
            if request.sort:
                order_parts = []
                for sort_field in request.sort:
                    order_parts.append(f"{sort_field.field} {sort_field.order.value.upper()}")
                sql += f" ORDER BY {', '.join(order_parts)}"

            # Add limit
            if request.limit:
                sql += f" LIMIT {request.limit}"

            # Execute query and track timing
            query_exec_start = time.time()
            if params:
                result = self.conn.execute(sql, params).fetchdf()
            else:
                result = self.conn.execute(sql).fetchdf()
            query_exec_time = (time.time() - query_exec_start) * 1000

            # Convert to dict
            data = result.to_dict(orient='records') if not result.empty else []
            
            # Calculate total query time
            total_time_ms = (time.time() - query_start) * 1000
            
            # Estimate scanned bytes (rough estimate based on result size)
            scanned_rows = len(data)
            scanned_bytes = None
            if data:
                # Estimate bytes: sum of string lengths + fixed overhead per row
                try:
                    import sys
                    scanned_bytes = sum(sys.getsizeof(str(v)) for row in data for v in row.values())
                except:
                    scanned_bytes = None

            from src.models import QueryResponseData, ResponseMetadata
            response = QueryResponse(
                success=True,
                data=QueryResponseData(
                    records=data,
                    query_metadata=QueryMetadata(
                        row_count=len(data),
                        execution_time_ms=round(query_exec_time, 2),
                        scanned_bytes=scanned_bytes,
                        scanned_rows=scanned_rows,
                        cache_hit=cache_hit,
                        query_id=query_id,
                        warnings=None
                    )
                ),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

            # Cache the successful query result
            self._query_cache[query_cache_key] = (response.dict(), time.time())

            # Simple LRU cache - limit size
            if len(self._query_cache) > 100:
                oldest_key = next(iter(self._query_cache))
                del self._query_cache[oldest_key]

            return response

        except Exception as e:
            from src.models import ResponseMetadata
            return QueryResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="QUERY_ERROR", message=str(e))
            )

    def update(self, request: UpdateRequest) -> UpdateResponse:
        """Update records - read from DuckDB, modify, write back with PyIceberg"""
        try:
            # First query the records to update - ONLY GET LATEST VERSION
            # We need to get the latest version of each record to avoid duplicates
            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )
            metadata_path = self._get_metadata_path(table_identifier)
            
            # Build filter SQL
            builder = TypeSafeQueryBuilder()
            filter_sql, params = builder._build_filters(request.filters, "")
            
            # Query to get only the LATEST version of each matching record
            # This uses a window function to rank versions per record_id
            sql = f"""
                WITH ranked_records AS (
                    SELECT *,
                           ROW_NUMBER() OVER (PARTITION BY _record_id ORDER BY _version DESC) as rn
                    FROM iceberg_scan('{metadata_path}')
                    WHERE _tenant_id = '{request.tenant_id}'
                      AND _deleted IS NOT TRUE
                      AND ({filter_sql})
                )
                SELECT * FROM ranked_records WHERE rn = 1
            """
            
            # Execute query
            if params:
                result_df = self.conn.execute(sql, params).fetchdf()
            else:
                result_df = self.conn.execute(sql).fetchdf()
            
            # Remove the 'rn' column added by ROW_NUMBER
            if 'rn' in result_df.columns:
                result_df = result_df.drop('rn', axis=1)
            
            # Convert to list of records
            records = result_df.to_dict(orient='records') if not result_df.empty else []
            
            # If no records found, return success with 0 updates
            if not records:
                from src.models import UpdateResponseData, ResponseMetadata
                return UpdateResponse(
                    success=True,
                    data=UpdateResponseData(records_updated=0),
                    metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                    error=None
                )

            # Update records - create new versions with updated values
            timestamp = datetime.utcnow()
            updated_records = []
            for record in records:
                # Ensure proper types before updating
                record["_version"] = int(record.get("_version", 1)) + 1
                record["_timestamp"] = timestamp
                # Handle NaT (Not a Time) values - convert to None
                if "_deleted_at" in record:
                    val = record["_deleted_at"]
                    # Check if it's NaT (pandas/numpy NaT shows as string "NaT")
                    if val is None or (isinstance(val, str) and val == "NaT") or str(val) == "NaT":
                        record["_deleted_at"] = None
                # Apply user updates
                record.update(request.updates)
                updated_records.append(record)

            # Convert directly to PyArrow table (bypass Polars to avoid type issues)
            arrow_table = pa.Table.from_pylist(updated_records)

            # Load table and get schema (table_identifier already defined above)
            table = self._get_catalog().load_table(table_identifier)

            # Get Iceberg table schema as PyArrow schema
            iceberg_schema = table.schema().as_arrow()

            # Reorder columns to match Iceberg schema field order
            field_names = [field.name for field in iceberg_schema]
            arrow_table = arrow_table.select(field_names)

            # Cast the arrow table to match Iceberg schema exactly
            arrow_table = arrow_table.cast(iceberg_schema)

            # Append to Iceberg table
            table.append(arrow_table)

            from src.models import UpdateResponseData, ResponseMetadata
            return UpdateResponse(
                success=True,
                data=UpdateResponseData(records_updated=len(updated_records)),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            from src.models import ResponseMetadata
            return UpdateResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="UPDATE_ERROR", message=str(e))
            )

    def delete(self, request: DeleteRequest) -> DeleteResponse:
        """Delete records (soft delete by marking _deleted=true)"""
        try:
            # Soft delete by updating _deleted flag
            update_req = UpdateRequest(
                tenant_id=request.tenant_id,
                namespace=request.namespace,
                table=request.table,
                updates={
                    "_deleted": True,
                    "_deleted_at": datetime.utcnow()
                },
                filters=request.filters
            )
            update_result = self.update(update_req)

            from src.models import DeleteResponseData, ResponseMetadata
            return DeleteResponse(
                success=update_result.success,
                data=DeleteResponseData(
                    records_deleted=update_result.data.records_updated if update_result.data else 0
                ) if update_result.success else None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=update_result.error
            )

        except Exception as e:
            from src.models import ResponseMetadata
            return DeleteResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="DELETE_ERROR", message=str(e))
            )

    def hard_delete(self, request: HardDeleteRequest) -> HardDeleteResponse:
        """
        Hard delete - physically remove records from storage.
        WARNING: This is irreversible!
        """
        try:
            # Safety check: require explicit confirmation
            if not request.confirm:
                from src.models import ResponseMetadata
                return HardDeleteResponse(
                    success=False,
                    data=None,
                    metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                    error=ErrorDetail(
                        code="CONFIRMATION_REQUIRED",
                        message="Hard delete requires confirm=true"
                    )
                )

            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )

            # Load table
            table = self._get_catalog().load_table(table_identifier)

            # First, query to count how many records will be deleted
            metadata_path = table.metadata_location

            # Build filter SQL
            builder = TypeSafeQueryBuilder()
            filter_sql, params = builder._build_filters(request.filters, "")

            count_sql = f"""
                SELECT COUNT(*) as count FROM iceberg_scan('{metadata_path}')
                WHERE _tenant_id = '{request.tenant_id}'
                AND ({filter_sql})
            """

            if params:
                count_result = self.conn.execute(count_sql, params).fetchone()
            else:
                count_result = self.conn.execute(count_sql).fetchone()

            records_to_delete = count_result[0] if count_result else 0

            if records_to_delete == 0:
                from src.models import HardDeleteResponseData, ResponseMetadata
                return HardDeleteResponse(
                    success=True,
                    data=HardDeleteResponseData(
                        records_deleted=0,
                        files_rewritten=0
                    ),
                    metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                    error=None
                )

            # Use PyIceberg's delete to physically remove rows
            # Build Iceberg filter expression from our filters array
            from pyiceberg.expressions import EqualTo, GreaterThan, LessThan, And, Or

            # Convert our filters to Iceberg expression
            iceberg_filter = self._build_iceberg_filter_from_array(request.filters)

            # Also add tenant filter
            tenant_filter = EqualTo("_tenant_id", request.tenant_id)
            combined_filter = And(tenant_filter, iceberg_filter) if iceberg_filter else tenant_filter

            # Execute physical deletion
            files_before = len(list(table.scan().plan_files()))
            table.delete(combined_filter)

            # Reload table to get updated file count
            table = self._get_catalog().load_table(table_identifier)
            files_after = len(list(table.scan().plan_files()))

            print(f"✓ Hard deleted {records_to_delete} records from {request.table}")
            print(f"  Files rewritten: {files_before - files_after}")

            from src.models import HardDeleteResponseData, ResponseMetadata
            return HardDeleteResponse(
                success=True,
                data=HardDeleteResponseData(
                    records_deleted=records_to_delete,
                    files_rewritten=files_before - files_after
                ),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            print(f"✗ Hard delete failed: {e}")
            import traceback
            traceback.print_exc()
            from src.models import ResponseMetadata
            return HardDeleteResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="HARD_DELETE_ERROR", message=str(e))
            )

    def _trigger_async_compact(self, tenant_id: str, namespace: str, table: str):
        """Trigger compaction asynchronously using Lambda invoke"""
        import boto3
        import json
        import os

        # Only trigger in production (Lambda environment)
        if 'AWS_LAMBDA_FUNCTION_NAME' not in os.environ:
            print("Skipping auto-compaction (not in Lambda environment)")
            return

        lambda_client = boto3.client('lambda')

        # Invoke same Lambda function asynchronously with COMPACT operation
        try:
            lambda_client.invoke(
                FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME'),
                InvocationType='Event',  # Async - doesn't wait
                Payload=json.dumps({
                    'body': json.dumps({
                        'operation': 'COMPACT',
                        'tenant_id': tenant_id,
                        'namespace': namespace,
                        'table': table,
                        'target_file_size_mb': 128,
                        'expire_snapshots': True,
                        'snapshot_retention_hours': 0  # Immediate cleanup
                    })
                })
            )
            print(f"✓ Auto-compaction triggered asynchronously for {table}")
        except Exception as e:
            print(f"Auto-compact trigger failed (non-blocking): {e}")

    def _build_iceberg_filter_from_array(self, filters: List) -> Any:
        """Convert filters array to PyIceberg filter expression (all ANDed)"""
        from pyiceberg.expressions import (
            EqualTo, NotEqualTo, GreaterThan, LessThan, 
            GreaterThanOrEqual, LessThanOrEqual, In, And
        )

        if not filters:
            return None

        iceberg_filters = []
        for filter_item in filters:
            field = filter_item.field
            operator = filter_item.operator
            value = filter_item.value

            if operator == "eq":
                iceberg_filters.append(EqualTo(field, value))
            elif operator == "ne":
                iceberg_filters.append(NotEqualTo(field, value))
            elif operator == "gt":
                iceberg_filters.append(GreaterThan(field, value))
            elif operator == "gte":
                iceberg_filters.append(GreaterThanOrEqual(field, value))
            elif operator == "lt":
                iceberg_filters.append(LessThan(field, value))
            elif operator == "lte":
                iceberg_filters.append(LessThanOrEqual(field, value))
            elif operator == "in":
                iceberg_filters.append(In(field, value))
            # Note: LIKE is not supported by PyIceberg expressions

        if len(iceberg_filters) == 0:
            return None
        elif len(iceberg_filters) == 1:
            return iceberg_filters[0]
        else:
            # Combine with AND
            result = iceberg_filters[0]
            for f in iceberg_filters[1:]:
                result = And(result, f)
            return result

    # DEPRECATED - Keep old method for reference
    def _build_iceberg_filter(self, filter_expr: Dict[str, Any]):
        """DEPRECATED: Convert old filter expression to PyIceberg filter"""
        from pyiceberg.expressions import EqualTo, GreaterThan, LessThan, GreaterThanOrEqual, LessThanOrEqual, And, Or

        if not filter_expr:
            return None

        filters = []
        for field, conditions in filter_expr.items():
            if isinstance(conditions, dict):
                for op, value in conditions.items():
                    if op == "eq":
                        filters.append(EqualTo(field, value))
                    elif op == "gt":
                        filters.append(GreaterThan(field, value))
                    elif op == "lt":
                        filters.append(LessThan(field, value))
                    elif op == "gte":
                        filters.append(GreaterThanOrEqual(field, value))
                    elif op == "lte":
                        filters.append(LessThanOrEqual(field, value))

        if len(filters) == 0:
            return None
        elif len(filters) == 1:
            return filters[0]
        else:
            # Combine with AND
            result = filters[0]
            for f in filters[1:]:
                result = And(result, f)
            return result

    def compact(self, request: CompactRequest) -> CompactResponse:
        """
        Compact small files into larger files to improve query performance.

        This addresses the "small files problem" where many small writes create
        too many tiny files, degrading query performance.
        """
        start_time = time.time()

        try:
            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )

            # Load Iceberg table
            table = self._get_catalog().load_table(table_identifier)

            # Get compaction config using nested keys
            compaction_config = self.config.get('iceberg', 'compaction')

            # Get threshold from config or request
            small_file_threshold_bytes = (
                request.target_file_size_mb or
                compaction_config.get('small_file_threshold_mb', 64)
            ) * 1024 * 1024

            max_files_per_compaction = (
                request.max_files or
                compaction_config.get('max_files_per_compaction', 100)
            )

            min_files_to_compact = compaction_config.get('min_files_to_compact', 10)

            # Inspect files using scan().plan_files()
            scan_tasks = list(table.scan().plan_files())

            if not scan_tasks:
                from src.models import CompactResponseData, ResponseMetadata
                return CompactResponse(
                    success=True,
                    data=CompactResponseData(
                        compacted=False,
                        reason="No files to compact",
                        stats=None
                    ),
                    metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                    error=None
                )

            # Calculate statistics before compaction
            total_files_before = len(scan_tasks)
            total_bytes_before = sum(task.file.file_size_in_bytes for task in scan_tasks)

            # Identify small files
            small_files = [
                task for task in scan_tasks
                if task.file.file_size_in_bytes < small_file_threshold_bytes
            ]

            # Check if compaction is needed
            if not request.force and len(small_files) < min_files_to_compact:
                from src.models import CompactResponseData, ResponseMetadata
                return CompactResponse(
                    success=True,
                    data=CompactResponseData(
                        compacted=False,
                        reason=f"Only {len(small_files)} small files (threshold: {min_files_to_compact})",
                        stats=None
                    ),
                    metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                    error=None
                )

            # Limit files to compact
            files_to_compact = small_files[:max_files_per_compaction]

            print(f"Compacting {len(files_to_compact)} small files out of {total_files_before} total files")

            # Read all data from the table (we'll rewrite everything to maintain consistency)
            metadata_path = table.metadata_location
            sql = f"""
                SELECT * FROM iceberg_scan('{metadata_path}')
                WHERE _tenant_id = '{request.tenant_id}'
            """

            # Read data using DuckDB
            result_df = self.conn.execute(sql).fetchdf()

            if result_df.empty:
                from src.models import CompactResponseData, ResponseMetadata
                return CompactResponse(
                    success=True,
                    data=CompactResponseData(
                        compacted=False,
                        reason="No data to compact",
                        stats=None
                    ),
                    metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                    error=None
                )

            # Convert to PyArrow table
            arrow_table = pa.Table.from_pandas(result_df)

            # Get Iceberg schema
            iceberg_schema = table.schema().as_arrow()

            # Reorder and cast to match Iceberg schema
            field_names = [field.name for field in iceberg_schema]
            arrow_table = arrow_table.select(field_names)
            arrow_table = arrow_table.cast(iceberg_schema)

            # Use table.overwrite() to replace all data with compacted version
            # This will delete old files and write new, optimally-sized files
            table.overwrite(arrow_table)

            # Refresh table metadata
            table = self._get_catalog().load_table(table_identifier)
            
            # Invalidate cache after compaction rewrite
            if table_identifier in self._metadata_cache:
                del self._metadata_cache[table_identifier]


            # Get new file statistics using scan().plan_files()
            new_scan_tasks = list(table.scan().plan_files())
            total_files_after = len(new_scan_tasks)
            total_bytes_after = sum(task.file.file_size_in_bytes for task in new_scan_tasks)

            # Count remaining small files
            small_files_remaining = len([
                task for task in new_scan_tasks
                if task.file.file_size_in_bytes < small_file_threshold_bytes
            ])

            # Expire old snapshots if requested
            # NOTE: This is the KEY to deleting old files!
            snapshots_expired = 0
            if request.expire_snapshots:
                try:
                    retention_time = datetime.utcnow() - timedelta(
                        hours=request.snapshot_retention_hours
                    )
                    
                    # Reload table to get latest metadata
                    table = self._get_catalog().load_table(table_identifier)
                    
                    # Get all snapshots
                    all_snapshots = list(table.history())
                    print(f"Total snapshots in table: {len(all_snapshots)}")
                    
                    # Check retention - but for compaction, we want to delete immediately!
                    # Set retention to NOW to expire old snapshots immediately after compaction
                    older_than_ms = int(datetime.utcnow().timestamp() * 1000)
                    
                    # Keep only the latest snapshot
                    if len(all_snapshots) > 1:
                        print(f"Expiring {len(all_snapshots) - 1} old snapshots...")
                        
                        # Use table.expire_snapshots() with older_than parameter
                        # This is the correct PyIceberg 0.10.0 API
                        table.manage_snapshots().expire_snapshots().expire_older_than(older_than_ms).commit()
                        
                        snapshots_expired = len(all_snapshots) - 1
                        print(f"✓ Expired {snapshots_expired} old snapshots and deleted orphan files")
                    else:
                        print("✓ Only 1 snapshot exists, no old files to delete")
                        
                except AttributeError as e:
                    print(f"⚠ Snapshot expiration API not available: {e}")
                    print(f"⚠ Old files will remain for time-travel queries")
                except Exception as e:
                    print(f"⚠ Could not expire snapshots: {e}")
                    print(f"⚠ Old files will remain on S3 until manual cleanup")

            # Calculate compaction time
            compaction_time_ms = (time.time() - start_time) * 1000

            # Build response
            stats = CompactionStats(
                files_before=total_files_before,
                files_after=total_files_after,
                files_compacted=len(files_to_compact),
                files_removed=total_files_before - total_files_after,
                bytes_before=total_bytes_before,
                bytes_after=total_bytes_after,
                bytes_saved=total_bytes_before - total_bytes_after,
                snapshots_expired=snapshots_expired,
                compaction_time_ms=compaction_time_ms,
                small_files_remaining=small_files_remaining
            )

            print(f"✓ Compaction complete: {total_files_before} → {total_files_after} files")
            print(f"  Small files: {len(small_files)} → {small_files_remaining}")
            print(f"  Size: {total_bytes_before / (1024*1024):.1f}MB → {total_bytes_after / (1024*1024):.1f}MB")
            print(f"  Time: {compaction_time_ms:.0f}ms")

            from src.models import CompactResponseData, ResponseMetadata
            return CompactResponse(
                success=True,
                data=CompactResponseData(
                    compacted=True,
                    reason=None,
                    stats=stats
                ),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            compaction_time_ms = (time.time() - start_time) * 1000
            print(f"✗ Compaction failed after {compaction_time_ms:.0f}ms: {e}")
            from src.models import ResponseMetadata
            return CompactResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="COMPACT_ERROR", message=str(e))
            )

    def list_tables(self, request: ListTablesRequest) -> ListTablesResponse:
        """List tables in namespace using PyIceberg catalog"""
        try:
            namespace = self._get_namespace(request.tenant_id, request.namespace)

            # List tables in namespace
            tables = self._get_catalog().list_tables(namespace)

            # Extract table names
            table_names = [table[1] for table in tables]  # tables are (namespace, name) tuples

            from src.models import ListTablesResponseData, ResponseMetadata
            return ListTablesResponse(
                success=True,
                data=ListTablesResponseData(tables=table_names),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            from src.models import ResponseMetadata
            return ListTablesResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="LIST_ERROR", message=str(e))
            )

    def describe_table(self, request: DescribeTableRequest) -> DescribeTableResponse:
        """Describe Iceberg table using PyIceberg"""
        try:
            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )

            # Load table
            table = self._get_catalog().load_table(table_identifier)

            # Get schema info
            schema_fields = {}
            for field in table.schema().fields:
                if not field.name.startswith('_'):  # Skip system fields
                    schema_fields[field.name] = str(field.field_type)

            # Get row count using DuckDB with metadata file
            metadata_path = table.metadata_location
            sql = f"""
                SELECT COUNT(*) as row_count
                FROM iceberg_scan('{metadata_path}')
                WHERE _deleted IS NOT TRUE
                AND _tenant_id = '{request.tenant_id}'
            """
            result = self.conn.execute(sql).fetchone()
            row_count = result[0] if result else 0

            table_desc = TableDescription(
                table_name=request.table,
                namespace=request.namespace,
                row_count=row_count,
                schema={"fields": schema_fields}
            )

            from src.models import DescribeTableResponseData, ResponseMetadata
            return DescribeTableResponse(
                success=True,
                data=DescribeTableResponseData(table=table_desc),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            from src.models import ResponseMetadata
            return DescribeTableResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="DESCRIBE_ERROR", message=str(e))
            )

    def drop_table(self, request: DropTableRequest) -> DropTableResponse:
        """Drop Iceberg table"""
        try:
            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )
            
            # Check if exists first
            try:
                self._get_catalog().load_table(table_identifier)
            except:
                from src.models import DropTableResponseData, ResponseMetadata
                return DropTableResponse(
                    success=True,
                    data=DropTableResponseData(
                        table_dropped=False,
                        table_existed=False
                    ),
                    metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                    error=None
                )

            # Drop table
            # purge=True means delete data files too
            # Drop table
            # NOTE: Some PyIceberg catalog implementations (like Glue) do not support the 'purge' argument yet.
            # We try with purge first, but if it fails with TypeError, we fallback to default drop.
            try:
                self._get_catalog().drop_table(table_identifier, purge=request.purge)
            except TypeError as te:
                if "unexpected keyword argument 'purge'" in str(te):
                    print("⚠ Catalog does not support 'purge' argument, retrying without it.")
                    self._get_catalog().drop_table(table_identifier)
                else:
                    raise te
            
            # Invalidate cache
            if table_identifier in self._metadata_cache:
                del self._metadata_cache[table_identifier]

            print(f"✓ Dropped table: {table_identifier} (purge={request.purge})")
            
            from src.models import DropTableResponseData, ResponseMetadata
            return DropTableResponse(
                success=True,
                data=DropTableResponseData(
                    table_dropped=True,
                    table_existed=True
                ),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            from src.models import ResponseMetadata
            return DropTableResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="DROP_TABLE_ERROR", message=str(e))
            )

    def drop_namespace(self, request: DropNamespaceRequest) -> DropNamespaceResponse:
        """Drop namespace (database)"""
        try:
            namespace = self._get_namespace(request.tenant_id, request.namespace)
            
            # Drop namespace
            # Only works if namespace is empty (no tables)
            self._get_catalog().drop_namespace(namespace)
            
            print(f"✓ Dropped namespace: {namespace}")
            
            from src.models import DropNamespaceResponseData, ResponseMetadata
            return DropNamespaceResponse(
                success=True,
                data=DropNamespaceResponseData(
                    namespace_dropped=True,
                    namespace_existed=True
                ),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            # Check if it's because it doesn't exist
            if "not found" in str(e).lower() or "does not exist" in str(e).lower():
                from src.models import DropNamespaceResponseData, ResponseMetadata
                return DropNamespaceResponse(
                    success=True,
                    data=DropNamespaceResponseData(
                        namespace_dropped=False,
                        namespace_existed=False
                    ),
                    metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                    error=None
                )
                
            from src.models import ResponseMetadata
            return DropNamespaceResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="DROP_NAMESPACE_ERROR", message=str(e))
            )

    def _map_to_iceberg_type(self, field_def):
        """
        Map field definition to Iceberg types (supports primitive and complex types)
        
        Args:
            field_def: Can be either a string (for simple types) or FieldDefinition object (for complex types)
            
        Returns:
            Iceberg type class instance
        """
        from src.models import FieldDefinition
        
        # Handle simple string type definition (backward compatibility)
        if isinstance(field_def, str):
            field_type = field_def.lower()
            type_mapping = {
                'string': StringType(),
                'integer': IntegerType(),
                'long': LongType(),
                'float': FloatType(),
                'double': DoubleType(),
                'boolean': BooleanType(),
                'date': DateType(),
                'timestamp': TimestampType(),
                'decimal': DecimalType(38, 9),  # Default precision and scale
                'binary': BinaryType(),
            }
            return type_mapping.get(field_type, StringType())
        
        # Handle FieldDefinition object (complex types)
        if isinstance(field_def, FieldDefinition):
            field_type = field_def.type.lower() if isinstance(field_def.type, str) else field_def.type.value.lower()
            
            # Handle array/list type
            if field_type == 'array':
                if not field_def.items:
                    raise ValueError("Array type must specify 'items' field definition")
                element_type = self._map_to_iceberg_type(field_def.items)
                # ListType expects element_id, element type, and required flag
                return ListType(element_id=1, element=element_type, element_required=field_def.items.required if isinstance(field_def.items, FieldDefinition) else False)
            
            # Handle map type
            elif field_type == 'map':
                if not field_def.key_type or not field_def.value_type:
                    raise ValueError("Map type must specify both 'key_type' and 'value_type'")
                key_iceberg_type = self._map_to_iceberg_type(field_def.key_type)
                value_iceberg_type = self._map_to_iceberg_type(field_def.value_type)
                # MapType expects key_id, key type, value_id, value type, and value_required flag
                return MapType(
                    key_id=1,
                    key=key_iceberg_type,
                    value_id=2,
                    value=value_iceberg_type,
                    value_required=field_def.value_type.required if isinstance(field_def.value_type, FieldDefinition) else False
                )
            
            # Handle struct/object type
            elif field_type == 'struct':
                if not field_def.fields:
                    raise ValueError("Struct type must specify 'fields' dictionary")
                # Build nested fields for the struct
                nested_fields = []
                field_id = 1
                for nested_field_name, nested_field_def in field_def.fields.items():
                    nested_iceberg_type = self._map_to_iceberg_type(nested_field_def)
                    nested_required = nested_field_def.required if isinstance(nested_field_def, FieldDefinition) else False
                    nested_fields.append(
                        NestedField(field_id, nested_field_name, nested_iceberg_type, required=nested_required)
                    )
                    field_id += 1
                return StructType(*nested_fields)
            
            # Handle primitive types
            else:
                type_mapping = {
                    'string': StringType(),
                    'integer': IntegerType(),
                    'long': LongType(),
                    'float': FloatType(),
                    'double': DoubleType(),
                    'boolean': BooleanType(),
                    'date': DateType(),
                    'timestamp': TimestampType(),
                    'decimal': DecimalType(38, 9),
                    'binary': BinaryType(),
                }
                return type_mapping.get(field_type, StringType())
        
        # Fallback to string type
        return StringType()


# Global instance
_iceberg_ops = None
_iceberg_ops_init_failed = False
_iceberg_ops_init_error = None

def get_iceberg_ops() -> FullIcebergOperations:
    """
    Get or create Iceberg operations instance
    
    Raises:
        RuntimeError: If initialization previously failed
    """
    global _iceberg_ops, _iceberg_ops_init_failed, _iceberg_ops_init_error
    
    # If initialization failed before, don't retry (requires container restart)
    if _iceberg_ops_init_failed:
        error_msg = (
            f"Iceberg operations initialization previously failed. "
            f"Container restart required. Original error: {_iceberg_ops_init_error}"
        )
        print(f"✗ {error_msg}")
        raise RuntimeError(error_msg)
    
    # Create instance if not exists
    if _iceberg_ops is None:
        try:
            print("Initializing Iceberg operations...")
            _iceberg_ops = FullIcebergOperations()
            print("✓ Iceberg operations initialized successfully")
        except Exception as e:
            _iceberg_ops_init_failed = True
            _iceberg_ops_init_error = str(e)
            print(f"✗ Iceberg operations initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Failed to initialize Iceberg operations: {e}") from e
    
    return _iceberg_ops


# Wrapper for compatibility with existing code
class DatabaseOperations:
    """Wrapper to use full Iceberg operations"""

    @staticmethod
    def write(request: WriteRequest) -> WriteResponse:
        return get_iceberg_ops().write(request)

    @staticmethod
    def query(request: QueryRequest) -> QueryResponse:
        return get_iceberg_ops().query(request)

    @staticmethod
    def update(request: UpdateRequest) -> UpdateResponse:
        return get_iceberg_ops().update(request)

    @staticmethod
    def delete(request: DeleteRequest) -> DeleteResponse:
        return get_iceberg_ops().delete(request)

    @staticmethod
    def hard_delete(request: HardDeleteRequest) -> HardDeleteResponse:
        return get_iceberg_ops().hard_delete(request)

    @staticmethod
    def create_table(request: CreateTableRequest) -> CreateTableResponse:
        return get_iceberg_ops().create_table(request)

    @staticmethod
    def describe_table(request: DescribeTableRequest) -> DescribeTableResponse:
        return get_iceberg_ops().describe_table(request)

    @staticmethod
    def list_tables(request: ListTablesRequest) -> ListTablesResponse:
        return get_iceberg_ops().list_tables(request)

    @staticmethod
    def compact(request: CompactRequest) -> CompactResponse:
        return get_iceberg_ops().compact(request)

    @staticmethod
    def drop_table(request: DropTableRequest) -> DropTableResponse:
        return get_iceberg_ops().drop_table(request)

    @staticmethod
    def drop_namespace(request: DropNamespaceRequest) -> DropNamespaceResponse:
        return get_iceberg_ops().drop_namespace(request)