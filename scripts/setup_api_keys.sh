#!/bin/bash

# Quick Setup for API Gateway API Keys (Simpler Alternative)

set -e

echo "=========================================="
echo "API Gateway API Keys Setup"
echo "=========================================="
echo ""

# Configuration
REGION="ap-south-1"
API_ID="dhxby8kzg1"
USAGE_PLAN_NAME="BasicPlan"

echo "Configuration:"
echo "  Region: $REGION"
echo "  API Gateway ID: $API_ID"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Step 1: Create Usage Plan
echo ""
echo "Step 1/5: Creating Usage Plan..."
USAGE_PLAN_OUTPUT=$(aws apigateway create-usage-plan \
  --name "$USAGE_PLAN_NAME" \
  --description "Basic API access with rate limiting" \
  --throttle burstLimit=200,rateLimit=100 \
  --quota limit=1000000,period=MONTH \
  --api-stages apiId=$API_ID,stage=default \
  --region $REGION \
  --output json 2>&1)

if echo "$USAGE_PLAN_OUTPUT" | grep -q "ConflictException"; then
  echo "⚠️ Usage plan already exists, retrieving..."
  USAGE_PLAN_ID=$(aws apigateway get-usage-plans \
    --query "items[?name=='$USAGE_PLAN_NAME'].id" \
    --output text \
    --region $REGION)
else
  USAGE_PLAN_ID=$(echo $USAGE_PLAN_OUTPUT | jq -r '.id')
fi

echo "✓ Usage Plan ID: $USAGE_PLAN_ID"

# Step 2: Create API Key
echo ""
echo "Step 2/5: Creating API Key..."
read -p "Enter customer name (e.g., 'customer-1'): " CUSTOMER_NAME

API_KEY_OUTPUT=$(aws apigateway create-api-key \
  --name "$CUSTOMER_NAME" \
  --description "API key for $CUSTOMER_NAME" \
  --enabled \
  --region $REGION \
  --output json)

API_KEY_ID=$(echo $API_KEY_OUTPUT | jq -r '.id')
API_KEY_VALUE=$(echo $API_KEY_OUTPUT | jq -r '.value')

echo "✓ API Key created"
echo "  ID: $API_KEY_ID"
echo "  Value: $API_KEY_VALUE"

# Step 3: Associate Key with Usage Plan
echo ""
echo "Step 3/5: Associating API Key with Usage Plan..."
aws apigateway create-usage-plan-key \
  --usage-plan-id $USAGE_PLAN_ID \
  --key-id $API_KEY_ID \
  --key-type API_KEY \
  --region $REGION \
  --output json

echo "✓ API Key associated with Usage Plan"

# Step 4: Get Resource ID
echo ""
echo "Step 4/5: Finding API Gateway resource..."
RESOURCES=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --region $REGION \
  --output json)

RESOURCE_ID=$(echo $RESOURCES | jq -r '.items[] | select(.path == "/{proxy+}") | .id')

if [ -z "$RESOURCE_ID" ]; then
  RESOURCE_ID=$(echo $RESOURCES | jq -r '.items[] | select(.path == "/") | .id')
fi

echo "✓ Resource found: $RESOURCE_ID"

# Step 5: Require API Key on Method
echo ""
echo "Step 5/5: Enabling API Key requirement..."
aws apigateway update-method \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method ANY \
  --patch-operations op=replace,path=/apiKeyRequired,value=true \
  --region $REGION \
  --no-cli-pager

# Deploy
echo ""
echo "Deploying API changes..."
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name default \
  --description "Added API key requirement" \
  --region $REGION \
  --no-cli-pager

echo "✓ API deployed"

# Save configuration
cat > api_keys_config.json << EOF
{
  "region": "$REGION",
  "apiId": "$API_ID",
  "usagePlanId": "$USAGE_PLAN_ID",
  "keys": [
    {
      "name": "$CUSTOMER_NAME",
      "keyId": "$API_KEY_ID",
      "keyValue": "$API_KEY_VALUE"
    }
  ]
}
EOF

echo "✓ Configuration saved to: api_keys_config.json"

# Test
echo ""
echo "=========================================="
echo "Setup Complete! 🎉"
echo "=========================================="
echo ""
echo "API Key for $CUSTOMER_NAME:"
echo "  $API_KEY_VALUE"
echo ""
echo "⚠️ SAVE THIS KEY! It won't be shown again."
echo ""
echo "Test with:"
echo '  curl -X POST "https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda" \'
echo "    -H \"x-api-key: $API_KEY_VALUE\" \\"
echo '    -H "Content-Type: application/json" \'
echo '    -d '"'"'{"operation":"LIST_TABLES","tenant_id":"test-tenant","namespace":"default"}'"'"
echo ""
echo "Rate Limits:"
echo "  - 100 requests/second"
echo "  - 200 burst capacity"
echo "  - 1,000,000 requests/month"
echo ""

