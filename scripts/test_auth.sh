#!/bin/bash

# Test Cognito Authentication

set -e

echo "=========================================="
echo "Testing Cognito Authentication"
echo "=========================================="
echo ""

# Load configuration
if [ ! -f cognito_config.json ]; then
  echo "❌ cognito_config.json not found!"
  echo "Run ./scripts/setup_cognito_auth.sh first"
  exit 1
fi

USER_POOL_ID=$(jq -r '.userPoolId' cognito_config.json)
CLIENT_ID=$(jq -r '.clientId' cognito_config.json)
REGION=$(jq -r '.region' cognito_config.json)
API_URL="https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda"

echo "Configuration loaded:"
echo "  User Pool: $USER_POOL_ID"
echo "  Client: $CLIENT_ID"
echo "  API: $API_URL"
echo ""

# Get credentials
read -p "Email: " EMAIL
read -s -p "Password: " PASSWORD
echo ""
echo ""

# Step 1: Login
echo "Step 1: Logging in..."
LOGIN_RESPONSE=$(aws cognito-idp admin-initiate-auth \
  --user-pool-id $USER_POOL_ID \
  --client-id $CLIENT_ID \
  --auth-flow ADMIN_NO_SRP_AUTH \
  --auth-parameters USERNAME=$EMAIL,PASSWORD=$PASSWORD \
  --region $REGION \
  --output json 2>&1)

if echo "$LOGIN_RESPONSE" | grep -q "NotAuthorizedException"; then
  echo "❌ Login failed: Invalid credentials"
  exit 1
fi

if echo "$LOGIN_RESPONSE" | grep -q "UserNotFoundException"; then
  echo "❌ Login failed: User not found"
  exit 1
fi

ACCESS_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.AuthenticationResult.AccessToken')
ID_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.AuthenticationResult.IdToken')
EXPIRES_IN=$(echo $LOGIN_RESPONSE | jq -r '.AuthenticationResult.ExpiresIn')

if [ "$ACCESS_TOKEN" == "null" ]; then
  echo "❌ Failed to get access token"
  echo "$LOGIN_RESPONSE"
  exit 1
fi

echo "✓ Login successful!"
echo "  Token expires in: ${EXPIRES_IN}s ($(($EXPIRES_IN / 60)) minutes)"
echo ""

# Step 2: Test API call without token
echo "Step 2: Testing API without token (should fail)..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "LIST_TABLES",
    "tenant_id": "test-tenant",
    "namespace": "default"
  }')

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" == "401" ] || [ "$HTTP_CODE" == "403" ]; then
  echo "✓ Correctly rejected (HTTP $HTTP_CODE)"
else
  echo "⚠️ Expected 401/403 but got HTTP $HTTP_CODE"
  echo "$BODY"
fi
echo ""

# Step 3: Test API call with token
echo "Step 3: Testing API with valid token..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "LIST_TABLES",
    "tenant_id": "test-tenant",
    "namespace": "default"
  }')

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" == "200" ]; then
  echo "✓ Authenticated successfully! (HTTP $HTTP_CODE)"
  echo ""
  echo "Response:"
  echo "$BODY" | jq '.'
else
  echo "❌ Authentication failed (HTTP $HTTP_CODE)"
  echo "$BODY"
fi
echo ""

# Step 4: Decode JWT to show user info
echo "Step 4: Decoding JWT token..."
echo ""
echo "JWT Claims:"
echo "$ACCESS_TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | jq '.' || echo "(Could not decode)"
echo ""

# Save token for Postman
echo ""
echo "=========================================="
echo "Authentication Test Complete! ✅"
echo "=========================================="
echo ""
echo "For Postman:"
echo "  1. Add environment variable 'jwt_token'"
echo "  2. Set value to: Bearer $ACCESS_TOKEN"
echo "  3. Add header: Authorization = {{jwt_token}}"
echo ""
echo "Token saved to: jwt_token.txt"
echo "Bearer $ACCESS_TOKEN" > jwt_token.txt
echo ""

