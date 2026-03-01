"""
Example MCP tools.

Each tool is a plain function decorated/registered via register_tools().
Keeping functions at module level makes them independently unit-testable
without starting a server.
"""

from fastmcp import FastMCP


def echo(text: str) -> str:
    """Echo the provided text back to the caller."""
    return text


def add(a: float, b: float) -> float:
    """Return the sum of two numbers."""
    return a + b


def register_tools(mcp: FastMCP) -> None:
    """Register all example tools on the given FastMCP instance."""
    mcp.tool()(echo)
    mcp.tool()(add)
