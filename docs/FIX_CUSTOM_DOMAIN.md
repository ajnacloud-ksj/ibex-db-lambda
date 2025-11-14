# Fix Custom Domain - Step by Step

## 🔍 Problem Identified

**From your screenshot:**
- Custom Domain: `smartlink.ajna.cloud` ✅
- Path: `ibexdb` ✅
- **API**: `ibex_db` ❌
- **Stage**: `dev` ❌

**Your actual API:**
- API ID: `dhxby8kzg1`
- API Name: `ibex-db-lambda`
- **Stage**: `default` ✅

**Issue:** The mapping points to the wrong stage (`dev` instead of `default`)

---

## ✅ Solution: Update the API Mapping

### Step 1: Open API Gateway Console

1. Go to: https://console.aws.amazon.com/apigateway
2. Click **Custom domain names** (left sidebar)
3. Click: **smartlink.ajna.cloud**

### Step 2: Find the ibexdb Mapping

In the **API mappings** section, you should see:

```
API: ibex_db
Stage: dev
Path: ibexdb
```

### Step 3: Edit the Mapping

**Option A: Edit Existing Mapping (Easiest)**

1. Click the **Edit** button next to the `ibexdb` mapping
2. Change:
   - **Stage**: `dev` → **`default`**
   - **API**: Should be `ibex-db-lambda` (or API ID: `dhxby8kzg1`)
3. Click **Save**
4. **Wait 5 minutes** for CloudFront to propagate

**Option B: Delete and Recreate (If Edit Doesn't Work)**

1. Click the checkbox next to the `ibexdb` mapping
2. Click **Delete**
3. Click **Configure API mappings**
4. Click **Add new mapping**
5. Enter:
   - **API**: Select `ibex-db-lambda` (or enter `dhxby8kzg1`)
   - **Stage**: `default`
   - **Path**: `ibexdb`
6. Click **Save**
7. **Wait 5 minutes** for CloudFront to propagate

---

## 🧪 Test After Fix

**Wait 5-10 minutes**, then run:

```bash
curl -X POST "https://smartlink.ajna.cloud/ibexdb" \
  -H "x-api-key: McuMsuWDXo1g9zqLBBzVy3uXsIKDklGT8GbIhpyl" \
  -H "Content-Type: application/json" \
  -d '{"operation":"LIST_TABLES","tenant_id":"test-tenant","namespace":"default"}'
```

**Expected Response:**
```json
{
  "success": true,
  "tables": ["users", "products", ...]
}
```

---

## 🎯 Quick Fix Command (AWS CLI)

If you prefer command line:

```bash
# Get your custom domain details
aws apigatewayv2 get-api-mappings \
  --domain-name smartlink.ajna.cloud \
  --region ap-south-1

# Note the ApiMappingId for ibexdb path

# Update the mapping to use 'default' stage
aws apigatewayv2 update-api-mapping \
  --domain-name smartlink.ajna.cloud \
  --api-mapping-id <API_MAPPING_ID_FROM_ABOVE> \
  --api-id dhxby8kzg1 \
  --stage default \
  --region ap-south-1
```

---

## 📋 Verification Checklist

After making changes:

- [ ] Mapping shows: API = `ibex-db-lambda` (or `dhxby8kzg1`)
- [ ] Mapping shows: Stage = `default`
- [ ] Mapping shows: Path = `ibexdb`
- [ ] Waited 5-10 minutes for CloudFront
- [ ] Tested with curl command above
- [ ] Received `{"success":true,...}` response

---

## 🚀 After It's Working

### Update Postman Environment

1. Import: `postman/environments/Production_CustomDomain.postman_environment.json`
2. Change environment to: "Production - Custom Domain"
3. Test requests
4. All should work! ✅

### Your URLs

**Original (always works):**
```
https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda
```

**Custom Domain (after fix):**
```
https://smartlink.ajna.cloud/ibexdb
```

**Both use same API key:**
```
x-api-key: McuMsuWDXo1g9zqLBBzVy3uXsIKDklGT8GbIhpyl
```

---

## ❓ Troubleshooting

### Still getting 403?
- Check you're using the correct API in the mapping
- Verify the API ID is `dhxby8kzg1`
- Confirm stage is `default` (not `dev`)
- Wait the full 10 minutes for CloudFront

### Can't find ibex-db-lambda in API dropdown?
- Use API ID directly: `dhxby8kzg1`
- Or check if it's named differently in your AWS account

### Mapping keeps reverting?
- You might have multiple mappings with same path
- Delete all `ibexdb` mappings
- Create fresh one with correct settings

---

## 📸 What Your Mapping Should Look Like

**After fix:**

```
┌─────────────────────────────────────────────────────┐
│ API mappings                                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│ API             Stage      Path      Enabled       │
│ ───────────────────────────────────────────────    │
│ ibex-db-lambda  default    ibexdb    ✓             │
│ (dhxby8kzg1)                                        │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## ✅ Summary

**Current Problem:**
- Mapping points to `dev` stage
- Your API uses `default` stage
- Result: 403 error

**Fix:**
1. Edit mapping to use `default` stage
2. Wait 5-10 minutes
3. Test
4. ✅ Custom domain works!

**Estimated Time:** 15 minutes (including CloudFront wait)

