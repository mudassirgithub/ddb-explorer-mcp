"""Read-only MCP server for Amazon DynamoDB.

Exposes list/describe/get/query/scan tools. No write operations are registered.
Supports stdio (default), streamable-HTTP, and SSE transports via MCP_TRANSPORT.

AWS credentials come from the standard boto3 chain (env vars, profile, IMDS).
HTTP mode has no built-in auth — put a reverse proxy in front of it.
"""

from __future__ import annotations

import decimal
import fnmatch
import json
import os
import re
import sys
import threading
import time
import warnings
from collections import deque
from typing import Any, Optional

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from mcp.server.fastmcp import FastMCP

REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-2"


# Security: Environment variable bounds for safe configuration
_ENV_INT_BOUNDS = {
    "DDB_SAMPLE_MAX_N": (1, 100),
    "DDB_QUERY_DEFAULT_LIMIT": (1, 500),
    "DDB_QUERY_MAX_LIMIT": (1, 1000),
    "DDB_SCAN_DEFAULT_LIMIT": (1, 500),
    "DDB_SCAN_MAX_LIMIT": (1, 1000),
    "DDB_SCAN_DEFAULT_MAX_PAGES": (1, 50),
    "DDB_SCAN_MAX_PAGES": (1, 100),
    "DDB_BATCH_CHUNK_SIZE": (1, 100),
    "DDB_BATCH_MAX_RETRIES": (1, 20),
    "DDB_MAX_ITEMS_PER_SESSION": (1, 100000),
    "DDB_MAX_CALLS_PER_MINUTE": (1, 1000),
    "DDB_MAX_RESPONSE_BYTES": (0, 10 * 1024 * 1024),  # 10MB max
    "DDB_READ_TIMEOUT": (1, 60),
    "MCP_PORT": (1024, 65535),
}


def _env_int(name: str, default: int) -> int:
    """Parse integer from environment with bounds validation for security."""
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        warnings.warn(f"Invalid integer value for {name}: {raw}, using default: {default}")
        return default
    
    # Apply security bounds if defined
    if name in _ENV_INT_BOUNDS:
        min_val, max_val = _ENV_INT_BOUNDS[name]
        if value < min_val or value > max_val:
            warnings.warn(
                f"Security: {name}={value} outside safe bounds [{min_val}, {max_val}], "
                f"clamping to range"
            )
            return max(min_val, min(value, max_val))
    
    return value


TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()
HTTP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
HTTP_PORT = _env_int("MCP_PORT", 8765)

SAMPLE_MAX_N = _env_int("DDB_SAMPLE_MAX_N", 20)
QUERY_DEFAULT_LIMIT = _env_int("DDB_QUERY_DEFAULT_LIMIT", 50)
QUERY_MAX_LIMIT = _env_int("DDB_QUERY_MAX_LIMIT", 500)
SCAN_DEFAULT_LIMIT = _env_int("DDB_SCAN_DEFAULT_LIMIT", 50)
SCAN_MAX_LIMIT = _env_int("DDB_SCAN_MAX_LIMIT", 500)
SCAN_DEFAULT_MAX_PAGES = _env_int("DDB_SCAN_DEFAULT_MAX_PAGES", 1)
SCAN_MAX_PAGES = _env_int("DDB_SCAN_MAX_PAGES", 20)
BATCH_CHUNK_SIZE = _env_int("DDB_BATCH_CHUNK_SIZE", 100)
BATCH_MAX_RETRIES = _env_int("DDB_BATCH_MAX_RETRIES", 10)

SHOW_COST = os.environ.get("DDB_SHOW_COST", "").strip().lower() in ("true", "1", "yes")

MAX_ITEMS_PER_SESSION = _env_int("DDB_MAX_ITEMS_PER_SESSION", 0)
MAX_CALLS_PER_MINUTE = _env_int("DDB_MAX_CALLS_PER_MINUTE", 0)
AUDIT_LOG = os.environ.get("DDB_AUDIT_LOG", "").strip().lower() in ("true", "1", "yes")

_ALLOWED_TABLES_RAW = os.environ.get("DDB_ALLOWED_TABLES", "").strip()
ALLOWED_TABLE_PATTERNS: list[str] = (
    [p.strip() for p in _ALLOWED_TABLES_RAW.split(",") if p.strip()] if _ALLOWED_TABLES_RAW else []
)

MAX_RESPONSE_BYTES = _env_int("DDB_MAX_RESPONSE_BYTES", 0)
READ_TIMEOUT = _env_int("DDB_READ_TIMEOUT", 10)

mcp = FastMCP("ddb-explorer", host=HTTP_HOST, port=HTTP_PORT)

_boto_config = BotoConfig(read_timeout=READ_TIMEOUT, retries={"max_attempts": 2})
_resource = boto3.resource("dynamodb", region_name=REGION, config=_boto_config)
_client = boto3.client("dynamodb", region_name=REGION, config=_boto_config)
_deserializer = TypeDeserializer()


def _jsonify(obj: Any) -> Any:
    """Recursively make a DynamoDB response JSON-serializable.

    - Decimal -> int if integral, else float
    - set/frozenset -> list
    - bytes -> utf-8 string (or placeholder)
    """
    if isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, (set, frozenset)):
        return [_jsonify(x) for x in obj]
    if isinstance(obj, list):
        return [_jsonify(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except Exception:
            return f"<{len(obj)} bytes>"
    return obj


# Security: Production mode for error sanitization
def _is_production_mode() -> bool:
    """Check if production mode is enabled (dynamic for testing)."""
    return os.environ.get("DDB_PRODUCTION", "").lower() in ("true", "1", "yes")

# Security: Sanitized error messages for production
_SANITIZED_ERROR_MESSAGES = {
    "ResourceNotFoundException": "Resource not found",
    "ValidationException": "Invalid request parameters",
    "ProvisionedThroughputExceededException": "Request rate exceeded",
    "ResourceInUseException": "Resource busy",
    "ItemCollectionSizeLimitExceededException": "Item collection limit exceeded",
    "TransactionCanceledException": "Transaction cancelled",
    "RequestLimitExceeded": "Request limit exceeded",
    "InternalServerError": "Internal server error",
    "ServiceUnavailable": "Service temporarily unavailable",
    "AccessDeniedException": "Access denied",
    "UnrecognizedClientException": "Authentication error",
    "InvalidSignatureException": "Authentication error",
    "TokenRefreshRequired": "Authentication error",
}


def _err(e: Exception) -> dict:
    """Return a structured error, sanitized in production mode to prevent info disclosure."""
    if isinstance(e, ClientError):
        err = e.response.get("Error", {})
        code = err.get("Code", "ClientError")
        message = err.get("Message", str(e))
    else:
        code = type(e).__name__
        message = str(e)
    
    # In production, sanitize error messages to prevent information disclosure
    if _is_production_mode():
        # Log full error for debugging (to stderr)
        if os.environ.get("DDB_DEBUG_ERRORS"):
            print(f"[ddb-security] Original error: code={code}, message={message}", 
                  file=sys.stderr, flush=True)
        
        # Return sanitized error
        return {
            "error": True,
            "code": code if code in _SANITIZED_ERROR_MESSAGES else "RequestError",
            "message": _SANITIZED_ERROR_MESSAGES.get(code, "Request could not be processed")
        }
    
    # In development, return full error details
    return {"error": True, "code": code, "message": message}


_RCC_KWARGS: dict = {"ReturnConsumedCapacity": "TOTAL"} if SHOW_COST else {}


def _consumed_capacity(resp: dict) -> dict | None:
    """Extract ConsumedCapacity from a DynamoDB response, if cost reporting is on."""
    if not SHOW_COST:
        return None
    cc = resp.get("ConsumedCapacity")
    if not cc:
        return None
    return {
        "table": cc.get("TableName"),
        "capacity_units": float(cc.get("CapacityUnits", 0)),
        "read_capacity_units": float(cc.get("ReadCapacityUnits", 0)),
    }


# ---------------------------------------------------------------------------
# Security guards: rate limit, table allowlist, session item cap, audit log
# ---------------------------------------------------------------------------

# Security: Expression validation patterns
_VALID_ATTRIBUTE_NAME = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
_VALID_EXPRESSION_PLACEHOLDER = re.compile(r'^:[a-zA-Z_][a-zA-Z0-9_]*$')
_VALID_ATTRIBUTE_PLACEHOLDER = re.compile(r'^#[a-zA-Z_][a-zA-Z0-9_]*$')

# Security: SQL injection keywords to block
_SQL_KEYWORDS = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'EXEC', 'UNION']
_DANGEROUS_CHARS = [';', '&&', '||', '|', '`', '$', '\n', '\r']

_guard_lock = threading.Lock()
_call_timestamps: deque[float] = deque()


def _check_rate_limit() -> dict | None:
    """Reject the call if the per-minute rate limit has been exceeded."""
    if MAX_CALLS_PER_MINUTE <= 0:
        return None
    with _guard_lock:
        now = time.monotonic()
        while _call_timestamps and _call_timestamps[0] < now - 60:
            _call_timestamps.popleft()
        if len(_call_timestamps) >= MAX_CALLS_PER_MINUTE:
            return {
                "error": True,
                "code": "RateLimitExceeded",
                "message": (
                    f"Rate limit of {MAX_CALLS_PER_MINUTE} calls/minute exceeded. Wait and retry."
                ),
            }
        _call_timestamps.append(now)
    return None


def _validate_expression(expression: str, expression_type: str = "condition") -> dict | None:
    """Validate DynamoDB expression for dangerous patterns to prevent injection attacks.
    
    Returns error dict if validation fails, None if valid.
    """
    if not expression:
        return None
    
    # Check for SQL injection attempts
    expr_upper = expression.upper()
    for keyword in _SQL_KEYWORDS:
        if keyword in expr_upper:
            return {
                "error": True,
                "code": "ValidationException",
                "message": f"Expression contains prohibited keyword: {keyword}"
            }
    
    # Check for command injection attempts
    for char in _DANGEROUS_CHARS:
        if char in expression:
            return {
                "error": True,
                "code": "ValidationException",
                "message": f"Expression contains prohibited character: {repr(char)}"
            }
    
    # Limit expression length to prevent DoS
    if len(expression) > 4096:
        return {
            "error": True,
            "code": "ValidationException",
            "message": f"Expression too long ({len(expression)} > 4096 characters)"
        }
    
    # Basic bracket balance check
    if expression.count('(') != expression.count(')'):
        return {
            "error": True,
            "code": "ValidationException",
            "message": "Unbalanced parentheses in expression"
        }
    
    return None


def _validate_expression_attributes(
    names: Optional[dict[str, str]] = None,
    values: Optional[dict[str, Any]] = None
) -> dict | None:
    """Validate expression attribute names and values for security.
    
    Returns error dict if validation fails, None if valid.
    """
    if names:
        for placeholder, actual in names.items():
            if not _VALID_ATTRIBUTE_PLACEHOLDER.match(placeholder):
                return {
                    "error": True,
                    "code": "ValidationException",
                    "message": f"Invalid attribute name placeholder: {placeholder}"
                }
            # Allow dotted notation for nested attributes
            parts = actual.split('.')
            for part in parts:
                if part and not _VALID_ATTRIBUTE_NAME.match(part):
                    return {
                        "error": True,
                        "code": "ValidationException",
                        "message": f"Invalid attribute name: {actual}"
                    }
    
    if values:
        for placeholder, value in values.items():
            if not _VALID_EXPRESSION_PLACEHOLDER.match(placeholder):
                return {
                    "error": True,
                    "code": "ValidationException",
                    "message": f"Invalid value placeholder: {placeholder}"
                }
            # Limit value size to prevent memory issues (DynamoDB limit is 400KB)
            if isinstance(value, str) and len(value) > 400_000:
                return {
                    "error": True,
                    "code": "ValidationException",
                    "message": f"Value for {placeholder} exceeds size limit"
                }
    
    return None


def _check_table_allowed(table_name: str) -> dict | None:
    """Reject the call if the table is not in the allowlist."""
    if not ALLOWED_TABLE_PATTERNS:
        return None
    if any(fnmatch.fnmatch(table_name, pat) for pat in ALLOWED_TABLE_PATTERNS):
        return None
    return {
        "error": True,
        "code": "TableNotAllowed",
        "message": (
            f"Table '{table_name}' is not in the allowed list. Allowed: {ALLOWED_TABLE_PATTERNS}"
        ),
    }


_session_items = 0


def _check_session_cap(count: int) -> dict | None:
    """Reject if cumulative items returned this session exceed the cap."""
    global _session_items
    if MAX_ITEMS_PER_SESSION <= 0:
        return None
    with _guard_lock:
        _session_items += count
        if _session_items > MAX_ITEMS_PER_SESSION:
            return {
                "error": True,
                "code": "SessionItemCapExceeded",
                "message": (
                    f"Session cap of {MAX_ITEMS_PER_SESSION} items reached "
                    f"({_session_items} total). Restart the server to reset."
                ),
            }
    return None


def _audit(tool: str, table: str | None = None, items: int = 0) -> None:
    """Log a tool invocation to stderr when audit logging is enabled."""
    if not AUDIT_LOG:
        return
    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    parts = [f"[ddb-audit] {ts} tool={tool}"]
    if table:
        parts.append(f"table={table}")
    if items:
        parts.append(f"items={items}")
    print(" ".join(parts), file=sys.stderr, flush=True)


def _check_response_size(result: dict) -> dict:
    """Truncate items if the serialized response exceeds MAX_RESPONSE_BYTES."""
    if MAX_RESPONSE_BYTES <= 0:
        return result
    serialized = json.dumps(result, default=str)
    if len(serialized.encode()) <= MAX_RESPONSE_BYTES:
        return result
    if "items" not in result:
        return {
            "error": True,
            "code": "ResponseTooLarge",
            "message": (
                f"Response ({len(serialized.encode())} bytes) exceeds "
                f"DDB_MAX_RESPONSE_BYTES ({MAX_RESPONSE_BYTES})."
            ),
        }
    items = result["items"]
    while items and len(json.dumps(result, default=str).encode()) > MAX_RESPONSE_BYTES:
        items.pop()
    result["items"] = items
    result["truncated"] = True
    result["truncated_message"] = (
        f"Response exceeded {MAX_RESPONSE_BYTES} bytes. Items truncated to {len(items)}."
    )
    if "count" in result:
        result["count"] = len(items)
    return result


@mcp.tool()
def list_tables(name_contains: str = "") -> dict:
    """List DynamoDB tables in the configured region.

    Args:
        name_contains: Optional case-insensitive substring filter
                       (e.g. "orders" matches "dev-orders-oc").
    """
    rl = _check_rate_limit()
    if rl:
        return rl
    try:
        names: list[str] = []
        paginator = _client.get_paginator("list_tables")
        for page in paginator.paginate():
            names.extend(page.get("TableNames", []))
        if name_contains:
            q = name_contains.lower()
            names = [n for n in names if q in n.lower()]
        if ALLOWED_TABLE_PATTERNS:
            names = [
                n for n in names if any(fnmatch.fnmatch(n, pat) for pat in ALLOWED_TABLE_PATTERNS)
            ]
        _audit("list_tables")
        return {"region": REGION, "count": len(names), "tables": names}
    except (ClientError, BotoCoreError) as e:
        return _err(e)


@mcp.tool()
def describe_table(table_name: str) -> dict:
    """Describe a table: key schema, attribute types, GSIs, LSIs, item count, size.

    NOTE: DynamoDB only declares attributes that are used as keys or index keys
    in `attribute_definitions`. Non-key attributes are schemaless — use
    `sample_items` to discover the full shape of items.
    """
    rl = _check_rate_limit()
    if rl:
        return rl
    ta = _check_table_allowed(table_name)
    if ta:
        return ta
    try:
        resp = _client.describe_table(TableName=table_name)
        t = resp["Table"]
        info = {
            "table_name": t.get("TableName"),
            "status": t.get("TableStatus"),
            "item_count": t.get("ItemCount"),
            "size_bytes": t.get("TableSizeBytes"),
            "billing_mode": (t.get("BillingModeSummary") or {}).get("BillingMode") or "PROVISIONED",
            "key_schema": t.get("KeySchema", []),
            "attribute_definitions": t.get("AttributeDefinitions", []),
            "global_secondary_indexes": [
                {
                    "name": gsi.get("IndexName"),
                    "key_schema": gsi.get("KeySchema"),
                    "projection": gsi.get("Projection"),
                    "status": gsi.get("IndexStatus"),
                    "item_count": gsi.get("ItemCount"),
                }
                for gsi in (t.get("GlobalSecondaryIndexes") or [])
            ],
            "local_secondary_indexes": [
                {
                    "name": lsi.get("IndexName"),
                    "key_schema": lsi.get("KeySchema"),
                    "projection": lsi.get("Projection"),
                }
                for lsi in (t.get("LocalSecondaryIndexes") or [])
            ],
            "stream": t.get("StreamSpecification"),
            "ttl_description": None,
            "arn": t.get("TableArn"),
            "created": str(t.get("CreationDateTime")),
        }
        try:
            ttl = _client.describe_time_to_live(TableName=table_name)
            info["ttl_description"] = ttl.get("TimeToLiveDescription")
        except (ClientError, BotoCoreError):
            pass
        _audit("describe_table", table=table_name)
        return _jsonify(info)
    except (ClientError, BotoCoreError) as e:
        return _err(e)


@mcp.tool()
def get_indexes(table_name: str) -> dict:
    """Trimmed view of only the GSIs and LSIs on a table (keys + projection)."""
    rl = _check_rate_limit()
    if rl:
        return rl
    ta = _check_table_allowed(table_name)
    if ta:
        return ta
    try:
        resp = _client.describe_table(TableName=table_name)
        t = resp["Table"]
        result = _jsonify(
            {
                "table_name": table_name,
                "global_secondary_indexes": [
                    {
                        "name": gsi.get("IndexName"),
                        "key_schema": gsi.get("KeySchema"),
                        "projection": gsi.get("Projection"),
                        "item_count": gsi.get("ItemCount"),
                    }
                    for gsi in (t.get("GlobalSecondaryIndexes") or [])
                ],
                "local_secondary_indexes": [
                    {
                        "name": lsi.get("IndexName"),
                        "key_schema": lsi.get("KeySchema"),
                        "projection": lsi.get("Projection"),
                    }
                    for lsi in (t.get("LocalSecondaryIndexes") or [])
                ],
            }
        )
        _audit("get_indexes", table=table_name)
        return result
    except (ClientError, BotoCoreError) as e:
        return _err(e)


@mcp.tool()
def sample_items(table_name: str, n: int = 5) -> dict:
    """Fetch a few items via a small scan to discover the attribute shape.

    Useful because DynamoDB is schemaless and `describe_table` only reveals
    key attributes. Capped at n={SAMPLE_MAX_N} (env: DDB_SAMPLE_MAX_N).
    """
    rl = _check_rate_limit()
    if rl:
        return rl
    ta = _check_table_allowed(table_name)
    if ta:
        return ta
    n = max(1, min(int(n), SAMPLE_MAX_N))
    try:
        table = _resource.Table(table_name)
        resp = table.scan(Limit=n, **_RCC_KWARGS)
        items = resp.get("Items", [])
        cap_err = _check_session_cap(len(items))
        if cap_err:
            return cap_err
        attrs: set[str] = set()
        for it in items:
            attrs.update(it.keys())
        result: dict = {
            "table_name": table_name,
            "returned": len(items),
            "attributes_seen": sorted(attrs),
            "items": items,
        }
        cc = _consumed_capacity(resp)
        if cc:
            result["consumed_capacity"] = cc
        _audit("sample_items", table=table_name, items=len(items))
        return _check_response_size(_jsonify(result))
    except (ClientError, BotoCoreError) as e:
        return _err(e)


@mcp.tool()
def get_item(
    table_name: str,
    key: dict,
    consistent_read: bool = False,
) -> dict:
    """Fetch a single item by primary key.

    Args:
        table_name: Exact table name (run `list_tables` first if unsure).
        key: Primary key dict. Partition-only: {"order_id": "abc"}.
             Composite: {"pk": "USER#1", "sk": "ORDER#2"}.
        consistent_read: Use strongly-consistent read. Default eventual.
    """
    rl = _check_rate_limit()
    if rl:
        return rl
    ta = _check_table_allowed(table_name)
    if ta:
        return ta
    try:
        table = _resource.Table(table_name)
        resp = table.get_item(Key=key, ConsistentRead=consistent_read, **_RCC_KWARGS)
        item = resp.get("Item")
        item_count = 1 if item else 0
        cap_err = _check_session_cap(item_count)
        if cap_err:
            return cap_err
        result: dict = {"found": item is not None, "item": item}
        cc = _consumed_capacity(resp)
        if cc:
            result["consumed_capacity"] = cc
        _audit("get_item", table=table_name, items=item_count)
        return _check_response_size(_jsonify(result))
    except (ClientError, BotoCoreError) as e:
        return _err(e)


@mcp.tool()
def batch_get_item(
    table_name: str,
    keys: list[dict],
    consistent_read: bool = False,
) -> dict:
    """Fetch multiple items by primary key. Automatically chunks into
    {BATCH_CHUNK_SIZE}s (env: DDB_BATCH_CHUNK_SIZE) and retries any
    UnprocessedKeys (up to {BATCH_MAX_RETRIES} retries, env: DDB_BATCH_MAX_RETRIES)."""
    rl = _check_rate_limit()
    if rl:
        return rl
    ta = _check_table_allowed(table_name)
    if ta:
        return ta
    if not keys:
        return {"count": 0, "items": []}
    try:
        all_items: list[dict] = []
        total_cu = 0.0
        total_rcu = 0.0
        for i in range(0, len(keys), BATCH_CHUNK_SIZE):
            chunk = keys[i : i + BATCH_CHUNK_SIZE]
            req = {
                table_name: {
                    "Keys": chunk,
                    "ConsistentRead": consistent_read,
                }
            }
            retries = 0
            while req:
                resp = _resource.batch_get_item(
                    RequestItems=req,
                    **_RCC_KWARGS,
                )
                all_items.extend(resp.get("Responses", {}).get(table_name, []))
                for cc in resp.get("ConsumedCapacity") or []:
                    total_cu += float(cc.get("CapacityUnits", 0))
                    total_rcu += float(cc.get("ReadCapacityUnits", 0))
                req = resp.get("UnprocessedKeys") or {}
                if req:
                    retries += 1
                    if retries > BATCH_MAX_RETRIES:
                        break
        cap_err = _check_session_cap(len(all_items))
        if cap_err:
            return cap_err
        result: dict = {"count": len(all_items), "items": all_items}
        if SHOW_COST:
            result["consumed_capacity"] = {
                "table": table_name,
                "capacity_units": total_cu,
                "read_capacity_units": total_rcu,
            }
        _audit("batch_get_item", table=table_name, items=len(all_items))
        return _check_response_size(_jsonify(result))
    except (ClientError, BotoCoreError) as e:
        return _err(e)


@mcp.tool()
def query(
    table_name: str,
    key_condition_expression: str,
    expression_attribute_values: dict,
    expression_attribute_names: dict | None = None,
    filter_expression: str | None = None,
    projection_expression: str | None = None,
    index_name: str | None = None,
    limit: int = QUERY_DEFAULT_LIMIT,
    scan_index_forward: bool = True,
    exclusive_start_key: dict | None = None,
) -> dict:
    """Query a table or a GSI/LSI using DynamoDB expression syntax.

    Example:
        key_condition_expression = "#pk = :pk AND begins_with(#sk, :sk)"
        expression_attribute_names  = {"#pk": "user_id", "#sk": "order_id"}
        expression_attribute_values = {":pk": "U123", ":sk": "ORD#"}
        index_name = "by_user_id"   # querying a GSI instead of the base table

    Pagination: if response includes `last_evaluated_key`, pass it back as
    `exclusive_start_key` to get the next page.

    Limits: `limit` is capped at {QUERY_MAX_LIMIT} (env: DDB_QUERY_MAX_LIMIT);
    default {QUERY_DEFAULT_LIMIT} (env: DDB_QUERY_DEFAULT_LIMIT).
    """
    rl = _check_rate_limit()
    if rl:
        return rl
    ta = _check_table_allowed(table_name)
    if ta:
        return ta
    
    # Security: Validate expressions to prevent injection
    expr_err = _validate_expression(key_condition_expression, "key_condition")
    if expr_err:
        return expr_err
    
    if filter_expression:
        filter_err = _validate_expression(filter_expression, "filter")
        if filter_err:
            return filter_err
    
    if projection_expression:
        proj_err = _validate_expression(projection_expression, "projection")
        if proj_err:
            return proj_err
    
    attr_err = _validate_expression_attributes(expression_attribute_names, expression_attribute_values)
    if attr_err:
        return attr_err
    
    limit = max(1, min(int(limit), QUERY_MAX_LIMIT))
    try:
        table = _resource.Table(table_name)
        kwargs: dict = {
            "KeyConditionExpression": key_condition_expression,
            "ExpressionAttributeValues": expression_attribute_values,
            "Limit": limit,
            "ScanIndexForward": scan_index_forward,
            **_RCC_KWARGS,
        }
        if expression_attribute_names:
            kwargs["ExpressionAttributeNames"] = expression_attribute_names
        if filter_expression:
            kwargs["FilterExpression"] = filter_expression
        if projection_expression:
            kwargs["ProjectionExpression"] = projection_expression
        if index_name:
            kwargs["IndexName"] = index_name
        if exclusive_start_key:
            kwargs["ExclusiveStartKey"] = exclusive_start_key
        resp = table.query(**kwargs)
        items = resp.get("Items", [])
        cap_err = _check_session_cap(len(items))
        if cap_err:
            return cap_err
        result: dict = {
            "count": resp.get("Count", 0),
            "scanned_count": resp.get("ScannedCount", 0),
            "items": items,
            "last_evaluated_key": resp.get("LastEvaluatedKey"),
        }
        cc = _consumed_capacity(resp)
        if cc:
            result["consumed_capacity"] = cc
        _audit("query", table=table_name, items=len(items))
        return _check_response_size(_jsonify(result))
    except (ClientError, BotoCoreError) as e:
        return _err(e)


@mcp.tool()
def scan(
    table_name: str,
    filter_expression: str | None = None,
    expression_attribute_values: dict | None = None,
    expression_attribute_names: dict | None = None,
    projection_expression: str | None = None,
    index_name: str | None = None,
    limit: int = SCAN_DEFAULT_LIMIT,
    exclusive_start_key: dict | None = None,
    max_pages: int = SCAN_DEFAULT_MAX_PAGES,
) -> dict:
    """Scan a table or index. Prefer `query` when you can — scans read every item.

    Safety: default max_pages={SCAN_DEFAULT_MAX_PAGES} (env: DDB_SCAN_DEFAULT_MAX_PAGES)
    to prevent accidentally walking huge tables.
    Hard caps: max_pages<={SCAN_MAX_PAGES} (env: DDB_SCAN_MAX_PAGES),
    limit<={SCAN_MAX_LIMIT} (env: DDB_SCAN_MAX_LIMIT).

    Pagination: pass returned `last_evaluated_key` back as `exclusive_start_key`.
    """
    rl = _check_rate_limit()
    if rl:
        return rl
    ta = _check_table_allowed(table_name)
    if ta:
        return ta
    
    # Security: Validate expressions to prevent injection
    if filter_expression:
        filter_err = _validate_expression(filter_expression, "filter")
        if filter_err:
            return filter_err
    
    if projection_expression:
        proj_err = _validate_expression(projection_expression, "projection")
        if proj_err:
            return proj_err
    
    attr_err = _validate_expression_attributes(expression_attribute_names, expression_attribute_values)
    if attr_err:
        return attr_err
    
    limit = max(1, min(int(limit), SCAN_MAX_LIMIT))
    max_pages = max(1, min(int(max_pages), SCAN_MAX_PAGES))
    try:
        table = _resource.Table(table_name)
        items: list[dict] = []
        last_key = exclusive_start_key
        pages = 0
        scanned_total = 0
        total_cu = 0.0
        total_rcu = 0.0
        while pages < max_pages:
            kwargs: dict = {"Limit": limit, **_RCC_KWARGS}
            if filter_expression:
                kwargs["FilterExpression"] = filter_expression
            if expression_attribute_values:
                kwargs["ExpressionAttributeValues"] = expression_attribute_values
            if expression_attribute_names:
                kwargs["ExpressionAttributeNames"] = expression_attribute_names
            if projection_expression:
                kwargs["ProjectionExpression"] = projection_expression
            if index_name:
                kwargs["IndexName"] = index_name
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            resp = table.scan(**kwargs)
            items.extend(resp.get("Items", []))
            scanned_total += resp.get("ScannedCount", 0)
            cc = resp.get("ConsumedCapacity") or {}
            total_cu += float(cc.get("CapacityUnits", 0))
            total_rcu += float(cc.get("ReadCapacityUnits", 0))
            last_key = resp.get("LastEvaluatedKey")
            pages += 1
            if not last_key:
                break
        cap_err = _check_session_cap(len(items))
        if cap_err:
            return cap_err
        result: dict = {
            "count": len(items),
            "scanned_count": scanned_total,
            "pages_read": pages,
            "items": items,
            "last_evaluated_key": last_key,
        }
        if SHOW_COST:
            result["consumed_capacity"] = {
                "table": table_name,
                "capacity_units": total_cu,
                "read_capacity_units": total_rcu,
            }
        _audit("scan", table=table_name, items=len(items))
        return _check_response_size(_jsonify(result))
    except (ClientError, BotoCoreError) as e:
        return _err(e)


def _check_credential_security() -> None:
    """Check AWS credential configuration for security issues and warn."""
    warnings_list = []
    
    # Check for hardcoded credentials
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        key_id = os.environ.get("AWS_ACCESS_KEY_ID", "")
        if key_id.startswith("AKIA"):
            warnings_list.append(
                "Using long-term AWS access key. Consider using temporary credentials (STS/SSO) instead."
            )
        warnings_list.append(
            "AWS_ACCESS_KEY_ID in environment. Consider using IAM roles or AWS_PROFILE instead."
        )
    
    # Warn about HTTP mode without auth and TLS
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport in ("http", "streamable-http", "sse"):
        warnings_list.append(
            f"Running in {transport.upper()} mode without built-in authentication. "
            "CRITICAL: Use a reverse proxy with authentication in production!"
        )
        
        # Check if TLS is configured
        if not os.environ.get("DDB_TLS_CERT") and not os.environ.get("DDB_REQUIRE_TLS"):
            warnings_list.append(
                "No TLS configuration detected. Data will be transmitted in plaintext. "
                "Set DDB_TLS_CERT/DDB_TLS_KEY or use a TLS-terminating proxy."
            )
    
    # Print warnings
    for warning in warnings_list:
        warnings.warn(f"[SECURITY] {warning}", stacklevel=2)
        print(f"[ddb-explorer] WARNING: {warning}", file=sys.stderr, flush=True)


def main() -> None:
    """Entry point. Dispatches to the transport selected by MCP_TRANSPORT."""
    # Security check on startup
    _check_credential_security()
    
    if TRANSPORT == "stdio":
        mcp.run()
        return
    if TRANSPORT in ("http", "streamable-http"):
        import sys

        print(
            f"[ddb-explorer] streamable-http listening on "
            f"http://{HTTP_HOST}:{HTTP_PORT}/mcp  (region={REGION})",
            file=sys.stderr,
            flush=True,
        )
        mcp.run(transport="streamable-http")
        return
    if TRANSPORT == "sse":
        import sys

        print(
            f"[ddb-explorer] sse listening on "
            f"http://{HTTP_HOST}:{HTTP_PORT}/sse  (region={REGION})",
            file=sys.stderr,
            flush=True,
        )
        mcp.run(transport="sse")
        return
    raise SystemExit(
        f"[ddb-explorer] Unknown MCP_TRANSPORT={TRANSPORT!r}. "
        f"Use one of: stdio, http (streamable-http), sse."
    )


if __name__ == "__main__":
    main()
