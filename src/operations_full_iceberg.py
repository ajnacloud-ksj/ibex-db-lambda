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
    DateType
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
    ErrorDetail, QueryMetadata
)
from .query_builder import TypeSafeQueryBuilder


class FullIcebergOperations:
    """Full Iceberg operations using PyIceberg for writes and DuckDB for reads"""

    def __init__(self):
        """Initialize PyIceberg catalog and DuckDB connection"""
        self.config = get_config()
        self.catalog = self._init_pyiceberg_catalog()
        self.conn = self._init_duckdb()

    def _init_pyiceberg_catalog(self) -> Catalog:
        """Initialize PyIceberg catalog (REST or Glue based on config)"""
        catalog_config = self.config.catalog
        s3_config = self.config.s3

        catalog_type = catalog_config['type']
        catalog_name = catalog_config['name']

        # Build warehouse path
        warehouse = f"s3://{s3_config['bucket_name']}/{s3_config['warehouse_path']}/"

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

            catalog = RestCatalog(name=catalog_name, **catalog_params)
            print(f"✓ PyIceberg REST catalog initialized at {catalog_config['uri']}")

        elif catalog_type == 'glue':
            # Production: AWS Glue Catalog (import only when needed)
            from pyiceberg.catalog.glue import GlueCatalog

            catalog_params = {
                "region_name": catalog_config['region'],
                "s3.region": s3_config['region'],
                "warehouse": warehouse,
                "py-io-impl": "pyiceberg.io.pyarrow.PyArrowFileIO",
            }

            catalog = GlueCatalog(name=catalog_name, **catalog_params)
            print(f"✓ PyIceberg Glue catalog initialized in {catalog_config['region']}")

        else:
            raise ValueError(f"Unsupported catalog type: {catalog_type}")

        return catalog

    def _init_duckdb(self) -> duckdb.DuckDBPyConnection:
        """Initialize DuckDB with Iceberg extension"""
        s3_config = self.config.s3
        duckdb_config = self.config.duckdb

        conn = duckdb.connect(':memory:')

        # Load extensions
        conn.execute("INSTALL iceberg;")
        conn.execute("INSTALL httpfs;")
        conn.execute("LOAD iceberg;")
        conn.execute("LOAD httpfs;")

        # Configure DuckDB settings
        conn.execute(f"SET memory_limit='{duckdb_config['memory_limit']}';")
        conn.execute(f"SET threads={duckdb_config['threads']};")

        # Configure S3
        s3_commands = [
            f"SET s3_region='{s3_config['region']}';"
        ]

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
                    func = agg.op.value.upper()

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
                self.catalog.create_namespace(namespace)
                print(f"✓ Created namespace: {namespace}")
            except Exception as e:
                if "already exists" not in str(e).lower():
                    print(f"Namespace creation note: {e}")

            # Check if table exists
            try:
                existing_table = self.catalog.load_table(table_identifier)
                if not request.if_not_exists:
                    return CreateTableResponse(
                        success=False,
                        table_created=False,
                        table_existed=True,
                        error=ErrorDetail(code="TABLE_EXISTS", message="Table already exists")
                    )
                return CreateTableResponse(
                    success=True,
                    table_created=False,
                    table_existed=True
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
                for field_name, field_def in request.table_schema.fields.items():
                    # field_def is a FieldDefinition object
                    field_type = field_def.type if hasattr(field_def, 'type') else 'string'
                    required = field_def.required if hasattr(field_def, 'required') else False
                    iceberg_type = self._map_to_iceberg_type(field_type)
                    fields.append(
                        NestedField(field_id, field_name, iceberg_type(), required=required)
                    )
                    field_id += 1

            schema = Schema(*fields)

            # Create table (location is determined by catalog warehouse config)
            table = self.catalog.create_table(
                identifier=table_identifier,
                schema=schema
            )

            print(f"✓ Created Iceberg table: {table_identifier}")
            return CreateTableResponse(
                success=True,
                table_created=True,
                table_existed=False
            )

        except Exception as e:
            return CreateTableResponse(
                success=False,
                table_created=False,
                error=ErrorDetail(code="CREATE_ERROR", message=str(e))
            )

    def write(self, request: WriteRequest) -> WriteResponse:
        """Write records to Iceberg table using PyIceberg and Polars"""
        try:
            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )

            # Load Iceberg table
            table = self.catalog.load_table(table_identifier)

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

            # Convert to PyArrow table
            arrow_table = df.to_arrow()

            # Get Iceberg table schema as PyArrow schema
            iceberg_schema = table.schema().as_arrow()

            # Reorder columns to match Iceberg schema field order
            field_names = [field.name for field in iceberg_schema]
            arrow_table = arrow_table.select(field_names)

            # Cast the arrow table to match Iceberg schema exactly
            # This ensures field types and nullability match
            arrow_table = arrow_table.cast(iceberg_schema)

            # Append to Iceberg table
            table.append(arrow_table)

            print(f"✓ Wrote {len(enriched_records)} records to {table_identifier}")

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
                    table = self.catalog.load_table(table_identifier)
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

            return WriteResponse(
                success=True,
                records_written=len(enriched_records),
                compaction_recommended=compaction_recommended,
                small_files_count=small_files_count
            )

        except Exception as e:
            return WriteResponse(
                success=False,
                records_written=0,
                error=ErrorDetail(code="WRITE_ERROR", message=str(e))
            )

    def query(self, request: QueryRequest) -> QueryResponse:
        """Query Iceberg table using DuckDB's iceberg_scan"""
        try:
            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )

            # Get table metadata location from catalog
            try:
                table = self.catalog.load_table(table_identifier)
                # Use the metadata file location for DuckDB iceberg_scan
                # DuckDB can read from the metadata JSON file directly
                metadata_path = table.metadata_location
            except Exception as e:
                # Table doesn't exist
                return QueryResponse(
                    success=True,
                    data=[],
                    metadata=QueryMetadata(row_count=0, execution_time_ms=0)
                )

            # Build SELECT clause based on projection and aggregations
            select_clause = self._build_select_clause(request.projection, request.aggregations)

            # Build DuckDB query using iceberg_scan with metadata file
            # Include deleted records if requested, otherwise filter them out
            deleted_filter = "" if request.include_deleted else "AND _deleted IS NOT TRUE"
            sql = f"""
                SELECT {select_clause} FROM iceberg_scan('{metadata_path}')
                WHERE _tenant_id = '{request.tenant_id}'
                {deleted_filter}
            """

            # Add custom filters
            params = []
            if request.filter:
                builder = TypeSafeQueryBuilder()
                filter_sql, params = builder._parse_filter_expression(request.filter)
                if filter_sql:
                    sql += f" AND ({filter_sql})"

            # Add GROUP BY clause
            if request.group_by:
                group_fields = ', '.join(request.group_by)
                sql += f" GROUP BY {group_fields}"

            # Add HAVING clause (post-aggregation filter)
            if request.having:
                builder = TypeSafeQueryBuilder()
                having_sql, having_params = builder._parse_filter_expression(request.having)
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

            # Execute query
            if params:
                result = self.conn.execute(sql, params).fetchdf()
            else:
                result = self.conn.execute(sql).fetchdf()

            # Convert to dict
            data = result.to_dict(orient='records') if not result.empty else []

            return QueryResponse(
                success=True,
                data=data,
                metadata=QueryMetadata(
                    row_count=len(data),
                    execution_time_ms=0
                )
            )

        except Exception as e:
            return QueryResponse(
                success=False,
                error=ErrorDetail(code="QUERY_ERROR", message=str(e))
            )

    def update(self, request: UpdateRequest) -> UpdateResponse:
        """Update records - read from DuckDB, modify, write back with PyIceberg"""
        try:
            # First query the records to update
            query_req = QueryRequest(
                tenant_id=request.tenant_id,
                namespace=request.namespace,
                table=request.table,
                filter=request.filter
            )
            query_result = self.query(query_req)

            if not query_result.success or not query_result.data:
                return UpdateResponse(
                    success=True,
                    records_updated=0
                )

            # Update records
            timestamp = datetime.utcnow()
            updated_records = []
            for record in query_result.data:
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

            # Load table and get schema
            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )
            table = self.catalog.load_table(table_identifier)

            # Get Iceberg table schema as PyArrow schema
            iceberg_schema = table.schema().as_arrow()

            # Reorder columns to match Iceberg schema field order
            field_names = [field.name for field in iceberg_schema]
            arrow_table = arrow_table.select(field_names)

            # Cast the arrow table to match Iceberg schema exactly
            arrow_table = arrow_table.cast(iceberg_schema)

            # Append to Iceberg table
            table.append(arrow_table)

            return UpdateResponse(
                success=True,
                records_updated=len(updated_records)
            )

        except Exception as e:
            return UpdateResponse(
                success=False,
                records_updated=0,
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
                filter=request.filter
            )
            update_result = self.update(update_req)

            return DeleteResponse(
                success=update_result.success,
                records_deleted=update_result.records_updated,
                error=update_result.error
            )

        except Exception as e:
            return DeleteResponse(
                success=False,
                records_deleted=0,
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
                return HardDeleteResponse(
                    success=False,
                    records_deleted=0,
                    error=ErrorDetail(
                        code="CONFIRMATION_REQUIRED",
                        message="Hard delete requires confirm=true"
                    )
                )

            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )

            # Load table
            table = self.catalog.load_table(table_identifier)

            # First, query to count how many records will be deleted
            metadata_path = table.metadata_location

            # Build filter SQL
            builder = TypeSafeQueryBuilder()
            filter_sql, params = builder._parse_filter_expression(request.filter)

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
                return HardDeleteResponse(
                    success=True,
                    records_deleted=0,
                    files_rewritten=0
                )

            # Use PyIceberg's delete to physically remove rows
            # Build Iceberg filter expression from our filter
            from pyiceberg.expressions import EqualTo, GreaterThan, LessThan, And, Or

            # Convert our filter to Iceberg expression
            iceberg_filter = self._build_iceberg_filter(request.filter)

            # Also add tenant filter
            tenant_filter = EqualTo("_tenant_id", request.tenant_id)
            combined_filter = And(tenant_filter, iceberg_filter) if iceberg_filter else tenant_filter

            # Execute physical deletion
            files_before = len(list(table.scan().plan_files()))
            table.delete(combined_filter)

            # Reload table to get updated file count
            table = self.catalog.load_table(table_identifier)
            files_after = len(list(table.scan().plan_files()))

            print(f"✓ Hard deleted {records_to_delete} records from {request.table}")
            print(f"  Files rewritten: {files_before - files_after}")

            return HardDeleteResponse(
                success=True,
                records_deleted=records_to_delete,
                files_rewritten=files_before - files_after
            )

        except Exception as e:
            print(f"✗ Hard delete failed: {e}")
            import traceback
            traceback.print_exc()
            return HardDeleteResponse(
                success=False,
                records_deleted=0,
                error=ErrorDetail(code="HARD_DELETE_ERROR", message=str(e))
            )

    def _build_iceberg_filter(self, filter_expr: Dict[str, Any]):
        """Convert our filter expression to PyIceberg filter"""
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
            table = self.catalog.load_table(table_identifier)

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
                return CompactResponse(
                    success=True,
                    compacted=False,
                    reason="No files to compact"
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
                return CompactResponse(
                    success=True,
                    compacted=False,
                    reason=f"Only {len(small_files)} small files (threshold: {min_files_to_compact})"
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
                return CompactResponse(
                    success=True,
                    compacted=False,
                    reason="No data to compact"
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
            table = self.catalog.load_table(table_identifier)

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
            snapshots_expired = 0
            if request.expire_snapshots:
                try:
                    retention_time = datetime.utcnow() - timedelta(
                        hours=request.snapshot_retention_hours
                    )
                    table.expire_snapshots(older_than=retention_time)

                    # Count expired snapshots (rough estimate)
                    all_snapshots = list(table.history())
                    snapshots_expired = len([
                        s for s in all_snapshots
                        if datetime.fromtimestamp(s.timestamp_ms / 1000) < retention_time
                    ])
                except Exception as e:
                    print(f"Warning: Could not expire snapshots: {e}")

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

            return CompactResponse(
                success=True,
                compacted=True,
                stats=stats
            )

        except Exception as e:
            compaction_time_ms = (time.time() - start_time) * 1000
            print(f"✗ Compaction failed after {compaction_time_ms:.0f}ms: {e}")
            return CompactResponse(
                success=False,
                compacted=False,
                error=ErrorDetail(code="COMPACT_ERROR", message=str(e))
            )

    def list_tables(self, request: ListTablesRequest) -> ListTablesResponse:
        """List tables in namespace using PyIceberg catalog"""
        try:
            namespace = self._get_namespace(request.tenant_id, request.namespace)

            # List tables in namespace
            tables = self.catalog.list_tables(namespace)

            # Extract table names
            table_names = [table[1] for table in tables]  # tables are (namespace, name) tuples

            return ListTablesResponse(
                success=True,
                tables=table_names
            )

        except Exception as e:
            return ListTablesResponse(
                success=False,
                tables=[],
                error=str(e)
            )

    def describe_table(self, request: DescribeTableRequest) -> DescribeTableResponse:
        """Describe Iceberg table using PyIceberg"""
        try:
            table_identifier = self._get_table_identifier(
                request.tenant_id, request.namespace, request.table
            )

            # Load table
            table = self.catalog.load_table(table_identifier)

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

            return DescribeTableResponse(
                success=True,
                table=table_desc
            )

        except Exception as e:
            return DescribeTableResponse(
                success=False,
                table=None,
                error=str(e)
            )

    def _map_to_iceberg_type(self, field_type: str):
        """Map field types to Iceberg types"""
        type_mapping = {
            'string': StringType,
            'integer': IntegerType,
            'long': LongType,
            'float': FloatType,
            'double': DoubleType,
            'boolean': BooleanType,
            'date': DateType,
            'timestamp': TimestampType,
        }
        return type_mapping.get(field_type.lower(), StringType)


# Global instance
_iceberg_ops = None

def get_iceberg_ops() -> FullIcebergOperations:
    """Get or create Iceberg operations instance"""
    global _iceberg_ops
    if _iceberg_ops is None:
        _iceberg_ops = FullIcebergOperations()
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