"""
Type-safe Query API Models using Pydantic for validation and clean API design.

Key improvements:
1. Use 'filter' instead of 'where' for modern convention
2. Explicit operator names (eq, gt, lt) instead of symbols
3. Full Pydantic validation with helpful error messages
4. Consistent structure throughout
5. IDE autocomplete support
"""

from typing import Any, Dict, List, Literal, Optional, Union, TypeVar, Generic
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum

# Type variable for generic responses
T = TypeVar('T')

# ============================================================================
# Enums for Constants
# ============================================================================

class OperationType(str, Enum):
    """Database operation types"""
    QUERY = "QUERY"
    WRITE = "WRITE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    HARD_DELETE = "HARD_DELETE"
    CREATE_TABLE = "CREATE_TABLE"
    LIST_TABLES = "LIST_TABLES"
    DESCRIBE_TABLE = "DESCRIBE_TABLE"
    AGGREGATE = "AGGREGATE"
    INSERT = "INSERT"
    UPSERT = "UPSERT"
    COMPACT = "COMPACT"

class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"

class JoinType(str, Enum):
    """SQL join types"""
    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    FULL = "full"
    CROSS = "cross"

class Consistency(str, Enum):
    """Consistency levels for distributed operations"""
    STRONG = "strong"
    EVENTUAL = "eventual"
    BOUNDED = "bounded"

class AggregateOp(str, Enum):
    """Aggregation operations"""
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    FIRST = "first"
    LAST = "last"
    STD_DEV = "std_dev"
    VARIANCE = "variance"
    MEDIAN = "median"
    PERCENTILE = "percentile"

# ============================================================================
# Filter Models - Simple Array Format (All filters ANDed)
# ============================================================================

class Filter(BaseModel):
    """Single filter condition - all filters are ANDed together"""
    
    field: str = Field(..., description="Field name to filter on")
    operator: str = Field(..., description="Filter operator: eq, ne, gt, gte, lt, lte, in, like")
    value: Any = Field(..., description="Value to compare against")
    
    @model_validator(mode='after')
    def validate_operator(self):
        """Validate operator is supported"""
        valid_operators = {'eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'like'}
        if self.operator not in valid_operators:
            raise ValueError(f"Invalid operator '{self.operator}'. Must be one of: {valid_operators}")
        return self

# ============================================================================
# Projection Models
# ============================================================================

class ProjectionField(BaseModel):
    """Detailed projection field with alias and transformations"""

    field: str = Field(..., description="Field name or expression")
    alias: Optional[str] = Field(None, description="Output alias for the field")
    cast: Optional[str] = Field(None, description="Cast to type (e.g., 'integer', 'text')")

    # Common transformations
    upper: Optional[bool] = Field(None, description="Convert to uppercase")
    lower: Optional[bool] = Field(None, description="Convert to lowercase")
    trim: Optional[bool] = Field(None, description="Trim whitespace")
    substring: Optional[tuple[int, int]] = Field(None, description="Extract substring (start, length)")

    # Date transformations
    date_format: Optional[str] = Field(None, description="Format date (e.g., 'YYYY-MM-DD')")
    date_trunc: Optional[str] = Field(None, description="Truncate date (e.g., 'day', 'month')")
    extract: Optional[str] = Field(None, description="Extract date part (e.g., 'year', 'month')")

# Projection can be string (simple) or ProjectionField (complex)
Projection = Union[str, ProjectionField]

# ============================================================================
# Aggregation Models
# ============================================================================

class AggregateField(BaseModel):
    """Aggregation field definition"""

    field: Optional[str] = Field(None, description="Field to aggregate (None for COUNT(*))")
    function: str = Field(..., description="Aggregation function: count, sum, avg, min, max")
    alias: str = Field(..., description="Output alias for aggregation")
    distinct: Optional[bool] = Field(False, description="Use DISTINCT")

    # Additional parameters for specific operations
    percentile_value: Optional[float] = Field(None, description="Percentile value (0-1) for percentile function")

    @model_validator(mode='after')
    def validate_function(self):
        """Validate aggregation function"""
        valid_functions = {'count', 'sum', 'avg', 'min', 'max', 'median', 'percentile'}
        if self.function not in valid_functions:
            raise ValueError(f"Invalid function '{self.function}'. Must be one of: {valid_functions}")
        
        if self.function == 'percentile' and self.percentile_value is None:
            raise ValueError("percentile_value required for percentile function")
        if self.percentile_value is not None and not (0 <= self.percentile_value <= 1):
            raise ValueError("percentile_value must be between 0 and 1")
        return self

# ============================================================================
# Join Models
# ============================================================================

class JoinCondition(BaseModel):
    """Join condition between tables"""

    left_field: str = Field(..., description="Field from left table")
    right_field: str = Field(..., description="Field from right table")
    operator: Optional[str] = Field("eq", description="Join operator (default: eq)")

class JoinClause(BaseModel):
    """Table join definition"""

    type: JoinType = Field(JoinType.INNER, description="Join type")
    table: str = Field(..., description="Table to join")
    alias: Optional[str] = Field(None, description="Table alias")
    on: List[JoinCondition] = Field(..., description="Join conditions")

# ============================================================================
# Sort Models
# ============================================================================

class SortField(BaseModel):
    """Sort field definition"""

    field: str = Field(..., description="Field to sort by")
    order: SortOrder = Field(SortOrder.ASC, description="Sort order")
    nulls_first: Optional[bool] = Field(None, description="NULL values first")

# ============================================================================
# Main Query Request Models
# ============================================================================

class QueryRequest(BaseModel):
    """Type-safe query request with modern conventions"""

    operation: Literal[OperationType.QUERY] = OperationType.QUERY
    tenant_id: str = Field(..., description="Multi-tenant identifier")
    namespace: str = Field("default", description="Table namespace")
    table: str = Field(..., description="Table name", min_length=1)
    alias: Optional[str] = Field(None, description="Table alias")

    # Core query components
    projection: Optional[List[Projection]] = Field(
        default_factory=lambda: ["*"],
        description="Fields to select (columns without aggregation)"
    )
    aggregations: Optional[List[AggregateField]] = Field(
        None,
        description="Aggregation functions (COUNT, SUM, AVG, etc.)"
    )
    filters: Optional[List[Filter]] = Field(None, description="Filter conditions (all ANDed together)")
    join: Optional[List[JoinClause]] = Field(None, description="Table joins")
    group_by: Optional[List[str]] = Field(None, description="Group by fields")
    having: Optional[List[Filter]] = Field(None, description="Post-aggregation filter")
    sort: Optional[List[SortField]] = Field(None, description="Sort order")
    distinct: Optional[bool] = Field(False, description="Return distinct rows")

    # Pagination
    limit: Optional[int] = Field(None, gt=0, le=100000, description="Maximum rows to return")
    offset: Optional[int] = Field(None, ge=0, description="Number of rows to skip")

    # Advanced options
    tenant_id: Optional[str] = Field(None, description="Multi-tenant identifier")
    consistency: Optional[Consistency] = Field(Consistency.STRONG, description="Read consistency")
    timeout_ms: Optional[int] = Field(30000, gt=0, description="Query timeout in milliseconds")
    explain: Optional[bool] = Field(False, description="Return query plan instead of results")
    include_deleted: Optional[bool] = Field(False, description="Include soft-deleted records in results")

    # Time travel
    as_of: Optional[datetime] = Field(None, description="Query data as of timestamp")
    between_times: Optional[tuple[datetime, datetime]] = Field(
        None,
        description="Query changes between timestamps"
    )

    @model_validator(mode='after')
    def validate_having_requires_group_by(self):
        """Ensure 'having' is only used with 'group_by'"""
        if self.having and not self.group_by:
            raise ValueError("'having' clause requires 'group_by'")
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "operation": "query",
                "table": "users",
                "projection": ["id", "name", "email"],
                "filter": {
                    "status": {"eq": "active"},
                    "age": {"gte": 18}
                },
                "sort": [{"field": "created_at", "order": "desc"}],
                "limit": 10
            }
        }

class AggregateRequest(BaseModel):
    """Type-safe aggregation request"""

    operation: Literal[OperationType.AGGREGATE] = OperationType.AGGREGATE
    tenant_id: str = Field(..., description="Multi-tenant identifier")
    namespace: str = Field("default", description="Table namespace")
    table: str = Field(..., description="Table name", min_length=1)

    # Aggregation pipeline
    filters: Optional[List[Filter]] = Field(None, description="Pre-aggregation filter (all ANDed)")
    group_by: List[str] = Field(..., description="Fields to group by")
    aggregations: List[AggregateField] = Field(..., description="Aggregation operations")
    having: Optional[List[Filter]] = Field(None, description="Post-aggregation filter (all ANDed)")
    sort: Optional[List[SortField]] = Field(None, description="Sort aggregated results")

    # Pagination
    limit: Optional[int] = Field(None, gt=0, le=10000, description="Maximum groups to return")
    offset: Optional[int] = Field(None, ge=0, description="Number of groups to skip")

    # Options
    tenant_id: Optional[str] = Field(None, description="Multi-tenant identifier")
    timeout_ms: Optional[int] = Field(60000, gt=0, description="Query timeout in milliseconds")

    class Config:
        json_schema_extra = {
            "example": {
                "operation": "aggregate",
                "table": "orders",
                "filter": {"status": {"eq": "completed"}},
                "group_by": ["customer_id"],
                "aggregations": [
                    {"op": "count", "field": None, "alias": "total_orders"},
                    {"op": "sum", "field": "amount", "alias": "revenue"},
                    {"op": "avg", "field": "amount", "alias": "avg_order"}
                ],
                "having": {"total_orders": {"gt": 5}},
                "sort": [{"field": "revenue", "order": "desc"}],
                "limit": 100
            }
        }

# ============================================================================
# Response Models
# ============================================================================

class QueryMetadata(BaseModel):
    """Query execution metadata"""

    row_count: int = Field(..., description="Number of rows returned")
    execution_time_ms: float = Field(..., description="Query execution time")
    scanned_bytes: Optional[int] = Field(None, description="Bytes scanned")
    scanned_rows: Optional[int] = Field(None, description="Rows scanned")
    cache_hit: bool = Field(False, description="Result from cache")
    query_id: Optional[str] = Field(None, description="Unique query identifier")
    warnings: Optional[List[str]] = Field(None, description="Query warnings")

class ErrorDetail(BaseModel):
    """Detailed error information"""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    field: Optional[str] = Field(None, description="Field that caused error")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    suggestion: Optional[str] = Field(None, description="Suggested fix")

class QueryResponse(BaseModel, Generic[T]):
    """Generic query response with type safety"""

    success: bool = Field(..., description="Operation success status")
    data: Optional[List[T]] = Field(None, description="Query results")
    error: Optional[ErrorDetail] = Field(None, description="Error details if failed")
    metadata: Optional[QueryMetadata] = Field(None, description="Query execution metadata")

    @model_validator(mode='after')
    def validate_response(self):
        """Ensure response has either data or error"""
        if self.success and self.data is None:
            raise ValueError("Successful response must include data")
        if not self.success and self.error is None:
            raise ValueError("Failed response must include error")
        return self

# ============================================================================
# Schema Definition Models for Table Creation
# ============================================================================

class FieldType(str, Enum):
    """Supported field types"""
    STRING = "string"
    INTEGER = "integer"
    LONG = "long"
    FLOAT = "float"
    DOUBLE = "double"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    DECIMAL = "decimal"
    BINARY = "binary"
    ARRAY = "array"
    MAP = "map"
    STRUCT = "struct"

class FieldDefinition(BaseModel):
    """Table field definition"""
    type: Union[FieldType, str]
    required: Optional[bool] = False
    nullable: Optional[bool] = True
    items: Optional['FieldDefinition'] = None  # For arrays
    key_type: Optional[Union[FieldType, str]] = None  # For maps
    value_type: Optional['FieldDefinition'] = None  # For maps
    fields: Optional[Dict[str, 'FieldDefinition']] = None  # For structs

class SchemaDefinition(BaseModel):
    """Table schema definition"""
    fields: Dict[str, FieldDefinition]
    primary_key: Optional[List[str]] = None

# ============================================================================
# Partition Configuration
# ============================================================================

class PartitionTransform(str, Enum):
    """Partition transformations"""
    IDENTITY = "identity"
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    BUCKET = "bucket"

class PartitionFieldConfig(BaseModel):
    """Partition field configuration"""
    field: str
    transform: PartitionTransform
    name: Optional[str] = None
    num_buckets: Optional[int] = None  # For bucket transform

class PartitionConfig(BaseModel):
    """Table partitioning configuration"""
    partitions: List[PartitionFieldConfig]

# ============================================================================
# Table Properties
# ============================================================================

class TableProperties(BaseModel):
    """Table properties and configuration"""
    compression: Optional[str] = "snappy"
    file_format: Optional[str] = "parquet"
    description: Optional[str] = None

# ============================================================================
# Write/Insert Operations
# ============================================================================

class WriteMode(str, Enum):
    """Write modes"""
    APPEND = "append"
    OVERWRITE = "overwrite"
    UPSERT = "upsert"

class WriteRequest(BaseModel):
    """Write/insert request"""
    operation: Literal[OperationType.WRITE] = OperationType.WRITE
    tenant_id: str
    namespace: str = "default"
    table: str
    records: List[Dict[str, Any]]
    table_schema: Optional[SchemaDefinition] = Field(None, alias="schema")
    mode: WriteMode = WriteMode.APPEND
    partition: Optional[PartitionConfig] = None
    properties: Optional[TableProperties] = None

class WriteResponse(BaseModel):
    """Write operation response"""
    success: bool
    records_written: int
    error: Optional[ErrorDetail] = None
    compaction_recommended: bool = Field(
        default=False,
        description="Whether compaction should be triggered"
    )
    small_files_count: Optional[int] = Field(
        None,
        description="Number of small files detected (if check performed)"
    )

# ============================================================================
# Update Operations
# ============================================================================

class UpdateRequest(BaseModel):
    """Update request"""
    operation: Literal[OperationType.UPDATE] = OperationType.UPDATE
    tenant_id: str
    namespace: str = "default"
    table: str
    updates: Dict[str, Any]
    filters: List[Filter] = Field(..., description="Filter conditions (all ANDed together)")
    table_schema: Optional[SchemaDefinition] = Field(None, alias="schema")

class UpdateResponse(BaseModel):
    """Update operation response"""
    success: bool
    records_updated: int
    error: Optional[ErrorDetail] = None

# ============================================================================
# Delete Operations
# ============================================================================

class DeleteMode(str, Enum):
    """Delete modes"""
    SOFT = "soft"
    HARD = "hard"

class DeleteRequest(BaseModel):
    """Delete request"""
    operation: Literal[OperationType.DELETE] = OperationType.DELETE
    tenant_id: str
    namespace: str = "default"
    table: str
    filters: List[Filter] = Field(..., description="Filter conditions (all ANDed together)")
    mode: DeleteMode = DeleteMode.SOFT
    table_schema: Optional[SchemaDefinition] = Field(None, alias="schema")

class DeleteResponse(BaseModel):
    """Delete operation response"""
    success: bool
    records_deleted: int
    error: Optional[ErrorDetail] = None

class HardDeleteRequest(BaseModel):
    """Hard delete request - physically removes records"""
    operation: Literal[OperationType.HARD_DELETE] = OperationType.HARD_DELETE
    tenant_id: str
    namespace: str = "default"
    table: str
    filters: List[Filter] = Field(..., description="Filter conditions (all ANDed together)")
    confirm: bool = Field(..., description="Must be True to confirm physical deletion")
    table_schema: Optional[SchemaDefinition] = Field(None, alias="schema")

class HardDeleteResponse(BaseModel):
    """Hard delete operation response"""
    success: bool
    records_deleted: int
    files_rewritten: Optional[int] = None
    error: Optional[ErrorDetail] = None

# ============================================================================
# Compact Operations
# ============================================================================

class CompactRequest(BaseModel):
    """File compaction request to merge small files"""
    operation: Literal[OperationType.COMPACT] = OperationType.COMPACT
    tenant_id: str
    namespace: str = "default"
    table: str

    # Compaction options
    force: bool = Field(
        default=False,
        description="Force compaction even if thresholds not met"
    )
    target_file_size_mb: Optional[int] = Field(
        None,
        description="Target file size in MB (uses config default if not specified)"
    )
    max_files: Optional[int] = Field(
        None,
        description="Maximum files to compact in single operation"
    )

    # Partition-specific compaction
    partition_filters: Optional[List[Filter]] = Field(
        None,
        description="Only compact files matching partition filters (all ANDed)"
    )

    # Snapshot management
    expire_snapshots: bool = Field(
        default=True,
        description="Expire old snapshots after compaction"
    )
    snapshot_retention_hours: int = Field(
        default=168,  # 7 days
        description="Hours to retain old snapshots"
    )

class CompactionStats(BaseModel):
    """Statistics about compaction operation"""
    files_before: int = Field(..., description="Number of files before compaction")
    files_after: int = Field(..., description="Number of files after compaction")
    files_compacted: int = Field(..., description="Number of files merged")
    files_removed: int = Field(..., description="Number of old files removed")
    bytes_before: int = Field(..., description="Total bytes before compaction")
    bytes_after: int = Field(..., description="Total bytes after compaction")
    bytes_saved: int = Field(..., description="Bytes saved by compression")
    snapshots_expired: int = Field(default=0, description="Old snapshots removed")
    compaction_time_ms: float = Field(..., description="Time taken for compaction")
    small_files_remaining: int = Field(..., description="Small files still remaining")

class CompactResponse(BaseModel):
    """Compaction operation response"""
    success: bool
    compacted: bool = Field(..., description="Whether compaction was performed")
    reason: Optional[str] = Field(None, description="Reason if compaction skipped")
    stats: Optional[CompactionStats] = None
    error: Optional[ErrorDetail] = None

# ============================================================================
# Create Table Operations
# ============================================================================

class CreateTableRequest(BaseModel):
    """Create table request"""
    operation: Literal[OperationType.CREATE_TABLE] = OperationType.CREATE_TABLE
    tenant_id: str
    namespace: str = "default"
    table: str
    table_schema: SchemaDefinition = Field(..., alias="schema")
    partition: Optional[PartitionConfig] = None
    properties: Optional[TableProperties] = None
    if_not_exists: bool = True

class CreateTableResponse(BaseModel):
    """Create table response"""
    success: bool
    table_created: bool
    table_existed: bool = False
    error: Optional[ErrorDetail] = None

# ============================================================================
# Describe Table Operations
# ============================================================================

class DescribeTableRequest(BaseModel):
    """Describe table request"""
    operation: Literal[OperationType.DESCRIBE_TABLE] = OperationType.DESCRIBE_TABLE
    tenant_id: str
    namespace: str = "default"
    table: str

class ListTablesRequest(BaseModel):
    """List tables request"""
    operation: Literal[OperationType.LIST_TABLES] = OperationType.LIST_TABLES
    tenant_id: str
    namespace: str = "default"

class TableDescription(BaseModel):
    """Table description"""
    table_name: str
    namespace: str
    table_schema: Optional[Dict[str, Any]] = Field(None, alias="schema")
    row_count: Optional[int] = None
    size_bytes: Optional[int] = None

class ListTablesResponse(BaseModel):
    """List tables response"""
    success: bool = True
    tables: List[str] = Field(default_factory=list)
    error: Optional[str] = None

class DescribeTableResponse(BaseModel):
    """Describe table response"""
    success: bool = True
    table: Optional[TableDescription] = None
    error: Optional[str] = None

# Update forward references for new models
FieldDefinition.model_rebuild()
SchemaDefinition.model_rebuild()