#!/bin/bash
# hello

# Local Testing Script for S3 ACID Database Lambda
# Tests all major operations and error handling

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
LAMBDA_URL="http://localhost:8080/2015-03-31/functions/function/invocations"
FASTAPI_URL="http://localhost:9000"
TEST_EVENTS_DIR="lambda_test_events"

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
print_header() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((TESTS_PASSED++))
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Test if services are running
check_services() {
    print_header "Checking Services"
    
    # Check Lambda
    if curl -s -f -o /dev/null "$LAMBDA_URL" -X POST -d '{}'; then
        print_success "Lambda API is running on port 8080"
    else
        print_error "Lambda API is not responding"
        print_info "Run: docker-compose -f docker/docker-compose.yml up"
        exit 1
    fi
    
    # Check FastAPI
    if curl -s -f "$FASTAPI_URL/health" > /dev/null 2>&1; then
        print_success "FastAPI is running on port 9000"
    else
        print_info "FastAPI is not running (optional)"
    fi
    
    # Check MinIO
    if curl -s -f "http://localhost:9005/minio/health/live" > /dev/null 2>&1; then
        print_success "MinIO is running on port 9005"
    else
        print_error "MinIO is not responding"
        exit 1
    fi
    
    # Check Iceberg REST
    if curl -s -f "http://localhost:8181/v1/config" > /dev/null 2>&1; then
        print_success "Iceberg REST catalog is running on port 8181"
    else
        print_error "Iceberg REST catalog is not responding"
        exit 1
    fi
}

# Test Lambda endpoint
test_lambda() {
    local test_name="$1"
    local test_file="$2"
    local expected_status="$3"
    
    print_info "Testing: $test_name"
    
    # Send request and capture response
    response=$(curl -s -X POST "$LAMBDA_URL" \
        -H "Content-Type: application/json" \
        -d @"$TEST_EVENTS_DIR/$test_file")
    
    # Extract status code from response
    status_code=$(echo "$response" | jq -r '.statusCode // 0')
    
    if [ "$status_code" = "$expected_status" ]; then
        print_success "$test_name - Status: $status_code"
        
        # Show execution time if available
        exec_time=$(echo "$response" | jq -r '.body' | jq -r '.execution_time_ms // "N/A"')
        if [ "$exec_time" != "N/A" ]; then
            echo "  Execution time: ${exec_time}ms"
        fi
        
        return 0
    else
        print_error "$test_name - Expected $expected_status, got $status_code"
        echo "  Response: $response" | head -n 5
        return 1
    fi
}

# Test FastAPI endpoint
test_fastapi() {
    local test_name="$1"
    local operation="$2"
    local payload="$3"
    
    print_info "Testing: $test_name (FastAPI)"
    
    response=$(curl -s -X POST "$FASTAPI_URL/database" \
        -H "Content-Type: application/json" \
        -d "$payload")
    
    success=$(echo "$response" | jq -r '.success // false')
    
    if [ "$success" = "true" ]; then
        print_success "$test_name (FastAPI)"
        return 0
    else
        print_error "$test_name (FastAPI)"
        echo "  Response: $response" | head -n 5
        return 1
    fi
}

# Main test suite
main() {
    print_header "S3 ACID Database - Local Test Suite"
    
    # Check if services are running
    check_services
    
    # Test 1: Health Check
    print_header "Test 1: Health Check"
    test_lambda "Health Check" "01_health_check.json" "200"
    
    # Test 2: Create Table
    print_header "Test 2: Create Table"
    test_lambda "Create Table" "02_create_table.json" "200"
    
    # Test 3: Write Data
    print_header "Test 3: Write Data"
    test_lambda "Write Users" "03_write_users.json" "200"
    
    # Test 4: Query Data
    print_header "Test 4: Query All Users"
    test_lambda "Query All Users" "04_query_all_users.json" "200"
    
    # Test 5: Query with Filter
    print_header "Test 5: Query with Filter"
    test_lambda "Query Filtered Users" "05_query_filter_by_name.json" "200"
    
    # Test 6: Update Data
    print_header "Test 6: Update User"
    test_lambda "Update User" "06_update_user.json" "200"
    
    # Test 7: Soft Delete
    print_header "Test 7: Soft Delete User"
    test_lambda "Delete User" "07_delete_user.json" "200"
    
    # Test 8: List Tables
    print_header "Test 8: List Tables"
    test_lambda "List Tables" "08_list_tables.json" "200"
    
    # Test 9: Describe Table
    print_header "Test 9: Describe Table"
    test_lambda "Describe Table" "09_describe_table.json" "200"
    
    # Test 10: Compact Table
    print_header "Test 10: Compact Table"
    test_lambda "Compact Table" "10_compact_table.json" "200"
    
    # Error Handling Tests
    print_header "Error Handling Tests"
    
    # Test: Invalid Operation
    print_info "Testing: Invalid Operation"
    response=$(curl -s -X POST "$LAMBDA_URL" \
        -H "Content-Type: application/json" \
        -d '{"httpMethod":"POST","path":"/database","body":"{\"operation\":\"INVALID_OP\",\"tenant_id\":\"test\",\"table\":\"users\"}"}')
    
    status_code=$(echo "$response" | jq -r '.statusCode')
    if [ "$status_code" = "400" ]; then
        print_success "Invalid Operation - Returns 400"
    else
        print_error "Invalid Operation - Expected 400, got $status_code"
    fi
    
    # Test: Missing Body
    print_info "Testing: Missing Request Body"
    response=$(curl -s -X POST "$LAMBDA_URL" \
        -H "Content-Type: application/json" \
        -d '{"httpMethod":"POST","path":"/database"}')
    
    status_code=$(echo "$response" | jq -r '.statusCode')
    if [ "$status_code" = "400" ]; then
        print_success "Missing Body - Returns 400"
    else
        print_error "Missing Body - Expected 400, got $status_code"
    fi
    
    # Summary
    print_header "Test Summary"
    echo -e "${GREEN}Tests Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Tests Failed: $TESTS_FAILED${NC}"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo ""
        echo -e "${GREEN}🎉 All tests passed!${NC}"
        echo ""
        print_info "Next steps:"
        echo "  1. Review logs: docker-compose -f docker/docker-compose.yml logs -f lambda-api"
        echo "  2. View MinIO data: http://localhost:9006 (minioadmin/minioadmin)"
        echo "  3. Deploy to AWS Lambda"
        exit 0
    else
        echo ""
        echo -e "${RED}❌ Some tests failed${NC}"
        echo ""
        print_info "Troubleshooting:"
        echo "  1. Check logs: docker-compose -f docker/docker-compose.yml logs lambda-api"
        echo "  2. Restart services: docker-compose -f docker/docker-compose.yml restart"
        echo "  3. Rebuild: docker-compose -f docker/docker-compose.yml up --build"
        exit 1
    fi
}

# Run tests
main

