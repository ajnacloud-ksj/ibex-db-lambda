"""
AWS Lambda Handler for S3 ACID Database
Handles API Gateway events and routes to appropriate database operations
"""

import json
import os
import traceback
from typing import Dict, Any

# Import our type-safe models and operations
from src.models import (
    OperationType,
    QueryRequest, WriteRequest, UpdateRequest, DeleteRequest, HardDeleteRequest,
    CompactRequest,
    CreateTableRequest, ListTablesRequest, DescribeTableRequest
)
# Use full Iceberg implementation with PyIceberg for writes and DuckDB for reads
from src.operations_full_iceberg import DatabaseOperations


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function

    Args:
        event: API Gateway event containing the request
        context: Lambda context (runtime information)

    Returns:
        API Gateway response with status code and body
    """

    # Handle health check
    if event.get('httpMethod') == 'GET' and event.get('path') == '/health':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'healthy',
                'service': 'S3 ACID Database',
                'version': '1.0.0'
            })
        }

    # Handle OPTIONS for CORS
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': ''
        }

    try:
        # Parse request body
        if not event.get('body'):
            return error_response(400, 'Request body is required')

        # Handle both string and dict body (for testing)
        if isinstance(event['body'], str):
            request_data = json.loads(event['body'])
        else:
            request_data = event['body']

        # Get operation type
        operation = request_data.get('operation', '').upper()

        # Route to appropriate handler
        if operation == OperationType.QUERY:
            request = QueryRequest(**request_data)
            result = DatabaseOperations.query(request)

        elif operation == OperationType.WRITE:
            request = WriteRequest(**request_data)
            result = DatabaseOperations.write(request)

        elif operation == OperationType.UPDATE:
            request = UpdateRequest(**request_data)
            result = DatabaseOperations.update(request)

        elif operation == OperationType.DELETE:
            request = DeleteRequest(**request_data)
            result = DatabaseOperations.delete(request)

        elif operation == OperationType.HARD_DELETE:
            request = HardDeleteRequest(**request_data)
            result = DatabaseOperations.hard_delete(request)

        elif operation == OperationType.COMPACT:
            request = CompactRequest(**request_data)
            result = DatabaseOperations.compact(request)

        elif operation == OperationType.CREATE_TABLE:
            request = CreateTableRequest(**request_data)
            result = DatabaseOperations.create_table(request)

        elif operation == OperationType.LIST_TABLES:
            request = ListTablesRequest(**request_data)
            result = DatabaseOperations.list_tables(request)

        elif operation == OperationType.DESCRIBE_TABLE:
            request = DescribeTableRequest(**request_data)
            result = DatabaseOperations.describe_table(request)

        else:
            return error_response(400, f'Unknown operation: {operation}')

        # Convert result to response
        response_body = result.model_dump() if hasattr(result, 'model_dump') else result.dict()

        return {
            'statusCode': 200 if response_body.get('success', False) else 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_body, default=str)
        }

    except ValueError as e:
        # Validation errors from Pydantic
        return error_response(400, f'Validation error: {str(e)}')

    except Exception as e:
        # Log the full error for debugging
        print(f"Error processing request: {e}")
        traceback.print_exc()

        return error_response(500, f'Internal server error: {str(e)}')


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Create an error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'success': False,
            'error': message
        })
    }


# For local testing
if __name__ == '__main__':
    # Test event
    test_event = {
        'httpMethod': 'POST',
        'path': '/database',
        'body': json.dumps({
            'operation': 'QUERY',
            'tenant_id': 'test',
            'namespace': 'default',
            'table': 'users',
            'limit': 10
        })
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))