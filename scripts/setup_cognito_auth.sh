#!/bin/bash

# Automated AWS Cognito Authentication Setup
# This script sets up complete JWT authentication for your API

set -e

echo "=========================================="
echo "AWS Cognito Authentication Setup"
echo "=========================================="
echo ""

# Configuration
REGION="ap-south-1"
USER_POOL_NAME="ibex-db-users"
APP_CLIENT_NAME="ibex-db-client"
API_ID="dhxby8kzg1"  # Your API Gateway ID

echo "Configuration:"
echo "  Region: $REGION"
echo "  User Pool Name: $USER_POOL_NAME"
echo "  API Gateway ID: $API_ID"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Step 1: Create User Pool
echo ""
echo "Step 1/7: Creating Cognito User Pool..."
USER_POOL_OUTPUT=$(aws cognito-idp create-user-pool \
  --pool-name "$USER_POOL_NAME" \
  --policies '{
    "PasswordPolicy": {
      "MinimumLength": 8,
      "RequireUppercase": true,
      "RequireLowercase": true,
      "RequireNumbers": true,
      "RequireSymbols": false
    }
  }' \
  --auto-verified-attributes email \
  --mfa-configuration OFF \
  --region $REGION \
  --output json)

USER_POOL_ID=$(echo $USER_POOL_OUTPUT | jq -r '.UserPool.Id')
USER_POOL_ARN=$(echo $USER_POOL_OUTPUT | jq -r '.UserPool.Arn')

echo "✓ User Pool created: $USER_POOL_ID"

# Step 2: Create App Client
echo ""
echo "Step 2/7: Creating App Client..."
APP_CLIENT_OUTPUT=$(aws cognito-idp create-user-pool-client \
  --user-pool-id $USER_POOL_ID \
  --client-name "$APP_CLIENT_NAME" \
  --generate-secret \
  --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH ALLOW_ADMIN_USER_PASSWORD_AUTH \
  --region $REGION \
  --output json)

CLIENT_ID=$(echo $APP_CLIENT_OUTPUT | jq -r '.UserPoolClient.ClientId')
CLIENT_SECRET=$(echo $APP_CLIENT_OUTPUT | jq -r '.UserPoolClient.ClientSecret')

echo "✓ App Client created: $CLIENT_ID"

# Step 3: Create API Gateway Authorizer
echo ""
echo "Step 3/7: Creating API Gateway Authorizer..."
AUTHORIZER_OUTPUT=$(aws apigateway create-authorizer \
  --rest-api-id $API_ID \
  --name CognitoAuthorizer \
  --type COGNITO_USER_POOLS \
  --provider-arns $USER_POOL_ARN \
  --identity-source method.request.header.Authorization \
  --region $REGION \
  --output json)

AUTHORIZER_ID=$(echo $AUTHORIZER_OUTPUT | jq -r '.id')

echo "✓ Authorizer created: $AUTHORIZER_ID"

# Step 4: Get Resource ID for your proxy endpoint
echo ""
echo "Step 4/7: Finding API Gateway resource..."
RESOURCES=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --region $REGION \
  --output json)

RESOURCE_ID=$(echo $RESOURCES | jq -r '.items[] | select(.path == "/{proxy+}") | .id')

if [ -z "$RESOURCE_ID" ]; then
  echo "⚠️ Could not find /{proxy+} resource. Trying / resource..."
  RESOURCE_ID=$(echo $RESOURCES | jq -r '.items[] | select(.path == "/") | .id')
fi

echo "✓ Resource found: $RESOURCE_ID"

# Step 5: Update method to require authorization
echo ""
echo "Step 5/7: Enabling authorization on API method..."
aws apigateway update-method \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method ANY \
  --patch-operations op=replace,path=/authorizationType,value=COGNITO_USER_POOLS op=replace,path=/authorizerId,value=$AUTHORIZER_ID \
  --region $REGION \
  --no-cli-pager

echo "✓ Authorization enabled"

# Step 6: Deploy API
echo ""
echo "Step 6/7: Deploying API changes..."
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name default \
  --description "Added Cognito authentication" \
  --region $REGION \
  --no-cli-pager

echo "✓ API deployed"

# Step 7: Create test user
echo ""
echo "Step 7/7: Creating test user..."
read -p "Enter test user email: " TEST_EMAIL
read -s -p "Enter password (min 8 chars, uppercase, lowercase, number): " TEST_PASSWORD
echo ""

aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username "$TEST_EMAIL" \
  --user-attributes Name=email,Value="$TEST_EMAIL" \
  --message-action SUPPRESS \
  --region $REGION

aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username "$TEST_EMAIL" \
  --password "$TEST_PASSWORD" \
  --permanent \
  --region $REGION

echo "✓ Test user created: $TEST_EMAIL"

# Save configuration
echo ""
echo "Saving configuration..."
cat > cognito_config.json << EOF
{
  "region": "$REGION",
  "userPoolId": "$USER_POOL_ID",
  "userPoolArn": "$USER_POOL_ARN",
  "clientId": "$CLIENT_ID",
  "clientSecret": "$CLIENT_SECRET",
  "authorizerId": "$AUTHORIZER_ID",
  "apiId": "$API_ID",
  "testUser": {
    "email": "$TEST_EMAIL",
    "password": "***REDACTED***"
  }
}
EOF

echo "✓ Configuration saved to: cognito_config.json"

# Test authentication
echo ""
echo "=========================================="
echo "Setup Complete! 🎉"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  User Pool ID: $USER_POOL_ID"
echo "  Client ID: $CLIENT_ID"
echo "  Client Secret: $CLIENT_SECRET"
echo "  Test User: $TEST_EMAIL"
echo ""
echo "Next steps:"
echo "  1. Test authentication:"
echo "     ./scripts/test_auth.sh"
echo ""
echo "  2. Create more users:"
echo "     ./scripts/create_user.sh"
echo ""
echo "  3. Update your application to use:"
echo "     - User Pool ID: $USER_POOL_ID"
echo "     - Client ID: $CLIENT_ID"
echo ""
echo "⚠️ IMPORTANT: Save the Client Secret securely!"
echo "   Client Secret: $CLIENT_SECRET"
echo ""

