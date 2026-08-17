from __future__ import annotations

from fastmcp import FastMCP

from . import (
    get_comment,
    get_docket,
    get_document,
    search_comments,
    search_dockets,
    search_documents,
)


def register_tools(mcp: FastMCP) -> None:
    """Register all regulations.gov tools with the MCP server."""
    search_documents.register(mcp)
    get_document.register(mcp)
    search_comments.register(mcp)
    get_comment.register(mcp)
    search_dockets.register(mcp)
    get_docket.register(mcp)
