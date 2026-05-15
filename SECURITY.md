# Security policy

## Reporting a vulnerability

If you believe you've found a security vulnerability in `ddb-explorer-mcp`,
please report it privately — **do not open a public GitHub issue**.

**Private report:** use GitHub's [Private Vulnerability Reporting](https://github.com/mudassirgithub/ddb-explorer-mcp/security/advisories/new).

Please include:

- A clear description of the issue and its impact.
- Steps to reproduce (minimal example preferred).
- Affected version(s).
- Any suggested mitigations, if known.

### What to expect

- Acknowledgement within 5 business days.
- A status update within 10 business days.
- A fix target date once the issue is triaged.
- Credit in the release notes (unless you prefer to remain anonymous).

## Supported versions

| Version | Supported |
|---------|-----------|
| Latest `0.x.y` | ✅ |
| Anything older | ❌ |

Security fixes land on the latest minor and are released as a patch.

## Security model & threat model

### What this project is

A **read-only** MCP server that lets an AI agent inspect and query DynamoDB
tables on behalf of a human operator.

### Guarantees by construction

- **No write tools are registered.** The MCP server does not expose
  `PutItem`, `UpdateItem`, `DeleteItem`, `BatchWriteItem`, `TransactWriteItems`,
  `CreateTable`, `DeleteTable`, or `UpdateTable`. This is a structural property
  of the code, not a runtime flag that can be flipped.
- **No arbitrary-SQL / no arbitrary-API surface.** Tool signatures are fixed;
  the server does not execute arbitrary boto3 calls provided by the LLM.
- **Expression injection protection.** DynamoDB expressions are validated to prevent
  SQL injection, command injection, and other malicious patterns before execution.
- **Input validation and bounds enforcement.** All environment variables, expressions,
  and parameters are validated with strict bounds checking.
- **Tool argument bounds are enforced.** `scan` caps `max_pages` at 20 and
  `limit` at 500; `query` caps `limit` at 500; `batch_get_item` retries
  `UnprocessedKeys` at most 10 times per chunk.

### What the project does NOT guarantee

- **Authenticity of the caller.** In HTTP mode, this server has no built-in
  authentication. You MUST front it with a reverse proxy that authenticates and
  authorizes requests (mTLS, JWT, basic auth, IAM-signed requests, etc.).
- **Confidentiality over the wire.** HTTP mode emits plaintext JSON-RPC. TLS
  must be terminated at your proxy.
- **Fine-grained authorization.** If you want "teammate A can read table X but
  not table Y", enforce that at the AWS IAM layer (separate deployments with
  separately-scoped task roles) or at your proxy.
- **Secrets hygiene in returned data.** If your DynamoDB items contain secrets,
  a read tool will return them. Don't store secrets in items you don't want the
  LLM to see.

### Security features

- **Production error sanitization.** Set `DDB_PRODUCTION=true` to sanitize error messages
  and prevent information disclosure while preserving debug capabilities.
- **Credential security warnings.** Server validates AWS credential configuration and warns
  about insecure practices (long-term keys, missing TLS, etc.) on startup.
- **Expression validation.** Comprehensive validation prevents injection attacks in
  DynamoDB expressions with configurable limits and safety checks.
- **Configuration bounds.** Environment variables are validated and clamped to safe ranges
  to prevent resource exhaustion and DoS attacks.

### Recommended deployment controls

- **Always** attach a minimal read-only IAM policy to the server's AWS identity.
  See [README.md § HTTP-mode deployment](README.md#http-mode-deployment).
- **Enable production mode** (`DDB_PRODUCTION=true`) to sanitize error messages.
- Use **distinct IAM roles per environment**. The server deployed to a "prod"
  host should not have access to any other account.
- Prefer **SSO / temporary credentials** over long-lived IAM user access keys.
- **Use TLS** for HTTP transport with `DDB_TLS_CERT`/`DDB_TLS_KEY` or a terminating proxy.
- **Monitor security warnings** in application logs for credential and configuration issues.
- Audit **CloudTrail** for unexpected query / scan patterns — DynamoDB data-plane
  events can be logged if you need full auditability.

### Known limitations

- **Scan costs.** Even with `max_pages=1`, a single scan on a very large table
  can consume significant RCU. Attach a Budget alarm to the deployment account.
- **Output size.** Items can be large. Clients may truncate or refuse to load
  responses exceeding their context window. Use `projection_expression` to
  limit what's returned when possible.

## Responsible disclosure

We ask that you give us a reasonable window to ship a fix (typically 90 days)
before any public disclosure. We'll work with you to coordinate timing.
