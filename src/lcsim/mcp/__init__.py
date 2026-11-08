"""The MCP server (spec 4 "MCP server" and "MCP tools"; M7).

``python -m lcsim.mcp`` serves the tools over stdio (``server``); every tool calls the
engine service's ``/v1`` API through one client (``client``), and one registry holds the
tools, checks their inputs and turns the service's answers into tool results (``tools``).
"""
