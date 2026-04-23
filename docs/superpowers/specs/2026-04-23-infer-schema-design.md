# Design: `infer_schema` tool

## Problem

`sample_items` returns DynamoDB items deserialized by the boto3 resource API.
Native DynamoDB type information is lost: `{"S": "hello"}` becomes `"hello"`,
`{"N": "42"}` becomes `42`, `{"SS": ["a","b"]}` becomes `["a","b"]`. Users
cannot determine the actual DynamoDB types (S, N, B, BOOL, NULL, SS, NS, BS,
L, M) from the output.

## Solution

A new `infer_schema` MCP tool that:

1. Uses the **low-level boto3 client** (`_client.scan()`) to get items in raw
   DynamoDB wire format, preserving native type codes.
2. Merges `describe_table` metadata (key schema, indexes) with inferred
   attribute types from sampled items.
3. Returns a structured schema with configurable output format.

## Tool signature

```python
@mcp.tool()
def infer_schema(
    table_name: str,
    sample_size: int = 20,
    max_depth: int = 3,
    output_format: str = "summary",
) -> dict:
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `table_name` | str | required | Exact DynamoDB table name |
| `sample_size` | int | 20 | Items to scan for inference. Capped by `SAMPLE_MAX_N`. |
| `max_depth` | int | 3 | Max recursion depth for Map/List types. 0 = flat (report M/L but don't recurse). |
| `output_format` | str | `"summary"` | Output format: `"summary"`, `"json_schema"`, or `"cfn"`. |

### Security guards

All existing guards apply in the same order as other tools:

1. `_check_rate_limit()`
2. `_check_table_allowed(table_name)`
3. `_check_session_cap(len(items))` — after scan
4. `_check_response_size(result)` — before return
5. `_audit("infer_schema", table=table_name, items=len(items))`
6. Cost reporting via `ReturnConsumedCapacity` when `DDB_SHOW_COST=true`

## How raw types are obtained

The low-level client's `scan()` returns items in DynamoDB wire format:

```json
{
  "Items": [
    {
      "user_id": {"S": "U123"},
      "age": {"N": "42"},
      "tags": {"SS": ["admin", "beta"]},
      "address": {"M": {"street": {"S": "123 Main"}, "city": {"S": "Austin"}}}
    }
  ]
}
```

Each attribute value is a single-key dict where the key is the DynamoDB type
code: `S`, `N`, `B`, `BOOL`, `NULL`, `SS`, `NS`, `BS`, `L`, `M`.

## Schema inference algorithm

```
function infer_attributes(items, max_depth, current_depth=0):
    schema = {}
    total = len(items)
    for each item in items:
        for each (attr_name, typed_value) in item:
            type_code = single key of typed_value  # e.g. "S", "M", "L"
            schema[attr_name].types.add(type_code)
            schema[attr_name].count += 1

            if type_code == "M" and current_depth < max_depth:
                nested_items = [typed_value["M"]]  # collect across all items
                schema[attr_name].nested = infer_attributes(nested_items, max_depth, current_depth+1)

            if type_code == "L" and current_depth < max_depth:
                for element in typed_value["L"]:
                    schema[attr_name].element_types.add(single key of element)
                    if element is "M":
                        recurse into nested schema

    for each attr in schema:
        attr.occurrence = f"{attr.count}/{total}"
        attr.required = (attr.count == total)
    return schema
```

For Maps: collect the Map values from all items that have the attribute, then
recurse to infer the nested schema (occurrence is relative to items that
*have* the parent attribute, not total items).

For Lists: collect element types as a union across all list elements in all
items. If elements are Maps, recurse to infer nested schema.

For type conflicts: `dynamodb_types` is always an array. `["S"]` for
consistent types, `["S", "N"]` for mixed types.

When `current_depth >= max_depth`: Maps report `"dynamodb_types": ["M"]` with
no `nested` field. Lists report `"dynamodb_types": ["L"]` with no
`element_types` field. This signals "there's structure here but we didn't
recurse into it."

## Output formats

### `"summary"` (default)

Optimized for LLM consumption and human readability.

```json
{
  "table_name": "dev-UserProfiles",
  "items_sampled": 20,
  "key_schema": [
    {"attribute_name": "user_id", "key_type": "HASH", "dynamodb_type": "S"},
    {"attribute_name": "created_at", "key_type": "RANGE", "dynamodb_type": "N"}
  ],
  "global_secondary_indexes": [
    {
      "index_name": "by-email",
      "key_schema": [
        {"attribute_name": "email", "key_type": "HASH", "dynamodb_type": "S"}
      ],
      "projection_type": "ALL"
    }
  ],
  "local_secondary_indexes": [],
  "attributes": {
    "user_id": {
      "dynamodb_types": ["S"],
      "occurrence": "20/20",
      "required": true,
      "key": "HASH"
    },
    "age": {
      "dynamodb_types": ["N", "S"],
      "occurrence": "18/20",
      "required": false,
      "note": "mixed types observed"
    },
    "tags": {
      "dynamodb_types": ["SS"],
      "occurrence": "12/20",
      "required": false
    },
    "address": {
      "dynamodb_types": ["M"],
      "occurrence": "15/20",
      "required": false,
      "nested": {
        "street": {"dynamodb_types": ["S"], "occurrence": "15/15", "required": true},
        "city": {"dynamodb_types": ["S"], "occurrence": "15/15", "required": true},
        "zip": {"dynamodb_types": ["N"], "occurrence": "10/15", "required": false}
      }
    },
    "recent_scores": {
      "dynamodb_types": ["L"],
      "occurrence": "8/20",
      "required": false,
      "element_types": ["N"]
    }
  }
}
```

### `"json_schema"`

Industry-standard JSON Schema (2020-12). DynamoDB-specific information is
carried in `x-dynamodb-*` extension fields.

```json
{
  "table_name": "dev-UserProfiles",
  "items_sampled": 20,
  "key_schema": [
    {"attribute_name": "user_id", "key_type": "HASH", "dynamodb_type": "S"}
  ],
  "global_secondary_indexes": [...],
  "local_secondary_indexes": [],
  "json_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "dev-UserProfiles",
    "type": "object",
    "properties": {
      "user_id": {
        "type": "string",
        "x-dynamodb-type": "S",
        "x-dynamodb-key": "HASH",
        "x-occurrence": "20/20"
      },
      "age": {
        "oneOf": [{"type": "number"}, {"type": "string"}],
        "x-dynamodb-types": ["N", "S"],
        "x-occurrence": "18/20"
      },
      "tags": {
        "type": "array",
        "items": {"type": "string"},
        "uniqueItems": true,
        "x-dynamodb-type": "SS",
        "x-occurrence": "12/20"
      },
      "address": {
        "type": "object",
        "x-dynamodb-type": "M",
        "x-occurrence": "15/20",
        "properties": {
          "street": {"type": "string", "x-dynamodb-type": "S"},
          "city": {"type": "string", "x-dynamodb-type": "S"}
        }
      }
    },
    "required": ["user_id", "created_at", "email"]
  }
}
```

DynamoDB type to JSON Schema type mapping:

| DynamoDB | JSON Schema `type` | Notes |
|---|---|---|
| S | `"string"` | |
| N | `"number"` | |
| B | `"string"` | with `"contentEncoding": "base64"` |
| BOOL | `"boolean"` | |
| NULL | `"null"` | |
| SS | `"array"` | with `"items": {"type": "string"}, "uniqueItems": true` |
| NS | `"array"` | with `"items": {"type": "number"}, "uniqueItems": true` |
| BS | `"array"` | with `"items": {"type": "string", "contentEncoding": "base64"}, "uniqueItems": true` |
| L | `"array"` | element types in `"items"` |
| M | `"object"` | nested `"properties"` |
| mixed | `"oneOf": [...]` | |

### `"cfn"`

CloudFormation-style output using native AWS naming conventions.

```json
{
  "table_name": "dev-UserProfiles",
  "items_sampled": 20,
  "cfn": {
    "TableName": "dev-UserProfiles",
    "KeySchema": [
      {"AttributeName": "user_id", "KeyType": "HASH"},
      {"AttributeName": "created_at", "KeyType": "RANGE"}
    ],
    "AttributeDefinitions": [
      {"AttributeName": "user_id", "AttributeType": "S"},
      {"AttributeName": "created_at", "AttributeType": "N"},
      {"AttributeName": "email", "AttributeType": "S"}
    ],
    "GlobalSecondaryIndexes": [
      {
        "IndexName": "by-email",
        "KeySchema": [{"AttributeName": "email", "KeyType": "HASH"}],
        "Projection": {"ProjectionType": "ALL"}
      }
    ]
  },
  "inferred_attributes": {
    "age": {"AttributeType": "N", "Occurrence": "18/20", "Required": false},
    "tags": {"AttributeType": "SS", "Occurrence": "12/20", "Required": false},
    "address": {
      "AttributeType": "M",
      "Occurrence": "15/20",
      "Required": false,
      "Nested": {
        "street": {"AttributeType": "S", "Occurrence": "15/15"},
        "city": {"AttributeType": "S", "Occurrence": "15/15"}
      }
    }
  }
}
```

Note: CloudFormation `AttributeDefinitions` only includes key attributes
(required by DynamoDB). Non-key attributes go in a separate
`inferred_attributes` section since CFn doesn't model schemaless attributes.

## Shared fields across all formats

All three formats include these top-level fields:

- `table_name` — the table name
- `items_sampled` — how many items were actually scanned
- `key_schema` — key schema with types (except `cfn` where it's inside `cfn`)
- `global_secondary_indexes` / `local_secondary_indexes`
- `consumed_capacity` — when `DDB_SHOW_COST=true`

## Implementation plan

All changes in `server.py`:

1. Add a `_infer_types(items, max_depth, current_depth)` helper that walks raw
   DynamoDB items and returns the attributes dict.
2. Add `_format_summary(table_info, attributes, items_sampled)` formatter.
3. Add `_format_json_schema(table_info, attributes, items_sampled)` formatter.
4. Add `_format_cfn(table_info, attributes, items_sampled)` formatter.
5. Add the `infer_schema` tool function that orchestrates: scan via client,
   describe table, infer types, format, apply guards, return.

Tests:

6. Add tests for `infer_schema` in `tests/test_server.py` using moto:
   - Test each output format
   - Test nested Map/List recursion
   - Test mixed types (union)
   - Test max_depth=0 (flat mode)
   - Test security guards (rate limit, table allowlist, session cap)

Docs:

7. Add `infer_schema` to the Tools reference table in `README.md`.

## Files changed

- `server.py` — new tool + 4 helper functions (~150-200 lines)
- `tests/test_server.py` or `tests/test_infer_schema.py` — new test cases
- `README.md` — tool reference table update
