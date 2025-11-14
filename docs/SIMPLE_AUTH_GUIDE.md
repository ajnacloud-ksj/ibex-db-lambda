# Simple Authentication Guide - START HERE

## 🤔 I'm Confused, Help!

**Question:** "Who runs these scripts for new users?"

**Answer:** You're mixing two things:

### 1. **YOU** (API Provider)
- Run setup scripts **ONCE**
- This protects your API

### 2. **YOUR CUSTOMERS** (End Users)
- Sign up / Get API key
- Use your API

---

## 🎯 The Simple Truth

You have **TWO realistic options:**

### Option A: API Keys (SIMPLEST) ⭐ **RECOMMENDED TO START**

```
┌─────────────────────────────────────────────────┐
│  HOW IT WORKS (API Keys)                        │
├─────────────────────────────────────────────────┤
│                                                 │
│  [ONE TIME - You do this]                       │
│  1. Run: ./scripts/setup_api_keys.sh           │
│     Time: 10 minutes                            │
│     Result: Your API now requires keys         │
│                                                 │
│  [WHEN YOU GET A CUSTOMER]                      │
│  2. AWS Console → API Gateway → API Keys       │
│     → Click "Create API Key"                    │
│     → Copy key: abc123xyz...                    │
│     → Email to customer                         │
│     Time: 30 seconds per customer               │
│                                                 │
│  [YOUR CUSTOMER USES IT]                        │
│  3. Customer calls API:                         │
│     curl -H "x-api-key: abc123xyz" \           │
│          https://your-api.com/...               │
│                                                 │
│  DONE! ✅                                       │
└─────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Setup: 10 minutes, ONE TIME
- ✅ Zero ongoing maintenance
- ✅ FREE forever
- ✅ Good for B2B (you control who gets access)
- ✅ Can revoke keys anytime

**Cons:**
- ⚠️ Manual: You create each key
- ⚠️ No self-service signup
- ⚠️ Keys don't expire (but you can revoke)

**Perfect for:**
- Partner APIs
- B2B integrations
- 5-100 customers
- MVP/early stage

---

### Option B: Cognito (AUTOMATED) 🚀 **BETTER FOR SCALE**

```
┌─────────────────────────────────────────────────┐
│  HOW IT WORKS (Cognito)                         │
├─────────────────────────────────────────────────┤
│                                                 │
│  [ONE TIME - You do this]                       │
│  1. Run: ./scripts/setup_cognito_auth.sh       │
│     Time: 1-2 hours                             │
│     Result: Cognito user pool created          │
│                                                 │
│  2. Deploy signup page (I'll provide HTML)      │
│     Time: 30 minutes                            │
│     Result: https://your-site.com/signup        │
│                                                 │
│  [YOUR CUSTOMER SIGNS UP - AUTOMATIC]           │
│  3. Customer visits: https://your-site.com/signup│
│     → Enters email/password                     │
│     → Gets verification email                   │
│     → Clicks link                               │
│     → Account active!                           │
│     Time: 2 minutes (they do it themselves!)    │
│                                                 │
│  [YOUR CUSTOMER LOGS IN - AUTOMATIC]            │
│  4. Customer visits: https://your-site.com/login│
│     → Enters email/password                     │
│     → Gets JWT token                            │
│     → Uses token:                               │
│       curl -H "Authorization: Bearer JWT..." \  │
│            https://your-api.com/...             │
│                                                 │
│  FULLY AUTOMATED! ✅                            │
└─────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Fully automated self-service
- ✅ Customers sign up themselves
- ✅ FREE for first 50k users
- ✅ Scalable to millions
- ✅ Tokens expire automatically (secure!)
- ✅ Password reset built-in
- ✅ Can add social login (Google, etc.)

**Cons:**
- ⚠️ Initial setup: 1-2 hours
- ⚠️ Need to host signup/login page

**Perfect for:**
- SaaS products
- Consumer apps
- 100+ customers
- Self-service model

---

## 🎯 My Recommendation

### **START with Option A (API Keys)**

**Why:**
1. ✅ 10 minutes setup
2. ✅ Zero complexity
3. ✅ Works great for first 50 customers
4. ✅ You can switch to Cognito later (no migration!)

**When to switch to Option B (Cognito):**
- When you have 50+ customers
- When manual key creation becomes a pain
- When customers want self-service

---

## 📋 Step-by-Step: API Keys (RECOMMENDED)

### Step 1: Run Setup Script (10 min)

```bash
cd /Users/parameshnalla/ajna/ajna-expriements/other-repos/ibex-db-lambda

# Make executable
chmod +x scripts/setup_api_keys.sh

# Run it
./scripts/setup_api_keys.sh
```

**What it does:**
1. Creates usage plan (rate limits)
2. Creates your first API key
3. Requires API key for all requests
4. Deploys changes

**Output:**
```
API Key for customer-1:
  a1b2c3d4e5f6g7h8i9j0

⚠️ SAVE THIS KEY! It won't be shown again.
```

### Step 2: Test It

```bash
# WITHOUT key - should fail
curl -X POST "https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda" \
  -H "Content-Type: application/json" \
  -d '{"operation":"LIST_TABLES","tenant_id":"test-tenant","namespace":"default"}'

# Response: {"message":"Forbidden"}


# WITH key - should work
curl -X POST "https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda" \
  -H "x-api-key: a1b2c3d4e5f6g7h8i9j0" \
  -H "Content-Type: application/json" \
  -d '{"operation":"LIST_TABLES","tenant_id":"test-tenant","namespace":"default"}'

# Response: {"success":true,"tables":[...]}
```

### Step 3: Create Keys for Customers (30 sec each)

**Option A: AWS Console (Easiest)**

1. Go to: https://console.aws.amazon.com/apigateway
2. Click: **API Keys** (left sidebar)
3. Click: **Actions** → **Create API Key**
4. Enter:
   - Name: `customer-name` (e.g., "acme-corp")
   - Description: Optional
5. Click: **Save**
6. **Copy the API key value** (shows only once!)
7. Email to customer

**Option B: AWS CLI (Faster for many keys)**

```bash
# Create key
aws apigateway create-api-key \
  --name "acme-corp" \
  --enabled \
  --region ap-south-1 \
  --query '{KeyId:id,KeyValue:value}' \
  --output json

# Associate with usage plan (so it works)
aws apigateway create-usage-plan-key \
  --usage-plan-id <YOUR_PLAN_ID> \
  --key-id <KEY_ID_FROM_ABOVE> \
  --key-type API_KEY \
  --region ap-south-1
```

### Step 4: Give Key to Customer

**Email template:**

```
Subject: Your API Key for Ibex DB

Hi [Customer Name],

Your API key: a1b2c3d4e5f6g7h8i9j0

Usage:
curl -X POST "https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda" \
  -H "x-api-key: a1b2c3d4e5f6g7h8i9j0" \
  -H "Content-Type: application/json" \
  -d '{"operation":"LIST_TABLES","tenant_id":"your-tenant","namespace":"default"}'

Rate limits:
- 100 requests/second
- 1,000,000 requests/month

Documentation: [link to your docs]

Questions? Reply to this email.

Thanks!
```

### Step 5: Monitor Usage

```bash
# View usage for a key
aws apigateway get-usage \
  --usage-plan-id <PLAN_ID> \
  --key-id <KEY_ID> \
  --start-date 2025-11-01 \
  --end-date 2025-11-30 \
  --region ap-south-1
```

### Step 6: Revoke Key (if needed)

```bash
# Disable key
aws apigateway update-api-key \
  --api-key <KEY_ID> \
  --patch-operations op=replace,path=/enabled,value=false \
  --region ap-south-1
```

---

## 🔄 When to Switch to Cognito

**Switch when:**
- ✅ You have 50+ customers
- ✅ Manual key creation is annoying
- ✅ Customers want self-service
- ✅ You want to offer free tier + paid plans

**Migration path:**
1. Keep API keys working (don't remove)
2. Add Cognito in parallel (run setup script)
3. New customers use Cognito
4. Old customers can stay on API keys
5. Gradually migrate if needed

**No downtime, no customer disruption!**

---

## 📊 Comparison Table

| Feature | API Keys | Cognito |
|---------|----------|---------|
| **Setup time** | 10 min | 1-2 hours |
| **Cost** | FREE | FREE (50k users) |
| **New customer** | Manual (30 sec) | Automatic |
| **Maintenance** | Zero | Zero |
| **Self-service** | ❌ No | ✅ Yes |
| **Password reset** | N/A | ✅ Built-in |
| **Rate limiting** | ✅ Yes | ✅ Yes |
| **Revocation** | ✅ Yes | ✅ Yes |
| **Best for** | B2B, MVP | SaaS, scale |

---

## ❓ FAQ

### Q: Can I use both API Keys AND Cognito?
**A:** Yes! You can add Cognito later without removing API keys.

### Q: What if a customer loses their API key?
**A:** Create a new key for them, delete the old one.

### Q: How many keys can I create?
**A:** Unlimited (AWS limit: 10,000 per account)

### Q: Can I change rate limits per customer?
**A:** Yes, create multiple usage plans with different limits.

### Q: What if I want to switch to Cognito later?
**A:** Just run the Cognito setup script. API keys keep working.

### Q: Do API keys expire?
**A:** No, but you can revoke them anytime.

### Q: Is this secure enough for production?
**A:** Yes! API keys are standard for B2B APIs. Add HTTPS (you have this).

---

## 🚀 Quick Start (5 commands)

```bash
# 1. Go to project directory
cd /Users/parameshnalla/ajna/ajna-expriements/other-repos/ibex-db-lambda

# 2. Make script executable
chmod +x scripts/setup_api_keys.sh

# 3. Run setup (10 minutes)
./scripts/setup_api_keys.sh

# 4. Test without key (should fail)
curl -X POST "https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda" \
  -H "Content-Type: application/json" \
  -d '{"operation":"LIST_TABLES","tenant_id":"test-tenant","namespace":"default"}'

# 5. Test with key (should work)
# Use the key from step 3 output
curl -X POST "https://dhxby8kzg1.execute-api.ap-south-1.amazonaws.com/default/ibex-db-lambda" \
  -H "x-api-key: YOUR_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"operation":"LIST_TABLES","tenant_id":"test-tenant","namespace":"default"}'
```

**DONE! Your API is now protected.** ✅

---

## 💡 Bottom Line

**Don't overthink it!**

1. **Start with API Keys** (10 min setup)
2. Create keys manually for first 50 customers (30 sec each)
3. If it becomes a pain, switch to Cognito
4. Both are FREE for most use cases

**You can always upgrade later with zero downtime.**

---

## 📞 Need Help?

1. Run into issues? Check: `docs/AUTHENTICATION_GUIDE.md`
2. Want Cognito instead? Run: `./scripts/setup_cognito_auth.sh`
3. Questions? Ask me!

---

**Pick what's simple and works. You can always improve later.** 🎯

