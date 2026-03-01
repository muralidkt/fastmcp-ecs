"""
Unit tests for MCP tools.

Uses the FastMCP in-process Client (no HTTP, no auth) to call tools directly.
"""

import pytest
from fastmcp import Client

from mcp_server.tools.example import add, echo


# ── echo ──────────────────────────────────────────────────────────────────────


async def test_echo_returns_input_text(mcp_client: Client) -> None:
    result = await mcp_client.call_tool("echo", {"text": "hello"})
    assert result[0].text == "hello"  # type: ignore[union-attr]


async def test_echo_empty_string(mcp_client: Client) -> None:
    result = await mcp_client.call_tool("echo", {"text": ""})
    assert result[0].text == ""  # type: ignore[union-attr]


async def test_echo_preserves_whitespace(mcp_client: Client) -> None:
    text = "  spaces  \nnewline\t"
    result = await mcp_client.call_tool("echo", {"text": text})
    assert result[0].text == text  # type: ignore[union-attr]


# ── add ───────────────────────────────────────────────────────────────────────


async def test_add_positive_numbers(mcp_client: Client) -> None:
    result = await mcp_client.call_tool("add", {"a": 2.0, "b": 3.0})
    assert float(result[0].text) == pytest.approx(5.0)  # type: ignore[union-attr]


async def test_add_negative_numbers(mcp_client: Client) -> None:
    result = await mcp_client.call_tool("add", {"a": -10.0, "b": 4.0})
    assert float(result[0].text) == pytest.approx(-6.0)  # type: ignore[union-attr]


async def test_add_floats(mcp_client: Client) -> None:
    result = await mcp_client.call_tool("add", {"a": 0.1, "b": 0.2})
    assert float(result[0].text) == pytest.approx(0.3)  # type: ignore[union-attr]


async def test_add_zero(mcp_client: Client) -> None:
    result = await mcp_client.call_tool("add", {"a": 42.0, "b": 0.0})
    assert float(result[0].text) == pytest.approx(42.0)  # type: ignore[union-attr]


# ── pure function tests (no FastMCP overhead) ─────────────────────────────────


@pytest.mark.parametrize(
    "text",
    ["hello", "", "unicode: 你好", "special: !@#$%"],
)
def test_echo_function_directly(text: str) -> None:
    assert echo(text) == text


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1.0, 2.0, 3.0),
        (0.0, 0.0, 0.0),
        (-5.0, 5.0, 0.0),
        (1.5, 2.5, 4.0),
    ],
)
def test_add_function_directly(a: float, b: float, expected: float) -> None:
    assert add(a, b) == pytest.approx(expected)
