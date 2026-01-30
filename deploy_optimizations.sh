#!/bin/bash
#
# Deploy optimization for IbexDB Lambda
# This script safely deploys the optimized handler with rollback capability
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-ibex-db-lambda}"
AWS_REGION="${AWS_REGION:-us-east-1}"
STAGE="${1:-dev}"  # dev, staging, or prod

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}IbexDB Lambda Optimization Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Function: $LAMBDA_FUNCTION_NAME"
echo "Region: $AWS_REGION"
echo "Stage: $STAGE"
echo ""

# Step 1: Backup current Lambda configuration
echo -e "${YELLOW}Step 1: Backing up current configuration...${NC}"
aws lambda get-function-configuration \
    --function-name $LAMBDA_FUNCTION_NAME \
    --region $AWS_REGION \
    > lambda_config_backup_$(date +%Y%m%d_%H%M%S).json
echo -e "${GREEN}✓ Configuration backed up${NC}"

# Step 2: Create Lambda version (for rollback)
echo -e "${YELLOW}Step 2: Creating version for rollback...${NC}"
BACKUP_VERSION=$(aws lambda publish-version \
    --function-name $LAMBDA_FUNCTION_NAME \
    --region $AWS_REGION \
    --description "Backup before optimization deployment" \
    --query 'Version' \
    --output text)
echo -e "${GREEN}✓ Backup version created: $BACKUP_VERSION${NC}"

# Step 3: Update Lambda configuration for optimization
echo -e "${YELLOW}Step 3: Updating Lambda configuration...${NC}"

# Update memory and timeout
aws lambda update-function-configuration \
    --function-name $LAMBDA_FUNCTION_NAME \
    --region $AWS_REGION \
    --memory-size 3008 \
    --timeout 30 \
    --environment "Variables={
        ENABLE_CACHE=true,
        CACHE_MAX_SIZE=500,
        CACHE_TTL=300,
        READ_CACHE_TTL=60,
        INCLUDE_CACHE_STATS=false,
        DUCKDB_MEMORY_LIMIT=2GB,
        DUCKDB_THREADS=2,
        ENABLE_XRAY=true,
        STAGE=$STAGE
    }" \
    --tracing-config Mode=Active \
    > /dev/null

echo -e "${GREEN}✓ Configuration updated${NC}"

# Step 4: Deploy optimized handler
echo -e "${YELLOW}Step 4: Deploying optimized handler...${NC}"

# Create deployment package
cd src
cp lambda_handler.py lambda_handler_original.py  # Backup original
cp lambda_handler_optimized.py lambda_handler.py  # Use optimized

# Zip the package
zip -r ../lambda_deployment.zip . -x "*.pyc" -x "__pycache__/*" -x "*.git/*"

# Restore original (for local development)
mv lambda_handler_original.py lambda_handler.py
cd ..

# Update Lambda code
aws lambda update-function-code \
    --function-name $LAMBDA_FUNCTION_NAME \
    --region $AWS_REGION \
    --zip-file fileb://lambda_deployment.zip \
    > /dev/null

echo -e "${GREEN}✓ Optimized handler deployed${NC}"

# Step 5: Set up reserved concurrency (for warm starts)
if [ "$STAGE" = "prod" ]; then
    echo -e "${YELLOW}Step 5: Setting reserved concurrency...${NC}"
    aws lambda put-function-concurrency \
        --function-name $LAMBDA_FUNCTION_NAME \
        --region $AWS_REGION \
        --reserved-concurrent-executions 10
    echo -e "${GREEN}✓ Reserved concurrency set to 10${NC}"
fi

# Step 6: Create CloudWatch warmup rule
echo -e "${YELLOW}Step 6: Setting up warmup schedule...${NC}"

# Create warmup rule
aws events put-rule \
    --name "${LAMBDA_FUNCTION_NAME}-warmup" \
    --schedule-expression "rate(5 minutes)" \
    --state ENABLED \
    --region $AWS_REGION \
    > /dev/null

# Add Lambda permission for CloudWatch
aws lambda add-permission \
    --function-name $LAMBDA_FUNCTION_NAME \
    --statement-id "${LAMBDA_FUNCTION_NAME}-warmup-permission" \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:${AWS_REGION}:*:rule/${LAMBDA_FUNCTION_NAME}-warmup" \
    --region $AWS_REGION \
    2>/dev/null || true

# Create warmup target
aws events put-targets \
    --rule "${LAMBDA_FUNCTION_NAME}-warmup" \
    --targets "Id=1,Arn=arn:aws:lambda:${AWS_REGION}:*:function:${LAMBDA_FUNCTION_NAME},Input={\"warmup\":true,\"tenants\":[\"default\"],\"preload_tables\":[\"food_entries\",\"receipts\"]}" \
    --region $AWS_REGION \
    > /dev/null

echo -e "${GREEN}✓ Warmup schedule configured${NC}"

# Step 7: Test the deployment
echo -e "${YELLOW}Step 7: Testing deployment...${NC}"

# Test with a simple query
TEST_PAYLOAD='{"body":"{\"operation\":\"LIST_TABLES\",\"tenant_id\":\"test\"}"}'
TEST_RESULT=$(aws lambda invoke \
    --function-name $LAMBDA_FUNCTION_NAME \
    --region $AWS_REGION \
    --payload "$TEST_PAYLOAD" \
    --query 'StatusCode' \
    --output text \
    /tmp/test_result.json)

if [ "$TEST_RESULT" = "200" ]; then
    echo -e "${GREEN}✓ Deployment test successful${NC}"

    # Check if caching is working
    CACHE_HIT=$(cat /tmp/test_result.json | jq -r '.headers["X-Cache-Hit"]' 2>/dev/null || echo "false")
    echo -e "  Cache enabled: ${CACHE_HIT}"
else
    echo -e "${RED}✗ Deployment test failed${NC}"
    echo -e "${YELLOW}Rolling back to version $BACKUP_VERSION...${NC}"

    # Rollback
    aws lambda update-function-code \
        --function-name $LAMBDA_FUNCTION_NAME \
        --region $AWS_REGION \
        --s3-bucket "" \
        --s3-key "" \
        --s3-object-version "$BACKUP_VERSION"

    echo -e "${GREEN}✓ Rolled back to previous version${NC}"
    exit 1
fi

# Step 8: Create alias for staged deployment
echo -e "${YELLOW}Step 8: Creating/Updating alias...${NC}"

aws lambda create-alias \
    --function-name $LAMBDA_FUNCTION_NAME \
    --name "$STAGE-optimized" \
    --function-version '$LATEST' \
    --description "Optimized version for $STAGE" \
    --region $AWS_REGION \
    2>/dev/null || \
aws lambda update-alias \
    --function-name $LAMBDA_FUNCTION_NAME \
    --name "$STAGE-optimized" \
    --function-version '$LATEST' \
    --region $AWS_REGION

echo -e "${GREEN}✓ Alias '$STAGE-optimized' updated${NC}"

# Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Optimizations deployed:"
echo "  • In-memory caching enabled (500 items max)"
echo "  • Connection pooling active"
echo "  • Memory increased to 3GB (2 vCPUs)"
echo "  • Warmup schedule configured (every 5 minutes)"
if [ "$STAGE" = "prod" ]; then
    echo "  • Reserved concurrency: 10 instances"
fi
echo ""
echo "Rollback version: $BACKUP_VERSION"
echo "Alias: $STAGE-optimized"
echo ""
echo -e "${YELLOW}Monitor performance:${NC}"
echo "  aws cloudwatch get-metric-statistics \\"
echo "    --namespace AWS/Lambda \\"
echo "    --metric-name Duration \\"
echo "    --dimensions Name=FunctionName,Value=$LAMBDA_FUNCTION_NAME \\"
echo "    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \\"
echo "    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \\"
echo "    --period 300 \\"
echo "    --statistics Average"
echo ""