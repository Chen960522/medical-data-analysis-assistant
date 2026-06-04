"""Entry point: ``python -m report_generation`` starts the stdio MCP server.

The heavy/optional ``mcp`` runtime is imported lazily inside
:func:`report_generation.server.create_server`, so this module stays importable
without the MCP package installed.
"""

from __future__ import annotations

from .server import create_server


def main() -> None:
    """Start the report-generation MCP server over stdio transport."""
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
