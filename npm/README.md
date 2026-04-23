# ddb-explorer-mcp

**Read-only [MCP](https://modelcontextprotocol.io) server for Amazon DynamoDB** — safe
exploration, querying, and schema discovery from your AI coding assistant.

This is a thin **npm wrapper** that delegates to the Python package via
[`uvx`](https://github.com/astral-sh/uv). It exists so JS-ecosystem users can
install the server with `npx`:

```bash
npx ddb-explorer-mcp
```

## Prerequisites

[`uv`](https://github.com/astral-sh/uv) must be installed. The script will
print install instructions if it is missing.

## Full documentation

See the main repository: <https://github.com/mudassirgithub/ddb-explorer-mcp>
