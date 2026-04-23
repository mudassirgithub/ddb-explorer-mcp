# syntax=docker/dockerfile:1.7
#
# Multi-stage build for ddb-explorer-mcp — small, non-root, HTTP-mode ready.
#
# Build:
#   docker build -t ddb-explorer-mcp:local .
#
# Run (HTTP mode, loopback):
#   docker run --rm -p 8765:8765 \
#     -e MCP_TRANSPORT=http -e MCP_HOST=0.0.0.0 \
#     -e AWS_REGION=us-east-2 \
#     -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... \
#     ddb-explorer-mcp:local
#
# In production, prefer IAM roles (ECS task role, IRSA, EC2 instance profile)
# over static access keys.

FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --upgrade pip build && \
    python -m build --wheel --outdir /wheels .

# ---

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8765

RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

COPY --from=builder /wheels/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

USER app

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; \
    r = urllib.request.urlopen('http://127.0.0.1:${MCP_PORT}/mcp', timeout=3); \
    sys.exit(0 if r.status in (200, 405, 406) else 1)" || exit 1

ENTRYPOINT ["ddb-explorer-mcp"]
