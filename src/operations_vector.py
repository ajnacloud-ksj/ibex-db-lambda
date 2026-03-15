"""
Vector operations using DuckDB VSS (Vector Similarity Search) extension.

Provides:
- VECTOR_SEARCH: Cosine/L2/IP similarity search with optional pre-filtering
- VECTOR_WRITE: Store embeddings in DuckDB tables with FLOAT[N] arrays
- VECTOR_INDEX: Create HNSW indexes for O(log n) approximate nearest neighbor search
"""

import time
from typing import List, Optional

from .models import (
    VectorSearchRequest, VectorSearchResponse, VectorSearchResponseData,
    VectorWriteRequest, VectorWriteResponse, VectorWriteResponseData,
    VectorIndexRequest, VectorIndexResponse, VectorIndexResponseData,
    ErrorDetail, ResponseMetadata, Filter
)


class VectorOperations:
    """Vector similarity search operations using DuckDB VSS extension"""

    def __init__(self, get_ops_fn):
        """
        Initialize with a function that returns the FullIcebergOperations instance.
        This gives access to the shared DuckDB connection.

        Args:
            get_ops_fn: Callable that returns FullIcebergOperations instance
        """
        self._get_ops = get_ops_fn
        self._vss_loaded = False

    def _ensure_vss(self):
        """Load the VSS extension if not already loaded"""
        if self._vss_loaded:
            return
        conn = self._get_ops().conn
        try:
            conn.execute("LOAD vss;")
            print("  VSS extension loaded")
            self._vss_loaded = True
        except Exception as e:
            # Try install + load if not pre-installed
            try:
                conn.execute("INSTALL vss; LOAD vss;")
                print("  VSS extension installed and loaded")
                self._vss_loaded = True
            except Exception as install_err:
                raise RuntimeError(
                    f"Failed to load VSS extension: {install_err}"
                ) from install_err

    def _get_vector_table_name(self, tenant_id: str, namespace: str, table: str) -> str:
        """Get the DuckDB table name for vector storage"""
        ns = f"{tenant_id}_{namespace}".replace("-", "_")
        return f"vec_{ns}_{table}"

    def _build_filter_sql(self, filters: Optional[List[Filter]]) -> tuple:
        """Build WHERE clause from filter list. Returns (sql_fragment, params)."""
        if not filters:
            return "", []

        operator_map = {
            'eq': '=', 'ne': '!=', 'gt': '>', 'gte': '>=',
            'lt': '<', 'lte': '<=', 'in': 'IN', 'like': 'LIKE'
        }

        conditions = []
        params = []
        for f in filters:
            sql_op = operator_map.get(f.operator)
            if not sql_op:
                raise ValueError(f"Unsupported filter operator: {f.operator}")
            if f.operator == 'in':
                if not isinstance(f.value, list):
                    raise ValueError("IN operator requires a list value")
                placeholders = ', '.join(['?'] * len(f.value))
                conditions.append(f'"{f.field}" IN ({placeholders})')
                params.extend(f.value)
            else:
                conditions.append(f'"{f.field}" {sql_op} ?')
                params.append(f.value)

        return " AND ".join(conditions), params

    # ========================================================================
    # VECTOR_SEARCH
    # ========================================================================

    def vector_search(self, request: VectorSearchRequest) -> VectorSearchResponse:
        """
        Perform vector similarity search using DuckDB VSS.

        Uses array_cosine_similarity / array_distance / array_inner_product
        depending on the table's index metric (defaults to cosine).
        """
        try:
            self._ensure_vss()
            conn = self._get_ops().conn

            vec_table = self._get_vector_table_name(
                request.tenant_id, request.namespace, request.table
            )
            vec_col = request.vector_column

            # Build projection columns
            if request.projection:
                select_cols = ', '.join(f'"{c}"' for c in request.projection)
            else:
                select_cols = '*'

            # Build similarity score expression (cosine similarity)
            vec_literal = f"[{', '.join(str(v) for v in request.vector)}]::FLOAT[{len(request.vector)}]"
            score_expr = f'array_cosine_similarity("{vec_col}", {vec_literal})'

            # Build pre-filter
            filter_sql, filter_params = self._build_filter_sql(request.filter)

            # Construct query
            where_parts = []
            if filter_sql:
                where_parts.append(filter_sql)

            where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

            # Add min_score filter as HAVING-style post-filter
            having_clause = ""
            if request.min_score is not None:
                if where_clause:
                    having_clause = f"AND _score >= ?"
                    filter_params.append(request.min_score)
                else:
                    having_clause = f"WHERE _score >= ?"
                    filter_params.append(request.min_score)

            sql = f"""
                SELECT {select_cols}, {score_expr} AS _score
                FROM "{vec_table}"
                {where_clause}
                {"" if not having_clause or where_clause else ""}{having_clause if not where_clause else ""}
                ORDER BY _score DESC
                LIMIT ?
            """

            # Simpler approach: build it cleanly
            all_conditions = []
            all_params = list(filter_params)  # reset

            # Re-build cleanly
            filter_sql2, filter_params2 = self._build_filter_sql(request.filter)
            all_params = list(filter_params2)

            min_score_clause = ""
            if request.min_score is not None:
                min_score_clause = f'{score_expr} >= ?'
                all_params.append(request.min_score)

            if filter_sql2:
                all_conditions.append(filter_sql2)
            if min_score_clause:
                all_conditions.append(min_score_clause)

            where_full = f"WHERE {' AND '.join(all_conditions)}" if all_conditions else ""
            all_params.append(request.k)

            sql = f"""
                SELECT {select_cols}, {score_expr} AS _score
                FROM "{vec_table}"
                {where_full}
                ORDER BY _score DESC
                LIMIT ?
            """

            print(f"Vector search SQL: {sql.strip()}")
            result = conn.execute(sql, all_params)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            matches = [dict(zip(columns, row)) for row in rows]

            # Convert numpy/array types to plain Python for JSON serialization
            for match in matches:
                for key, val in match.items():
                    if hasattr(val, 'tolist'):
                        match[key] = val.tolist()

            return VectorSearchResponse(
                success=True,
                data=VectorSearchResponseData(
                    matches=matches,
                    total_matches=len(matches)
                ),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            print(f"Vector search error: {e}")
            import traceback
            traceback.print_exc()
            return VectorSearchResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="VECTOR_SEARCH_ERROR", message=str(e))
            )

    # ========================================================================
    # VECTOR_WRITE
    # ========================================================================

    def vector_write(self, request: VectorWriteRequest) -> VectorWriteResponse:
        """
        Write vector embeddings to a DuckDB table.

        Auto-creates the table if it doesn't exist with FLOAT[dimensions] type
        for the vector column.
        """
        try:
            self._ensure_vss()
            conn = self._get_ops().conn

            vec_table = self._get_vector_table_name(
                request.tenant_id, request.namespace, request.table
            )
            vec_col = request.vector_column
            dims = request.dimensions

            if not request.records:
                raise ValueError("No records provided for vector write")

            # Determine schema from first record
            sample = request.records[0]

            # Check if table exists
            table_exists = False
            try:
                conn.execute(f'SELECT 1 FROM "{vec_table}" LIMIT 0')
                table_exists = True
            except Exception:
                table_exists = False

            if not table_exists:
                # Auto-create table from record schema
                col_defs = []
                for col_name, col_value in sample.items():
                    if col_name == vec_col:
                        col_defs.append(f'"{col_name}" FLOAT[{dims}]')
                    elif isinstance(col_value, int):
                        col_defs.append(f'"{col_name}" BIGINT')
                    elif isinstance(col_value, float):
                        col_defs.append(f'"{col_name}" DOUBLE')
                    elif isinstance(col_value, bool):
                        col_defs.append(f'"{col_name}" BOOLEAN')
                    else:
                        col_defs.append(f'"{col_name}" VARCHAR')

                create_sql = f'CREATE TABLE "{vec_table}" ({", ".join(col_defs)})'
                print(f"Creating vector table: {create_sql}")
                conn.execute(create_sql)

            # Insert records
            col_names = list(sample.keys())
            placeholders = ', '.join(['?'] * len(col_names))
            insert_sql = f'INSERT INTO "{vec_table}" ({", ".join(f"{c}" for c in col_names)}) VALUES ({placeholders})'

            records_written = 0
            for record in request.records:
                values = []
                for col in col_names:
                    val = record.get(col)
                    if col == vec_col and isinstance(val, list):
                        # DuckDB expects list for FLOAT[] columns
                        values.append(val)
                    else:
                        values.append(val)
                conn.execute(insert_sql, values)
                records_written += 1

            print(f"Wrote {records_written} vector records to {vec_table}")

            return VectorWriteResponse(
                success=True,
                data=VectorWriteResponseData(records_written=records_written),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            print(f"Vector write error: {e}")
            import traceback
            traceback.print_exc()
            return VectorWriteResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="VECTOR_WRITE_ERROR", message=str(e))
            )

    # ========================================================================
    # VECTOR_INDEX
    # ========================================================================

    def vector_index(self, request: VectorIndexRequest) -> VectorIndexResponse:
        """
        Create an HNSW index on a vector column for O(log n) approximate nearest neighbor search.
        """
        try:
            self._ensure_vss()
            conn = self._get_ops().conn

            vec_table = self._get_vector_table_name(
                request.tenant_id, request.namespace, request.table
            )
            vec_col = request.vector_column
            metric = request.metric

            # Validate metric
            valid_metrics = {'cosine', 'l2', 'ip'}
            if metric not in valid_metrics:
                raise ValueError(f"Invalid metric '{metric}'. Must be one of: {valid_metrics}")

            # Generate index name
            index_name = f"idx_{vec_table}_{vec_col}_hnsw"

            # Create HNSW index
            create_idx_sql = (
                f'CREATE INDEX "{index_name}" ON "{vec_table}" '
                f'USING HNSW ("{vec_col}") WITH (metric = \'{metric}\')'
            )
            print(f"Creating HNSW index: {create_idx_sql}")
            conn.execute(create_idx_sql)

            print(f"HNSW index '{index_name}' created on {vec_table}.{vec_col} with metric={metric}")

            return VectorIndexResponse(
                success=True,
                data=VectorIndexResponseData(
                    index_created=True,
                    index_name=index_name
                ),
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=None
            )

        except Exception as e:
            print(f"Vector index error: {e}")
            import traceback
            traceback.print_exc()
            return VectorIndexResponse(
                success=False,
                data=None,
                metadata=ResponseMetadata(request_id="temp", execution_time_ms=0),
                error=ErrorDetail(code="VECTOR_INDEX_ERROR", message=str(e))
            )
