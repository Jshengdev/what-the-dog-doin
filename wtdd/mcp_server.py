"""MCP (stdio) server over the same tools folder, so any MCP client (Claude Code, Codex, Hermes) can drive the house.

  pip install mcp
  claude mcp add wtdd -- /path/to/.venv/bin/python -m wtdd.mcp_server
Each file in wtdd/tools becomes one MCP tool with the same name, doc, and args. Results are JSON strings.
"""
from __future__ import annotations
import json
import sys

from . import tools


def main() -> int:
    try:
        from mcp.server.mcpserver import MCPServer as Server   # mcp >= 2
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP as Server    # mcp 1.x
        except ImportError:
            print("pip install mcp   (the MCP python SDK) then re-run", file=sys.stderr)
            return 1
    mcp = Server("wtdd")
    for name, mod in tools.registry().items():
        spec = getattr(mod, "ARGS", {})
        doc = getattr(mod, "DOC", "") + ("\nargs: " + json.dumps(spec) if spec else "")

        def make(n):
            def tool(args: str = "{}") -> str:
                """args: JSON object of the tool's arguments."""
                return json.dumps(tools.call(n, **json.loads(args or "{}")), default=str)
            tool.__name__ = n
            tool.__doc__ = doc
            return tool
        mcp.add_tool(make(name), name=name, description=doc)
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
