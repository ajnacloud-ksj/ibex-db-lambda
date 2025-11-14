#!/bin/bash

# Create Cognito User

set -e

echo "=========================================="
echo "Create Cognito User"
echo "=========================================="
echo ""

# Load configuration
if [ ! -f cognito_config.json ]; then
  echo "❌ cognito_config.json not found!"
  echo "Run ./scripts/setup_cognito_auth.sh first"
  exit 1
fi

USER_POOL_ID=$(jq -r '.userPoolId' cognito_config.json)
REGION=$(jq -r '.region' cognito_config.json)

echo "User Pool: $USER_POOL_ID"
echo ""

# Get user details
read -p "Email: " EMAIL
read -s -p "Password (min 8 chars, uppercase, lowercase, number): " PASSWORD
echo ""
read -p "Send welcome email? (y/n): " SEND_EMAIL

# Create user
echo ""
echo "Creating user..."

if [ "$SEND_EMAIL" == "y" ]; then
  # Send welcome email with temporary password
  aws cognito-idp admin-create-user \
    --user-pool-id $USER_POOL_ID \
    --username "$EMAIL" \
    --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true \
    --region $REGION
  
  echo "✓ User created: $EMAIL"
  echo "  Temporary password sent to email"
  echo "  User must change password on first login"
else
  # Create with permanent password
  aws cognito-idp admin-create-user \
    --user-pool-id $USER_POOL_ID \
    --username "$EMAIL" \
    --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true \
    --message-action SUPPRESS \
    --region $REGION
  
  aws cognito-idp admin-set-user-password \
    --user-pool-id $USER_POOL_ID \
    --username "$EMAIL" \
    --password "$PASSWORD" \
    --permanent \
    --region $REGION
  
  echo "✓ User created: $EMAIL"
  echo "  Password set (permanent)"
fi

echo ""
echo "User can now login with:"
echo "  Email: $EMAIL"
echo "  Password: ********"
echo ""

# Test login
read -p "Test login now? (y/n): " TEST_LOGIN

if [ "$TEST_LOGIN" == "y" ]; then
  CLIENT_ID=$(jq -r '.clientId' cognito_config.json)
  
  echo ""
  echo "Testing login..."
  LOGIN_RESPONSE=$(aws cognito-idp admin-initiate-auth \
    --user-pool-id $USER_POOL_ID \
    --client-id $CLIENT_ID \
    --auth-flow ADMIN_NO_SRP_AUTH \
    --auth-parameters USERNAME=$EMAIL,PASSWORD=$PASSWORD \
    --region $REGION \
    --output json 2>&1)
  
  if echo "$LOGIN_RESPONSE" | grep -q "AccessToken"; then
    echo "✓ Login test successful!"
    ACCESS_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.AuthenticationResult.AccessToken')
    echo ""
    echo "JWT Token (first 50 chars):"
    echo "${ACCESS_TOKEN:0:50}..."
  else
    echo "❌ Login test failed"
    echo "$LOGIN_RESPONSE"
  fi
fi

echo ""
echo "=========================================="
echo "User Creation Complete! ✅"
echo "=========================================="
echo ""

