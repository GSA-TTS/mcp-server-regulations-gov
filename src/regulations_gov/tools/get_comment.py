from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from ..models import ResponseFormat
from ..utils import (
    READ_ONLY_ANNOTATIONS,
    format_comment_markdown,
    format_detail_response_markdown,
    handle_api_error,
    make_api_request,
    to_json_response,
)


def register(mcp: FastMCP) -> None:
    """Register the regulations_get_comment tool with the MCP server."""

    @mcp.tool(
        name="regulations_get_comment",
        annotations={
            "title": "Get Regulations.gov Comment Details",
            **READ_ONLY_ANNOTATIONS,
        },
    )
    async def regulations_get_comment(
        comment_id: Annotated[
            str,
            Field(
                description="The comment object ID or document ID (e.g., 'EPA-HQ-OAR-2021-0257-0542')",
                min_length=1,
                max_length=100,
            ),
        ],
        include_attachments: Annotated[
            bool,
            Field(
                description=(
                    "Include attachment metadata in the response using the API's include=attachments parameter. "
                    "Returns titles, file formats, sizes, and download URLs for each attachment. "
                    "Many comments are submitted as PDFs — use this to discover their download URLs."
                )
            ),
        ] = False,
        response_format: Annotated[
            ResponseFormat,
            Field(description="Output format: 'markdown' for human-readable, 'json' for machine-readable"),
        ] = ResponseFormat.MARKDOWN,
    ) -> str:
        """Get full details for a specific public comment on regulations.gov.

        Retrieves the full text and metadata for a single public comment. Many comments
        are submitted as PDF attachments rather than inline text — use include_attachments=True
        to get attachment titles, formats, sizes, and download URLs via the API.

        Note: personally identifiable information (address, email, phone) is never returned
        by the API per regulations.gov policy.

        Use when:
            - Get inline comment text: comment_id='EPA-HQ-OAR-2021-0257-0542'
            - Get comment with attachment URLs: comment_id='...', include_attachments=True

        Returns the full comment text and metadata. If include_attachments=True, also lists
        each attachment with its title, format, size, and direct download URL. On error,
        returns a string beginning with 'Error:'.
        """
        try:
            api_params = {"include": "attachments"} if include_attachments else {}

            data = await make_api_request(f"comments/{comment_id}", api_params or None)

            if response_format == ResponseFormat.JSON:
                return to_json_response(data)

            return format_detail_response_markdown(
                data.get("data", data), "Comment", format_comment_markdown
            )
        except Exception as e:
            return handle_api_error(e)
