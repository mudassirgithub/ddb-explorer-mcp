"""ddb-explorer-mcp — read-only MCP server for Amazon DynamoDB."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ddb-explorer-mcp")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
