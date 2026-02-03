# Nested Data Operations - Complete Summary

## Quick Answer

**Q: How do updates or queries on nested objects and arrays work?**

**A: Use dot notation for nested fields, and read-modify-write pattern for partial updates.**

---

## Querying Nested Data

### ✅ Nested Objects (Structs) - Fully Supported

```json
{
  "operation": "QUERY",
  "table": "users",
  "projection": ["name", "address.city", "address.state"],
  "filters": [
    {"field": "address.state", "operator": "eq", "value": "CA"}
  ],
  "sort": [{"field": "address.city", "order": "asc"}]
}
```

**What works**:
- ✅ Select nested fields: `address.city`
- ✅ Filter by nested fields: `address.state = 'CA'`
- ✅ Sort by nested fields
- ✅ Group by nested fields
- ✅ Aggregate on nested fields

### ⚠️ Arrays - Limited Support

```json
{
  "operation": "QUERY",
  "table": "products",
  "filters": [
    {"field": "tags", "operator": "like", "value": "%electronics%"}
  ]
}
```

**What works**:
- ✅ Query returns entire array
- ⚠️ Filter with LIKE (converts array to string)
- ❌ Filter by specific array element
- ❌ Filter by array length
- ❌ Complex array operations

**Workaround**: Query all data, filter in application
```python
results = query({"table": "products"})
filtered = [r for r in results if "electronics" in r["tags"]]
```

---

## Updating Nested Data

### ✅ Replace Entire Nested Object

```json
{
  "operation": "UPDATE",
  "table": "users",
  "filters": [{"field": "user_id", "operator": "eq", "value": 1}],
  "updates": {
    "address": {
      "street": "456 New St",
      "city": "Los Angeles",
      "state": "CA",
      "zip_code": "90001"
    }
  }
}
```

**Result**: Entire `address` object is replaced

### ⚠️ Update Single Nested Field (Read-Modify-Write)

**Cannot do this directly**:
```json
{
  "updates": {
    "address.city": "Seattle"  // ❌ Not supported
  }
}
```

**Must use Read-Modify-Write pattern**:

```python
# 1. Read current record
response = query({
  "table": "users",
  "filters": [{"field": "user_id", "operator": "eq", "value": 1}]
})
user = response["data"]["records"][0]

# 2. Modify the nested field
user["address"]["city"] = "Seattle"

# 3. Write back the entire object
update({
  "table": "users",
  "filters": [{"field": "user_id", "operator": "eq", "value": 1}],
  "updates": {
    "address": user["address"]  # Full object
  }
})
```

### ✅ Replace Entire Array

```json
{
  "operation": "UPDATE",
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}],
  "updates": {
    "tags": ["electronics", "computers", "sale", "featured"]
  }
}
```

### ⚠️ Add/Remove Array Elements (Read-Modify-Write)

```python
# Get current product
product = query({
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}]
})["data"]["records"][0]

# Modify array
product["tags"].append("new-tag")  # Add
# or
product["tags"].remove("old-tag")  # Remove

# Write back
update({
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}],
  "updates": {
    "tags": product["tags"]
  }
})
```

---

## How It Works Internally

### Storage (Apache Iceberg + Parquet)

```
Parquet Column Layout:
┌──────────────────────────────────────────┐
│ Columnar Storage for Nested Data        │
├──────────────────────────────────────────┤
│ user_id:        [1, 2, 3]                │
│ name:           ["John", "Jane", "Bob"]  │
│ address.street: ["123 Main", ...]        │
│ address.city:   ["SF", "NY", "LA"]       │
│ address.state:  ["CA", "NY", "CA"]       │
└──────────────────────────────────────────┘
```

**Benefits**:
- ✅ Efficient columnar storage
- ✅ Fast queries on nested fields
- ✅ Predicate pushdown works on nested fields
- ✅ Good compression

### Queries (DuckDB)

DuckDB natively understands nested types:

```sql
-- Your API call:
{
  "projection": ["name", "address.city"],
  "filters": [{"field": "address.state", "operator": "eq", "value": "CA"}]
}

-- Translates to SQL:
SELECT name, address.city
FROM iceberg_scan('metadata.json')
WHERE address.state = 'CA'
```

DuckDB:
1. Reads Parquet files with nested schema
2. Understands struct/array types
3. Supports dot notation
4. Returns nested data as JSON

---

## Complete Examples

### Example 1: User Management

```python
# CREATE TABLE
{
  "operation": "CREATE_TABLE",
  "table": "users",
  "schema": {
    "fields": {
      "user_id": {"type": "long", "required": true},
      "name": {"type": "string", "required": true},
      "address": {
        "type": "struct",
        "fields": {
          "street": {"type": "string"},
          "city": {"type": "string"},
          "state": {"type": "string"},
          "zip": {"type": "string"}
        }
      }
    }
  }
}

# WRITE
{
  "operation": "WRITE",
  "table": "users",
  "records": [{
    "user_id": 1,
    "name": "John Doe",
    "address": {
      "street": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "zip": "94105"
    }
  }]
}

# QUERY - Find users in California
{
  "operation": "QUERY",
  "table": "users",
  "projection": ["name", "address.city", "address.state"],
  "filters": [
    {"field": "address.state", "operator": "eq", "value": "CA"}
  ]
}

# Returns:
{
  "name": "John Doe",
  "address.city": "San Francisco",
  "address.state": "CA"
}

# UPDATE - Change entire address
{
  "operation": "UPDATE",
  "table": "users",
  "filters": [{"field": "user_id", "operator": "eq", "value": 1}],
  "updates": {
    "address": {
      "street": "456 New Ave",
      "city": "Los Angeles",
      "state": "CA",
      "zip": "90001"
    }
  }
}

# UPDATE - Change only city (read-modify-write)
user = query(...)["records"][0]
user["address"]["city"] = "Seattle"
update({"updates": {"address": user["address"]}})
```

### Example 2: Products with Tags

```python
# CREATE TABLE
{
  "operation": "CREATE_TABLE",
  "table": "products",
  "schema": {
    "fields": {
      "product_id": {"type": "long", "required": true},
      "name": {"type": "string", "required": true},
      "tags": {
        "type": "array",
        "items": {"type": "string"}
      }
    }
  }
}

# WRITE
{
  "operation": "WRITE",
  "table": "products",
  "records": [{
    "product_id": 1,
    "name": "Laptop",
    "tags": ["electronics", "computers"]
  }]
}

# QUERY - Find products with 'electronics' tag
{
  "operation": "QUERY",
  "table": "products",
  "filters": [
    {"field": "tags", "operator": "like", "value": "%electronics%"}
  ]
}

# UPDATE - Replace all tags
{
  "operation": "UPDATE",
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}],
  "updates": {
    "tags": ["electronics", "computers", "bestseller"]
  }
}

# UPDATE - Add a tag (read-modify-write)
product = query(...)["records"][0]
product["tags"].append("sale")
update({"updates": {"tags": product["tags"]}})
```

### Example 3: Orders with Items (Complex)

```python
# CREATE TABLE
{
  "operation": "CREATE_TABLE",
  "table": "orders",
  "schema": {
    "fields": {
      "order_id": {"type": "long", "required": true},
      "customer_id": {"type": "long", "required": true},
      "items": {
        "type": "array",
        "items": {
          "type": "struct",
          "fields": {
            "product_id": {"type": "long"},
            "name": {"type": "string"},
            "quantity": {"type": "integer"},
            "price": {"type": "double"}
          }
        }
      }
    }
  }
}

# WRITE
{
  "operation": "WRITE",
  "table": "orders",
  "records": [{
    "order_id": 1001,
    "customer_id": 501,
    "items": [
      {"product_id": 1, "name": "Laptop", "quantity": 1, "price": 999.99},
      {"product_id": 2, "name": "Mouse", "quantity": 2, "price": 24.99}
    ]
  }]
}

# QUERY - Get order
{
  "operation": "QUERY",
  "table": "orders",
  "filters": [
    {"field": "order_id", "operator": "eq", "value": 1001}
  ]
}

# Returns full nested structure:
{
  "order_id": 1001,
  "customer_id": 501,
  "items": [
    {"product_id": 1, "name": "Laptop", "quantity": 1, "price": 999.99},
    {"product_id": 2, "name": "Mouse", "quantity": 2, "price": 24.99}
  ]
}

# UPDATE - Add item to order (read-modify-write)
order = query(...)["records"][0]
order["items"].append({
  "product_id": 3,
  "name": "Keyboard",
  "quantity": 1,
  "price": 149.99
})
update({
  "filters": [{"field": "order_id", "operator": "eq", "value": 1001}],
  "updates": {"items": order["items"]}
})

# Calculate total in application
total = sum(item["quantity"] * item["price"] for item in order["items"])
```

---

## Feature Support Matrix

| Feature | Nested Objects (Struct) | Arrays |
|---------|-------------------------|--------|
| **CREATE TABLE** | ✅ | ✅ |
| **WRITE** | ✅ | ✅ |
| **QUERY - Select** | ✅ Dot notation | ✅ Full array |
| **QUERY - Filter** | ✅ Any nested field | ⚠️ LIKE only |
| **QUERY - Sort** | ✅ | ❌ |
| **QUERY - Group** | ✅ | ❌ |
| **UPDATE - Full replace** | ✅ | ✅ |
| **UPDATE - Partial** | ⚠️ Read-modify-write | ⚠️ Read-modify-write |
| **Nesting** | ✅ Unlimited | ✅ Unlimited |

**Legend**:
- ✅ Fully supported
- ⚠️ Workaround available
- ❌ Not supported

---

## Key Limitations & Workarounds

### 1. Cannot Update Single Nested Field Directly

**Limitation**:
```json
{"updates": {"address.city": "Seattle"}}  // ❌
```

**Workaround**: Read-modify-write (shown in examples above)

### 2. Limited Array Filtering

**Limitation**:
```json
{"filters": [{"field": "tags[0]", "operator": "eq", "value": "x"}]}  // ❌
```

**Workaround**: Use LIKE or filter in application

### 3. No Array Aggregations

**Limitation**: Cannot count array elements in SQL

**Workaround**: Process in application
```python
results = query(...)
for record in results:
    tag_count = len(record["tags"])
```

---

## Best Practices

1. **Use dot notation** for nested field queries
2. **Read-modify-write** for partial updates
3. **Keep nesting shallow** (2-3 levels max)
4. **Use structs for related data** (address, contact info)
5. **Use arrays for collections** (tags, items, emails)
6. **Filter in database** when possible (use nested field filters)
7. **Batch updates** to minimize read-modify-write cycles

---

## Test Files

Try these examples:

| File | What It Tests |
|------|---------------|
| `lambda_test_events/13_create_table_with_struct.json` | Create table with nested object |
| `lambda_test_events/14_write_users_with_struct.json` | Write nested object data |
| `lambda_test_events/18_query_nested_struct.json` | Query nested fields with filters |
| `lambda_test_events/19_update_nested_struct.json` | Update nested object |
| `lambda_test_events/20_query_array_filter.json` | Filter by array content |
| `lambda_test_events/21_update_array.json` | Update array |

---

## Documentation

| Document | Purpose |
|----------|---------|
| **`docs/NESTED_DATA_QUICK_REF.md`** | ⭐ Quick reference (START HERE) |
| **`docs/QUERYING_NESTED_DATA.md`** | Complete guide with examples |
| **`docs/COMPLEX_TYPES_GUIDE.md`** | Schema design guide |
| **`docs/COMPLEX_TYPES_QUICK_REFERENCE.md`** | Type definitions cheat sheet |

---

## Summary

### Querying

✅ **Nested objects**: Full support with dot notation  
⚠️ **Arrays**: Limited filtering, full array returned  
✅ **Predicate pushdown**: Works on nested fields  
✅ **DuckDB**: Native nested type support  

### Updating

✅ **Full replace**: Both objects and arrays  
⚠️ **Partial update**: Requires read-modify-write  
✅ **Versioning**: Works correctly with nested data  
✅ **ACID**: Full transaction guarantees  

### Storage

✅ **Columnar**: Efficient Parquet storage  
✅ **Compression**: Good compression ratios  
✅ **Schema evolution**: Add new nested fields  
✅ **Performance**: Fast queries with proper filters  

---

**You now have full support for querying and updating nested objects and arrays! 🎉**


