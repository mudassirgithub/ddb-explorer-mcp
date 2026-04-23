# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **One-click install links** for Cursor, VS Code, and Smithery in README.
- **Automated release pipeline** (`.github/workflows/release.yml`):
  PyPI via Trusted Publishing (OIDC), multi-arch Docker to GHCR, GitHub Release
  with auto-generated notes and attached artifacts.
- **Edge Docker workflow** (`.github/workflows/docker-edge.yml`): rolling
  `ghcr.io/.../ddb-explorer-mcp:edge` image from main.
- **`server.json`** manifest for the official MCP registry.
- **`smithery.yaml`** config for Smithery registry listing and hosted deploy.
- **npm wrapper** (`npm/`) so JS-ecosystem users can `npx ddb-explorer-mcp`.
- **`examples/`** directory with ready-to-paste client configs for Cursor,
  Claude Desktop, VS Code, Docker Compose, and a curated prompt collection.
- **GitHub issue templates** (bug report, feature request) and PR template.
- **Dependabot** config for pip, GitHub Actions, and Docker base images.
- **`CODE_OF_CONDUCT.md`** (Contributor Covenant v2.1).
- **Windsurf** client configuration in README.

## [0.1.0] — 2026-04-23

### Added

- Initial release.
- Eight read-only DynamoDB tools: `list_tables`, `describe_table`,
  `get_indexes`, `sample_items`, `get_item`, `batch_get_item`, `query`, `scan`.
- stdio and streamable-HTTP transports, selectable via `MCP_TRANSPORT` env var.
- Automatic pagination for `query`; safe bounded pagination for `scan`
  (default `max_pages=1`, hard cap 20).
- `batch_get_item` auto-chunks into 100s and retries `UnprocessedKeys`.
- `Decimal` / `set` / `bytes` coercion to JSON-native types.
- Full test suite using `moto` for in-memory DynamoDB.
- Apache 2.0 license.

[Unreleased]: https://github.com/mudassirgithub/ddb-explorer-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mudassirgithub/ddb-explorer-mcp/releases/tag/v0.1.0
