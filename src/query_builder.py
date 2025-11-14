"""
Type-safe Query Builder using Pydantic models for validation.

This builder translates type-safe query models into parameterized SQL,
preventing SQL injection while maintaining clean, readable code.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
from decimal import Decimal

from .models import (
    QueryRequest,
    AggregateRequest,
    Filter,
    ProjectionField,
    AggregateField,
    JoinClause,
    JoinCondition,
    SortField,
    JoinType,
    SortOrder,
)


class TypeSafeQueryBuilder:
    """
    Builds parameterized SQL from type-safe query models.

    Features:
    - Full SQL injection prevention through parameterization
    - Clean, readable query syntax
    - Comprehensive operator support
    - Optimized SQL generation
    """

    def __init__(self, dialect: str = "duckdb"):
        """
        Initialize query builder.

        Args:
            dialect: SQL dialect to use (duckdb, postgres, sqlite)
        """
        self.dialect = dialect
        self.param_style = self._get_param_style(dialect)

    def _get_param_style(self, dialect: str) -> str:
        """Get parameter style for dialect"""
        styles = {
            "duckdb": "?",
            "postgres": "%s",
            "sqlite": "?",
            "mysql": "%s",
        }
        return styles.get(dialect, "?")

    def build_query(self, request: QueryRequest) -> Tuple[str, List[Any]]:
        """
        Build SELECT query from QueryRequest.

        Args:
            request: Validated QueryRequest model

        Returns:
            Tuple of (sql_query, parameters)
        """
        sql_parts = []
        params = []

        # SELECT clause
        select_sql = self._build_select(request.projection, request.distinct)
        sql_parts.append(select_sql)

        # FROM clause
        from_sql = self._build_from(request.table, request.alias)
        sql_parts.append(from_sql)

        # JOIN clauses
        if request.join:
            for join_clause in request.join:
                join_sql, join_params = self._build_join(join_clause)
                sql_parts.append(join_sql)
                params.extend(join_params)

        # WHERE clause
        if request.filters:
            where_sql, where_params = self._build_filters(request.filters, "WHERE")
            if where_sql:
                sql_parts.append(where_sql)
                params.extend(where_params)

        # GROUP BY clause
        if request.group_by:
            group_sql = f"GROUP BY {', '.join(request.group_by)}"
            sql_parts.append(group_sql)

        # HAVING clause
        if request.having:
            having_sql, having_params = self._build_filters(request.having, "HAVING")
            if having_sql:
                sql_parts.append(having_sql)
                params.extend(having_params)

        # ORDER BY clause
        if request.sort:
            order_sql = self._build_order_by(request.sort)
            sql_parts.append(order_sql)

        # LIMIT/OFFSET
        if request.limit:
            sql_parts.append(f"LIMIT {request.limit}")
        if request.offset:
            sql_parts.append(f"OFFSET {request.offset}")

        # Time travel (DuckDB/Iceberg specific)
        if request.as_of and self.dialect == "duckdb":
            # Append time travel syntax
            sql_parts.append(f"AS OF TIMESTAMP '{request.as_of.isoformat()}'")

        return " ".join(sql_parts), params

    def build_aggregate(self, request: AggregateRequest) -> Tuple[str, List[Any]]:
        """
        Build aggregation query from AggregateRequest.

        Args:
            request: Validated AggregateRequest model

        Returns:
            Tuple of (sql_query, parameters)
        """
        sql_parts = []
        params = []

        # Build aggregation fields
        agg_fields = []
        for agg in request.aggregations:
            agg_sql = self._build_aggregate_field(agg)
            agg_fields.append(f"{agg_sql} AS {agg.alias}")

        # Add group by fields to SELECT
        select_fields = request.group_by + agg_fields
        sql_parts.append(f"SELECT {', '.join(select_fields)}")

        # FROM clause
        sql_parts.append(f"FROM {request.table}")

        # WHERE clause (pre-aggregation filter)
        if request.filter:
            where_sql, where_params = self._build_filter(request.filter, "WHERE")
            if where_sql:
                sql_parts.append(where_sql)
                params.extend(where_params)

        # GROUP BY clause
        sql_parts.append(f"GROUP BY {', '.join(request.group_by)}")

        # HAVING clause (post-aggregation filter)
        if request.having:
            having_sql, having_params = self._build_filter(request.having, "HAVING")
            if having_sql:
                sql_parts.append(having_sql)
                params.extend(having_params)

        # ORDER BY clause
        if request.sort:
            order_sql = self._build_order_by(request.sort)
            sql_parts.append(order_sql)

        # LIMIT/OFFSET
        if request.limit:
            sql_parts.append(f"LIMIT {request.limit}")
        if request.offset:
            sql_parts.append(f"OFFSET {request.offset}")

        return " ".join(sql_parts), params

    def _build_select(self, projection: Optional[List[Union[str, ProjectionField]]], distinct: bool) -> str:
        """Build SELECT clause"""
        if not projection:
            projection = ["*"]

        select_parts = []
        for field in projection:
            if isinstance(field, str):
                select_parts.append(field)
            elif isinstance(field, ProjectionField):
                field_sql = self._build_projection_field(field)
                select_parts.append(field_sql)

        distinct_str = "DISTINCT " if distinct else ""
        return f"SELECT {distinct_str}{', '.join(select_parts)}"

    def _build_projection_field(self, field: ProjectionField) -> str:
        """Build projection field with transformations"""
        expr = field.field

        # Apply transformations
        if field.upper:
            expr = f"UPPER({expr})"
        elif field.lower:
            expr = f"LOWER({expr})"

        if field.trim:
            expr = f"TRIM({expr})"

        if field.substring:
            start, length = field.substring
            expr = f"SUBSTRING({expr}, {start}, {length})"

        # Date transformations
        if field.date_trunc:
            expr = f"DATE_TRUNC('{field.date_trunc}', {expr})"
        elif field.extract:
            expr = f"EXTRACT({field.extract} FROM {expr})"
        elif field.date_format:
            expr = f"STRFTIME({expr}, '{field.date_format}')"

        # Cast if specified
        if field.cast:
            expr = f"CAST({expr} AS {field.cast})"

        # Add alias
        if field.alias:
            expr = f"{expr} AS {field.alias}"

        return expr

    def _build_from(self, table: str, alias: Optional[str]) -> str:
        """Build FROM clause"""
        if alias:
            return f"FROM {table} AS {alias}"
        return f"FROM {table}"

    def _build_join(self, join: JoinClause) -> Tuple[str, List[Any]]:
        """Build JOIN clause"""
        params = []

        # Join type
        join_type = join.type.value.upper()

        # Table with optional alias
        table_ref = join.table
        if join.alias:
            table_ref = f"{join.table} AS {join.alias}"

        # Build ON conditions
        on_conditions = []
        for condition in join.on:
            op = condition.operator or "eq"
            if op == "eq":
                on_conditions.append(f"{condition.left_field} = {condition.right_field}")
            else:
                # Support other operators if needed
                on_conditions.append(f"{condition.left_field} {op} {condition.right_field}")

        on_clause = " AND ".join(on_conditions)
        sql = f"{join_type} JOIN {table_ref} ON {on_clause}"

        return sql, params

    def _build_filters(
        self,
        filters: List[Filter],
        clause_type: str = "WHERE"
    ) -> Tuple[str, List[Any]]:
        """Build WHERE or HAVING clause from filters array (all ANDed)"""
        if not filters:
            return "", []

        conditions = []
        params = []

        for filter_item in filters:
            condition_sql, condition_params = self._build_single_filter(filter_item)
            if condition_sql:
                conditions.append(condition_sql)
                params.extend(condition_params)

        if conditions:
            sql = " AND ".join(conditions)
            if clause_type:
                return f"{clause_type} {sql}", params
            else:
                return sql, params
        return "", []

    def _build_single_filter(self, filter_item: Filter) -> Tuple[str, List[Any]]:
        """Build SQL for a single filter condition"""
        field = filter_item.field
        operator = filter_item.operator
        value = filter_item.value

        # Map operators to SQL
        operator_map = {
            'eq': '=',
            'ne': '!=',
            'gt': '>',
            'gte': '>=',
            'lt': '<',
            'lte': '<=',
            'in': 'IN',
            'like': 'LIKE'
        }

        sql_operator = operator_map.get(operator)
        if not sql_operator:
            raise ValueError(f"Unsupported operator: {operator}")

        # Handle IN operator
        if operator == 'in':
            if not isinstance(value, list):
                raise ValueError(f"IN operator requires a list value, got {type(value)}")
            placeholders = ', '.join([self.param_style] * len(value))
            return f"{field} IN ({placeholders})", value

        # Handle LIKE operator
        elif operator == 'like':
            return f"{field} LIKE {self.param_style}", [value]

        # Handle standard comparison operators
        else:
            return f"{field} {sql_operator} {self.param_style}", [value]

    # DEPRECATED - Keep for backwards compatibility but not used
    def _parse_filter_expression(self, expr: Union[Dict, Any]) -> Tuple[str, List[Any]]:
        """DEPRECATED: Old filter parsing method - kept for reference"""
        conditions = []
        params = []

        # Handle field filters (dict)
        if isinstance(expr, dict):
            for field, value in expr.items():
                # Skip logical operators (handled above)
                if field in ["and", "or", "not"]:
                    continue

                # Parse field condition
                field_sql, field_params = self._parse_field_condition(field, value)
                if field_sql:
                    conditions.append(field_sql)
                    params.extend(field_params)

        return " AND ".join(conditions), params

    def _parse_field_condition(self, field: str, value: Any) -> Tuple[str, List[Any]]:
        """Parse a single field condition"""
        params = []

        # Direct value (implicit equals)
        if not isinstance(value, (dict, FilterOperator)):
            params.append(value)
            return f"{field} = {self.param_style}", params

        # FilterOperator or dict with operators
        if isinstance(value, FilterOperator):
            op_dict = value.model_dump(exclude_none=True)
        else:
            op_dict = value

        # Process operators
        for op, op_value in op_dict.items():
            if op == "eq":
                params.append(op_value)
                return f"{field} = {self.param_style}", params

            elif op == "ne":
                params.append(op_value)
                return f"{field} != {self.param_style}", params

            elif op == "gt":
                params.append(op_value)
                return f"{field} > {self.param_style}", params

            elif op == "gte":
                params.append(op_value)
                return f"{field} >= {self.param_style}", params

            elif op == "lt":
                params.append(op_value)
                return f"{field} < {self.param_style}", params

            elif op == "lte":
                params.append(op_value)
                return f"{field} <= {self.param_style}", params

            elif op == "between":
                params.extend(op_value)
                return f"{field} BETWEEN {self.param_style} AND {self.param_style}", params

            elif op == "not_between":
                params.extend(op_value)
                return f"{field} NOT BETWEEN {self.param_style} AND {self.param_style}", params

            elif op in ["in", "in_"]:
                placeholders = ", ".join([self.param_style] * len(op_value))
                params.extend(op_value)
                return f"{field} IN ({placeholders})", params

            elif op == "not_in":
                placeholders = ", ".join([self.param_style] * len(op_value))
                params.extend(op_value)
                return f"{field} NOT IN ({placeholders})", params

            elif op == "like":
                params.append(op_value)
                return f"{field} LIKE {self.param_style}", params

            elif op == "not_like":
                params.append(op_value)
                return f"{field} NOT LIKE {self.param_style}", params

            elif op == "ilike":
                params.append(op_value)
                if self.dialect == "postgres":
                    return f"{field} ILIKE {self.param_style}", params
                else:
                    return f"LOWER({field}) LIKE LOWER({self.param_style})", params

            elif op == "regex":
                params.append(op_value)
                if self.dialect == "postgres":
                    return f"{field} ~ {self.param_style}", params
                else:
                    return f"REGEXP_MATCHES({field}, {self.param_style})", params

            elif op == "starts_with":
                params.append(f"{op_value}%")
                return f"{field} LIKE {self.param_style}", params

            elif op == "ends_with":
                params.append(f"%{op_value}")
                return f"{field} LIKE {self.param_style}", params

            elif op == "contains":
                params.append(f"%{op_value}%")
                return f"{field} LIKE {self.param_style}", params

            elif op == "is_null":
                if op_value:
                    return f"{field} IS NULL", params
                else:
                    return f"{field} IS NOT NULL", params

            elif op == "is_not_null":
                if op_value:
                    return f"{field} IS NOT NULL", params
                else:
                    return f"{field} IS NULL", params

            elif op == "array_contains":
                params.append(op_value)
                if self.dialect == "duckdb":
                    return f"list_contains({field}, {self.param_style})", params
                elif self.dialect == "postgres":
                    return f"{self.param_style} = ANY({field})", params
                else:
                    # Fallback for other dialects
                    return f"{self.param_style} IN {field}", params

            elif op == "has_key":
                if self.dialect in ["postgres", "duckdb"]:
                    params.append(op_value)
                    return f"{field}->>{self.param_style} IS NOT NULL", params
                else:
                    # Fallback
                    params.append(f"$.{op_value}")
                    return f"json_extract({field}, {self.param_style}) IS NOT NULL", params

        return "", []

    def _build_aggregate_field(self, agg: AggregateField) -> str:
        """Build aggregation expression"""
        distinct_str = "DISTINCT " if agg.distinct else ""

        if agg.op == AggregateOp.COUNT:
            if agg.field:
                return f"COUNT({distinct_str}{agg.field})"
            else:
                return "COUNT(*)"

        elif agg.op == AggregateOp.COUNT_DISTINCT:
            if not agg.field:
                raise ValueError("COUNT_DISTINCT requires a field")
            return f"COUNT(DISTINCT {agg.field})"

        elif agg.op == AggregateOp.SUM:
            return f"SUM({distinct_str}{agg.field})"

        elif agg.op == AggregateOp.AVG:
            return f"AVG({distinct_str}{agg.field})"

        elif agg.op == AggregateOp.MIN:
            return f"MIN({agg.field})"

        elif agg.op == AggregateOp.MAX:
            return f"MAX({agg.field})"

        elif agg.op == AggregateOp.MEDIAN:
            if self.dialect == "duckdb":
                return f"MEDIAN({agg.field})"
            else:
                # Fallback for dialects without MEDIAN
                return f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {agg.field})"

        elif agg.op == AggregateOp.PERCENTILE:
            if self.dialect == "duckdb":
                return f"PERCENTILE_CONT({agg.field}, {agg.percentile_value})"
            else:
                return f"PERCENTILE_CONT({agg.percentile_value}) WITHIN GROUP (ORDER BY {agg.field})"

        elif agg.op == AggregateOp.STD_DEV:
            return f"STDDEV({agg.field})"

        elif agg.op == AggregateOp.VARIANCE:
            return f"VARIANCE({agg.field})"

        elif agg.op == AggregateOp.FIRST:
            if self.dialect == "duckdb":
                return f"FIRST({agg.field})"
            else:
                return f"FIRST_VALUE({agg.field})"

        elif agg.op == AggregateOp.LAST:
            if self.dialect == "duckdb":
                return f"LAST({agg.field})"
            else:
                return f"LAST_VALUE({agg.field})"

        else:
            raise ValueError(f"Unsupported aggregation operation: {agg.op}")

    def _build_order_by(self, sort_fields: List[SortField]) -> str:
        """Build ORDER BY clause"""
        order_parts = []

        for sort_field in sort_fields:
            order = sort_field.order.value.upper()
            order_expr = f"{sort_field.field} {order}"

            # Handle nulls first/last
            if sort_field.nulls_first is not None:
                if sort_field.nulls_first:
                    order_expr += " NULLS FIRST"
                else:
                    order_expr += " NULLS LAST"

            order_parts.append(order_expr)

        return f"ORDER BY {', '.join(order_parts)}"


# ============================================================================
# Usage Examples
# ============================================================================

def example_usage():
    """Demonstrate usage of type-safe query builder"""

    builder = TypeSafeQueryBuilder(dialect="duckdb")

    # Example 1: Simple query with filter
    query1 = QueryRequest(
        table="users",
        projection=["id", "name", "email"],
        filter={
            "status": {"eq": "active"},
            "age": {"gte": 18}
        },
        sort=[SortField(field="created_at", order=SortOrder.DESC)],
        limit=10
    )

    sql, params = builder.build_query(query1)
    print("Example 1 - Simple Query:")
    print(f"SQL: {sql}")
    print(f"Params: {params}")
    print()

    # Example 2: Complex filter with logical operators
    query2 = QueryRequest(
        table="products",
        filter={
            "and": [
                {"category": {"in": ["electronics", "books"]}},
                {"price": {"between": (10, 100)}},
                {
                    "or": [
                        {"status": {"eq": "active"}},
                        {"featured": {"eq": True}}
                    ]
                }
            ]
        },
        limit=50
    )

    sql, params = builder.build_query(query2)
    print("Example 2 - Complex Filter:")
    print(f"SQL: {sql}")
    print(f"Params: {params}")
    print()

    # Example 3: Aggregation query
    agg_query = AggregateRequest(
        table="orders",
        filter={"status": {"eq": "completed"}},
        group_by=["customer_id"],
        aggregations=[
            AggregateField(op=AggregateOp.COUNT, field=None, alias="total_orders"),
            AggregateField(op=AggregateOp.SUM, field="amount", alias="revenue"),
            AggregateField(op=AggregateOp.AVG, field="amount", alias="avg_order")
        ],
        having={"revenue": {"gt": 1000}},
        sort=[SortField(field="revenue", order=SortOrder.DESC)],
        limit=100
    )

    sql, params = builder.build_aggregate(agg_query)
    print("Example 3 - Aggregation:")
    print(f"SQL: {sql}")
    print(f"Params: {params}")
    print()

    # Example 4: Query with joins
    query4 = QueryRequest(
        table="orders",
        alias="o",
        join=[
            JoinClause(
                type=JoinType.INNER,
                table="customers",
                alias="c",
                on=[JoinCondition(left_field="o.customer_id", right_field="c.id")]
            )
        ],
        projection=[
            "o.id",
            "o.total",
            ProjectionField(field="c.name", alias="customer_name"),
            ProjectionField(
                field="o.created_at",
                date_format="%Y-%m-%d",
                alias="order_date"
            )
        ],
        filter={"o.status": {"eq": "shipped"}},
        sort=[SortField(field="o.created_at", order=SortOrder.DESC)]
    )

    sql, params = builder.build_query(query4)
    print("Example 4 - Query with Joins:")
    print(f"SQL: {sql}")
    print(f"Params: {params}")


if __name__ == "__main__":
    example_usage()