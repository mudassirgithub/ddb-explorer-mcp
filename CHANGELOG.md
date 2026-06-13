# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This file is auto-maintained by
[`python-semantic-release`](https://python-semantic-release.readthedocs.io/) on
every release. Add new entries under `[Unreleased]`; PSR will move them under
the new version on the next release.

## [Unreleased]

### Added

- Eight read-only DynamoDB tools: `list_tables`, `describe_table`,
  `get_indexes`, `sample_items`, `get_item`, `batch_get_item`, `query`, `scan`.
- stdio and streamable-HTTP transports, selectable via `MCP_TRANSPORT` env var.
- Automatic pagination for `query`; safe bounded pagination for `scan`
  (default `max_pages=1`, hard cap 20).
- `batch_get_item` auto-chunks into 100s and retries `UnprocessedKeys`.
- `Decimal` / `set` / `bytes` coercion to JSON-native types.
- Full test suite using `moto` for in-memory DynamoDB.
- Apache 2.0 license.
- **One-click install links** for Cursor, VS Code, and Smithery in README.
- **`server.json`** manifest for the official MCP registry.
- **`smithery.yaml`** config for Smithery registry listing and hosted deploy.
- **npm wrapper** (`npm/`) so JS-ecosystem users can `npx ddb-explorer-mcp`.
- **`examples/`** directory with ready-to-paste client configs for Cursor,
  Claude Desktop, VS Code, Docker Compose, and a curated prompt collection.
- **GitHub issue templates** (bug report, feature request) and PR template.
- **`CODE_OF_CONDUCT.md`** (Contributor Covenant v2.1).
- **Windsurf** client configuration in README.

### Release pipeline

- **Single-build release pipeline** (`.github/workflows/semantic-release.yml`):
  one multi-arch Docker build per push to `main`, conditionally tagged with
  the released version.
- **Automated versioning** via
  [`python-semantic-release`](https://python-semantic-release.readthedocs.io/):
  Conventional-Commits-driven version bumps, changelog updates, and PyPI /
  GHCR / npm publishing in lockstep — no manual version bumping required.
- **PyPI Trusted Publishing** (OIDC) with **PEP 740 attestations** so PyPI
  shows the verified-publish badge on the project page.
- **SLSA-Level-3 build provenance** via `actions/attest-build-provenance`
  for both the wheel/sdist and the Docker image, verifiable with
  `gh attestation verify`.

### Security / supply chain

- **All GitHub Actions SHA-pinned** with version comments across every
  workflow (per GitHub's hardening guide and OpenSSF Scorecard).
- **Default `permissions: contents: read`** on every workflow, with per-job
  escalation. `persist-credentials: false` on read-only checkouts.
- **CodeQL** (Python, `security-and-quality` query suite) on PRs touching
  source + weekly schedule.
- **OpenSSF Scorecard** running weekly (results private, in repo Security tab).
- **`CODEOWNERS`** routing review for `.github/`, `Dockerfile`, `pyproject.toml`,
  `src/`, and `SECURITY.md`.
- **`Renovate`** in issue-only mode: a single auto-maintained "Dependency
  Dashboard" issue lists all available updates without ever opening PRs.
  CVE-driven security PRs come from GitHub's native Dependabot security updates.
