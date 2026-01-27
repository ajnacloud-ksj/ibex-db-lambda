# Querying and Updating Nested Data (Objects & Arrays)

## Overview

With complex types support, you can now query and update nested objects (structs) and arrays. This guide shows you how.

## Table of Contents
1. [Querying Nested Objects (Structs)](#querying-nested-objects)
2. [Querying Arrays](#querying-arrays)
3. [Updating Nested Objects](#updating-nested-objects)
4. [Updating Arrays](#updating-arrays)
5. [Advanced Patterns](#advanced-patterns)
6. [Limitations](#limitations)

---

## Querying Nested Objects (Structs)

### Setup Example

```json
{
  "operation": "CREATE_TABLE",
  "table": "users",
  "schema": {
    "fields": {
      "user_id": {"type": "long", "required": true},
      "name": {"type": "string", "required": true},
      "email": {"type": "string", "required": true},
      "address": {
        "type": "struct",
        "required": false,
        "fields": {
          "street": {"type": "string"},
          "city": {"type": "string"},
          "state": {"type": "string"},
          "zip_code": {"type": "string"}
        }
      }
    }
  }
}
```

### 1. Query All Data

```json
{
  "operation": "QUERY",
  "table": "users",
  "limit": 10
}
```

**Returns**:
```json
{
  "records": [
    {
      "user_id": 1,
      "name": "John Doe",
      "email": "john@example.com",
      "address": {
        "street": "123 Main St",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94105"
      }
    }
  ]
}
```

### 2. Select Specific Nested Fields (Dot Notation)

```json
{
  "operation": "QUERY",
  "table": "users",
  "projection": ["name", "email", "address.city", "address.state"]
}
```

**Returns**:
```json
{
  "records": [
    {
      "name": "John Doe",
      "email": "john@example.com",
      "address.city": "San Francisco",
      "address.state": "CA"
    }
  ]
}
```

**Note**: DuckDB returns nested field names with dot notation in the result.

### 3. Filter by Nested Field

```json
{
  "operation": "QUERY",
  "table": "users",
  "filters": [
    {"field": "address.state", "operator": "eq", "value": "CA"}
  ]
}
```

**Returns**: All users in California

### 4. Filter by Multiple Nested Fields

```json
{
  "operation": "QUERY",
  "table": "users",
  "filters": [
    {"field": "address.city", "operator": "eq", "value": "San Francisco"},
    {"field": "address.state", "operator": "eq", "value": "CA"}
  ]
}
```

**Returns**: Users in San Francisco, CA (both conditions must match)

### 5. Sort by Nested Field

```json
{
  "operation": "QUERY",
  "table": "users",
  "sort": [
    {"field": "address.city", "order": "asc"}
  ]
}
```

### 6. Aggregate on Nested Field

```json
{
  "operation": "QUERY",
  "table": "users",
  "aggregations": [
    {"function": "count", "field": null, "alias": "user_count"}
  ],
  "group_by": ["address.state"],
  "sort": [{"field": "user_count", "order": "desc"}]
}
```

**Returns**: Count of users per state

---

## Querying Arrays

### Setup Example

```json
{
  "operation": "CREATE_TABLE",
  "table": "products",
  "schema": {
    "fields": {
      "product_id": {"type": "long", "required": true},
      "name": {"type": "string", "required": true},
      "price": {"type": "double", "required": true},
      "tags": {
        "type": "array",
        "required": false,
        "items": {"type": "string"}
      }
    }
  }
}
```

**Sample Data**:
```json
{
  "operation": "WRITE",
  "table": "products",
  "records": [
    {
      "product_id": 1,
      "name": "Laptop",
      "price": 999.99,
      "tags": ["electronics", "computers", "bestseller"]
    },
    {
      "product_id": 2,
      "name": "Coffee Mug",
      "price": 12.99,
      "tags": ["home", "kitchen"]
    }
  ]
}
```

### 1. Query All (Arrays Returned as JSON)

```json
{
  "operation": "QUERY",
  "table": "products"
}
```

**Returns**:
```json
{
  "records": [
    {
      "product_id": 1,
      "name": "Laptop",
      "price": 999.99,
      "tags": ["electronics", "computers", "bestseller"]
    }
  ]
}
```

### 2. Filter by Array Content (Contains)

**Current Limitation**: Direct array filtering with our filter syntax is limited. However, you can use LIKE on the array:

```json
{
  "operation": "QUERY",
  "table": "products",
  "filters": [
    {"field": "tags", "operator": "like", "value": "%electronics%"}
  ]
}
```

**Note**: This converts array to string and searches. More advanced array operations require custom SQL.

### 3. Access Array Elements (Read-Only)

Arrays are returned as complete arrays in query results. Individual element access is not directly supported in the filter syntax but can be done in application code.

---

## Updating Nested Objects (Structs)

### 1. Update Entire Nested Object

```json
{
  "operation": "UPDATE",
  "table": "users",
  "filters": [
    {"field": "user_id", "operator": "eq", "value": 1}
  ],
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

**Result**: Replaces the entire `address` object with new values.

### 2. Update Top-Level Field, Keep Nested Object

```json
{
  "operation": "UPDATE",
  "table": "users",
  "filters": [
    {"field": "user_id", "operator": "eq", "value": 1}
  ],
  "updates": {
    "email": "newemail@example.com"
  }
}
```

**Result**: Updates email, `address` remains unchanged.

### 3. Update Nested Field (Requires Reading Current Value)

**Current Limitation**: You cannot directly update a single nested field like `address.city` without reading the full object first.

**Workaround**:
```python
# Step 1: Query current record
response = query({
  "table": "users",
  "filters": [{"field": "user_id", "operator": "eq", "value": 1}]
})

current_record = response["data"]["records"][0]
current_address = current_record["address"]

# Step 2: Modify the nested field
current_address["city"] = "Seattle"

# Step 3: Update with modified object
update({
  "table": "users",
  "filters": [{"field": "user_id", "operator": "eq", "value": 1}],
  "updates": {
    "address": current_address  # Full object with change
  }
})
```

**Why**: Iceberg/Parquet stores structs as complete objects, not individual fields.

---

## Updating Arrays

### 1. Replace Entire Array

```json
{
  "operation": "UPDATE",
  "table": "products",
  "filters": [
    {"field": "product_id", "operator": "eq", "value": 1}
  ],
  "updates": {
    "tags": ["electronics", "computers", "sale", "featured"]
  }
}
```

**Result**: Replaces entire array with new values.

### 2. Add Element to Array (Read-Modify-Write)

```python
# Step 1: Query current record
response = query({
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}]
})

current_tags = response["data"]["records"][0]["tags"]

# Step 2: Modify array
current_tags.append("new-tag")

# Step 3: Update
update({
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}],
  "updates": {
    "tags": current_tags
  }
})
```

### 3. Remove Element from Array (Read-Modify-Write)

```python
# Query, modify, update pattern
current_tags = [...get from query...]
current_tags.remove("old-tag")  # or current_tags = [t for t in current_tags if t != "old-tag"]

update({
  "updates": {"tags": current_tags}
})
```

---

## Advanced Patterns

### 1. Complex Nested Structure (Orders with Items)

**Schema**:
```json
{
  "order_id": {"type": "long"},
  "customer_id": {"type": "long"},
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
```

**Query Orders**:
```json
{
  "operation": "QUERY",
  "table": "orders",
  "filters": [
    {"field": "customer_id", "operator": "eq", "value": 501}
  ]
}
```

**Returns**:
```json
{
  "records": [
    {
      "order_id": 1001,
      "customer_id": 501,
      "items": [
        {"product_id": 1, "name": "Laptop", "quantity": 1, "price": 999.99},
        {"product_id": 2, "name": "Mouse", "quantity": 2, "price": 24.99}
      ]
    }
  ]
}
```

### 2. Update Complex Nested Structure

**Add Item to Order**:
```python
# Get current order
order = query(...)["data"]["records"][0]

# Add new item
new_item = {
  "product_id": 3,
  "name": "Keyboard",
  "quantity": 1,
  "price": 149.99
}
order["items"].append(new_item)

# Update order
update({
  "filters": [{"field": "order_id", "operator": "eq", "value": 1001}],
  "updates": {
    "items": order["items"]
  }
})
```

### 3. Query with Multiple Nested Levels

```json
{
  "operation": "QUERY",
  "table": "orders",
  "projection": [
    "order_id",
    "customer_id",
    "items"
  ],
  "filters": [
    {"field": "customer_id", "operator": "eq", "value": 501}
  ]
}
```

**Note**: You get the full `items` array in results. Filter/access individual array elements in your application code.

---

## How It Works Internally

### DuckDB's Nested Type Support

When you query, DuckDB:

1. **Reads Parquet files** with nested structures
2. **Understands column structure**:
   ```
   address STRUCT(
     street VARCHAR,
     city VARCHAR,
     state VARCHAR,
     zip_code VARCHAR
   )
   ```

3. **Supports dot notation** in SQL:
   ```sql
   SELECT name, address.city, address.state
   FROM users
   WHERE address.state = 'CA'
   ```

4. **Returns nested data** as JSON-compatible structures

### Iceberg's Storage

Parquet files store nested data efficiently:

```
Column Layout:
- user_id: [1, 2, 3]
- name: ["John", "Jane", "Bob"]
- address.street: ["123 Main", "456 Oak", "789 Pine"]
- address.city: ["SF", "NY", "LA"]
- address.state: ["CA", "NY", "CA"]
- address.zip_code: ["94105", "10001", "90001"]
```

**Benefits**:
- ✅ Columnar storage (fast queries)
- ✅ Efficient compression
- ✅ Predicate pushdown on nested fields
- ✅ Schema evolution support

---

## Limitations & Workarounds

### 1. Cannot Update Single Nested Field Directly

**Limitation**:
```json
{
  "updates": {
    "address.city": "Seattle"  // ❌ Not supported
  }
}
```

**Workaround**: Read full object, modify, write back
```json
// Read current record
→ Get full address object
→ Modify city field
→ Write entire address object back
```

### 2. Array Element Access in Filters

**Limitation**:
```json
{
  "filters": [
    {"field": "tags[0]", "operator": "eq", "value": "electronics"}  // ❌ Not supported
  ]
}
```

**Workaround**: Use LIKE for simple cases
```json
{
  "filters": [
    {"field": "tags", "operator": "like", "value": "%electronics%"}
  ]
}
```

Or query all and filter in application:
```python
results = query({"table": "products"})
filtered = [r for r in results if "electronics" in r["tags"]]
```

### 3. Array Aggregations

**Limitation**: Cannot directly aggregate on array length or elements

**Workaround**: Query data and process in application
```python
results = query({"table": "products", "projection": ["product_id", "tags"]})
for record in results:
    tag_count = len(record["tags"])
```

### 4. Complex Joins on Nested Fields

**Limitation**: Cannot join tables on nested fields in current API

**Workaround**: 
- Denormalize data (duplicate field at top level)
- Or implement join logic in application layer

---

## Best Practices

### 1. Use Structs for Related Data

**Good**:
```json
"address": {
  "type": "struct",
  "fields": {
    "street": {"type": "string"},
    "city": {"type": "string"},
    "state": {"type": "string"}
  }
}
```

**Why**: Groups related fields, better organization

### 2. Use Arrays for Collections

**Good**:
```json
"tags": {
  "type": "array",
  "items": {"type": "string"}
}
```

**Why**: Flexible collection size, proper data model

### 3. Keep Nesting Shallow (2-3 levels max)

**Good**:
```
user → address → city  (2 levels)
```

**Bad**:
```
user → location → address → details → city → district → street  (6 levels)
```

**Why**: Deep nesting hurts query performance

### 4. Index on Frequently Filtered Fields

If you frequently filter by `address.state`, consider:
- Adding `state` at top level (denormalize)
- Or using Iceberg partition spec on nested field

### 5. Read-Modify-Write Pattern for Partial Updates

```python
def update_nested_field(table, filters, nested_path, new_value):
    # 1. Read current record
    record = query(table, filters)["records"][0]
    
    # 2. Navigate to nested field
    keys = nested_path.split(".")
    obj = record
    for key in keys[:-1]:
        obj = obj[key]
    
    # 3. Update value
    obj[keys[-1]] = new_value
    
    # 4. Write back
    update(table, filters, {"updates": {keys[0]: record[keys[0]]}})

# Usage
update_nested_field("users", 
                    [{"field": "user_id", "operator": "eq", "value": 1}],
                    "address.city", 
                    "Seattle")
```

---

## Practical Examples

### Example 1: User Management with Address

```python
# Create user
write({
  "table": "users",
  "records": [{
    "user_id": 1,
    "name": "John Doe",
    "email": "john@example.com",
    "address": {
      "street": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "zip_code": "94105"
    }
  }]
})

# Find users in California
ca_users = query({
  "table": "users",
  "filters": [
    {"field": "address.state", "operator": "eq", "value": "CA"}
  ]
})

# Update user's address
update({
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
})
```

### Example 2: Product Tags

```python
# Create product
write({
  "table": "products",
  "records": [{
    "product_id": 1,
    "name": "Laptop",
    "price": 999.99,
    "tags": ["electronics", "computers"]
  }]
})

# Find products with electronics tag
electronics = query({
  "table": "products",
  "filters": [
    {"field": "tags", "operator": "like", "value": "%electronics%"}
  ]
})

# Add tag to product (read-modify-write)
product = query({
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}]
})["records"][0]

product["tags"].append("bestseller")

update({
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}],
  "updates": {"tags": product["tags"]}
})
```

### Example 3: Orders with Line Items

```python
# Create order
write({
  "table": "orders",
  "records": [{
    "order_id": 1001,
    "customer_id": 501,
    "items": [
      {"product_id": 1, "name": "Laptop", "quantity": 1, "price": 999.99},
      {"product_id": 2, "name": "Mouse", "quantity": 2, "price": 24.99}
    ]
  }]
})

# Query order
order = query({
  "table": "orders",
  "filters": [{"field": "order_id", "operator": "eq", "value": 1001}]
})["records"][0]

# Add item to order
order["items"].append({
  "product_id": 3,
  "name": "Keyboard",
  "quantity": 1,
  "price": 149.99
})

update({
  "table": "orders",
  "filters": [{"field": "order_id", "operator": "eq", "value": 1001}],
  "updates": {"items": order["items"]}
})

# Calculate total in application
total = sum(item["quantity"] * item["price"] for item in order["items"])
```

---

## Summary

### Querying Nested Data

| Operation | Supported | Syntax |
|-----------|-----------|--------|
| Select nested field | ✅ | `"projection": ["address.city"]` |
| Filter by nested field | ✅ | `"filters": [{"field": "address.state", "operator": "eq", "value": "CA"}]` |
| Sort by nested field | ✅ | `"sort": [{"field": "address.city", "order": "asc"}]` |
| Group by nested field | ✅ | `"group_by": ["address.state"]` |
| Array element access | ⚠️ Limited | Use LIKE or filter in application |
| Complex array queries | ❌ | Filter in application layer |

### Updating Nested Data

| Operation | Supported | Method |
|-----------|-----------|--------|
| Replace entire struct | ✅ | Direct update |
| Replace entire array | ✅ | Direct update |
| Update single nested field | ⚠️ | Read-modify-write pattern |
| Add array element | ⚠️ | Read-modify-write pattern |
| Remove array element | ⚠️ | Read-modify-write pattern |

### Key Points

1. ✅ **Dot notation** works for querying nested fields
2. ✅ **DuckDB** has excellent nested type support
3. ✅ **Iceberg** stores efficiently in Parquet
4. ⚠️ **Partial updates** require read-modify-write
5. ⚠️ **Array operations** limited without custom SQL

---

## Further Reading

- **Examples**: `lambda_test_events/13_*.json`, `lambda_test_events/15_*.json`
- **Postman**: `postman/COMPLEX_TYPES_EXAMPLES.json`
- **Guide**: `docs/COMPLEX_TYPES_GUIDE.md`
- [DuckDB Nested Types](https://duckdb.org/docs/sql/data_types/nested)
- [Parquet Nested Types](https://parquet.apache.org/docs/file-format/types/)


