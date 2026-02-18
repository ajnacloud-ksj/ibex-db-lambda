"""
AWS Lambda Handler for S3 ACID Database
Handles API Gateway events and routes to appropriate database operations
"""

import json
import os
import signal
import traceback
import time
from typing import Dict, Any
from datetime import datetime

# Use faster JSON library if available (3x faster)
try:
    import orjson
    def dumps_json(obj, default=str):
        """Fast JSON serialization with orjson"""
        return orjson.dumps(obj, default=default).decode('utf-8')
    HAS_ORJSON = True
except ImportError:
    def dumps_json(obj, default=str):
        """Fallback to standard json"""
        return json.dumps(obj, default=default)
    HAS_ORJSON = False

# Import our type-safe models and operations
from src.models import (
    OperationType,
    QueryRequest, WriteRequest, UpdateRequest, DeleteRequest, HardDeleteRequest, UpsertRequest,
    CompactRequest,
    CreateTableRequest, ListTablesRequest, DescribeTableRequest,
    DropTableRequest, DropNamespaceRequest, ExportCsvRequest
)
# Use full Iceberg implementation with PyIceberg for writes and DuckDB for reads
from src.operations_full_iceberg import DatabaseOperations
from src.operations_storage import StorageOperations


# ============================================================================
# Timeout Handler
# ============================================================================

class TimeoutError(Exception):
    """Raised when operation times out"""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout"""
    raise TimeoutError("Operation exceeded maximum execution time")


def _normalize_event(event: Dict[str, Any]) -> tuple[str, str]:
    """
    Normalize event format to extract HTTP method and path
    Supports both Lambda Function URL and API Gateway formats
    
    Lambda Function URL format:
        - requestContext.http.method
        - rawPath
    
    API Gateway format:
        - httpMethod
        - path
    
    Args:
        event: Lambda event
        
    Returns:
        tuple: (http_method, path)
    """
    # Check if Lambda Function URL format
    if 'requestContext' in event and 'http' in event.get('requestContext', {}):
        http_method = event['requestContext']['http'].get('method', 'POST')
        path = event.get('rawPath', '/')
    # Check if API Gateway format
    elif 'httpMethod' in event:
        http_method = event.get('httpMethod', 'POST')
        path = event.get('path', '/')
    else:
        # Fallback - assume POST to /database
        http_method = 'POST'
        path = '/database'
    
    return http_method, path


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler function
    Supports both API Gateway and Lambda Function URL event formats

    Args:
        event: API Gateway or Lambda Function URL event
        context: Lambda context (runtime information)

    Returns:
        API Gateway response with status code and body
    """
    start_time = time.time()
    request_id = context.aws_request_id if context else 'local-test'
    
    # Set up timeout protection (leave 5s buffer for cleanup)
    if context:
        remaining_ms = context.get_remaining_time_in_millis()
        timeout_seconds = max(5, (remaining_ms // 1000) - 5)
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)
    
    try:
        print(f"\n{'='*60}")
        print(f"Request ID: {request_id}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
        print(f"{'='*60}\n")
        
        # Normalize event format (Lambda Function URL vs API Gateway)
        http_method, path = _normalize_event(event)

        # Handle health check
        if http_method == 'GET' and path == '/health':
            execution_time_ms = (time.time() - start_time) * 1000
            print(f"✓ Health check completed in {execution_time_ms:.2f}ms")
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'X-Request-ID': request_id
                },
                'body': dumps_json({
                    'status': 'healthy',
                    'service': 'S3 ACID Database',
                    'version': '1.0.0',
                    'request_id': request_id,
                    'execution_time_ms': round(execution_time_ms, 2)
                })
            }

        # Handle OPTIONS for CORS
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, x-api-key, api_key, Authorization',
                    'X-Request-ID': request_id
                },
                'body': ''
            }

        # Parse request body
        if not event.get('body'):
            return error_response(400, 'Request body is required', request_id)

        # Handle both string and dict body (for testing)
        if isinstance(event['body'], str):
            request_data = json.loads(event['body'])
        else:
            request_data = event['body']

        # Get operation type
        operation = request_data.get('operation', '').upper()
        tenant_id = request_data.get('tenant_id', 'unknown')
        table_name = request_data.get('table', 'unknown')
        
        print(f"Operation: {operation}")
        print(f"Tenant ID: {tenant_id}")
        print(f"Table: {table_name}")

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

        elif operation == OperationType.UPSERT:
            request = UpsertRequest(**request_data)
            result = DatabaseOperations.upsert(request)

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

        elif operation == OperationType.DROP_TABLE:
            request = DropTableRequest(**request_data)
            result = DatabaseOperations.drop_table(request)

        elif operation == OperationType.DROP_NAMESPACE:
            request = DropNamespaceRequest(**request_data)
            result = DatabaseOperations.drop_namespace(request)

        elif operation == OperationType.EXPORT_CSV:
            request = ExportCsvRequest(**request_data)
            result = DatabaseOperations.export_csv(request)

        elif operation == OperationType.GET_UPLOAD_URL:
            # Import models dynamically or use from import above
            from src.models import GetUploadUrlRequest
            request = GetUploadUrlRequest(**request_data)
            result = StorageOperations.get_upload_url(request)

        elif operation == OperationType.GET_DOWNLOAD_URL:
            from src.models import GetDownloadUrlRequest
            request = GetDownloadUrlRequest(**request_data)
            result = StorageOperations.get_download_url(request)

        else:
            print(f"✗ Unknown operation: {operation}")
            return error_response(400, f'Unknown operation: {operation}', request_id)

        # Calculate execution time
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Reconstruct response with proper metadata
        # The operation returns a response, but we need to add/update the metadata
        from src.models import ResponseMetadata
        
        response_body = result.model_dump() if hasattr(result, 'model_dump') else result.dict()
        
        # Update metadata with actual request_id and execution_time
        response_body['metadata'] = {
            'request_id': request_id,
            'execution_time_ms': round(execution_time_ms, 2)
        }
        
        success = response_body.get('success', False)
        status_code = 200 if success else 400
        
        print(f"\n{'='*60}")
        print(f"{'✓' if success else '✗'} Operation: {operation}")
        print(f"Status: {status_code}")
        print(f"Execution time: {execution_time_ms:.2f}ms")
        print(f"{'='*60}\n")

        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'X-Request-ID': request_id,
                'X-Execution-Time-Ms': str(round(execution_time_ms, 2))
            },
            'body': dumps_json(response_body, default=str)
        }

    except TimeoutError as e:
        execution_time_ms = (time.time() - start_time) * 1000
        print(f"\n✗ Request timed out after {execution_time_ms:.2f}ms")
        return error_response(504, f'Request timeout: {str(e)}', request_id)

    except ValueError as e:
        # Validation errors from Pydantic
        execution_time_ms = (time.time() - start_time) * 1000
        print(f"\n✗ Validation error after {execution_time_ms:.2f}ms: {e}")
        return error_response(400, f'Validation error: {str(e)}', request_id)

    except RuntimeError as e:
        # Initialization errors
        execution_time_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        print(f"\n✗ Runtime error after {execution_time_ms:.2f}ms: {error_msg}")
        traceback.print_exc()
        
        # If it's an initialization failure, return 503 to indicate service unavailable
        if 'initialization' in error_msg.lower() or 'failed to initialize' in error_msg.lower():
            return error_response(503, f'Service initialization failed: {error_msg}', request_id)
        else:
            return error_response(500, f'Runtime error: {error_msg}', request_id)

    except Exception as e:
        # Generic errors
        execution_time_ms = (time.time() - start_time) * 1000
        error_msg = str(e)
        print(f"\n✗ Unexpected error after {execution_time_ms:.2f}ms: {error_msg}")
        traceback.print_exc()
        
        return error_response(500, f'Internal server error: {error_msg}', request_id)
    
    finally:
        # Cancel timeout alarm
        if context:
            signal.alarm(0)


def error_response(status_code: int, message: str, request_id: str = None) -> Dict[str, Any]:
    """
    Create an error response
    
    Args:
        status_code: HTTP status code
        message: Error message
        request_id: Request ID for tracking
        
    Returns:
        Lambda response dict
    """
    error_body = {
        'success': False,
        'error': message,
        'request_id': request_id or 'unknown',
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'X-Request-ID': request_id or 'unknown'
        },
        'body': dumps_json(error_body)
    }


# For local testing
if __name__ == '__main__':
    # Test event
    test_event = {
        'httpMethod': 'POST',
        'path': '/database',
        'body': dumps_json({
            'operation': 'QUERY',
            'tenant_id': 'test',
            'namespace': 'default',
            'table': 'users',
            'limit': 10
        })
    }

    result = lambda_handler(test_event, None)
    print(dumps_json(result, indent=2))