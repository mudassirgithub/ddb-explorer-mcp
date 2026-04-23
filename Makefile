.PHONY: setup run run-http test lint format check clean

# One-command local setup: installs Python + dependencies via uv
setup:
	@command -v uv >/dev/null 2>&1 || { echo "Error: uv is required. Install: https://github.com/astral-sh/uv"; exit 1; }
	uv sync --extra dev
	@echo ""
	@echo "Done! Run 'make run' to start the server, or 'make test' to run tests."

# Start the MCP server in stdio mode (for IDE integration)
run:
	uv run ddb-explorer-mcp

# Start the MCP server in HTTP mode on localhost:8765
run-http:
	MCP_TRANSPORT=http MCP_HOST=127.0.0.1 MCP_PORT=8765 uv run ddb-explorer-mcp

# Run the full test suite (uses moto — no real AWS credentials needed)
test:
	uv run pytest --tb=short

# Lint with ruff
lint:
	uv run ruff check .

# Auto-format with ruff
format:
	uv run ruff format .

# Run all checks (lint + format-check + tests) — same as CI
check: lint
	uv run ruff format --check .
	uv run pytest --tb=short -q

# Remove build/cache artifacts
clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
