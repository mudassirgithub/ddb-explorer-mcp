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
5. Open a PR with a [Conventional Commits](https://www.conventionalcommits.org/)
   title (see "Commit messages" below). Include:
   - What changed and why
   - Test plan
   - Any user-visible behavior changes worth a CHANGELOG entry

## Commit messages (Conventional Commits)

This repo uses [`python-semantic-release`](https://python-semantic-release.readthedocs.io/)
to automate versioning. **PR titles must follow Conventional Commits** because
PRs are squash-merged — the PR title becomes the single commit on `main` and
that commit determines the next version.

| PR title prefix | Effect on `main` |
| --- | --- |
| `feat: …`        | minor bump (`0.X.0`) |
| `fix: …`         | patch bump (`0.0.X`) |
| `perf: …`        | patch bump |
| `feat!: …` (or any `!:` prefix, or `BREAKING CHANGE:` in body) | major bump (`X.0.0`) |
| `docs: …` / `refactor: …` / `style: …` / `test: …` / `chore: …` / `ci: …` / `build: …` | **no release** |

Examples:

- `feat(query): support exclusive_start_key for pagination`
- `fix: handle empty page in scan_table`
- `feat!: drop Python 3.9 support`
- `docs: clarify HTTP transport defaults` *(no version bump)*

Breaking changes can also be marked with a footer:

```
feat: switch default region resolution

BREAKING CHANGE: AWS_REGION is now required when no profile is set.
```

The `pr-title` CI check (`amannn/action-semantic-pull-request`) blocks PRs
whose titles don't conform.

## Coding style

- Type hints are expected on all public functions.
- Prefer `dict` return types over custom dataclasses for MCP tool returns
  (JSON-shaped output is friendlier to LLMs).
- Catch `ClientError` / `BotoCoreError` and convert to structured `{"error": True, ...}`
  responses; never let boto3 exceptions escape a tool.
- Keep defaults conservative (safe caps, low page counts). An LLM with enthusiastic
  parameters should not cause a $10k bill.

## Release process (maintainers)

Releases are **fully automated**. When a PR with a release-worthy title
(`feat:`, `fix:`, `perf:`, or any breaking-change marker) is merged into
`main`, the `Semantic Release` workflow:

1. Computes the next version from the commits since the last `vX.Y.Z` tag.
2. Updates `version` in `pyproject.toml` and prepends a section to `CHANGELOG.md`.
3. Commits the bump as `chore(release): vX.Y.Z [skip ci]`.
4. Pushes a `vX.Y.Z` tag.
5. Triggers `release.yml` (via `workflow_call`), which builds the wheel + sdist,
   publishes to PyPI (Trusted Publishing), pushes the multi-arch image to GHCR,
   and creates the GitHub Release.

You should not need to edit `CHANGELOG.md` or bump the version by hand.

### Manual override

If you need to force a release or a specific bump level, run the
`Semantic Release` workflow from the Actions tab with `force` set to one of
`prerelease`, `patch`, `minor`, or `major`.

### Required repo settings

- **Branch protection on `main`:** require PRs, require status checks
  (`pr-title`, `lint`, `test`, `build`), require linear history,
  **disable** "Require pull request reviews from Code Owners" *for the
  `github-actions[bot]` user* OR add it to the bypass list — otherwise PSR
  cannot push the release commit. (Settings → Branches → Branch protection
  rules → "Allow specified actors to bypass required pull requests".)
- **Squash merging only.** Set Settings → General → "Pull Requests" to allow
  *only* "Allow squash merging", and set "Default to PR title" so the squash
  commit message is the validated PR title.
- **Workflow permissions:** Settings → Actions → General → "Workflow
  permissions" must be **Read and write permissions** so PSR can push the
  release commit and tag.
- **PyPI Trusted Publisher:** as documented in `release.yml`.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Do not open public issues for security bugs.
