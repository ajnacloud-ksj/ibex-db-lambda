# Nested Data Quick Reference

## Querying Nested Objects (Structs)

### Select Nested Fields (Dot Notation)

```json
{
  "operation": "QUERY",
  "table": "users",
  "projection": ["name", "address.city", "address.state"]
}
```

Returns:
```json
{
  "name": "John Doe",
  "address.city": "San Francisco",
  "address.state": "CA"
}
```

### Filter by Nested Field

```json
{
  "operation": "QUERY",
  "table": "users",
  "filters": [
    {"field": "address.state", "operator": "eq", "value": "CA"}
  ]
}
```

### Sort by Nested Field

```json
{
  "operation": "QUERY",
  "table": "users",
  "sort": [{"field": "address.city", "order": "asc"}]
}
```

### Group by Nested Field

```json
{
  "operation": "QUERY",
  "table": "users",
  "aggregations": [
    {"function": "count", "field": null, "alias": "count"}
  ],
  "group_by": ["address.state"]
}
```

---

## Querying Arrays

### Get All Records with Arrays

```json
{
  "operation": "QUERY",
  "table": "products"
}
```

Returns:
```json
{
  "product_id": 1,
  "tags": ["electronics", "computers", "bestseller"]
}
```

### Filter by Array Content (LIKE)

```json
{
  "operation": "QUERY",
  "table": "products",
  "filters": [
    {"field": "tags", "operator": "like", "value": "%electronics%"}
  ]
}
```

---

## Updating Nested Objects

### Replace Entire Object

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

### Update Single Nested Field (Read-Modify-Write)

```python
# Step 1: Read current record
response = query({
  "table": "users",
  "filters": [{"field": "user_id", "operator": "eq", "value": 1}]
})

user = response["data"]["records"][0]

# Step 2: Modify nested field
user["address"]["city"] = "Seattle"

# Step 3: Write back entire object
update({
  "table": "users",
  "filters": [{"field": "user_id", "operator": "eq", "value": 1}],
  "updates": {
    "address": user["address"]
  }
})
```

---

## Updating Arrays

### Replace Entire Array

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

### Add Element to Array (Read-Modify-Write)

```python
# Step 1: Read current record
response = query({
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}]
})

product = response["data"]["records"][0]

# Step 2: Add element
product["tags"].append("new-tag")

# Step 3: Write back
update({
  "table": "products",
  "filters": [{"field": "product_id", "operator": "eq", "value": 1}],
  "updates": {
    "tags": product["tags"]
  }
})
```

### Remove Element from Array

```python
# Read, modify, write
product = query(...)["data"]["records"][0]
product["tags"].remove("old-tag")
# or: product["tags"] = [t for t in product["tags"] if t != "old-tag"]

update({
  "updates": {"tags": product["tags"]}
})
```

---

## Complex Nested Structures

### Array of Objects (Order Items)

**Query**:
```json
{
  "operation": "QUERY",
  "table": "orders",
  "filters": [{"field": "order_id", "operator": "eq", "value": 1001}]
}
```

**Returns**:
```json
{
  "order_id": 1001,
  "items": [
    {"product_id": 1, "name": "Laptop", "quantity": 1, "price": 999.99},
    {"product_id": 2, "name": "Mouse", "quantity": 2, "price": 24.99}
  ]
}
```

**Add Item**:
```python
order = query(...)["data"]["records"][0]

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
```

---

## Supported Operations Matrix

| Operation | Nested Object (Struct) | Array |
|-----------|------------------------|-------|
| **Query** | ✅ | ✅ |
| Select specific fields | ✅ `address.city` | ⚠️ Get entire array |
| Filter | ✅ `address.state = 'CA'` | ⚠️ LIKE only |
| Sort | ✅ | ❌ |
| Group by | ✅ | ❌ |
| **Update** | ✅ | ✅ |
| Replace entire | ✅ Direct | ✅ Direct |
| Update single field/element | ⚠️ Read-modify-write | ⚠️ Read-modify-write |
| Add element | N/A | ⚠️ Read-modify-write |
| Remove element | N/A | ⚠️ Read-modify-write |

**Legend**:
- ✅ Fully supported
- ⚠️ Limited support / workaround needed
- ❌ Not supported

---

## Common Patterns

### Pattern 1: User with Address

```python
# Create
write({
  "records": [{
    "user_id": 1,
    "name": "John",
    "address": {"city": "SF", "state": "CA"}
  }]
})

# Query by city
query({
  "filters": [{"field": "address.city", "operator": "eq", "value": "SF"}]
})

# Update address
update({
  "filters": [{"field": "user_id", "operator": "eq", "value": 1}],
  "updates": {"address": {"city": "LA", "state": "CA"}}
})
```

### Pattern 2: Product with Tags

```python
# Create
write({
  "records": [{
    "product_id": 1,
    "name": "Laptop",
    "tags": ["electronics", "computers"]
  }]
})

# Find by tag
query({
  "filters": [{"field": "tags", "operator": "like", "value": "%electronics%"}]
})

# Add tag (read-modify-write)
product = query(...)["records"][0]
product["tags"].append("bestseller")
update({"updates": {"tags": product["tags"]}})
```

### Pattern 3: Order with Items

```python
# Create
write({
  "records": [{
    "order_id": 1,
    "items": [
      {"product_id": 1, "qty": 1, "price": 999.99}
    ]
  }]
})

# Add item (read-modify-write)
order = query(...)["records"][0]
order["items"].append({"product_id": 2, "qty": 2, "price": 24.99})
update({"updates": {"items": order["items"]}})

# Calculate total in app
total = sum(item["qty"] * item["price"] for item in order["items"])
```

---

## Limitations & Workarounds

### ❌ Cannot: Update single nested field directly

```json
{
  "updates": {
    "address.city": "Seattle"  // ❌ Not supported
  }
}
```

**✅ Workaround**: Read-modify-write pattern (shown above)

### ❌ Cannot: Access array elements by index

```json
{
  "filters": [
    {"field": "tags[0]", "operator": "eq", "value": "electronics"}  // ❌
  ]
}
```

**✅ Workaround**: Use LIKE or filter in application

### ❌ Cannot: Complex array queries

```json
{
  "filters": [
    {"field": "items", "operator": "contains", "value": {"product_id": 1}}  // ❌
  ]
}
```

**✅ Workaround**: Query all, filter in application

---

## Performance Tips

1. **Index frequently queried nested fields**: Consider denormalizing
2. **Keep nesting shallow**: 2-3 levels max
3. **Use structs for related data**: Groups logically
4. **Batch updates**: Update multiple records at once
5. **Filter at database level**: Use nested field filters when possible

---

## Test Examples

- **Query nested struct**: `lambda_test_events/18_query_nested_struct.json`
- **Update nested struct**: `lambda_test_events/19_update_nested_struct.json`
- **Query array filter**: `lambda_test_events/20_query_array_filter.json`
- **Update array**: `lambda_test_events/21_update_array.json`

---

## Full Documentation

- **Complete Guide**: `docs/QUERYING_NESTED_DATA.md`
- **Complex Types Guide**: `docs/COMPLEX_TYPES_GUIDE.md`
- **Quick Reference**: `docs/COMPLEX_TYPES_QUICK_REFERENCE.md`


