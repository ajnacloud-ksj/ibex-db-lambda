# Authentication Implementation Guide

## Current State
- ✅ Lambda connected to API Gateway
- ❌ No authentication
- ❌ No authorization
- ⚠️ **Anyone with the URL can access your API**

## Target State
- ✅ Token-based authentication
- ✅ User/API key management
- ✅ Rate limiting per token
- ✅ Audit trail of who accessed what

---

## 🎯 Recommended Solutions (Ranked)

### **Option 1: AWS Cognito + JWT (BEST for public SaaS)** ⭐ RECOMMENDED
**Best for:** User-facing SaaS, mobile apps, web apps

**Pros:**
- ✅ Full user management (sign up, login, password reset)
- ✅ JWT tokens (industry standard)
- ✅ MFA support
- ✅ Social login (Google, Facebook, etc.)
- ✅ Free tier: 50,000 MAU
- ✅ No code in Lambda for auth (handled by API Gateway)

**Cons:**
- ⚠️ More complex setup (30-60 min)
- ⚠️ Costs after free tier ($0.0055/MAU)

**Implementation Time:** 1-2 hours

---

### **Option 2: API Gateway API Keys (FASTEST)** ⚡
**Best for:** Partner APIs, B2B integrations, getting started quickly

**Pros:**
- ✅ Extremely simple (10 min setup)
- ✅ Built into API Gateway
- ✅ Free
- ✅ Usage plans & rate limiting included
- ✅ Good for service-to-service auth

**Cons:**
- ⚠️ No user management
- ⚠️ Manual key creation
- ⚠️ Keys are long-lived (rotation needed)
- ⚠️ No fine-grained permissions

**Implementation Time:** 10-15 minutes

---

### **Option 3: Custom JWT Tokens (FLEXIBLE)** 🔧
**Best for:** Existing user system, full control needed

**Pros:**
- ✅ Full control over auth logic
- ✅ Integrate with existing user database
- ✅ Custom claims/permissions
- ✅ No AWS Cognito dependency

**Cons:**
- ⚠️ You manage token signing/verification
- ⚠️ Code changes in Lambda required
- ⚠️ More maintenance

**Implementation Time:** 2-3 hours

---

## 📋 IMPLEMENTATION GUIDES

---

# OPTION 1: AWS Cognito + JWT (Recommended)

## Architecture
```
User → Cognito (Login) → JWT Token
                            ↓
User → API Gateway (validates JWT) → Lambda → Your Code
```

API Gateway validates the JWT **before** calling your Lambda. Zero code changes needed!

---

## Step-by-Step Implementation

### **Step 1: Create Cognito User Pool (5 min)**

```bash
# Create User Pool
aws cognito-idp create-user-pool \
  --pool-name ibex-db-users \
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
  --region ap-south-1

# Save the UserPoolId from output
# Example: ap-south-1_aBcDeFgHi
```

### **Step 2: Create Cognito App Client (2 min)**

```bash
# Create App Client
aws cognito-idp create-user-pool-client \
  --user-pool-id ap-south-1_YOUR_POOL_ID \
  --client-name ibex-db-client \
  --generate-secret \
  --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH \
  --region ap-south-1

# Save the ClientId and ClientSecret from output
```

### **Step 3: Configure API Gateway Authorizer (10 min)**

**Option A: AWS Console (Easier)**

1. Go to **API Gateway Console**
2. Select your API: `ibex-db-lambda`
3. Click **Authorizers** → **Create New Authorizer**
4. Configure:
   - Name: `CognitoAuthorizer`
   - Type: `Cognito`
   - Cognito User Pool: Select the pool you created
   - Token Source: `Authorization`
   - Token Validation: Leave empty (validates all)
5. Click **Create**
6. Go to **Resources** → Select `ANY /{proxy+}`
7. Click **Method Request**
8. Change **Authorization** from `NONE` to `CognitoAuthorizer`
9. Click **Actions** → **Deploy API** → Select stage

**Option B: AWS CLI (Faster)**

```bash
# Get your API ID
API_ID="dhxby8kzg1"  # From your URL

# Create Cognito Authorizer
aws apigateway create-authorizer \
  --rest-api-id $API_ID \
  --name CognitoAuthorizer \
  --type COGNITO_USER_POOLS \
  --provider-arns arn:aws:cognito-idp:ap-south-1:YOUR_ACCOUNT_ID:userpool/ap-south-1_YOUR_POOL_ID \
  --identity-source method.request.header.Authorization \
  --region ap-south-1

# Save the Authorizer ID from output

# Update your method to require authorization
aws apigateway update-method \
  --rest-api-id $API_ID \
  --resource-id RESOURCE_ID \
  --http-method ANY \
  --patch-operations op=replace,path=/authorizationType,value=COGNITO_USER_POOLS \
  --region ap-south-1

# Deploy the changes
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name default \
  --region ap-south-1
```

---

### **Step 4: Create Test User (2 min)**

```bash
# Create a test user
aws cognito-idp admin-create-user \
  --user-pool-id ap-south-1_YOUR_POOL_ID \
  --username testuser@example.com \
  --user-attributes Name=email,Value=testuser@example.com \
  --temporary-password TempPassword123! \
  --region ap-south-1

# Set permanent password (optional)
aws cognito-idp admin-set-user-password \
  --user-pool-id ap-south-1_YOUR_POOL_ID \
  --username testuser@example.com \
  --password MySecurePassword123! \
  --permanent \
  --region ap-south-1
```

---

### **Step 5: Test Authentication (5 min)**

**Login and Get JWT Token:**

```bash
# Login to get JWT token
aws cognito-idp admin-initiate-auth \
  --user-pool-id ap-south-1_YOUR_POOL_ID \
  --client-id YOUR_CLIENT_ID \
  --auth-flow ADMIN_NO_SRP_AUTH \
  --auth-parameters USERNAME=testuser@example.com,PASSWORD=MySecurePassword123! \
  --region ap-south-1

# Output will include:
# {
#   "AuthenticationResult": {
#     "AccessToken": "eyJraWQiOiJ...",  # <-- This is your JWT!
#     "IdToken": "eyJraWQiOiJ...",
#     "RefreshToken": "eyJjdHki...",
#     "ExpiresIn": 3600
#   }
# }
```

**Make Authenticated API Call:**

```bash
# Save your JWT token
JWT_TOKEN="eyJraWQiOiJ..."  # From AccessToken above

# Call your API with the token
curl -X POST "https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "LIST_TABLES",
    "tenant_id": "test-tenant",
    "namespace": "default"
  }'

# ✅ Success: Returns your tables
# ❌ Without token: Returns {"message":"Unauthorized"}
```

---

### **Step 6: Access User Info in Lambda (Optional)**

The JWT claims are automatically passed to your Lambda in the `event`:

```python
# In src/lambda_handler.py

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    # Get user info from JWT claims
    authorizer = event.get('requestContext', {}).get('authorizer', {})
    
    # Available claims:
    user_email = authorizer.get('claims', {}).get('email')
    user_sub = authorizer.get('claims', {}).get('sub')  # Unique user ID
    username = authorizer.get('claims', {}).get('cognito:username')
    
    print(f"Authenticated user: {user_email} ({user_sub})")
    
    # You can now:
    # - Use user_sub as tenant_id (single-tenant per user)
    # - Check user permissions
    # - Log who made the request
    
    # Rest of your handler...
```

---

### **Step 7: User Management**

**Create API for users to sign up:**

```python
# In a separate Lambda or your backend

import boto3

cognito = boto3.client('cognito-idp')

def signup_user(email: str, password: str):
    """Register new user"""
    response = cognito.sign_up(
        ClientId='YOUR_CLIENT_ID',
        Username=email,
        Password=password,
        UserAttributes=[
            {'Name': 'email', 'Value': email}
        ]
    )
    return response

def confirm_signup(email: str, confirmation_code: str):
    """Verify email with code"""
    cognito.confirm_sign_up(
        ClientId='YOUR_CLIENT_ID',
        Username=email,
        ConfirmationCode=confirmation_code
    )

def login_user(email: str, password: str):
    """Login and get JWT"""
    response = cognito.initiate_auth(
        ClientId='YOUR_CLIENT_ID',
        AuthFlow='USER_PASSWORD_AUTH',
        AuthParameters={
            'USERNAME': email,
            'PASSWORD': password
        }
    )
    return response['AuthenticationResult']['AccessToken']
```

---

### **Step 8: Update Postman Collections**

Add environment variable:

```json
{
  "key": "jwt_token",
  "value": "Bearer eyJraWQiOiJ...",
  "type": "default"
}
```

Add to all requests:

```json
{
  "key": "Authorization",
  "value": "{{jwt_token}}",
  "type": "default"
}
```

---

## Cost Estimate (Cognito)

- **Free Tier**: 50,000 Monthly Active Users (MAU)
- **After Free Tier**: $0.0055 per MAU
- **Example**: 10,000 users = FREE, 100,000 users = $275/month

---

# OPTION 2: API Gateway API Keys (Fastest)

## Architecture
```
Client → API Gateway (checks API key) → Lambda → Your Code
```

---

## Step-by-Step Implementation

### **Step 1: Create Usage Plan (2 min)**

**AWS Console:**

1. Go to **API Gateway Console**
2. Select your API: `ibex-db-lambda`
3. Click **Usage Plans** → **Create**
4. Configure:
   - Name: `BasicPlan`
   - Enable throttling:
     - Rate: 100 requests/second
     - Burst: 200 requests
   - Enable quota:
     - 1,000,000 requests per month
5. Click **Next**
6. Add API Stage:
   - API: `ibex-db-lambda`
   - Stage: `default`
7. Click **Done**

**AWS CLI:**

```bash
API_ID="dhxby8kzg1"

# Create usage plan
aws apigateway create-usage-plan \
  --name "BasicPlan" \
  --description "Basic API access" \
  --throttle burstLimit=200,rateLimit=100 \
  --quota limit=1000000,period=MONTH \
  --api-stages apiId=$API_ID,stage=default \
  --region ap-south-1
```

### **Step 2: Create API Keys (2 min)**

**AWS Console:**

1. Click **API Keys** → **Actions** → **Create API Key**
2. Name: `customer-1`
3. Click **Save**
4. Copy the API Key (shows only once!)

**AWS CLI:**

```bash
# Create API key
aws apigateway create-api-key \
  --name "customer-1" \
  --description "API key for Customer 1" \
  --enabled \
  --region ap-south-1

# Output includes the API key value
# Example: a1b2c3d4e5f6g7h8i9j0
```

### **Step 3: Associate Key with Usage Plan (1 min)**

```bash
# Get usage plan ID
USAGE_PLAN_ID=$(aws apigateway get-usage-plans \
  --query 'items[?name==`BasicPlan`].id' \
  --output text \
  --region ap-south-1)

# Get API key ID
API_KEY_ID=$(aws apigateway get-api-keys \
  --query 'items[?name==`customer-1`].id' \
  --output text \
  --region ap-south-1)

# Associate
aws apigateway create-usage-plan-key \
  --usage-plan-id $USAGE_PLAN_ID \
  --key-id $API_KEY_ID \
  --key-type API_KEY \
  --region ap-south-1
```

### **Step 4: Require API Key on Method (5 min)**

**AWS Console:**

1. Go to **Resources** → Select `ANY /{proxy+}`
2. Click **Method Request**
3. Set **API Key Required** to `true`
4. Click **Actions** → **Deploy API**

**AWS CLI:**

```bash
# Update method to require API key
aws apigateway update-method \
  --rest-api-id $API_ID \
  --resource-id RESOURCE_ID \
  --http-method ANY \
  --patch-operations op=replace,path=/apiKeyRequired,value=true \
  --region ap-south-1

# Deploy
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name default \
  --region ap-south-1
```

### **Step 5: Test with API Key**

```bash
# Your API key
API_KEY="a1b2c3d4e5f6g7h8i9j0"

# Call API with key
curl -X POST "https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "LIST_TABLES",
    "tenant_id": "test-tenant",
    "namespace": "default"
  }'

# ✅ With valid key: Success
# ❌ Without key: {"message":"Forbidden"}
# ❌ Invalid key: {"message":"Forbidden"}
```

### **Step 6: Monitor Usage**

```bash
# Check usage for a key
aws apigateway get-usage \
  --usage-plan-id $USAGE_PLAN_ID \
  --key-id $API_KEY_ID \
  --start-date 2025-11-01 \
  --end-date 2025-11-30 \
  --region ap-south-1
```

### **Step 7: Key Management Script**

```bash
#!/bin/bash
# scripts/manage_api_keys.sh

create_customer_key() {
  CUSTOMER_NAME=$1
  
  # Create key
  KEY_OUTPUT=$(aws apigateway create-api-key \
    --name "$CUSTOMER_NAME" \
    --enabled \
    --region ap-south-1 \
    --query '{id:id,value:value}' \
    --output json)
  
  KEY_ID=$(echo $KEY_OUTPUT | jq -r '.id')
  KEY_VALUE=$(echo $KEY_OUTPUT | jq -r '.value')
  
  # Associate with usage plan
  aws apigateway create-usage-plan-key \
    --usage-plan-id $USAGE_PLAN_ID \
    --key-id $KEY_ID \
    --key-type API_KEY \
    --region ap-south-1
  
  echo "Created API key for $CUSTOMER_NAME"
  echo "Key ID: $KEY_ID"
  echo "Key Value: $KEY_VALUE"
  echo ""
  echo "⚠️ Save this key! It won't be shown again."
}

revoke_customer_key() {
  KEY_ID=$1
  
  aws apigateway update-api-key \
    --api-key $KEY_ID \
    --patch-operations op=replace,path=/enabled,value=false \
    --region ap-south-1
  
  echo "Revoked API key: $KEY_ID"
}

# Usage:
# ./manage_api_keys.sh create_customer "Acme Corp"
# ./manage_api_keys.sh revoke abc123
```

---

## Cost Estimate (API Keys)

- **FREE** - No additional cost beyond API Gateway requests
- API Gateway: $3.50 per million requests
- Example: 10M requests/month = $35

---

# OPTION 3: Custom JWT (Advanced)

## Architecture
```
Your Auth Service → JWT Token
                      ↓
Client → API Gateway → Lambda (verifies JWT) → Your Code
```

---

## Implementation

### **Step 1: Install Dependencies**

```bash
# Add to requirements.txt
PyJWT==2.8.0
cryptography==41.0.7
```

### **Step 2: Create Auth Helper**

```python
# src/auth.py

import jwt
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Secret key for signing JWTs (store in AWS Secrets Manager in production)
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

def create_token(user_id: str, tenant_id: str, permissions: list = None) -> str:
    """Generate JWT token"""
    payload = {
        'user_id': user_id,
        'tenant_id': tenant_id,
        'permissions': permissions or [],
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode JWT token"""
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")

def extract_token_from_event(event: Dict[str, Any]) -> Optional[str]:
    """Extract JWT from API Gateway event"""
    headers = event.get('headers', {})
    
    # Try Authorization header (case-insensitive)
    for header_name, header_value in headers.items():
        if header_name.lower() == 'authorization':
            return header_value
    
    return None
```

### **Step 3: Update Lambda Handler**

```python
# src/lambda_handler.py

from auth import verify_token, extract_token_from_event

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    start_time = time.time()
    request_id = context.aws_request_id if context else 'local-test'
    
    try:
        # Extract and verify JWT token
        token = extract_token_from_event(event)
        
        if not token:
            return error_response(401, 'Missing authentication token', request_id)
        
        try:
            token_payload = verify_token(token)
            user_id = token_payload['user_id']
            tenant_id = token_payload['tenant_id']
            permissions = token_payload.get('permissions', [])
            
            print(f"Authenticated user: {user_id}, tenant: {tenant_id}")
        except ValueError as e:
            return error_response(401, f'Authentication failed: {str(e)}', request_id)
        
        # Parse request body
        if event.get('body'):
            body = json.loads(event['body'])
        else:
            body = event
        
        # Verify tenant_id in request matches token
        request_tenant_id = body.get('tenant_id')
        if request_tenant_id and request_tenant_id != tenant_id:
            return error_response(403, 'Access denied: tenant_id mismatch', request_id)
        
        # Override tenant_id with the one from token (security!)
        body['tenant_id'] = tenant_id
        
        # Rest of your handler logic...
        operation = body.get('operation')
        
        # Check permissions
        if operation and not has_permission(permissions, operation):
            return error_response(403, f'Permission denied for operation: {operation}', request_id)
        
        # ... your existing code ...
        
    except Exception as e:
        return error_response(500, str(e), request_id)

def has_permission(permissions: list, operation: str) -> bool:
    """Check if user has permission for operation"""
    if 'admin' in permissions:
        return True
    
    operation_permissions = {
        'QUERY': 'read',
        'LIST_TABLES': 'read',
        'DESCRIBE_TABLE': 'read',
        'CREATE_TABLE': 'write',
        'WRITE': 'write',
        'UPDATE': 'write',
        'DELETE': 'write',
        'COMPACT': 'admin'
    }
    
    required_permission = operation_permissions.get(operation, 'admin')
    return required_permission in permissions
```

### **Step 4: Create Login Endpoint (Separate Lambda)**

```python
# login_lambda.py

import json
import bcrypt
from auth import create_token

# In production, fetch from database
USERS_DB = {
    'user@example.com': {
        'password_hash': bcrypt.hashpw(b'password123', bcrypt.gensalt()),
        'tenant_id': 'tenant-001',
        'permissions': ['read', 'write']
    }
}

def lambda_handler(event, context):
    body = json.loads(event['body'])
    email = body.get('email')
    password = body.get('password')
    
    user = USERS_DB.get(email)
    if not user:
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Invalid credentials'})
        }
    
    if not bcrypt.checkpw(password.encode(), user['password_hash']):
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Invalid credentials'})
        }
    
    # Generate JWT
    token = create_token(
        user_id=email,
        tenant_id=user['tenant_id'],
        permissions=user['permissions']
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'token': token,
            'expires_in': 86400  # 24 hours
        })
    }
```

### **Step 5: Test Custom JWT**

```bash
# Login to get token
curl -X POST "https://YOUR-LOGIN-ENDPOINT.amazonaws.com/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'

# Response:
# {"token": "eyJhbGci...", "expires_in": 86400}

# Use token
JWT_TOKEN="eyJhbGci..."

curl -X POST "https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "QUERY",
    "tenant_id": "tenant-001",
    "table": "users",
    "limit": 10
  }'
```

---

## Comparison Matrix

| Feature | API Keys | Cognito JWT | Custom JWT |
|---------|----------|-------------|------------|
| **Setup Time** | 10 min | 1-2 hours | 2-3 hours |
| **User Management** | Manual | ✅ Built-in | Code required |
| **Scalability** | ✅ High | ✅ High | ⚠️ Medium |
| **Cost** | Free | $0.0055/MAU | Free |
| **Fine-grained Permissions** | ❌ No | ✅ Yes | ✅ Yes |
| **MFA Support** | ❌ No | ✅ Yes | Code required |
| **Social Login** | ❌ No | ✅ Yes | Code required |
| **Maintenance** | ✅ Low | ✅ Low | ⚠️ High |
| **Best For** | B2B APIs | SaaS apps | Custom needs |

---

## My Recommendation for Your Public API

### **Use AWS Cognito + JWT** ⭐

**Why:**
1. ✅ Industry-standard JWT tokens
2. ✅ No code changes in your Lambda
3. ✅ Built-in user management
4. ✅ Scalable to millions of users
5. ✅ MFA & social login ready
6. ✅ Free for first 50k users

**Implementation Plan:**
1. **Week 1, Day 1**: Set up Cognito (1-2 hours)
2. **Week 1, Day 2**: Test with Postman (30 min)
3. **Week 1, Day 3**: Build signup/login UI (1 day)
4. **Week 1, Day 4**: Deploy to production
5. **Week 1, Day 5**: Monitor & iterate

---

## Quick Start Scripts

I'll create automated scripts for you in the next response!


