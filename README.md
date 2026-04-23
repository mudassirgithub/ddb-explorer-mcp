# ddb-explorer-mcp

<p align="center">
  <strong>Read-only <a href="https://modelcontextprotocol.io">MCP</a> server for Amazon DynamoDB</strong><br>
  Safe exploration, querying, and schema discovery from your AI coding assistant.
</p>

<p align="center">
  <a href="https://pypi.org/project/ddb-explorer-mcp/"><img src="https://img.shields.io/pypi/v/ddb-explorer-mcp.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/ddb-explorer-mcp/"><img src="https://img.shields.io/pypi/pyversions/ddb-explorer-mcp.svg" alt="Python"></a>
  <a href="https://pypi.org/project/ddb-explorer-mcp/"><img src="https://img.shields.io/pypi/dm/ddb-explorer-mcp.svg" alt="Downloads"></a>
  <a href="https://github.com/mudassirgithub/ddb-explorer-mcp/actions/workflows/ci.yml"><img src="https://github.com/mudassirgithub/ddb-explorer-mcp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/mudassirgithub/ddb-explorer-mcp/pkgs/container/ddb-explorer-mcp"><img src="https://img.shields.io/badge/GHCR-image-blue?logo=docker" alt="Docker"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License: Apache-2.0"></a>
  <a href="https://smithery.ai/server/ddb-explorer-mcp"><img src="https://smithery.ai/badge/ddb-explorer-mcp" alt="Smithery"></a>
</p>

---

## One-click install

Add `ddb-explorer-mcp` to your IDE in one click:

[<img src="https://cursor.com/deeplink/mcp-install-dark.svg" alt="Install in Cursor" height="32">](https://cursor.com/install-mcp?name=ddb-explorer&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJkZGItZXhwbG9yZXItbWNwIl0sImVudiI6eyJBV1NfUkVHSU9OIjoidXMtZWFzdC0yIn19)
&nbsp;&nbsp;
[<img src="https://img.shields.io/badge/VS_Code-Install_MCP-007ACC?logo=visual-studio-code&logoColor=white" alt="Install in VS Code" height="32">](https://insiders.vscode.dev/redirect?url=vscode%3Amcp%2Finstall%3F%7B%22name%22%3A%22ddb-explorer%22%2C%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22ddb-explorer-mcp%22%5D%2C%22env%22%3A%7B%22AWS_REGION%22%3A%22us-east-2%22%7D%7D)
&nbsp;&nbsp;
[<img src="https://img.shields.io/badge/Smithery-Install-orange?logo=data:image/svg+xml;base64,..." alt="Install via Smithery" height="32">](https://smithery.ai/server/ddb-explorer-mcp)

Or install from the command line:

```bash
# Smithery (auto-configures your client)
npx -y @smithery/cli install ddb-explorer-mcp --client cursor

# Claude Code CLI
claude mcp add ddb-explorer -- uvx ddb-explorer-mcp

# npm wrapper (delegates to uvx under the hood)
npx ddb-explorer-mcp
```

---

## Why ddb-explorer-mcp?

Write operations are **structurally not exposed**. The LLM cannot call
`PutItem`, `UpdateItem`, `DeleteItem`, `BatchWriteItem`, `TransactWriteItems`,
`CreateTable`, `DeleteTable`, or `UpdateTable` because those tools are not
registered with the server. Not a config flag — they physically do not exist
in the tool namespace.

| | |
|---|---|
| **Safe by construction** | Read-only tool surface; no writes possible |
| **Eight practical tools** | list / describe / get / batch-get / query / scan + schema discovery helpers |
| **Two transports** | stdio (local) or streamable-HTTP (hosted) |
| **Works everywhere** | Cursor, Claude Desktop, VS Code, Windsurf, Zed, Claude Code CLI, any MCP client |
| **Standard AWS creds** | Env vars, profiles, SSO, IMDS all just work |
| **Guardrails for scans** | Default `max_pages=1`, hard caps on limits (all [configurable via env vars](#safety-limits)), auto-pagination for `query` |
| **Smart batch ops** | `batch_get_item` auto-chunks into 100s and retries `UnprocessedKeys` |
| **JSON-clean output** | `Decimal`, `set`, `bytes` coerced to JSON-native types |

## Installation

### For end users (individual, stdio mode)

```bash
uvx ddb-explorer-mcp
```

That's it. [`uv`](https://github.com/astral-sh/uv) downloads, caches, and runs the server
in an isolated environment on first use.

### From a local clone

Clone the repo and the MCP server auto-registers in **Cursor** and **VS Code**:

```bash
git clone https://github.com/mudassirgithub/ddb-explorer-mcp.git
cd ddb-explorer-mcp
make setup          # installs Python + all dependencies via uv
```

Open the cloned folder in your IDE:

- **Cursor** — reads `.cursor/mcp.json` automatically. Restart Cursor, then
  check Settings → Tools & MCP. The server appears as `ddb-explorer`.
- **VS Code** — reads `.vscode/mcp.json` automatically (native MCP support in
  VS Code 1.99+). No extension required.
- **Claude Code CLI** — register the local server manually:

  ```bash
  claude mcp add ddb-explorer -- uv run --directory /path/to/ddb-explorer-mcp ddb-explorer-mcp
  ```

- **Claude Desktop / Windsurf / other clients** — copy the config from
  [`examples/cursor-local.json`](examples/cursor-local.json) and replace the
  path with your clone directory.

Edit `AWS_REGION` / `AWS_PROFILE` in the relevant MCP config to match your
environment. Changes to the Python source are picked up on the next server
restart — no reinstall needed.

#### Makefile targets

| Target | What it does |
|---|---|
| `make setup` | Install Python + dependencies via `uv sync` |
| `make run` | Start the server in stdio mode |
| `make run-http` | Start the server in HTTP mode on `localhost:8765` |
| `make test` | Run the test suite (uses moto — no real AWS creds needed) |
| `make lint` | Lint with ruff |
| `make format` | Auto-format with ruff |
| `make check` | Run lint + format-check + tests (same as CI) |
| `make clean` | Remove build/cache artifacts |

### For teams (hosted HTTP mode)

```bash
docker run --rm -p 8765:8765 \
  -e MCP_TRANSPORT=http \
  -e MCP_HOST=0.0.0.0 \
  -e AWS_REGION=us-east-2 \
  -e AWS_ACCESS_KEY_ID=... \
  -e AWS_SECRET_ACCESS_KEY=... \
  ghcr.io/mudassirgithub/ddb-explorer-mcp:latest
```

See [HTTP deployment](#http-mode-deployment) below.

## Client configuration

Ready-to-paste configs are also available in the [`examples/`](examples/) directory.

### Cursor

Add to `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (per-project):

```json
{
  "mcpServers": {
    "ddb-explorer": {
      "command": "uvx",
      "args": ["ddb-explorer-mcp"],
      "env": {
        "AWS_PROFILE": "default",
        "AWS_REGION": "us-east-2"
      }
    }
  }
}
```

Restart Cursor (⌘Q on macOS). Open Settings → Tools & MCP to verify.

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "ddb-explorer": {
      "command": "uvx",
      "args": ["ddb-explorer-mcp"],
      "env": {
        "AWS_PROFILE": "default",
        "AWS_REGION": "us-east-2"
      }
    }
  }
}
```

### Claude Code CLI

```bash
claude mcp add ddb-explorer \
  --env AWS_PROFILE=default \
  --env AWS_REGION=us-east-2 \
  -- uvx ddb-explorer-mcp
```

### VS Code (with Cline, Continue, or native MCP)

Add to your VS Code `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "ddb-explorer": {
        "command": "uvx",
        "args": ["ddb-explorer-mcp"],
        "env": {
          "AWS_PROFILE": "default",
          "AWS_REGION": "us-east-2"
        }
      }
    }
  }
}
```

### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "ddb-explorer": {
      "command": "uvx",
      "args": ["ddb-explorer-mcp"],
      "env": {
        "AWS_PROFILE": "default",
        "AWS_REGION": "us-east-2"
      }
    }
  }
}
```

### Remote HTTP (any client)

```json
{
  "mcpServers": {
    "ddb-explorer": {
      "type": "streamableHttp",
      "url": "https://ddb-explorer.example.com/mcp",
      "headers": {
        "Authorization": "Bearer <your-token>"
      }
    }
  }
}
```

## Tools reference

| Tool | Purpose |
|---|---|
| `list_tables(name_contains?)` | List tables in the region, optionally filtered by substring |
| `describe_table(table_name)` | Full description: keys, attrs, GSIs, LSIs, TTL, item count, size |
| `get_indexes(table_name)` | Trimmed view — just the secondary indexes |
| `sample_items(table_name, n?)` | Fetch a few items to discover the schemaless attribute shape |
| `get_item(table_name, key, consistent_read?)` | Single-item read by primary key |
| `batch_get_item(table_name, keys[], consistent_read?)` | Many items by PK, auto-chunked into 100s, retries `UnprocessedKeys` |
| `query(table_name, key_condition_expression, expression_attribute_values, ...)` | Query base table or GSI/LSI with full DynamoDB expression syntax |
| `scan(table_name, filter_expression?, max_pages?, ...)` | Scan with safe pagination caps (default `max_pages=1`, hard cap 20) |

### Example prompts

> "List all tables with `order` in the name and describe the newest one."

> "Query `prod-orders` where `user_id = 'U123'` and `created_at > '2026-01-01'`, using the `by_user_created` GSI, limit 20."

> "Sample 5 items from `prod-events` and tell me which attributes are always present."

> "Compare the schemas of `prod-orders` and `staging-orders` — are there attributes in one that don't exist in the other?"

See [`examples/PROMPTS.md`](examples/PROMPTS.md) for more.

## Configuration

All configuration is via environment variables.

### AWS credentials / region

The server uses the **standard boto3 credential resolution chain**. The first
valid source wins:

1. `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (+ optional `AWS_SESSION_TOKEN`) env vars
2. `AWS_PROFILE` pointing to a profile in `~/.aws/credentials` or `~/.aws/config`
3. AWS SSO cache
4. IAM role attached to the execution context (EC2 instance profile, ECS task role, Lambda role)

| Variable | Default | Purpose |
|---|---|---|
| `AWS_REGION` | `us-east-2` | DynamoDB region |
| `AWS_DEFAULT_REGION` | — | Fallback for region |
| `AWS_PROFILE` | — | Named profile to use |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` | — | Explicit credentials |

### Transport

| Variable | Default | Purpose |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `stdio` \| `http` \| `sse` |
| `MCP_HOST` | `127.0.0.1` | HTTP bind host (use `0.0.0.0` to expose) |
| `MCP_PORT` | `8765` | HTTP bind port |

### Safety limits

All tool safety caps are configurable via environment variables. Defaults match
the original hardcoded values — existing deployments are unaffected unless you
explicitly override them.

| Variable | Default | Purpose | Cost / data implications |
|---|---|---|---|
| `DDB_SCAN_MAX_LIMIT` | `500` | Hard cap on items per scan page | **Most impactful.** Scans read every item in the table. On large prod tables (millions of items), high limits burn RCUs and can return sensitive data into the LLM context. Consider `50`–`100` for production. |
| `DDB_SCAN_DEFAULT_LIMIT` | `50` | Default items per scan page (when caller omits `limit`) | Safety net — keeps casual/unparameterized scans small. |
| `DDB_SCAN_MAX_PAGES` | `20` | Hard cap on pages per scan call | Combined with `SCAN_MAX_LIMIT`, this controls the maximum blast radius of a single scan. `20 pages × 500 items = 10,000 items` worst case. Lower to `3`–`5` on production. |
| `DDB_SCAN_DEFAULT_MAX_PAGES` | `1` | Default pages per scan (when caller omits `max_pages`) | **Keep this at `1` for production.** This single setting prevents the LLM from accidentally walking an entire table. |
| `DDB_QUERY_MAX_LIMIT` | `500` | Hard cap on items per query | Queries are targeted (use a partition key), so cost is lower than scans. But a hot partition could still have thousands of items. `100`–`200` is safer for production. |
| `DDB_QUERY_DEFAULT_LIMIT` | `50` | Default items per query | Safety net for unparameterized queries. |
| `DDB_SAMPLE_MAX_N` | `20` | Max items returned by `sample_items` | Low risk — this is a schema discovery tool. Even at `20`, cost is negligible. |
| `DDB_BATCH_CHUNK_SIZE` | `100` | Keys per `BatchGetItem` API call | Matches the DynamoDB service maximum. Lowering this adds round-trips without saving cost. Leave at `100` unless you need to reduce per-request throughput spikes on provisioned tables. |
| `DDB_BATCH_MAX_RETRIES` | `10` | Max retries for `UnprocessedKeys` | Only relevant under throttling. On provisioned-capacity tables, aggressive retries can amplify throttle pressure. On on-demand tables, this rarely triggers. |
| `DDB_SHOW_COST` | `false` | When `true`, each data-plane tool response includes a `consumed_capacity` field with exact RCUs reported by DynamoDB | Zero overhead when disabled. When enabled, uses DynamoDB's native `ReturnConsumedCapacity` — no extra API calls, no estimation. Covers `get_item`, `batch_get_item`, `query`, `scan`, and `sample_items`. Control-plane tools (`list_tables`, `describe_table`, `get_indexes`) are always free and never report capacity. |
| `DDB_MAX_ITEMS_PER_SESSION` | `0` (unlimited) | Cumulative cap on total items returned across all tool calls in a server session | Prevents data exfiltration by bounding how much data can be extracted before a server restart. Set to `500`–`2000` for production. Once exceeded, all data-plane calls return an error until the server is restarted. |
| `DDB_MAX_CALLS_PER_MINUTE` | `0` (unlimited) | Max tool calls allowed per rolling 60-second window | Prevents rapid-fire automated extraction. Applies to all 8 tools. Rejected calls return a `RateLimitExceeded` error. Set to `30`–`60` for production. |
| `DDB_AUDIT_LOG` | `false` | When `true`, every tool call is logged to stderr with timestamp, tool name, table, and item count | Enables post-incident investigation and real-time monitoring. Logs go to stderr so they don't interfere with MCP's stdio transport. Pair with a log aggregator in HTTP mode. |
| `DDB_ALLOWED_TABLES` | *(empty = all)* | Comma-separated list of allowed table names/patterns (supports `*` globs) | App-level table restriction independent of IAM. `list_tables` only returns matching tables; all other tools reject non-matching tables. Examples: `dev-*`, `dev-UserProfiles,dev-Orders`, `dev-*,staging-*`. |
| `DDB_MAX_RESPONSE_BYTES` | `0` (unlimited) | Cap the serialized JSON size of a single tool response | Prevents a few very large items (DynamoDB allows up to 400 KB/item) from token-bombing the LLM context window. When exceeded, `items` are progressively dropped and a `truncated` flag is added. For `get_item` (single item, no list), an error is returned instead. Set to `500000`–`1000000` for production. |
| `DDB_READ_TIMEOUT` | `10` (seconds) | boto3 read timeout for every DynamoDB API call | Prevents slow or hung queries from tying up server resources (DoS vector in HTTP mode). A `ReadTimeoutError` is caught by the existing error handler and returned cleanly. Lower to `5` in latency-sensitive deployments; raise to `30` if scanning very large pages. |

#### Quick cost reference

| Scenario | RCUs consumed | Approximate cost |
|---|---|---|
| Scan 50 items × 1 KB (1 page, default settings) | ~13 | $0.000003 |
| Scan 500 items × 1 KB (1 page, max limit) | ~125 | $0.00003 |
| Scan 500 items × 20 pages × 1 KB (max everything) | ~2,500 | $0.0006 |
| Full table scan of 1M items × 1 KB | ~250,000 | $0.06 |
| Query 50 items × 1 KB | ~13 | $0.000003 |
| BatchGetItem 100 items × 1 KB | ~25 | $0.000006 |

Costs shown are for eventually consistent reads at $0.25 per million RCUs
(on-demand pricing, us-east-2). Strongly consistent reads cost 2×.

Beyond DynamoDB cost, large result sets also increase **LLM token usage** —
500 items serialized as JSON can easily exceed 50K tokens.

#### Example: tightened production config

```json
{
  "mcpServers": {
    "ddb-explorer": {
      "command": "uvx",
      "args": ["ddb-explorer-mcp"],
      "env": {
        "AWS_PROFILE": "prod-readonly",
        "AWS_REGION": "us-east-2",
        "DDB_SCAN_DEFAULT_LIMIT": "20",
        "DDB_SCAN_MAX_LIMIT": "100",
        "DDB_SCAN_DEFAULT_MAX_PAGES": "1",
        "DDB_SCAN_MAX_PAGES": "3",
        "DDB_QUERY_MAX_LIMIT": "200",
        "DDB_SHOW_COST": "true",
        "DDB_MAX_ITEMS_PER_SESSION": "1000",
        "DDB_MAX_CALLS_PER_MINUTE": "30",
        "DDB_AUDIT_LOG": "true",
        "DDB_ALLOWED_TABLES": "prod-orders,prod-users,prod-events",
        "DDB_MAX_RESPONSE_BYTES": "500000",
        "DDB_READ_TIMEOUT": "10"
      }
    }
  }
}
```

## HTTP-mode deployment

HTTP mode is for **hosted / team** scenarios. A single server instance serves
many remote clients; the server holds the AWS credentials, clients don't.

### What the server does NOT provide

- TLS — terminate at a reverse proxy (nginx, Caddy, ALB, CloudFront)
- Authentication — enforce at the proxy (Basic auth, JWT, mTLS, API Gateway + IAM, OAuth2)
- Rate limiting — handle at the proxy or a sidecar

### Recommended production shape

```
Internet ──► ALB (TLS + OIDC/JWT)
             │
             └─► ECS Fargate task
                   Image: ghcr.io/mudassirgithub/ddb-explorer-mcp:vX.Y.Z
                   Env:   MCP_TRANSPORT=http, MCP_HOST=0.0.0.0
                   IAM:   task role with read-only DynamoDB policy
```

A ready-to-use `docker-compose.yml` is available in [`examples/`](examples/docker-compose.yml).

### Minimal IAM policy for the server's AWS identity

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:DescribeTable",
        "dynamodb:DescribeTimeToLive",
        "dynamodb:GetItem",
        "dynamodb:BatchGetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:ListTables"
      ],
      "Resource": "*"
    }
  ]
}
```

For extra isolation, scope `Resource` to specific table ARNs.

### Quick local HTTP test

```bash
MCP_TRANSPORT=http MCP_PORT=8765 uvx ddb-explorer-mcp
```

Then in another terminal:

```bash
curl -i http://127.0.0.1:8765/mcp
# Expect HTTP 406 — endpoint is live; MCP needs proper JSON-RPC POST + Accept.
```

Connect an MCP client pointing at `http://127.0.0.1:8765/mcp` to actually exercise it.

## Security model

- **Read-only by construction.** No write tools are registered with the MCP server.
  This is a structural property, not a runtime flag.
- **No tool masquerading.** Tool signatures are fixed; the server does not
  dynamically execute arbitrary DynamoDB API calls on behalf of the LLM.
- **Scan safety.** `scan` defaults to `max_pages=1` (one page only). Hard cap 20 pages.
  `query` paginates internally with a `limit`; hard-capped at 500 items per call.
  All caps are configurable via environment variables — see [Safety limits](#safety-limits).
- **Session item cap.** `DDB_MAX_ITEMS_PER_SESSION` bounds the total items a single
  server session can return across all tool calls. Once exceeded, all data-plane
  calls are rejected until the server is restarted. Prevents automated exfiltration loops.
- **Rate limiting.** `DDB_MAX_CALLS_PER_MINUTE` enforces a sliding-window call
  rate across all tools. Prevents rapid-fire extraction or accidental runaway loops.
- **Table allowlist.** `DDB_ALLOWED_TABLES` restricts which tables the server can
  access, independent of IAM permissions. Supports glob patterns (e.g. `dev-*`).
  `list_tables` only returns matching tables; all other tools reject non-matching ones.
- **Audit logging.** `DDB_AUDIT_LOG=true` logs every tool call to stderr with
  timestamp, tool name, table, and item count. Useful for monitoring and
  post-incident investigation, especially in HTTP mode with a log aggregator.
- **Response size cap.** `DDB_MAX_RESPONSE_BYTES` limits the serialized JSON size
  of any single tool response. Large items (DynamoDB allows up to 400 KB each)
  can overwhelm the LLM context window and spike token costs. When exceeded,
  items are progressively dropped and a `truncated` flag is set.
- **DynamoDB call timeout.** `DDB_READ_TIMEOUT` (default 10 s) prevents slow or
  hung queries from tying up server resources. Applies to every boto3 call via
  `botocore.config.Config`. Timeout errors are caught and returned cleanly.
- **No credential exposure to the LLM.** Credentials live in the server process's
  environment or IAM role. The LLM sees tool *results*, never config.
- **Prompt injection risk.** DynamoDB items are user-generated data. A malicious
  item could contain text designed to influence LLM behavior (e.g. "ignore
  previous instructions and..."). This is inherent to any system that feeds
  untrusted data into an LLM. Mitigations: restrict table access via
  `DDB_ALLOWED_TABLES` to trusted tables, enable human-in-the-loop approval for
  tool calls in your MCP client, and review `DDB_AUDIT_LOG` output for
  unexpected access patterns.
- **HTTP mode isolation.** In HTTP mode (`MCP_TRANSPORT=http`), rate limits
  (`DDB_MAX_CALLS_PER_MINUTE`) and session caps (`DDB_MAX_ITEMS_PER_SESSION`)
  are **per-server-process**, not per-client. One client's usage counts against
  all clients sharing the same server instance. For multi-tenant isolation, run
  **separate server instances per client/team**, or proxy through an API gateway
  that enforces per-client quotas. The server's internal counters are thread-safe
  but intentionally shared to provide a global safety net.
- **Defense in depth.** Even with the above guarantees, you should still attach
  the server's AWS identity to a read-only DynamoDB IAM policy. Never give it
  write or admin permissions, ever. Scope `Resource` in the IAM policy to specific
  table ARNs for maximum isolation.

## Development

```bash
git clone https://github.com/mudassirgithub/ddb-explorer-mcp.git
cd ddb-explorer-mcp
make setup   # one-time: installs Python + deps

make test    # run the full test suite
make check   # lint + format-check + tests (same as CI)
make run     # start the server in stdio mode
```

Or without `make`:

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ddb-explorer-mcp
```

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## Security

To report a security vulnerability, see [SECURITY.md](SECURITY.md).
Please do **not** open public issues for security matters.

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Trademark notice

This project is not affiliated with, endorsed by, or sponsored by Amazon Web
Services, Inc. "AWS" and "Amazon DynamoDB" are trademarks of Amazon.com, Inc.
or its affiliates.
