# ddb-explorer-mcp

Read-only MCP server for Amazon DynamoDB — safe exploration, querying, and schema discovery.

## Quick Start

```bash
# Install dependencies
make setup

# Run the server (stdio mode, for local MCP clients)
make run

# Run in HTTP mode (for remote/team use)
make run-http

# Run tests (uses moto, no real AWS creds needed)
make test
```

## Register as MCP Server

```bash
# Claude Code CLI — from this directory:
claude mcp add ddb-explorer -- uv run --directory . ddb-explorer-mcp

# Or globally via uvx (no clone needed):
claude mcp add ddb-explorer -- uvx ddb-explorer-mcp
```

Set your AWS credentials via environment variables or `AWS_PROFILE`:

```bash
export AWS_REGION=us-east-2
export AWS_PROFILE=default
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_tables` | List all DynamoDB tables (with optional name filter) |
| `describe_table` | Schema, key structure, indexes, billing, item count |
| `get_item` | Fetch a single item by primary key |
| `batch_get_item` | Fetch up to 100 items in one call (auto-chunks) |
| `query` | Query by partition key with optional sort-key conditions |
| `scan` | Full-table scan with optional filters (default max 1 page) |
| `get_paginated_items` | Auto-paginating query/scan with cursor support |
| `describe_all_schemas` | Summarize key schemas for all tables at once |

## Architecture

- **Source:** `src/ddb_explorer_mcp/server.py` (single-file server)
- **Transport:** stdio (default) or streamable-HTTP (`MCP_TRANSPORT=http`)
- **Safety:** Write operations are structurally absent — not disabled, not implemented
- **Dependencies:** `mcp>=1.9.0`, `boto3>=1.34.0`

## Development

```bash
make lint       # Lint with ruff
make format     # Auto-format
make check      # lint + format-check + tests (same as CI)
```

Tests use `moto` to mock DynamoDB — no AWS credentials or network access required.
