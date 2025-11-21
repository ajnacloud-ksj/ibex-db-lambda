# Complex Types Guide: Arrays, Objects, and Nested Structures

This guide explains how to use complex types (arrays, maps, structs) in your Iceberg tables.

## Overview

The system now supports:
- **Primitive types**: string, integer, long, float, double, boolean, date, timestamp, decimal, binary
- **Array/List types**: Collections of elements of the same type
- **Map types**: Key-value pairs
- **Struct types**: Nested objects with named fields

## Supported Field Types

```json
{
  "type": "string|integer|long|float|double|boolean|date|timestamp|decimal|binary|array|map|struct",
  "required": true|false,
  "nullable": true|false
}
```

---

## Example 1: Table with Array Field

Create a products table with an array of tags:

```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "products",
  "schema": {
    "fields": {
      "product_id": {
        "type": "long",
        "required": true
      },
      "name": {
        "type": "string",
        "required": true
      },
      "price": {
        "type": "double",
        "required": true
      },
      "tags": {
        "type": "array",
        "required": false,
        "items": {
          "type": "string",
          "required": false
        }
      }
    }
  }
}
```

**Writing data with arrays:**

```json
{
  "operation": "WRITE",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
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

---

## Example 2: Table with Nested Struct/Object

Create a users table with a nested address object:

```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "users",
  "schema": {
    "fields": {
      "user_id": {
        "type": "long",
        "required": true
      },
      "name": {
        "type": "string",
        "required": true
      },
      "email": {
        "type": "string",
        "required": true
      },
      "address": {
        "type": "struct",
        "required": false,
        "fields": {
          "street": {
            "type": "string",
            "required": false
          },
          "city": {
            "type": "string",
            "required": false
          },
          "state": {
            "type": "string",
            "required": false
          },
          "zip_code": {
            "type": "string",
            "required": false
          },
          "country": {
            "type": "string",
            "required": false
          }
        }
      }
    }
  }
}
```

**Writing data with nested objects:**

```json
{
  "operation": "WRITE",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "users",
  "records": [
    {
      "user_id": 1,
      "name": "John Doe",
      "email": "john@example.com",
      "address": {
        "street": "123 Main St",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94105",
        "country": "USA"
      }
    },
    {
      "user_id": 2,
      "name": "Jane Smith",
      "email": "jane@example.com",
      "address": {
        "street": "456 Oak Ave",
        "city": "New York",
        "state": "NY",
        "zip_code": "10001",
        "country": "USA"
      }
    }
  ]
}
```

---

## Example 3: Table with Map Type

Create a products table with a map of attributes:

```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "products_with_metadata",
  "schema": {
    "fields": {
      "product_id": {
        "type": "long",
        "required": true
      },
      "name": {
        "type": "string",
        "required": true
      },
      "metadata": {
        "type": "map",
        "required": false,
        "key_type": "string",
        "value_type": {
          "type": "string",
          "required": false
        }
      }
    }
  }
}
```

**Writing data with maps:**

```json
{
  "operation": "WRITE",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "products_with_metadata",
  "records": [
    {
      "product_id": 1,
      "name": "Laptop",
      "metadata": {
        "brand": "Dell",
        "model": "XPS 15",
        "color": "Silver",
        "warranty": "2 years"
      }
    }
  ]
}
```

---

## Example 4: Complex Nested Structure

Create an orders table with arrays of nested objects:

```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "orders",
  "schema": {
    "fields": {
      "order_id": {
        "type": "long",
        "required": true
      },
      "customer_id": {
        "type": "long",
        "required": true
      },
      "order_date": {
        "type": "timestamp",
        "required": true
      },
      "total_amount": {
        "type": "double",
        "required": true
      },
      "items": {
        "type": "array",
        "required": false,
        "items": {
          "type": "struct",
          "required": false,
          "fields": {
            "product_id": {
              "type": "long",
              "required": true
            },
            "product_name": {
              "type": "string",
              "required": true
            },
            "quantity": {
              "type": "integer",
              "required": true
            },
            "unit_price": {
              "type": "double",
              "required": true
            },
            "subtotal": {
              "type": "double",
              "required": true
            }
          }
        }
      },
      "shipping_address": {
        "type": "struct",
        "required": true,
        "fields": {
          "street": {
            "type": "string",
            "required": true
          },
          "city": {
            "type": "string",
            "required": true
          },
          "state": {
            "type": "string",
            "required": true
          },
          "zip_code": {
            "type": "string",
            "required": true
          }
        }
      }
    }
  }
}
```

**Writing complex nested data:**

```json
{
  "operation": "WRITE",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "orders",
  "records": [
    {
      "order_id": 1001,
      "customer_id": 501,
      "order_date": "2024-01-15T10:30:00Z",
      "total_amount": 1249.97,
      "items": [
        {
          "product_id": 1,
          "product_name": "Laptop",
          "quantity": 1,
          "unit_price": 999.99,
          "subtotal": 999.99
        },
        {
          "product_id": 2,
          "product_name": "Mouse",
          "quantity": 2,
          "unit_price": 24.99,
          "subtotal": 49.98
        },
        {
          "product_id": 3,
          "product_name": "USB Cable",
          "quantity": 5,
          "unit_price": 9.99,
          "subtotal": 49.95
        }
      ],
      "shipping_address": {
        "street": "789 Tech Blvd",
        "city": "Seattle",
        "state": "WA",
        "zip_code": "98101"
      }
    }
  ]
}
```

---

## Example 5: E-commerce Product Catalog (Real-World)

```json
{
  "operation": "CREATE_TABLE",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "product_catalog",
  "schema": {
    "fields": {
      "product_id": {
        "type": "long",
        "required": true
      },
      "name": {
        "type": "string",
        "required": true
      },
      "description": {
        "type": "string",
        "required": false
      },
      "category": {
        "type": "string",
        "required": true
      },
      "price": {
        "type": "double",
        "required": true
      },
      "stock": {
        "type": "integer",
        "required": true
      },
      "tags": {
        "type": "array",
        "required": false,
        "items": {
          "type": "string",
          "required": false
        }
      },
      "variants": {
        "type": "array",
        "required": false,
        "items": {
          "type": "struct",
          "required": false,
          "fields": {
            "sku": {
              "type": "string",
              "required": true
            },
            "color": {
              "type": "string",
              "required": false
            },
            "size": {
              "type": "string",
              "required": false
            },
            "price_modifier": {
              "type": "double",
              "required": false
            },
            "stock": {
              "type": "integer",
              "required": true
            }
          }
        }
      },
      "specifications": {
        "type": "map",
        "required": false,
        "key_type": "string",
        "value_type": {
          "type": "string",
          "required": false
        }
      },
      "reviews": {
        "type": "struct",
        "required": false,
        "fields": {
          "average_rating": {
            "type": "double",
            "required": false
          },
          "total_reviews": {
            "type": "integer",
            "required": false
          },
          "five_star": {
            "type": "integer",
            "required": false
          },
          "four_star": {
            "type": "integer",
            "required": false
          },
          "three_star": {
            "type": "integer",
            "required": false
          },
          "two_star": {
            "type": "integer",
            "required": false
          },
          "one_star": {
            "type": "integer",
            "required": false
          }
        }
      }
    }
  }
}
```

**Sample product data:**

```json
{
  "operation": "WRITE",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "product_catalog",
  "records": [
    {
      "product_id": 1001,
      "name": "Premium Wireless Headphones",
      "description": "High-quality noise-cancelling wireless headphones",
      "category": "Electronics",
      "price": 299.99,
      "stock": 150,
      "tags": ["electronics", "audio", "wireless", "noise-cancelling"],
      "variants": [
        {
          "sku": "WH-001-BLK",
          "color": "Black",
          "size": "Standard",
          "price_modifier": 0.0,
          "stock": 80
        },
        {
          "sku": "WH-001-WHT",
          "color": "White",
          "size": "Standard",
          "price_modifier": 0.0,
          "stock": 70
        }
      ],
      "specifications": {
        "battery_life": "30 hours",
        "bluetooth_version": "5.0",
        "driver_size": "40mm",
        "impedance": "32 ohms",
        "frequency_response": "20Hz - 20kHz"
      },
      "reviews": {
        "average_rating": 4.5,
        "total_reviews": 342,
        "five_star": 210,
        "four_star": 98,
        "three_star": 24,
        "two_star": 7,
        "one_star": 3
      }
    }
  ]
}
```

---

## Querying Complex Types

### Accessing Nested Fields

When querying, you can access nested fields using dot notation:

```json
{
  "operation": "QUERY",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "users",
  "projection": ["user_id", "name", "address.city", "address.state"],
  "filters": [
    {
      "field": "address.state",
      "operator": "eq",
      "value": "CA"
    }
  ]
}
```

### Array Operations

```json
{
  "operation": "QUERY",
  "tenant_id": "{{tenant_id}}",
  "namespace": "{{namespace}}",
  "table": "products",
  "filters": [
    {
      "field": "tags",
      "operator": "like",
      "value": "%electronics%"
    }
  ]
}
```

---

## Best Practices

1. **Use structs for related fields**: Group related fields together (e.g., address, contact info)
2. **Arrays for collections**: Use arrays when you have multiple items of the same type
3. **Maps for dynamic attributes**: Use maps when field names are not known in advance
4. **Keep nesting reasonable**: Avoid deeply nested structures (3+ levels) for better query performance
5. **Required vs Optional**: Mark fields as required only when necessary
6. **Schema evolution**: Plan for schema changes - Iceberg supports adding new fields

---

## Schema Evolution

Apache Iceberg supports schema evolution. You can add new fields to complex types without breaking existing data:

- Add new fields to structs
- Add new items to arrays (schema for items can evolve)
- Add new key-value pairs to maps

---

## Performance Considerations

1. **Predicate pushdown**: Filters on nested fields work efficiently with Iceberg
2. **Projection pruning**: Select only needed nested fields to reduce data scanning
3. **Partitioning**: Consider partitioning on top-level fields, not nested ones
4. **File sizes**: Complex types can increase row sizes - monitor file sizes after writes

---

## Error Handling

Common errors and solutions:

**Error: "Array type must specify 'items' field definition"**
- Solution: Add an `items` field to your array definition

**Error: "Map type must specify both 'key_type' and 'value_type'"**
- Solution: Add both `key_type` and `value_type` to your map definition

**Error: "Struct type must specify 'fields' dictionary"**
- Solution: Add a `fields` dictionary with nested field definitions

---

## Migration Guide

If you have existing tables with primitive types only, you can:

1. Create a new table with complex types
2. Query existing data and transform it
3. Write to the new table
4. Drop the old table (or keep for historical data)

Example transformation:

```python
# Old table: tags as comma-separated string
# New table: tags as array

old_data = query_old_table()
new_records = []

for record in old_data:
    new_record = record.copy()
    # Convert "tag1,tag2,tag3" -> ["tag1", "tag2", "tag3"]
    new_record['tags'] = record['tags'].split(',') if record['tags'] else []
    new_records.append(new_record)

write_to_new_table(new_records)
```

---

## Summary

Your Iceberg database now supports:

- ✅ **Primitive types**: string, integer, long, float, double, boolean, date, timestamp, decimal, binary
- ✅ **Arrays**: Collections of any type
- ✅ **Maps**: Key-value pairs
- ✅ **Structs**: Nested objects with named fields
- ✅ **Complex nesting**: Arrays of structs, structs with arrays, etc.

This enables rich data modeling similar to JSON/Document databases while maintaining ACID guarantees and high query performance!

