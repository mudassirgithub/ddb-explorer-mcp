# Contributing to ddb-explorer-mcp

Thanks for your interest in contributing!

## Ground rules

- **Read-only is a hard invariant.** This server exposes DynamoDB **reads only**.
  Any PR that adds a write-capable tool (`put_item`, `update_item`, `delete_item`,
  `batch_write_item`, `transact_write_items`, `create_table`, etc.) will be
  closed. If you need write capabilities, fork the project with a different name
  and a clear security disclosure. Do not submit write tools here.
- **No new top-level dependencies without discussion.** The dependency surface
  is deliberately tiny (`mcp`, `boto3`). Open an issue first.
- **Be kind.** Assume good intent, explain your reasoning, and keep review
  threads short.

## Development setup

Requires Python 3.10+ and [`uv`](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/mudassirgithub/ddb-explorer-mcp.git
cd ddb-explorer-mcp
make setup            # installs Python + all dependencies
```

Or without `make`: `uv sync --extra dev`

Opening the cloned folder in **Cursor** or **VS Code** auto-registers the MCP
server (via `.cursor/mcp.json` / `.vscode/mcp.json`). Changes to the Python
source take effect on the next server restart — no reinstall step.

## Running the server locally

```bash
make run              # stdio (default)
make run-http         # HTTP on 127.0.0.1:8765
```

Or without `make`:

```bash
uv run ddb-explorer-mcp                    # stdio
MCP_TRANSPORT=http uv run ddb-explorer-mcp # HTTP
```

## Running tests

```bash
make test             # full suite
uv run pytest -k query                     # one test by name
uv run pytest -x --ff                      # stop on first failure
```

Tests use [`moto`](https://github.com/getmoto/moto) for an in-memory DynamoDB.
**You do not need real AWS credentials** or a live AWS account to run the test
suite.

## Linting & formatting

```bash
make lint             # ruff check
make format           # ruff format (auto-fix)
make check            # lint + format-check + tests (same as CI)
```

Or without `make`:

```bash
uv run ruff check .
uv run ruff format .
```

CI runs both on every PR.

## Submitting a change

1. Open an issue first for non-trivial changes (new tool, behavior change,
   new dependency). Small fixes and docs can skip this.
2. Create a branch: `git checkout -b feat/short-description`
3. Add tests for new behavior; keep coverage at least at current level.
4. Run the full lint + test suite locally before pushing.
5. Open a PR. Include:
   - What changed and why
   - Test plan
   - Any user-visible behavior changes worth a CHANGELOG entry

## Coding style

- Type hints are expected on all public functions.
- Prefer `dict` return types over custom dataclasses for MCP tool returns
  (JSON-shaped output is friendlier to LLMs).
- Catch `ClientError` / `BotoCoreError` and convert to structured `{"error": True, ...}`
  responses; never let boto3 exceptions escape a tool.
- Keep defaults conservative (safe caps, low page counts). An LLM with enthusiastic
  parameters should not cause a $10k bill.

## Release process (maintainers)

1. Update `CHANGELOG.md` — move entries under `Unreleased` into a new versioned
   section.
2. Bump `version` in `pyproject.toml`.
3. Commit: `git commit -am "Release vX.Y.Z"`
4. Tag: `git tag vX.Y.Z`
5. Push: `git push && git push --tags`
6. GitHub Actions will publish to PyPI and GHCR automatically on tag push.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Do not open public issues for security bugs.
