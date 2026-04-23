# Example prompts

Copy-paste these into any MCP-compatible AI assistant (Cursor, Claude Desktop,
Claude Code, Windsurf, Zed, etc.) after installing `ddb-explorer-mcp`.

## Discovery

> List all DynamoDB tables in this region.

> List all tables with "orders" in the name and describe the newest one.

> Show me the schema for the `prod-users` table — include every GSI and LSI.

## Schema exploration

> Sample 5 items from `prod-events` and tell me which attributes are always
> present vs. occasionally missing.

> What secondary indexes does `prod-orders` have? Which one should I use to
> query by `user_id` and `created_at`?

## Single-item reads

> Using ddb-explorer, get the item from `prod-users` with primary key
> `{"user_id": "U-a1b2c3"}`.

## Batch reads

> Batch-get these order IDs from `prod-orders`:
> `[{"order_id": "ORD-001"}, {"order_id": "ORD-002"}, {"order_id": "ORD-003"}]`

## Query (GSI)

> Query `prod-orders` where `user_id = 'U-a1b2c3'` and
> `created_at > '2026-01-01'`, using the `by_user_created` GSI, limit 20,
> newest first.

## Scan (small tables only)

> Scan `staging-feature-flags` and show me every item. It's a small table
> (< 50 items).

## Cross-table analysis

> Compare the schemas of `prod-orders` and `staging-orders`. Are there
> attributes in one that don't exist in the other?

> Look at the GSIs on `prod-users` and `prod-sessions`. Do any share the
> same partition key, suggesting I could merge the tables?
