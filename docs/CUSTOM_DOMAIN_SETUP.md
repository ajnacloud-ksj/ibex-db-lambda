# Custom Domain Setup Issue & Fix

## Current Status

### ✅ What's Working
- **API Key**: `McuMsuWDXo1g9zqLBBzVy3uXsIKDklGT8GbIhpyl` ✅
- **Original URL**: `https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda` ✅

### ❌ What's Not Working
- **Custom Domain**: `https://smartlink.ajna.cloud/ibexdb` ❌
- **Error**: `{"message":"Missing Authentication Token"}`

---

## Problem

The custom domain `smartlink.ajna.cloud` is configured, but the path mapping isn't correctly pointing to your API Gateway stage.

---

## Solution

### Option 1: Fix the Path Mapping (Recommended)

**In AWS Console:**

1. Go to **API Gateway Console**
2. Click **Custom Domain Names** (left sidebar)
3. Click: `smartlink.ajna.cloud`
4. Under **API mappings**, you should see:
   - Path: `ibexdb`
   - Destination: Your API
   - Stage: `default`

**The issue**: The path mapping might be incorrect. Fix it:

1. Click **Edit** on the mapping
2. Set:
   - **Path**: `ibexdb`
   - **API**: Select `ibex-db-lambda` (or your API ID: `dhxby8kzg1`)
   - **Stage**: `default`
3. Click **Save**

**Wait 5 minutes** for CloudFront to update, then test:

```bash
curl -X POST "https://smartlink.ajna.cloud/ibexdb" \
  -H "x-api-key: McuMsuWDXo1g9zqLBBzVy3uXsIKDklGT8GbIhpyl" \
  -H "Content-Type: application/json" \
  -d '{"operation":"LIST_TABLES","tenant_id":"test-tenant","namespace":"default"}'
```

---

### Option 2: Use Root Path (Simpler)

Instead of `/ibexdb`, use the root path `/`:

1. Go to **API Gateway Console** → **Custom Domain Names** → `smartlink.ajna.cloud`
2. **Delete** the current mapping (path: `ibexdb`)
3. **Create** new mapping:
   - **Path**: `` (empty / root)
   - **API**: `ibex-db-lambda`
   - **Stage**: `default`
4. Click **Save**

**Then use:**
```bash
https://smartlink.ajna.cloud  # No /ibexdb path!
```

---

### Option 3: Use Subdomain (Cleanest)

Create a subdomain instead of a path:

1. In **Route 53**, create:
   - **Domain**: `ibexdb.ajna.cloud` or `api.ajna.cloud`
2. In **API Gateway** → **Custom Domain Names**:
   - Create new custom domain: `ibexdb.ajna.cloud`
   - Map to your API (stage: `default`)
3. Use:
```bash
https://ibexdb.ajna.cloud
```

---

## Quick Fix (AWS CLI)

```bash
# Get your custom domain details
aws apigateway get-domain-name \
  --domain-name smartlink.ajna.cloud \
  --region ap-south-1

# Update the mapping
aws apigatewayv2 update-api-mapping \
  --api-id dhxby8kzg1 \
  --domain-name smartlink.ajna.cloud \
  --api-mapping-key ibexdb \
  --stage default \
  --region ap-south-1
```

---

## For Now: Use the Working URL

**Until custom domain is fixed, use:**

```bash
# Working URL (original)
https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda

# API Key (works!)
x-api-key: McuMsuWDXo1g9zqLBBzVy3uXsIKDklGT8GbIhpyl
```

**Test:**
```bash
curl -X POST "https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda" \
  -H "x-api-key: McuMsuWDXo1g9zqLBBzVy3uXsIKDklGT8GbIhpyl" \
  -H "Content-Type: application/json" \
  -d '{"operation":"LIST_TABLES","tenant_id":"test-tenant","namespace":"default"}'

# Response: {"success":true,"tables":["users","products",...]}
```

---

## Testing Custom Domain After Fix

```bash
# Should work after fix:
curl -X POST "https://smartlink.ajna.cloud/ibexdb" \
  -H "x-api-key: McuMsuWDXo1g9zqLBBzVy3uXsIKDklGT8GbIhpyl" \
  -H "Content-Type: application/json" \
  -d '{"operation":"LIST_TABLES","tenant_id":"test-tenant","namespace":"default"}'
```

---

## Summary

✅ **API Key is working**: `McuMsuWDXo1g9zqLBBzVy3uXsIKDklGT8GbIhpyl`  
✅ **Original URL works**: `https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda`  
⚠️ **Custom domain needs fix**: Path mapping configuration issue  

**Action**: Fix the API mapping in API Gateway console (5 minutes)

---

## Updated Postman Collections

I've updated the Postman collections with your working URL and API key!

- `postman/environments/Production.postman_environment.json`
- Collections use: `{{baseUrl}}` and `{{api_key}}`

