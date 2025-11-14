# Schema Format Reference

**IMPORTANT**: The Lambda handler uses a **dictionary-based schema format**, not an array.

## ✅ Correct Format

```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "test-tenant",
  "namespace": "default",
  "table": "products",
  "schema": {
    "fields": {
      "product_id": {"type": "long", "required": true},
      "name": {"type": "string", "required": true},
      "category": {"type": "string", "required": false},
      "price": {"type": "double", "required": true},
      "stock": {"type": "integer", "required": false}
    }
  }
}
```

### Key Points:
- ✅ `schema` is an **object**, not an array
- ✅ Contains a `fields` key which is a dictionary
- ✅ Each field is a key-value pair: `"field_name": {config}`
- ✅ Use `required: true/false` (not `nullable`)
- ✅ `required: true` means field must be present
- ✅ `required: false` means field is optional

---

## ❌ Wrong Format (Do Not Use)

```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "test-tenant",
  "namespace": "default",
  "table": "products",
  "schema": [
    {"name": "product_id", "type": "long", "nullable": false},
    {"name": "name", "type": "string", "nullable": false},
    {"name": "category", "type": "string", "nullable": true},
    {"name": "price", "type": "double", "nullable": false},
    {"name": "stock", "type": "integer", "nullable": true}
  ]
}
```

### Why This Fails:
- ❌ `schema` is an array (not allowed)
- ❌ Uses `"name"` key (should be field name directly)
- ❌ Uses `nullable` (should be `required`)
- ❌ Pydantic validation error: "Input should be a valid dictionary"

---

## 📋 Supported Field Types

| Type | Description | Example |
|------|-------------|---------|
| `string` | Text data | `"John Doe"` |
| `long` | 64-bit integer | `123456789` |
| `integer` | 32-bit integer | `42` |
| `double` | Floating point | `99.99` |
| `float` | Single precision | `3.14` |
| `boolean` | True/False | `true` |
| `date` | Date only | `"2025-01-15"` |
| `timestamp` | Date+Time | `"2025-01-15T10:30:00Z"` |
| `binary` | Byte data | Base64 encoded |

---

## 🎯 Complete Examples

### Example 1: Users Table
```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "test-tenant",
  "namespace": "default",
  "table": "users",
  "schema": {
    "fields": {
      "id": {"type": "long", "required": true},
      "name": {"type": "string", "required": true},
      "email": {"type": "string", "required": false},
      "age": {"type": "integer", "required": false},
      "is_active": {"type": "boolean", "required": false},
      "created_at": {"type": "timestamp", "required": false}
    }
  }
}
```

### Example 2: Orders Table
```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "test-tenant",
  "namespace": "default",
  "table": "orders",
  "schema": {
    "fields": {
      "order_id": {"type": "long", "required": true},
      "customer_id": {"type": "long", "required": true},
      "total_amount": {"type": "double", "required": true},
      "status": {"type": "string", "required": true},
      "order_date": {"type": "date", "required": true},
      "notes": {"type": "string", "required": false}
    }
  }
}
```

### Example 3: Products Table (from AWS collection)
```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "test-tenant",
  "namespace": "default",
  "table": "products",
  "schema": {
    "fields": {
      "product_id": {"type": "long", "required": true},
      "name": {"type": "string", "required": true},
      "category": {"type": "string", "required": false},
      "price": {"type": "double", "required": true},
      "stock": {"type": "integer", "required": false},
      "is_available": {"type": "boolean", "required": false}
    }
  }
}
```

---

## 🔍 Validation Rules

### Required vs Optional
```json
// required: true - Field MUST be present in all WRITE operations
{"name": {"type": "string", "required": true}}

// required: false - Field is optional, can be omitted
{"email": {"type": "string", "required": false}}
```

### When to Use Required
- ✅ Primary keys (id, order_id, etc.)
- ✅ Core business fields (name, price, status)
- ✅ Fields needed for queries/joins

### When to Use Optional
- ✅ Nullable fields (email, notes, description)
- ✅ Optional metadata (tags, categories)
- ✅ Timestamps that auto-generate (created_at, updated_at)

---

## 🐛 Common Errors

### Error 1: Array Schema
**Error Message:**
```
"Validation error: schema - Input should be a valid dictionary or instance of SchemaDefinition"
```

**Cause:** Used array format instead of dictionary  
**Fix:** Change `"schema": [...]` to `"schema": {"fields": {...}}`

---

### Error 2: Missing "fields" Key
**Request:**
```json
{
  "schema": {
    "product_id": {"type": "long", "required": true}
  }
}
```

**Error Message:**
```
"Validation error: schema - Field required"
```

**Fix:** Add `fields` wrapper:
```json
{
  "schema": {
    "fields": {
      "product_id": {"type": "long", "required": true}
    }
  }
}
```

---

### Error 3: Using "nullable" Instead of "required"
**Wrong:**
```json
{"name": {"type": "string", "nullable": false}}
```

**Correct:**
```json
{"name": {"type": "string", "required": true}}
```

**Note:** `nullable: false` is OPPOSITE of `required: true`
- `nullable: false` = must have value (not null)
- `required: true` = must be present in input

---

## 📝 Quick Conversion Guide

| Old Format (Array) | New Format (Dictionary) |
|--------------------|------------------------|
| `"schema": [...]` | `"schema": {"fields": {...}}` |
| `{"name": "id", "type": "long"}` | `"id": {"type": "long"}` |
| `"nullable": false` | `"required": true` |
| `"nullable": true` | `"required": false` |

---

## ✅ Testing Your Schema

### Test 1: Validate Format
```bash
curl -X POST "https://YOUR-API-GATEWAY-URL" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "CREATE_TABLE",
    "tenant_id": "test-tenant",
    "namespace": "default",
    "table": "test_table",
    "schema": {
      "fields": {
        "id": {"type": "long", "required": true},
        "name": {"type": "string", "required": true}
      }
    }
  }'
```

**Expected Success:**
```json
{
  "success": true,
  "table_created": true,
  "table_existed": false
}
```

### Test 2: Write Data
```bash
curl -X POST "https://YOUR-API-GATEWAY-URL" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "WRITE",
    "tenant_id": "test-tenant",
    "namespace": "default",
    "table": "test_table",
    "records": [
      {"id": 1, "name": "Test 1"},
      {"id": 2, "name": "Test 2"}
    ]
  }'
```

---

## 🎓 Best Practices

### 1. Always Include Required Fields
```json
{
  "fields": {
    "id": {"type": "long", "required": true},  // Primary key
    "created_at": {"type": "timestamp", "required": false}  // Auto-generated
  }
}
```

### 2. Use Appropriate Types
```json
{
  "price": {"type": "double", "required": true},    // Not "float" for money
  "quantity": {"type": "integer", "required": true}, // Not "long" for small numbers
  "email": {"type": "string", "required": false}     // Nullable strings
}
```

### 3. Keep Schema Simple
- ✅ Use flat structures when possible
- ✅ Avoid nested complex types for now
- ✅ Use appropriate types (don't use string for everything)

---

## 📚 Additional Resources

- **Main README**: `../README.md`
- **Postman Collections**: `collections/`
- **Environments**: `environments/`
- **Models Reference**: `../../src/models.py` (line 391-404)

---

## ✅ Summary

**DO:**
```json
"schema": {
  "fields": {
    "field_name": {"type": "string", "required": true}
  }
}
```

**DON'T:**
```json
"schema": [
  {"name": "field_name", "type": "string", "nullable": false}
]
```

---

**All Postman collections have been updated with the correct format!** 🎉

