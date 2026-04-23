<!--
Thanks for contributing to ddb-explorer-mcp! Please fill out the checklist
below. PRs that add write-side DynamoDB operations will be closed — see
README's "Security model" section.
-->

## Summary

<!-- What does this PR do? Why? Link to any related issue with "Fixes #123". -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New tool or feature (non-breaking)
- [ ] Docs / CI / infra
- [ ] Breaking change

## Read-only invariant

- [ ] This PR does **not** register any tool that performs a DynamoDB write,
      schema mutation, or admin operation (`PutItem`, `UpdateItem`,
      `DeleteItem`, `BatchWriteItem`, `TransactWriteItems`, `CreateTable`,
      `DeleteTable`, `UpdateTable`, IAM changes, etc.).

## Checklist

- [ ] `uv run pytest` passes locally
- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format --check .` passes
- [ ] New tools have docstrings that an LLM can usefully read
- [ ] Added or updated tests for new behavior
- [ ] Updated `README.md` / `CHANGELOG.md` where appropriate
