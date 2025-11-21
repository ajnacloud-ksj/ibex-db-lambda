# Complex Types Quick Reference

## Type Definitions Cheat Sheet

### Array (List)

```json
{
  "field_name": {
    "type": "array",
    "required": false,
    "items": {
      "type": "string",  // or any other type
      "required": false
    }
  }
}
```

### Struct (Object)

```json
{
  "field_name": {
    "type": "struct",
    "required": false,
    "fields": {
      "sub_field1": {
        "type": "string",
        "required": false
      },
      "sub_field2": {
        "type": "integer",
        "required": false
      }
    }
  }
}
```

### Map (Key-Value)

```json
{
  "field_name": {
    "type": "map",
    "required": false,
    "key_type": "string",
    "value_type": {
      "type": "string",  // or any other type
      "required": false
    }
  }
}
```

### Array of Objects

```json
{
  "items": {
    "type": "array",
    "items": {
      "type": "struct",
      "fields": {
        "id": {"type": "long"},
        "name": {"type": "string"}
      }
    }
  }
}
```

### Object with Array

```json
{
  "user": {
    "type": "struct",
    "fields": {
      "name": {"type": "string"},
      "emails": {
        "type": "array",
        "items": {"type": "string"}
      }
    }
  }
}
```

## Primitive Types

| Type | Description | Example Value |
|------|-------------|---------------|
| `string` | Text | `"Hello"` |
| `integer` | 32-bit integer | `42` |
| `long` | 64-bit integer | `9223372036854775807` |
| `float` | 32-bit floating point | `3.14` |
| `double` | 64-bit floating point | `3.141592653589793` |
| `boolean` | True/False | `true` |
| `date` | Date (YYYY-MM-DD) | `"2024-01-15"` |
| `timestamp` | Date and time | `"2024-01-15T10:30:00Z"` |
| `decimal` | Precise decimal | `"123.45"` |
| `binary` | Binary data | `[0, 1, 2, 3]` |

## Common Patterns

### E-commerce Product

```json
{
  "product_id": {"type": "long", "required": true},
  "name": {"type": "string", "required": true},
  "price": {"type": "double", "required": true},
  "tags": {
    "type": "array",
    "items": {"type": "string"}
  },
  "variants": {
    "type": "array",
    "items": {
      "type": "struct",
      "fields": {
        "sku": {"type": "string"},
        "color": {"type": "string"},
        "size": {"type": "string"},
        "stock": {"type": "integer"}
      }
    }
  }
}
```

### User Profile

```json
{
  "user_id": {"type": "long", "required": true},
  "name": {"type": "string", "required": true},
  "email": {"type": "string", "required": true},
  "address": {
    "type": "struct",
    "fields": {
      "street": {"type": "string"},
      "city": {"type": "string"},
      "state": {"type": "string"},
      "zip": {"type": "string"}
    }
  },
  "preferences": {
    "type": "map",
    "key_type": "string",
    "value_type": {"type": "string"}
  }
}
```

### Order with Line Items

```json
{
  "order_id": {"type": "long", "required": true},
  "customer_id": {"type": "long", "required": true},
  "order_date": {"type": "timestamp", "required": true},
  "total": {"type": "double", "required": true},
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
  },
  "shipping_address": {
    "type": "struct",
    "fields": {
      "street": {"type": "string"},
      "city": {"type": "string"},
      "state": {"type": "string"},
      "zip": {"type": "string"}
    }
  }
}
```

## Querying Nested Data

### Access Nested Field (Struct)

```json
{
  "operation": "QUERY",
  "table": "users",
  "projection": ["name", "address.city", "address.state"],
  "filters": [
    {"field": "address.state", "operator": "eq", "value": "CA"}
  ]
}
```

### Filter by Array Element

```json
{
  "operation": "QUERY",
  "table": "products",
  "filters": [
    {"field": "tags", "operator": "like", "value": "%electronics%"}
  ]
}
```

### Select All Fields

```json
{
  "operation": "QUERY",
  "table": "orders",
  "projection": ["*"],
  "limit": 10
}
```

## Writing Data

### With Arrays

```json
{
  "operation": "WRITE",
  "table": "products",
  "records": [
    {
      "product_id": 1,
      "name": "Laptop",
      "tags": ["electronics", "computers"]
    }
  ]
}
```

### With Nested Objects

```json
{
  "operation": "WRITE",
  "table": "users",
  "records": [
    {
      "user_id": 1,
      "name": "John",
      "address": {
        "city": "SF",
        "state": "CA"
      }
    }
  ]
}
```

### With Arrays of Objects

```json
{
  "operation": "WRITE",
  "table": "orders",
  "records": [
    {
      "order_id": 1,
      "items": [
        {"product_id": 1, "quantity": 2},
        {"product_id": 2, "quantity": 1}
      ]
    }
  ]
}
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Array type must specify 'items'" | Missing items definition | Add `"items": {"type": "..."}` |
| "Map type must specify key_type and value_type" | Missing map definition | Add both `"key_type"` and `"value_type"` |
| "Struct type must specify 'fields'" | Missing fields | Add `"fields": {...}` dictionary |
| Type mismatch on write | Data doesn't match schema | Ensure data structure matches schema exactly |

## Tips

1. **Start Simple**: Begin with primitive types, add complexity as needed
2. **Use Structs for Related Data**: Group related fields (e.g., address, contact)
3. **Arrays for Collections**: Use arrays for repeated elements of same type
4. **Maps for Dynamic Keys**: Use maps when field names aren't known upfront
5. **Keep Nesting Shallow**: Avoid more than 2-3 levels of nesting for performance
6. **Mark Required Carefully**: Only mark fields as required if truly necessary

## Examples to Try

See these files for complete examples:
- `lambda_test_events/11_create_table_with_array.json`
- `lambda_test_events/13_create_table_with_struct.json`
- `lambda_test_events/15_create_table_complex.json`
- `postman/COMPLEX_TYPES_EXAMPLES.json`

## Full Documentation

- **User Guide**: `docs/COMPLEX_TYPES_GUIDE.md`
- **Implementation Details**: `docs/COMPLEX_TYPES_IMPLEMENTATION.md`

